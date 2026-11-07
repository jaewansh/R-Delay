"""선박 단위 백테스트(두 번째 분석) 결과 요약·그림·웹 자료(docs/data/backtest_ship.json)·문서 절.

공개 산출물에는 신항 전체 집계만 넣는다(선박 이름·호출부호·터미널 이름 없음, Clarksons 없음).
해석 문장은 숫자 조건으로 고른다(자료가 바뀌면 문장도 따라 바뀜).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import subprocess

import numpy as np
import pandas as pd

from . import evaluate as ev
from . import grid, models as M, paths

COL = {"ink": "#0e2238", "ink2": "#2e4359", "brand": "#1f5fa8", "red": "#c62828", "amber": "#e8a317",
       "green": "#1f8a55", "muted": "#5f7286", "line": "#d3dce5", "grid": "#e8edf2", "page": "#eef2f5"}
NAMES = {"S0": "터미널별 평균(기후값)", "S1": "현재 터미널 상태", "S2_logit": "통계 기준선(로지스틱)", "S2_gbm": "통계 기준선(GBM)",
         "R1": "R-Delay 선석 대기열만", "R2": "대기열+재보정", "R3_logit": "R-Delay 실자료판(하이브리드)",
         "R3_gbm": "R-Delay 실자료판(GBM)", "SIS_p1": "번짐 지수 P(R_d>1)만", "SIS_x": "SIS 대기 비율만"}
NAMES_T1 = {**NAMES, "S0": "시간대·요일 평균(기후값)", "S1": "현재 대기 상태(지속성)"}
SOURCES = ["해양수산부 PORT-MIS 관제정보(공공데이터포털)", "기상청 기상자료개방포털 ASOS·해양기상부이·태풍 경로(공공누리 제1유형)",
           "한국도로공사 노선별 1시간 구간통행속도(공공데이터)"]
RULE = "부산신항 터미널의 수출 반입 마감(접안 12시간 전)"
ANALYSIS_START = "2023-01-30"
LEADS = ["24", "12", "6", "2", "0"]
DEMO = "https://jaewansh.github.io/R-Delay/backtest-ship.html"   # 이 분석(선박 단위) 화면
MAIN_DEMO = "https://jaewansh.github.io/R-Delay/backtest.html"  # 신항 전체 24시간 경보(realdata/, 주 분석) 화면
PROTO = "realdata_ship/PROTOCOL.md"
COMPARE = "realdata_ship/results/compare.md"
REPORT_ANCHOR = "REPORT.md#두-번째-분석-선박별-하루-전-경보"
FIRST_RUN = {"pr_auc": 0.196, "roc_auc": 0.858}  # 시험 첫 계산(누설 수정 전) 24시간 전 하이브리드 — PROTOCOL 부록 B


FONTS = ("Pretendard", "Malgun Gothic", "AppleGothic", "Apple SD Gothic Neo", "NanumGothic", "Noto Sans CJK KR", "Noto Sans KR",
         "Noto Sans CJK JP")  # 마지막은 리눅스용(CJK 글꼴에 한글도 들어 있음)


def _font():
    """그림 설정. 창을 띄우지 않는 Agg로 그리고, 한글 글꼴은 있는 것 중 앞에서부터 고른다.

    Windows는 맑은 고딕, Mac은 AppleGothic이 기본으로 있다. 다른 글꼴을 쓰려면 .env에 RDELAY_FONT_DIR=<ttf·otf 폴더>.
    """
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import font_manager as fm
    extra = os.environ.get("RDELAY_FONT_DIR", "").strip()
    if extra and pathlib.Path(extra).expanduser().is_dir():
        for f in sorted(pathlib.Path(extra).expanduser().glob("*.[ot]tf")):
            fm.fontManager.addfont(str(f))
    have = {f.name for f in fm.fontManager.ttflist}
    name = next((n for n in FONTS if n in have), None)
    if name:
        matplotlib.rcParams["font.family"] = name
    else:
        print("[알림] 한글 글꼴(맑은 고딕·AppleGothic·나눔고딕)을 찾지 못해 그림의 한글이 네모로 보일 수 있습니다. "
              "숫자 결과에는 영향이 없습니다. 글꼴 폴더를 .env의 RDELAY_FONT_DIR에 적으면 그 글꼴을 씁니다.")
    matplotlib.rcParams.update({"axes.unicode_minus": False, "axes.edgecolor": COL["line"], "axes.labelcolor": COL["ink2"],
                                "xtick.color": COL["muted"], "ytick.color": COL["muted"], "axes.titleweight": "bold",
                                "axes.titlecolor": COL["ink"], "axes.grid": True, "grid.color": COL["grid"],
                                "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
                                "figure.facecolor": "white", "savefig.facecolor": "white", "font.size": 11})


def _git_commit() -> str:
    """HEAD 짧은 해시. 작업 트리에 커밋하지 않은 변경이 있으면 '+작업본'을 붙인다."""
    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=paths.ROOT, capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=paths.ROOT,
                               capture_output=True, text=True).stdout.strip()
        return head + ("+작업본" if dirty else "")
    except Exception:
        return ""


def _load():
    R = paths.RESULTS
    res = json.loads((R / "test_results.json").read_text(encoding="utf-8"))
    cal = json.loads((R / "sis_calibration.json").read_text(encoding="utf-8"))
    sens = json.loads((R / "sensitivity.json").read_text(encoding="utf-8")) if (R / "sensitivity.json").exists() else None
    p1 = pd.read_parquet(paths.CACHE / "test_preds_t1.parquet")
    g = pd.read_parquet(paths.CACHE / "grid_r1s.parquet")
    return res, cal, sens, p1, g


def _r(x, n=3):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), n)


def _p(x, d=1):
    return "—" if x is None else f"{x * 100:.{d}f}%"


def _f(x, d=3):
    return "—" if x is None else f"{x:.{d}f}"


def _tenths(x, josa: tuple[str, str] | None = None) -> str:
    """말하기용: 0.385 → '열에 넷'. josa=(받침 있을 때, 없을 때)를 주면 조사를 붙인다('하나'만 받침 없음)."""
    n = min(9, max(1, int(round(float(x) * 10))))
    w = "열에 " + "하나 둘 셋 넷 다섯 여섯 일곱 여덟 아홉".split()[n - 1]
    return w + ((josa[1] if n == 1 else josa[0]) if josa else "")


def _months(a, b) -> int:
    a, b = pd.Timestamp(a), pd.Timestamp(b)
    return (b.year - a.year) * 12 + (b.month - a.month) + (1 if b.day >= 15 else 0) - (1 if a.day >= 15 else 0)


def _ym(n: int) -> str:
    return f"{n // 12}년 {n % 12}개월" if n >= 12 and n % 12 else (f"{n // 12}년" if n >= 12 else f"{n}개월")


def _period_label(a, b) -> str:
    """[a, b) → 'a~b 전날'(b가 자정일 때). 시험 끝처럼 시각이 있으면 그 시각까지."""
    b = pd.Timestamp(b)
    end = (b - pd.Timedelta(days=1)).strftime("%Y-%m-%d") if b == b.normalize() else b.strftime("%Y-%m-%d %H:%M")
    return f"{pd.Timestamp(a).strftime('%Y-%m-%d')}~{end}"


def _chg(drop) -> str:
    """요인을 뺐을 때 PR-AUC 변화량(감소 = 음수), 수학 빼기 기호로."""
    v = -float(drop)
    return "0.000" if abs(v) < 5e-4 else f"{v:+.3f}".replace("-", "−")


def _m(m: dict) -> dict:
    return {"pr_auc": _r(m.get("pr_auc")), "pr_auc_ci": [_r(x) for x in m["pr_auc_ci"]] if m.get("pr_auc_ci") else None,
            "roc_auc": _r(m.get("roc_auc")), "bss": _r(m.get("bss")),
            "bss_ci": [_r(x) for x in m["bss_ci"]] if m.get("bss_ci") else None, "base_rate": _r(m.get("base_rate"), 4)}


def summary(res, cal, sens, p1, g) -> dict:
    vall = grid.voyages()                         # 라벨 파일 전체(2023-01-01~)
    v = vall[vall["arrival_t"] >= pd.Timestamp(ANALYSIS_START)]
    pos_all = vall[vall["pos12"]]
    yr = vall["arrival_t"].dt.year
    by_year = {}
    for y in sorted(yr.unique()):
        s = vall[yr == y]
        pp = s[s["pos12"]]
        by_year[int(y)] = {"voyages": int(len(s)), "long_waits": int(len(pp)), "excess_hours": int(round(float((pp["wait_h"] - 12).sum())))}
    vv = pd.read_parquet(paths.CACHE / "ship_r1s.parquet")
    z = vv[vv["L"] == 0]
    longw = z[z["pos12"]]
    anch = z[z["anchored"] & ~z["excluded"]]
    direct = z[~z["anchored"]]
    free_at_arrival = {"long_wait_ships": int(len(longw)),
                       "long_wait_with_free_berth": _r((longw["free"] >= 1).mean()),
                       "anchored_with_free_berth": _r((anch["free"] >= 1).mean()),
                       "direct_with_free_berth": _r((direct["free"] >= 1).mean())}
    t2 = res["t2"]
    lead = {L: {k: _m(m) for k, m in t2[L].items()} for L in LEADS}
    m24 = t2["24"]["R3_logit"]
    bss_raw = {L: float(t2[L]["R3_logit"]["bss"]) for L in LEADS}
    t1 = {k: {**_m(m), "alarm_rate_valid_f1": _r(m["alarm_valid_f1"]["alarm_rate"])} for k, m in res["t1"].items()}
    t3_reg = {k: {**{kk: (_r(x, 2) if isinstance(x, float) else x) for kk, x in m["events"].items()},
                  "alarm_rate": _r(m["alarm_valid_f1"]["alarm_rate"], 2)} for k, m in res["t1"].items()}
    eps = ev.episodes(vv.loc[(vv["L"] == 0) & vv["pos12"], "arrival_t"].to_numpy())
    a, b = pd.Timestamp(res["test_period"][0]), pd.Timestamp(res["test_period"][1])
    eps = [e for e in eps if a <= e[0] < b]
    post = {}
    for k in ("S0", "S2_logit", "R3_logit", "SIS_p1"):
        thr = float(np.quantile(p1[k], 0.9))
        e = ev.event_stats(pd.DatetimeIndex(p1["tau"]), p1[k].to_numpy() >= thr, eps)
        post[k] = {kk: (_r(x, 2) if isinstance(x, float) else x) for kk, x in e.items()}
    # 요인 묶음 제거(사후): R3_logit, 24시간 전, 학습+검증 적합 → 시험 PR-AUC
    d = M.prep_ship(vv)
    d = d[~d["excluded"] & (d["L"] == 24)]
    tv = ev.split(d, "arrival_t", ("2023-01-30", "2025-07-01"))
    te = ev.split(d, "arrival_t", tuple(res["test_period"]))
    C24 = float(res["t2_choice"]["24"]["R3_logit"])
    cols = M.T2_S2 + M.T2_R1 + M.SIS
    base_m = M.Logit(cols, C=C24).fit(tv, tv["pos12"].astype(int))
    base_ap = ev.metrics(te["pos12"], base_m.predict(te))["pr_auc"]
    signs = {c: _r(float(base_m.m.coef_[0][cols.index(c)]), 4) for c in ("log_gt", "prev_pos", "slot_rate", "logit_r1", "sis_rd")}
    groups = {"같은 선박의 이전 기항 이력": ["prev_pos", "prev_known", "prev_n180"],
              "같은 요일·시간대 슬롯 이력": ["slot_rate", "log_slot_n"], "선박 크기(총톤수)": ["log_gt"],
              "그 터미널 대기열·예정 도착·점유": ["queue", "sched_ahead", "occ", "free"],
              "R-Delay 선석 대기열": ["logit_r1", "r1_ewait"], "SIS 상태(번짐 지수)": ["sis_x", "sis_z", "sis_rd"],
              "기상·태풍": ["wind_bsn_max6", "hs_geoje_max6", "gust_geoje_max6", "rain_bsn_6h", "ty_near500", "log_ty_dist"],
              "배후 도로": ["road_cong_frac", "road_rel_med"], "신항 전체 대기": ["n_wait_all", "max_wait_all", "recent7_pos"]}
    ablation = []
    for gname, gcols in groups.items():
        keep = [c for c in cols if c not in gcols]
        ap = ev.metrics(te["pos12"], M.Logit(keep, C=C24).fit(tv, tv["pos12"].astype(int)).predict(te))["pr_auc"]
        ablation.append({"group": gname, "pr_auc_without": _r(ap), "drop": _r(base_ap - ap)})
    ablation.sort(key=lambda r: -r["drop"])
    rd = g["sis_rd"].dropna()
    rd = rd[rd.index >= pd.Timestamp(ANALYSIS_START)]
    return {
        "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "commit": _git_commit(),
        "data": {"period": [str(vall["arrival_t"].min().date()), str(pd.Timestamp(res["data_end"]).date())],
                 "voyages": int(len(vall)), "long_waits": int(len(pos_all)), "anchored": int(vall["anchored"].sum()),
                 "excluded_over_cap": int(vall["excluded"].sum()), "long_wait_share": _r(len(pos_all) / len(vall), 4),
                 "by_year": by_year, "analysis_start": ANALYSIS_START, "analysis_voyages": int(len(v)),
                 "median_wait_anchored_h": _r(vall.loc[vall["anchored"] & ~vall["excluded"], "wait_h"].median(), 1)},
        "free_at_arrival": free_at_arrival,
        "periods": {"train": list(ev.PERIODS["train"]), "valid": list(ev.PERIODS["valid"]), "test": list(res["test_period"])},
        "periods_label": {k: _period_label(*v) for k, v in (("train", ev.PERIODS["train"]), ("valid", ev.PERIODS["valid"]), ("test", res["test_period"]))},
        "test_counts": {"voyages": t2["24"]["S0"]["n"], "long_waits": t2["24"]["S0"]["pos"],
                        "base_rate": _r(t2["24"]["S0"]["base_rate"], 4), "episodes": res["episodes_test"]},
        "test_runs": 2, "first_run": FIRST_RUN,
        "choices": {"t2": res["t2_choice"], "t1": res["t1_choice"]},
        "t2_lead": lead, "bss_raw": bss_raw, "bss_reached_leads": [L for L in LEADS if bss_raw[L] >= 0.1],
        "t2_24": {**_m(m24), "top5": {k: _r(x) for k, x in m24["alarm_top5"].items()},
                  "top10": {k: _r(x) for k, x in m24["alarm_top10"].items()},
                  "valid_f1": {k: _r(x) for k, x in m24["alarm_valid_f1"].items()},
                  "reliability": m24.get("reliability", [])},
        "t1": t1, "t1_base_rate": _r(res["t1"]["S0"]["base_rate"]),
        "t3_registered": t3_reg, "t3_posthoc_top10": post,
        "subgroups": {"summer2026_t1": {k: _m(m) for k, m in res["subgroups"]["t1_summer2026"].items()},
                      "typhoon_tau": res["subgroups"]["t1_typhoon_tau"]},
        "sensitivity": sens,
        "ablation_posthoc": {"base_pr_auc": _r(base_ap), "groups": ablation, "coef_std": signs},
        "sis": {"beta_over_gamma": cal["best"]["beta_ratio"], "kappa_sea_land": cal["best"]["kappa"],
                "gamma_s": _r(cal["gamma_s"], 4), "mean_wait_h": _r(1 / cal["gamma_s"], 1),
                "rd_quantiles": {str(q): _r(rd.quantile(q)) for q in (0.05, 0.25, 0.5, 0.75, 0.95)},
                "p_rd_gt1_share": _r((rd > 1).mean()), "f_omega": cal.get("f_omega"),
                "valid_loglik_gain_f_omega": _r(cal.get("valid_loglik_with", 0) - cal.get("valid_loglik_without", 0), 1),
                "loglik_grid": cal["grid"]},
    }


# ── 해석 조건(숫자에서 문장을 고른다) ─────────────────────────────────────────
def facts(S) -> dict:
    ab = {g["group"]: g["drop"] for g in S["ablation_posthoc"]["groups"]}
    mech = (ab.get("R-Delay 선석 대기열", 0) or 0) + (ab.get("SIS 상태(번짐 지수)", 0) or 0)
    L24 = S["t2_lead"]["24"]
    t1 = S["t1"]
    reg = S["t3_registered"]
    share = [e["detected"] / e["episodes"] for e in reg.values() if e["episodes"]]
    return {
        "t3_reg_min_alarm": min(e["alarm_rate"] for e in reg.values()),
        "small_ship_riskier": (S["ablation_posthoc"]["coef_std"]["log_gt"] or 0) < 0,
        "history_positive": (S["ablation_posthoc"]["coef_std"]["prev_pos"] or 0) > 0 and (S["ablation_posthoc"]["coef_std"]["slot_rate"] or 0) > 0,
        "fomega_wind_hs_negative": bool((S["sis"].get("f_omega") or {}).get("coef")) and S["sis"]["f_omega"]["coef"][0] < 0 and S["sis"]["f_omega"]["coef"][1] < 0,
        "t3_reg_uninformative": bool(share) and min(share) >= 0.95,
        "mech_drop": round(mech, 3), "mech_small": mech < 0.01,
        "mech_parts": {"queue": ab.get("R-Delay 선석 대기열", 0) or 0, "sis": ab.get("SIS 상태(번짐 지수)", 0) or 0},
        "s2gbm_ge_r3gbm": (L24["S2_gbm"]["pr_auc"] or 0) >= (L24["R3_gbm"]["pr_auc"] or 0),
        "sis_alone_at_base": (t1["SIS_p1"]["pr_auc"] or 0) <= 1.1 * (S["t1_base_rate"] or 0),
        "r3_beats_clim_24": (L24["R3_logit"]["pr_auc_ci"] or [0])[0] > (L24["S0"]["pr_auc"] or 0),
        "top3": [g["group"] for g in S["ablation_posthoc"]["groups"][:3]],
    }


def _main_vessel_24() -> float | None:
    """주 분석(realdata/)의 선박 단위 참고 표에서 '도착 24시간 전' 기준선 PR-AUC(없으면 None)."""
    f = paths.ROOT / "docs" / "data" / "backtest.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        v = next(x for x in d.get("vessel", []) if str(x.get("name", "")).startswith("T2-24"))
        return float(v["baseline"]["pr_auc"])
    except Exception:
        return None


def _bss_sentence(S) -> str:
    raw, reached = S["bss_raw"], S["bss_reached_leads"]
    lab = lambda L: "도착 순간" if L == "0" else f"{L}시간 전"
    ci = S["t2_24"]["bss_ci"]
    fmt = lambda L: f"{lab(L)}({raw[L]:+.4f}" + (f", 95% {ci[0]:+.3f}~{ci[1]:+.3f}" if L == "24" else "") + ")"
    under = [L for L in LEADS if L not in reached]
    if not under:
        body = "모든 리드에서 넘었습니다"
    elif not reached:
        body = f"어느 리드에서도 넘지 못했습니다({', '.join(fmt(L) for L in under)})"
    else:
        body = f"{'·'.join(fmt(L) for L in reached)}에서 넘었고, {'·'.join(fmt(L) for L in under)}은 못 미쳤습니다"
    tail = " 2시간 전·도착 순간 값에는 라벨 정의 효과가 섞여 있습니다." if {"2", "0"} & set(reached) else ""
    return (f"로드맵 ① 통과 기준(Brier 기술점수 ≥ 0.1, 반올림 전 값): 하이브리드는 {body}.{tail}"
            " 비교 기준은 계획서의 '공지 반영 ETA 규칙'이 아니라 터미널별 기후값입니다(공개 자료에 운영 공지가 없음).")


# ── 그림 ───────────────────────────────────────────────────────────────────
def _save(fig, name):
    paths.ensure_dirs()
    fig.savefig(paths.REPORTS / f"{name}.png", dpi=200, bbox_inches="tight")
    paths.PRESENTATION.mkdir(parents=True, exist_ok=True)
    fig.savefig(paths.PRESENTATION / f"{name}.png", dpi=200, bbox_inches="tight")
    if name in ("fig_alarm", "fig_leads"):  # README용(공개 자료 집계만)
        fig.savefig(paths.ROOT / "image" / f"backtest_ship_{name[4:]}.png", dpi=130, bbox_inches="tight")


def fig_leads(S):
    import matplotlib.pyplot as plt
    leads = [int(x) for x in LEADS]
    fig, ax = plt.subplots(figsize=(8.0, 4.3))
    base = S["test_counts"]["base_rate"]
    ax.axhline(base, color=COL["muted"], lw=1, ls=(0, (4, 3)))
    ax.text(len(leads) - 0.75, base - 0.004, f"무작위(기저율 {base:.1%})", color=COL["muted"], fontsize=9, ha="right", va="top")
    style = {"S0": (COL["muted"], "o", "-", NAMES["S0"]), "R1": (COL["amber"], "s", "-", NAMES["R1"]),
             "S2_gbm": (COL["ink2"], "v", "--", "통계 기준선(GBM, R-Delay 부품 없음)"),
             "R3_logit": (COL["brand"], "D", "-", NAMES["R3_logit"]), "R3_gbm": (COL["ink"], "^", "-", NAMES["R3_gbm"])}
    xs = list(range(len(leads)))
    for k, (c, mk, ls, lab) in style.items():
        y = [S["t2_lead"][str(L)][k]["pr_auc"] for L in leads]
        ax.plot(xs, y, color=c, marker=mk, ls=ls, lw=2 if k.startswith("R3") else 1.4, label=lab, ms=5.5)
        ci = [S["t2_lead"][str(L)][k]["pr_auc_ci"] for L in leads]
        if all(ci) and k in ("R3_logit", "S0", "R1"):
            ax.fill_between(xs, [c_[0] for c_ in ci], [c_[1] for c_ in ci], color=c, alpha=0.10, lw=0)
    ax.axvspan(2.5, 4.5, color=COL["grid"], alpha=0.6, lw=0)
    ax.set_xlim(-0.3, len(leads) - 0.7)
    ax.set_xticks(xs, [f"{L}시간 전" if L else "도착 순간" for L in leads])
    ax.set_ylabel("PR-AUC (높을수록 정확)")
    ax.set_title("선박별 '12시간 넘게 기다릴까' — 도착 몇 시간 전에 얼마나 맞히나")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.text(0.99, -0.17, f"시험 기간 {S['periods']['test'][0]} ~ {S['periods']['test'][1][:10]} · 신항 컨테이너선 {S['test_counts']['voyages']:,}항차 중 장기 대기 {S['test_counts']['long_waits']}척 · 띠 = 95% 구간(주 단위 블록 부트스트랩)\n"
            "회색 바탕(2시간 전·도착 순간) = 라벨 정의상 일부 저절로 맞는 구간(바로 접안한 배는 도착 순간 빈 선석이 있게 마련)",
            transform=ax.transAxes, ha="right", va="top", fontsize=8, color=COL["muted"], linespacing=1.5)
    _save(fig, "fig_leads")
    plt.close(fig)


def fig_alarm(S):
    import matplotlib.pyplot as plt
    t5, vf = S["t2_24"]["top5"], S["t2_24"]["valid_f1"]
    base = S["test_counts"]["base_rate"]
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.8), gridspec_kw={"width_ratios": [1.15, 1]})
    ax = axes[0]
    vals = [base, t5["precision"]]
    bars = ax.barh(["무작위로 5% 고르기", "R-Delay 위험 상위 5%"], vals, color=[COL["line"], COL["brand"]], height=0.55)
    for b_, v_ in zip(bars, vals):
        ax.text(v_ + 0.004, b_.get_y() + b_.get_height() / 2, f"{v_:.1%}", va="center", fontsize=11, color=COL["ink"], fontweight="bold")
    ax.set_xlim(0, max(vals) * 1.35)
    ax.set_title("경보 받은 배가 실제로 12시간 넘게 기다린 비율", fontsize=11)
    ax.grid(axis="y", visible=False)
    ax.set_xticks([])
    ax = axes[1]
    rec = t5["recall"]
    ax.pie([rec, 1 - rec], colors=[COL["brand"], COL["grid"]], startangle=90, counterclock=False,
           wedgeprops={"width": 0.36, "edgecolor": "white"})
    ax.text(0, 0.06, f"{rec:.1%}", ha="center", va="center", fontsize=21, fontweight="bold", color=COL["ink"])
    ax.text(0, -0.22, "미리 잡은 비율", ha="center", va="center", fontsize=9, color=COL["muted"])
    ax.set_title("장기 대기 선박 중 하루 전 경보에 든 비율", fontsize=11)
    fig.suptitle(f"하루(24시간) 전, 위험 상위 5% 선박만 골라도 — 무작위의 {t5['lift']:.1f}배", fontsize=13, fontweight="bold", color=COL["ink"], y=1.04)
    fig.text(0.5, -0.04, f"상위 5% = 시험 기간 예측값 분포의 상위 5%(사후 기준). 검증 기간에서 미리 정한 문턱으로는 경보 {vf['alarm_rate']:.1%}, 정밀도 {vf['precision']:.1%}, 재현율 {vf['recall']:.1%}.",
             ha="center", fontsize=8, color=COL["muted"])
    _save(fig, "fig_alarm")
    plt.close(fig)


def fig_reliability(S):
    import matplotlib.pyplot as plt
    rel = S["t2_24"]["reliability"]
    if not rel:
        return
    fig, ax = plt.subplots(figsize=(4.6, 4.2))
    mx = max(max(r["p_mean"] for r in rel), max(r["y_rate"] for r in rel)) * 1.1
    ax.plot([0, mx], [0, mx], color=COL["muted"], ls=(0, (4, 3)), lw=1)
    ax.plot([r["p_mean"] for r in rel], [r["y_rate"] for r in rel], marker="o", color=COL["brand"], lw=2)
    ax.set_xlabel("예측 확률(10분위 평균)")
    ax.set_ylabel("실제 장기 대기 비율")
    ax.set_title("확률이 실제와 맞나(24시간 전, 시험 기간)", fontsize=11)
    _save(fig, "fig_reliability")
    plt.close(fig)


def fig_drivers(S):
    import matplotlib.pyplot as plt
    ab = S["ablation_posthoc"]
    rows = ab["groups"][::-1]
    fig, ax = plt.subplots(figsize=(7.6, 4.0))
    vals = [max(r["drop"], 0.0) for r in rows]
    ax.barh([r["group"] for r in rows], vals, color=[COL["brand"] if v > 0.005 else COL["line"] for v in vals], height=0.6)
    for i, r in enumerate(rows):
        ax.text(vals[i] + 0.001, i, _chg(r["drop"]), va="center", fontsize=9, color=COL["ink2"])
    ax.axvline(0, color=COL["muted"], lw=1)
    ax.set_xlabel(f"막대 = 빼면 떨어지는 폭 · 숫자 = PR-AUC 변화 (전체 {ab['base_pr_auc']:.3f})")
    ax.set_title("하루 전 예측력은 어디서 오나 — 요인 묶음을 하나씩 뺐을 때", fontsize=12)
    ax.grid(axis="y", visible=False)
    ax.text(0.99, -0.2, "R-Delay 실자료판(하이브리드), 24시간 전, 시험 기간 사후 분석(모형 선택에 쓰지 않음)", transform=ax.transAxes,
            ha="right", fontsize=8, color=COL["muted"])
    _save(fig, "fig_drivers")
    plt.close(fig)


# ── 웹 자료 ──────────────────────────────────────────────────────────────────
def web_json(S) -> dict:
    keep = ["S0", "R1", "S2_logit", "S2_gbm", "R3_logit", "R3_gbm"]
    F = facts(S)
    fk = ("top3", "mech_small", "mech_drop", "mech_parts", "s2gbm_ge_r3gbm", "small_ship_riskier", "history_positive")
    return {
        "generated": S["generated"], "commit": S["commit"],
        "notice": ("공개 실자료 후향 검증(실시간 운영 검증 아님)의 두 번째 분석(선박 단위)이다. 신항 전체 집계만 담았고 선박·터미널 이름은 넣지 않았다. "
                   f"시험 기간은 두 번 계산했다(시험 뒤 누설을 더 엄격하게 고친 1건, 두 결과 모두 {PROTO} 부록 B에 기록)."),
        "rule": RULE, "sources": SOURCES, "first_run": S["first_run"],
        "data": S["data"], "periods": S["periods"], "periods_label": S["periods_label"], "test_counts": S["test_counts"],
        "free_at_arrival": S["free_at_arrival"],
        "lead": {L: {k: S["t2_lead"][L][k] for k in keep} for L in LEADS},
        "headline": S["t2_24"], "bss_raw": S["bss_raw"], "bss_reached_leads": S["bss_reached_leads"],
        "sensitivity": S["sensitivity"], "facts": {k: F[k] for k in fk}, "names": NAMES,
        "ablation_posthoc": S["ablation_posthoc"], "links": {"main": MAIN_DEMO, "protocol": PROTO, "compare": COMPARE},
        "main_vessel_24_baseline_pr_auc": _r(_main_vessel_24()),
    }


# ── 문서 절 ──────────────────────────────────────────────────────────────────
def _lead_table(S, keys, with_bss=True) -> list[str]:
    rows = ["| 예측기 | " + " | ".join(f"{x}시간 전" if x != "0" else "도착 순간" for x in LEADS) + " |", "|---|" + "---|" * len(LEADS)]
    for k in keys:
        cells = []
        for x in LEADS:
            m = S["t2_lead"][x].get(k)
            if not m:
                cells.append("—")
                continue
            ci = m.get("pr_auc_ci")
            c = f"{m['pr_auc']:.3f}"
            if with_bss and k != "S0" and m.get("bss") is not None:
                c += f" / {m['bss']:+.3f}"
            elif not with_bss and ci:
                c += f" ({ci[0]:.3f}–{ci[1]:.3f})"
            cells.append(c)
        rows.append(f"| {NAMES.get(k, k)} | " + " | ".join(cells) + " |")
    return rows


def compare_md(S) -> str:
    t1 = ["| 예측기 | PR-AUC (95% 구간) | ROC-AUC | Brier 기술점수 |", "|---|---|---|---|"]
    for k, m in S["t1"].items():
        ci = m.get("pr_auc_ci")
        t1.append(f"| {NAMES_T1.get(k, k)} | {m['pr_auc']:.3f}" + (f" ({ci[0]:.3f}–{ci[1]:.3f})" if ci else "") +
                  f" | {m['roc_auc']:.3f} | {m['bss']:+.3f} |")
    h, tc = S["t2_24"], S["test_counts"]
    reg = S["t3_registered"]
    sens = S.get("sensitivity")
    sub = S["subgroups"]["summer2026_t1"]
    return "\n".join([
        "# 선박별 하루 전 경보 — 실자료 백테스트 결과 비교 (두 번째 분석)", "",
        "- 같은 공개 자료·같은 정답(대기 12시간 초과)으로 선박 하나하나를 도착 전에 맞히는지 본 **두 번째 분석**(`realdata_ship/`)입니다. "
        "신항 전체 24시간 경보의 공식 결과는 [realdata/results/compare.md](../../realdata/results/compare.md)(주 분석)입니다.",
        f"- 생성: {S['generated']} · 커밋 {S['commit']} · 프로토콜: {PROTO}",
        f"- 시험 기간: {S['periods']['test'][0]} ~ {S['periods']['test'][1]} · 신항 컨테이너선 {tc['voyages']:,}항차, 12시간 초과 대기 {tc['long_waits']}척(기저율 {tc['base_rate']:.1%}), 에피소드 {tc['episodes']}개",
        "- 시험 기간은 두 번 계산했습니다(시험 뒤 누설을 더 엄격하게 고친 1건). 두 결과는 PROTOCOL.md 부록 B에 있습니다.",
        f"- 로지스틱 C(검증 기간에서 선택): T2 {json.dumps(S['choices']['t2'], ensure_ascii=False)}, T1 {json.dumps(S['choices']['t1'], ensure_ascii=False)}",
        "", "## T2 선박 단위 — PR-AUC (95% 구간, 주 단위 블록 부트스트랩)", "",
        *_lead_table(S, ("S0", "S1", "S2_logit", "S2_gbm", "R1", "R2", "R3_logit", "R3_gbm"), with_bss=False), "",
        "- 도착 순간·2시간 전 값은 라벨 정의 때문에 일부가 저절로 맞습니다(정박지를 거치지 않은 배는 도착 시각 = 접안 시각이라 그때 빈 선석이 있게 마련). 주 결과는 24·12·6시간 전입니다.",
        f"- 24시간 전 하이브리드: PR-AUC {h['pr_auc']:.3f}, ROC-AUC {h['roc_auc']:.3f}, Brier 기술점수 {h['bss']:+.3f}(95% {h['bss_ci'][0]:+.3f}~{h['bss_ci'][1]:+.3f})",
        "- Brier 기술점수(하이브리드, 반올림 전): " + ", ".join(f"{L}h {S['bss_raw'][L]:+.4f}" for L in LEADS),
        f"- 위험 상위 5%(시험 기간 예측 분포 기준): 정밀도 {h['top5']['precision']:.1%}(무작위 {tc['base_rate']:.1%}의 {h['top5']['lift']:.1f}배), 재현율 {h['top5']['recall']:.1%}",
        f"- 위험 상위 10%: 정밀도 {h['top10']['precision']:.1%}, 재현율 {h['top10']['recall']:.1%}",
        f"- 검증 기간 F1 최대 문턱(미리 정한 기준): 경보 비율 {h['valid_f1']['alarm_rate']:.1%}, 정밀도 {h['valid_f1']['precision']:.1%}, 재현율 {h['valid_f1']['recall']:.1%}",
        *([f"- 민감도(라벨 상한 336시간): 하이브리드 24시간 전 PR-AUC {sens['t2_24_r3_logit']['pr_auc']:.3f}, 장기 대기 {sens['t2_24_r3_logit']['pos']}척"] if sens else []),
        "", f"## 참고 계산: T1 시스템 경보(24시간 안에 장기 대기 선박 1척 이상, 기저율 {S['t1_base_rate']:.1%})", "",
        "> 선박별 표를 모아 만든 보조 계산이라 **앞으로 24시간 안에 올 선박과 그 이력을 미리 안다**는 낙관적 가정이 들어 있습니다. "
        "공식 T1 결과(주 분석, 기상·대기 상태만 씀)와 직접 비교하지 마세요.", "",
        *t1, "",
        f"- 2026년 6~9월 혼잡기 소분석: 기저율 {sub['S0']['base_rate']:.3f}, 하이브리드 PR-AUC {sub['R3_logit']['pr_auc']:.3f}, 통계 기준선 {sub['S2_logit']['pr_auc']:.3f}, 번짐 지수만 {sub['SIS_p1']['pr_auc']:.3f}",
        f"- 태풍 근접(중심 500km 이내) 판단 시각: {S['subgroups']['typhoon_tau']}개 — 따로 평가하기엔 적습니다.",
        "", "## 참고 계산: T3 사건 단위", "",
        ("미리 정한 기준(검증 기간 F1 최대 문턱)으로는 모든 예측기가 경보를 자주 켜서(경보 비율이 높음) 사건 탐지 지표가 변별력을 잃었습니다:"
         if facts(S)["t3_reg_uninformative"] else "미리 정한 기준(검증 기간 F1 최대 문턱):"),
        *[f"- {NAMES_T1.get(k, k)}: 경보 비율 {_p(e['alarm_rate'], 0)}, 탐지 {e['detected']}/{e['episodes']}, 오경보 {e['false_alarms']}/{e['alarms']}" for k, e in reg.items()],
        "", "사후 분석(경보를 시험 기간 예측 상위 10%로 고정):",
        *[f"- {NAMES_T1.get(k, k)}: 탐지 {e['detected']}/{e['episodes']}, 선행시간 중앙값 {e['lead_median_h']}시간, 미리 울린 비율 {_p(e['early_share'], 0)}, 경보 {e['alarms']}회 중 오경보 {e['false_alarms']}"
          for k, e in S["t3_posthoc_top10"].items()],
        "- 이 지표는 경보가 얼마나 자주 바뀌는지에 민감해 예측기 비교에는 T2 지표를 씁니다.",
        "", "## 참고: 이 분석의 SIS 필터", "",
        "> 이 분석의 SIS 필터(연속 입자필터, `sis_pf.py`)는 주 분석(`realdata/rdelay_real.py`)과 관측 모형·모수 추정 방식이 달라 R_d 수준을 서로 비교할 수 없습니다. "
        "선박 단위 결과에서 SIS 상태 특징의 기여는 0이었습니다(요인 제거 실험).", "",
        f"- β̄_S/γ_S = {S['sis']['beta_over_gamma']}, 해상–육상 결합 κ = {S['sis']['kappa_sea_land']}(학습 기간 우도 최대), 평균 대기 {S['sis']['mean_wait_h']}시간",
        "- R_d 분위수: " + " · ".join(f"{float(k) * 100:.0f}% {v:.3f}" for k, v in S["sis"]["rd_quantiles"].items()) + f", R_d>1 비율 {_p(S['sis']['p_rd_gt1_share'], 0)}",
        f"- f_ω(풍속·파고·휴일·태풍) 검증 우도 증가 {S['sis']['valid_loglik_gain_f_omega']}",
    ]) + "\n"


def readme_md(S) -> str:
    h, tc = S["t2_24"], S["test_counts"]
    F = facts(S)
    return "\n".join([
        f"> **선박별로 보면**(두 번째 분석, 선박 단위): 도착 24시간 전 위험 상위 5% 선박에 실제 12시간 초과 대기의 {_p(h['top5']['recall'])}가 들었고, "
        f"경보 정밀도는 {_p(h['top5']['precision'])}로 무작위({_p(tc['base_rate'])})의 {h['top5']['lift']:.1f}배였습니다"
        f"(상위 5%는 시험 기간 예측 분포 기준, 미리 정한 문턱으로는 경보 {_p(h['valid_f1']['alarm_rate'])}·정밀도 {_p(h['valid_f1']['precision'])}·재현율 {_p(h['valid_f1']['recall'])}). "
        f"예측력은 주로 {', '.join(F['top3'])}에서 나왔고"
        + (", 선석 대기열·번짐 지수가 더한 몫은 작았습니다" if F["mech_small"] else ", 선석 대기열·번짐 지수도 일부 더했습니다")
        + ". 대상 선박의 도착 시각과 터미널을 미리 안다는 낙관적 가정이 들어 있습니다.",
        ">",
        f"> → [선박별 검증 화면]({DEMO}) · [비교표 `{COMPARE}`]({COMPARE}) · [기술 보고서의 해당 절]({REPORT_ANCHOR})",
    ])


def report_md(S) -> str:
    h, tc, d = S["t2_24"], S["test_counts"], S["data"]
    F = facts(S)
    fa = S["free_at_arrival"]
    ab = S["ablation_posthoc"]
    sens = S.get("sensitivity")
    L24 = S["t2_lead"]["24"]
    return "\n".join([
        "### 두 번째 분석: 선박별 하루 전 경보",
        "",
        f"> 같은 공개 자료·같은 정답(대기 12시간 초과)으로 **선박 하나하나**를 도착 몇 시간 전에 맞히는지 따로 본 분석입니다(`realdata_ship/`). "
        f"위 절(신항 전체 24시간 경보)과 코드·모형을 나누지 않는 독립 구현이고, 설계는 시험 기간을 보기 전에 [{PROTO}]({PROTO})에 정했습니다. "
        f"시험 뒤 누설을 더 엄격하게 고친 1건이 있어 시험 기간을 두 번 계산했고 두 결과를 부록 B에 적었습니다. "
        f"화면: [선박별 검증]({DEMO}) · 전체 표: [{COMPARE}]({COMPARE}) · 재현: `python -m realdata_ship.run_all`",
        "",
        f"- **판단 시각**: 각 선박 도착 24·12·6·2·0시간 전. 대상 선박의 도착 시각과 갈 터미널, 그보다 먼저 올 선박은 미리 안다고 가정했습니다(정기선 일정을 실제 값으로 대체한 낙관적 가정).",
        f"- **기간**: 학습 {S['periods_label']['train']} · 검증 {S['periods_label']['valid']} · 시험 {S['periods_label']['test']}. 시험 기간 {tc['voyages']:,}항차 중 12시간 넘게 기다린 배는 {tc['long_waits']}척(기저율 {_p(tc['base_rate'])})입니다.",
        "- **예측기**: 터미널별 기후값, 통계 기준선(이력·선박 크기·기상 등, R-Delay 부품 없음: 로지스틱·GBM), R-Delay 선석 대기열(터미널별 몬테카를로), 하이브리드(통계 특징 + 대기열 확률 + SIS 상태, 시험 전에 최종 모형으로 정함).",
        "",
        "PR-AUC / Brier 기술점수(기준: 터미널별 기후값), 시험 기간:",
        "",
        *_lead_table(S, ("S0", "R1", "S2_logit", "S2_gbm", "R3_logit", "R3_gbm")),
        "",
        "![선박별 하루 전 경보](./image/backtest_ship_alarm.png)",
        "",
        f"- 도착 24시간 전 하이브리드: PR-AUC {_f(h['pr_auc'])}(95% {_f(h['pr_auc_ci'][0])}~{_f(h['pr_auc_ci'][1])}), ROC-AUC {_f(h['roc_auc'])}. 시험 기간 예측 상위 5%: 정밀도 {_p(h['top5']['precision'])}(무작위의 {h['top5']['lift']:.1f}배), 재현율 {_p(h['top5']['recall'])}. 상위 10%: 정밀도 {_p(h['top10']['precision'])}, 재현율 {_p(h['top10']['recall'])}. 검증 기간에서 미리 정한 문턱으로는 경보 {_p(h['valid_f1']['alarm_rate'])}, 정밀도 {_p(h['valid_f1']['precision'])}, 재현율 {_p(h['valid_f1']['recall'])}.",
        (f"- R-Delay 부품 없이 같은 특징만 쓴 통계 GBM(PR-AUC {_f(L24['S2_gbm']['pr_auc'])})이 R-Delay GBM({_f(L24['R3_gbm']['pr_auc'])})과 같거나 높았습니다. 하루 전 예측력은 이력 특징에서 나옵니다." if F["s2gbm_ge_r3gbm"] else
         f"- R-Delay GBM {_f(L24['R3_gbm']['pr_auc'])}, 통계 GBM {_f(L24['S2_gbm']['pr_auc'])}."),
        "- 도착 순간·2시간 전 값은 라벨 정의 때문에 일부가 저절로 맞습니다(정박지를 거치지 않은 배는 도착 시각이 곧 접안 시각이라 그때 빈 선석이 있게 마련). 주 결과는 24·12·6시간 전입니다.",
        *([f"- 민감도(라벨 상한 336시간): 하이브리드 24시간 전 PR-AUC {_f(sens['t2_24_r3_logit']['pr_auc'])}(장기 대기 {sens['t2_24_r3_logit']['pos']}척)."] if sens else []),
        "- 요인 묶음을 하나씩 뺐을 때 24시간 전 PR-AUC 변화(사후 분석): " + ", ".join(f"{g['group']} {_chg(g['drop'])}" for g in ab["groups"]) + "."
        + (" 같은 배·같은 슬롯이 최근 오래 기다렸을수록, 작은 피더선일수록 위험했습니다." if F["small_ship_riskier"] and F["history_positive"] else ""),
        f"- 정박지에서 기다린 배의 {_p(fa['anchored_with_free_berth'], 0)}(12시간 넘게 기다린 배만 보면 {_p(fa['long_wait_with_free_berth'], 0)})는 도착 순간 그 터미널에 빈 선석(학습 기간 선석 수 기준)이 있었는데도 기다렸습니다. 선석은 먼저 온 순서가 아니라 선석 계획(창구)대로 배정되므로, 터미널 선석 계획(ETB)·선사 ETA를 연동해야 대기열 모형이 제 몫을 합니다.",
        f"- {_bss_sentence(S)}",
        *([f"- 위 절의 선박 단위 참고 표(같은 낙관적 가정, 이력 특징 없음)에서는 도착 24시간 전 기준선 PR-AUC가 {_main_vessel_24():.3f}였습니다. 이 분석은 같은 선박·같은 요일 슬롯의 대기 이력(판단 시각 12시간 전까지 확정된 항차만)을 더했고, 요인 제거 실험에서 차이의 대부분이 이 이력에서 나왔습니다. 대기열만으로는 약하다는 결론은 같습니다."] if _main_vessel_24() is not None else []),
        "- 이 분석의 SIS 상태 특징은 기여가 0이었고, SIS 필터 설정(관측 모형·모수 추정)이 위 절과 달라 R<sub>d</sub> 값은 서로 비교하지 않습니다.",
    ])


def model_md(S) -> str:
    return "\n".join([
        "## 11-2. 선박 단위 분석 (`realdata_ship/`)",
        "",
        "11절(신항 전체 24시간 경보)과 따로, 선박 하나하나의 '대기 > 12시간'을 도착 전에 맞히는 두 번째 분석을 `realdata_ship/`에 두었다. 엔진(`docs/py/rdelay`)은 고치지 않았다.",
        "",
        "- **선석 대기열(터미널별 몬테카를로)**: 서버 = 학습 기간 선석 이름 수, 서비스 = 학습 기간 실제 체류시간 경험분포, 대 있는 선박의 남은 체류 = 경과시간 조건부 표본, 순서 = 정박지 대기(도착순) → 예정 도착(도착순). 400회로 대상 선박의 P(대기 > 12h).",
        "- **학습형 모듈(하이브리드)**: 로지스틱 회귀(표준화, L2, C는 검증 기간에서 리드별로 선택) — 대기열 확률, SIS 상태, 같은 선박의 이전 기항 이력, 같은 요일·시간대 슬롯의 최근 8주 장기 대기율, 선박 크기, 터미널 대기열·예정 도착, 기상·태풍·도로. 이력은 판단 시각 12시간 전까지 결과('대기 > 12시간')가 확정된 항차만 쓴다.",
        "- **SIS 상태 특징**: 엔진의 `sis`·`stats` 함수로 만든 연속 입자필터(입자 512, Δt 0.5시간, 관측 2시간)의 판단 시각 요약(x̂, ẑ, R̂<sub>d</sub>)을 특징으로만 썼다. 관측 모형·모수 추정이 11절과 달라 R<sub>d</sub> 수준은 비교하지 않는다(선박 단위 결과에서 기여 0).",
        "",
        f"결과는 [REPORT.md]({REPORT_ANCHOR}), 설계는 [{PROTO}]({PROTO}).",
    ])


def _replace_between(path: pathlib.Path, tag: str, body: str) -> bool:
    """문서의 <!-- tag:start --> ~ <!-- tag:end --> 사이만 바꾼다. 표시가 없으면 아무것도 하지 않는다."""
    s = path.read_text(encoding="utf-8")
    start, end = f"<!-- {tag}:start -->", f"<!-- {tag}:end -->"
    if start not in s or end not in s:
        return False
    s = s[: s.index(start)] + f"{start}\n{body}\n{end}" + s[s.index(end) + len(end):]
    paths.write_text(path, s)
    return True


def update_docs(S) -> dict:
    R = paths.ROOT
    return {
        "README": _replace_between(R / "README.md", "realdata-ship-readme", readme_md(S)),
        "REPORT": _replace_between(R / "REPORT.md", "realdata-ship-report", report_md(S)),
        "MODEL": _replace_between(R / "MODEL.md", "realdata-ship-model", model_md(S)),
    }


def build_all():
    _font()
    res, cal, sens, p1, g = _load()
    S = summary(res, cal, sens, p1, g)
    paths.write_text(paths.RESULTS / "summary.json", json.dumps(S, ensure_ascii=False, indent=1, default=str))
    paths.write_text(paths.RESULTS / "compare.md", compare_md(S))
    fig_leads(S)
    fig_alarm(S)
    fig_reliability(S)
    fig_drivers(S)
    out = paths.ROOT / "docs" / "data" / "backtest_ship.json"
    paths.write_text(out, json.dumps(web_json(S), ensure_ascii=False, separators=(",", ":"), default=str))
    docs = update_docs(S)
    print(f"summary → {paths.RESULTS / 'summary.json'} · web → {out} ({out.stat().st_size / 1024:.0f} KB) · figs → {paths.REPORTS} · docs {docs}")
    return S
