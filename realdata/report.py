"""백테스트 결과 요약·그림·웹 자료(docs/data/backtest.json)·문서 절·발표 문안.

공개 산출물에는 신항 전체 집계만 넣는다(선박 이름·호출부호·터미널 이름 없음, Clarksons 없음).
해석 문장은 숫자 조건으로 고른다(자료가 바뀌면 문장도 따라 바뀜).
"""
from __future__ import annotations

import datetime as dt
import json
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
DEMO = "https://jaewansh.github.io/R-Delay/backtest.html"
FIRST_RUN = {"pr_auc": 0.196, "roc_auc": 0.858}  # 시험 첫 계산(누설 수정 전) 24시간 전 하이브리드 — PROTOCOL 부록 B


def _font():
    import matplotlib
    from matplotlib import font_manager as fm
    for d in (pathlib.Path.home() / "fontpkg/pt/package/dist/public/static/alternative",
              pathlib.Path("/home/claude/fontpkg/pt/package/dist/public/static/alternative")):
        if d.exists():
            for f in d.glob("Pretendard-*.ttf"):
                fm.fontManager.addfont(str(f))
    have = {f.name for f in fm.fontManager.ttflist}
    for name in ("Pretendard", "Malgun Gothic", "AppleGothic", "Apple SD Gothic Neo", "NanumGothic", "Noto Sans CJK KR"):
        if name in have:
            matplotlib.rcParams["font.family"] = name
            break
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
        fig.savefig(paths.ROOT / "image" / f"backtest_{name[4:]}.png", dpi=130, bbox_inches="tight")


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


def pick_cases(res, p1) -> tuple[dict, float]:
    vv = pd.read_parquet(paths.CACHE / "ship_r1s.parquet")
    pos = vv.loc[(vv["L"] == 0) & vv["pos12"], "arrival_t"].sort_values()
    a, b = pd.Timestamp(res["test_period"][0]), pd.Timestamp(res["test_period"][1])
    pt = pos[(pos >= a) & (pos < b)]
    s = pd.Series(1, index=pt).resample("1D").sum().rolling(14).sum()
    peak_end = s.idxmax().normalize() + pd.Timedelta(days=1)
    cases = {"peak": {"title": "혼잡이 가장 몰린 2주", "start": peak_end - pd.Timedelta(days=14), "end": peak_end}}
    cases["typhoon"] = {"title": "태풍 참피 접근(2026-10)", "start": pd.Timestamp("2026-10-19"), "end": pd.Timestamp("2026-11-01")}
    thr = float(np.quantile(p1["R3_logit"], 0.9))
    on = p1.set_index("tau")["R3_logit"] >= thr
    eps = [e for e in ev.episodes(pos.to_numpy()) if a <= e[0] < b]
    missed = []
    for s0, e0, n in eps:
        w = on[(on.index >= s0 - pd.Timedelta(hours=72)) & (on.index <= s0 + pd.Timedelta(hours=12))]
        if not w.any():
            missed.append((n, s0, e0))
    if missed:
        n, s0, e0 = sorted(missed, key=lambda x: (-x[0], x[1]))[0]
        cases["miss"] = {"title": "경보가 놓친 사례", "start": s0.normalize() - pd.Timedelta(days=5), "end": e0.normalize() + pd.Timedelta(days=3)}
    return cases, thr


def case_series(case, p1, g) -> pd.DataFrame:
    vv = pd.read_parquet(paths.CACHE / "ship_r1s.parquet")
    pos = vv.loc[(vv["L"] == 0) & vv["pos12"], "arrival_t"]
    idx = pd.date_range(case["start"], case["end"], freq="2h", inclusive="left")
    x = pd.DataFrame(index=idx)
    gg = g.reindex(idx)
    x["n_wait"] = gg["n_wait"]
    x["rd"] = gg["sis_rd"]
    x["wind"] = gg["wind_bsn_max6"]
    x["hs"] = gg["hs_geoje_max6"]
    x["p_r3"] = p1.set_index("tau")["R3_logit"].reindex(idx)
    x["pos_arr"] = pd.Series(1, index=pos).resample("2h").sum().reindex(idx).fillna(0)
    return x


def fig_case(name, case, x, thr):
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(9.0, 6.6), sharex=True, gridspec_kw={"height_ratios": [1.2, 1, 0.9]})
    ax = axes[0]
    ax.fill_between(x.index, x["n_wait"], step="post", color=COL["line"], alpha=0.9, lw=0)
    ax.step(x.index, x["n_wait"], where="post", color=COL["ink2"], lw=1)
    arr = x[x["pos_arr"] > 0]
    ax.scatter(arr.index, np.full(len(arr), max(x["n_wait"].max(), 1) + 0.6), marker="v", s=40 * arr["pos_arr"],
               color=COL["red"], zorder=3, label="12시간 넘게 기다린 선박 도착")
    ax.set_ylabel("정박지 대기 척수")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax.set_title(case["title"], loc="left", fontsize=12)
    ax = axes[1]
    ax.plot(x.index, x["p_r3"], color=COL["brand"], lw=1.8, label="R-Delay: 24시간 안에 장기 대기 선박이 나올 확률")
    ax.axhline(thr, color=COL["red"], lw=1, ls=(0, (4, 3)))
    ax.fill_between(x.index, 0, 1, where=(x["p_r3"] >= thr).to_numpy(), color=COL["red"], alpha=0.07, step="post",
                    transform=ax.get_xaxis_transform())
    ax.text(x.index[0], thr, " 경보선(시험 기간 상위 10%)", color=COL["red"], fontsize=8, va="bottom")
    ax.set_ylim(0, 1)
    ax.set_ylabel("확률")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    ax = axes[2]
    ax.plot(x.index, x["rd"], color=COL["ink"], lw=1.4, label="번짐 지수 R_d")
    ax.axhline(1.0, color=COL["muted"], lw=1, ls=(0, (2, 2)))
    ax.set_ylabel("R_d")
    ax2 = ax.twinx()
    ax2.plot(x.index, x["hs"], color=COL["green"], lw=1.2, label="거제 유의파고(m)")
    ax2.set_ylabel("파고(m)", color=COL["green"])
    ax2.grid(False)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8, loc="upper left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    fig.align_ylabels(axes)
    _save(fig, f"fig_case_{name}")
    plt.close(fig)


# ── 웹 자료 ──────────────────────────────────────────────────────────────────
def web_json(S, cases_data) -> dict:
    keep = ["S0", "R1", "S2_logit", "S2_gbm", "R3_logit", "R3_gbm"]
    F = facts(S)
    return {
        "generated": S["generated"], "commit": S["commit"],
        "notice": ("공개 실자료 후향 검증(실시간 운영 검증 아님). 신항 전체 집계만 담았고 선박·터미널 이름은 넣지 않았다. "
                   "시험 기간은 두 번 계산했다(시험 뒤 누설을 더 엄격하게 고친 1건, 두 결과 모두 PROTOCOL.md 부록 B에 기록)."),
        "rule": RULE, "sources": SOURCES, "first_run": S["first_run"],
        "data": S["data"], "periods": S["periods"], "periods_label": S["periods_label"], "test_counts": S["test_counts"],
        "free_at_arrival": S["free_at_arrival"],
        "lead": {L: {k: S["t2_lead"][L][k] for k in keep} for L in LEADS},
        "headline": S["t2_24"], "bss_raw": S["bss_raw"], "bss_reached_leads": S["bss_reached_leads"],
        "t1": {k: S["t1"][k] for k in ("S0", "S1", "R1", "SIS_p1", "S2_logit", "S2_gbm", "R3_logit", "R3_gbm") if k in S["t1"]},
        "t1_base_rate": S["t1_base_rate"], "t3_registered": S["t3_registered"], "t3_posthoc_top10": S["t3_posthoc_top10"],
        "subgroups": S["subgroups"], "sensitivity": S["sensitivity"],
        "sis": {k: S["sis"][k] for k in ("beta_over_gamma", "kappa_sea_land", "mean_wait_h", "rd_quantiles", "p_rd_gt1_share",
                                          "valid_loglik_gain_f_omega")},
        "facts": F, "names": NAMES, "names_t1": NAMES_T1, "cases": cases_data, "ablation_posthoc": S["ablation_posthoc"],
    }


# ── 문서 절 ──────────────────────────────────────────────────────────────────
def compare_md(S) -> str:
    rows = ["| 예측기 | " + " | ".join(f"{x}시간 전" if x != "0" else "도착 순간" for x in LEADS) + " |", "|---|" + "---|" * len(LEADS)]
    for k in ("S0", "S1", "S2_logit", "S2_gbm", "R1", "R2", "R3_logit", "R3_gbm"):
        cells = []
        for x in LEADS:
            m = S["t2_lead"][x].get(k)
            ci = m.get("pr_auc_ci") if m else None
            cells.append("—" if not m else f"{m['pr_auc']:.3f}" + (f" ({ci[0]:.3f}–{ci[1]:.3f})" if ci else ""))
        rows.append(f"| {NAMES.get(k, k)} | " + " | ".join(cells) + " |")
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
        "# 실자료 백테스트 결과 비교", "",
        f"- 생성: {S['generated']} · 커밋 {S['commit']} · 프로토콜: realdata/PROTOCOL.md",
        f"- 시험 기간: {S['periods']['test'][0]} ~ {S['periods']['test'][1]} · 신항 컨테이너선 {tc['voyages']:,}항차, 12시간 초과 대기 {tc['long_waits']}척(기저율 {tc['base_rate']:.1%}), 에피소드 {tc['episodes']}개",
        "- 시험 기간은 두 번 계산했습니다(시험 뒤 누설을 더 엄격하게 고친 1건). 두 결과는 PROTOCOL.md 부록 B에 있습니다.",
        f"- 로지스틱 C(검증 기간에서 선택): T2 {json.dumps(S['choices']['t2'], ensure_ascii=False)}, T1 {json.dumps(S['choices']['t1'], ensure_ascii=False)}",
        "", "## T2 선박 단위 — PR-AUC (95% 구간, 주 단위 블록 부트스트랩)", "", *rows, "",
        "- 도착 순간·2시간 전 값은 라벨 정의 때문에 일부가 저절로 맞습니다(정박지를 거치지 않은 배는 도착 시각 = 접안 시각이라 그때 빈 선석이 있게 마련). 주 결과는 24·12·6시간 전입니다.",
        f"- 24시간 전 R-Delay 실자료판(하이브리드): PR-AUC {h['pr_auc']:.3f}, ROC-AUC {h['roc_auc']:.3f}, Brier 기술점수 {h['bss']:+.3f}(95% {h['bss_ci'][0]:+.3f}~{h['bss_ci'][1]:+.3f})",
        f"- Brier 기술점수(하이브리드, 반올림 전): " + ", ".join(f"{L}h {S['bss_raw'][L]:+.4f}" for L in LEADS),
        f"- 위험 상위 5%(시험 기간 예측 분포 기준): 정밀도 {h['top5']['precision']:.1%}(무작위 {tc['base_rate']:.1%}의 {h['top5']['lift']:.1f}배), 재현율 {h['top5']['recall']:.1%}",
        f"- 위험 상위 10%: 정밀도 {h['top10']['precision']:.1%}, 재현율 {h['top10']['recall']:.1%}",
        f"- 검증 기간 F1 최대 문턱(미리 정한 기준): 경보 비율 {h['valid_f1']['alarm_rate']:.1%}, 정밀도 {h['valid_f1']['precision']:.1%}, 재현율 {h['valid_f1']['recall']:.1%}",
        *([f"- 민감도(라벨 상한 336시간): 하이브리드 24시간 전 PR-AUC {sens['t2_24_r3_logit']['pr_auc']:.3f}, 장기 대기 {sens['t2_24_r3_logit']['pos']}척"] if sens else []),
        "", f"## T1 시스템 경보(24시간 안에 장기 대기 선박 1척 이상, 기저율 {S['t1_base_rate']:.1%})", "", *t1, "",
        f"- 2026년 6~9월 혼잡기 소분석: 기저율 {sub['S0']['base_rate']:.3f}, 하이브리드 PR-AUC {sub['R3_logit']['pr_auc']:.3f}, 통계 기준선 {sub['S2_logit']['pr_auc']:.3f}, 번짐 지수만 {sub['SIS_p1']['pr_auc']:.3f}",
        f"- 태풍 근접(중심 500km 이내) 판단 시각: {S['subgroups']['typhoon_tau']}개 — 따로 평가하기엔 적습니다.",
        "", "## T3 사건 단위", "",
        ("미리 정한 기준(검증 기간 F1 최대 문턱)으로는 모든 예측기가 경보를 자주 켜서(경보 비율이 높음) 사건 탐지 지표가 변별력을 잃었습니다:"
         if facts(S)["t3_reg_uninformative"] else "미리 정한 기준(검증 기간 F1 최대 문턱):"),
        *[f"- {NAMES_T1.get(k, k)}: 경보 비율 {_p(e['alarm_rate'], 0)}, 탐지 {e['detected']}/{e['episodes']}, 오경보 {e['false_alarms']}/{e['alarms']}" for k, e in reg.items()],
        "", "사후 분석(경보를 시험 기간 예측 상위 10%로 고정):",
        *[f"- {NAMES_T1.get(k, k)}: 탐지 {e['detected']}/{e['episodes']}, 선행시간 중앙값 {e['lead_median_h']}시간, 미리 울린 비율 {_p(e['early_share'], 0)}, 경보 {e['alarms']}회 중 오경보 {e['false_alarms']}"
          for k, e in S["t3_posthoc_top10"].items()],
        ("- 해석: 기후값(시간대·요일 평균) 경보는 같은 상위 10%에서도 더 자주 켜졌다 꺼져(경보 "
         f"{S['t3_posthoc_top10']['S0']['alarms']}회 대 하이브리드 {S['t3_posthoc_top10']['R3_logit']['alarms']}회) 더 많은 에피소드를 '탐지'합니다. "
         if S["t3_posthoc_top10"]["S0"]["alarms"] > S["t3_posthoc_top10"]["R3_logit"]["alarms"]
         and S["t3_posthoc_top10"]["S0"]["detected"] > S["t3_posthoc_top10"]["R3_logit"]["detected"] else "- ")
        + "이 지표는 경보가 얼마나 자주 바뀌는지에 민감해 예측기 비교에는 T1·T2 지표를 씁니다.",
        "", "## SIS(번짐 지수) 실자료 적합", "",
        f"- β̄_S/γ_S = {S['sis']['beta_over_gamma']}, 해상–육상 결합 κ = {S['sis']['kappa_sea_land']}(학습 기간 우도 최대), 평균 대기 {S['sis']['mean_wait_h']}시간",
        "- R_d 분위수: " + " · ".join(f"{float(k) * 100:.0f}% {v:.3f}" for k, v in S["sis"]["rd_quantiles"].items()) + f", R_d>1 비율 {_p(S['sis']['p_rd_gt1_share'], 0)}",
        f"- f_ω(풍속·파고·휴일·태풍) 검증 우도 증가 {S['sis']['valid_loglik_gain_f_omega']}",
    ]) + "\n"


def readme_md(S) -> str:
    h, tc, p, d = S["t2_24"], S["test_counts"], S["periods"], S["data"]
    F = facts(S)
    L24 = S["t2_lead"]["24"]
    mech = ("공개 자료만으로는 선석 대기열과 번짐 지수 R<sub>d</sub>가 하루 전 예측력을 거의 더하지 못했습니다"
            if F["mech_small"] else f"선석 대기열과 번짐 지수 R<sub>d</sub>는 하루 전 PR-AUC를 {F['mech_drop']:.3f} 더했습니다")
    gbm = (f" R-Delay 부품 없이 같은 이력 특징만 쓴 통계 GBM(PR-AUC {L24['S2_gbm']['pr_auc']:.3f})도 R-Delay GBM({L24['R3_gbm']['pr_auc']:.3f})과 같거나 높았습니다."
           if F["s2gbm_ge_r3gbm"] else "")
    return "\n".join([
        "### 실자료 검증 — 부산신항 2023~2026 공개 자료 백테스트",
        "",
        f"- PORT-MIS 관제정보로 잰 신항 컨테이너선 {d['voyages']:,}항차({d['period'][0]}~{d['period'][1]})의 정박지 대기로 R-Delay를 되돌려 검증했습니다. 기간·목표·지표는 시험 기간을 보기 전에 [정했고](realdata/PROTOCOL.md), 시험 뒤 누설을 더 엄격하게 고친 1건이 있어 시험 기간을 두 번 계산했습니다(두 결과 모두 기록). 시험 기간({S['periods_label']['test'][:21]}) {tc['voyages']:,}항차 중 12시간 넘게 기다린 배는 {tc['long_waits']}척(기저율 {_p(tc['base_rate'])})입니다.",
        f"- **도착 24시간 전, 예측 위험 상위 5% 선박에 실제 장기 대기의 {_p(h['top5']['recall'])}가 들어 있었고, 경보 정밀도는 {_p(h['top5']['precision'])}로 무작위의 {h['top5']['lift']:.1f}배였습니다**(상위 5%는 시험 기간 예측 분포 기준; 검증 기간에서 미리 정한 문턱으로는 경보 {_p(h['valid_f1']['alarm_rate'])}, 정밀도 {_p(h['valid_f1']['precision'])}, 재현율 {_p(h['valid_f1']['recall'])}). PR-AUC {_f(h['pr_auc'])}(95% {_f(h['pr_auc_ci'][0])}~{_f(h['pr_auc_ci'][1])}, 무작위 {_f(tc['base_rate'])}).",
        f"- 예측력은 주로 {', '.join(F['top3'])}에서 나왔습니다. {mech}.{gbm} 터미널 선석 계획(ETB) 연동이 다음 단계입니다.",
        "",
        "![하루 전 경보](./image/backtest_alarm.png)",
        "![도착 몇 시간 전에 얼마나 맞히나](./image/backtest_leads.png)",
        "",
        f"- 자세히: [실자료 검증 화면]({DEMO}) · [REPORT](REPORT.md#검증-실제-공개-자료-백테스트) · [전체 비교표](realdata/results/compare.md) · 재현 `python -m realdata.run_all`",
    ])


def report_md(S) -> str:
    h, tc, p, d = S["t2_24"], S["test_counts"], S["periods"], S["data"]
    F = facts(S)
    fa = S["free_at_arrival"]
    lead_rows = ["| 예측기 | " + " | ".join(f"{x}시간 전" if x != "0" else "도착 순간" for x in LEADS) + " |", "|---|" + "---|" * len(LEADS)]
    for k in ("S0", "R1", "S2_logit", "S2_gbm", "R3_logit", "R3_gbm"):
        cells = []
        for x in LEADS:
            m = S["t2_lead"][x][k]
            cells.append(f"{_f(m['pr_auc'])}" + (f" / {m['bss']:+.3f}" if k != "S0" and m.get("bss") is not None else ""))
        lead_rows.append(f"| {NAMES[k]} | " + " | ".join(cells) + " |")
    t1_rows = ["| 예측기 | PR-AUC (95% 구간) | ROC-AUC | Brier 기술점수 |", "|---|---|---|---|"]
    for k in ("S0", "S1", "R1", "SIS_p1", "S2_logit", "S2_gbm", "R3_logit", "R3_gbm"):
        m = S["t1"][k]
        ci = m.get("pr_auc_ci")
        t1_rows.append(f"| {NAMES_T1[k]} | {_f(m['pr_auc'])}" + (f" ({_f(ci[0])}~{_f(ci[1])})" if ci else "") +
                       f" | {_f(m['roc_auc'])} | {m['bss']:+.3f} |")
    ab = S["ablation_posthoc"]
    s = S["sis"]
    q = s["rd_quantiles"]
    post = S["t3_posthoc_top10"]
    sens = S.get("sensitivity")
    sis_line = ("P(R<sub>d</sub>>1) 하나만으로는 24시간 뒤를 미리 맞히지 못했습니다(기저율 수준)" if F["sis_alone_at_base"]
                else "P(R<sub>d</sub>>1) 하나만으로도 기저율보다 나았습니다")
    return "\n".join([
        "## 검증: 실제 공개 자료 백테스트",
        "",
        f"> 부산신항 {d['period'][0]}~{d['period'][1]} 공개 실자료로 과거를 되돌려 본 **후향 검증**입니다(실시간 운영 검증 아님). 기간 나누기·목표·지표·경보 기준은 시험 기간 결과를 보기 전에 [realdata/PROTOCOL.md](realdata/PROTOCOL.md)에 정했습니다. 시험 뒤 누설을 더 엄격하게 고친 1건이 있어 시험 기간을 두 번 계산했고, 두 결과를 부록 B에 함께 적었습니다. 화면: [실자료 검증]({DEMO}) · 전체 표: [realdata/results/compare.md](realdata/results/compare.md) · 재현: `python -m realdata.run_all`",
        "",
        "**자료와 정답**",
        "",
        f"- 해양수산부 PORT-MIS 관제정보로 신항 컨테이너선 {d['voyages']:,}항차의 정박지 대기(정박지 도착 → 신항 선석 첫 접안)를 쟀습니다. {RULE} 규정에 맞춰 12시간 초과를 장기 대기로 봤고 {d['long_waits']}척({_p(d['long_wait_share'])})입니다. 168시간을 넘는 {d['excluded_over_cap']}건은 혼잡이 아닌 장기 체류로 보고 정답에서 뺐습니다(민감도: 상한 336시간).",
        f"- 학습 {S['periods_label']['train']} · 검증 {S['periods_label']['valid']} · 시험 {S['periods_label']['test']}(분석은 물동량 28일 기준선을 채운 {d['analysis_start']}부터). 시험 기간: {tc['voyages']:,}항차 중 장기 대기 {tc['long_waits']}척(기저율 {_p(tc['base_rate'])}), 에피소드 {tc['episodes']}개.",
        "- 특징은 판단 시각까지 알 수 있는 것만 썼습니다(터미널별 선석 점유·대기열, 신항 전체 대기, 기상청 ASOS·거제도 부이, 태풍 경로, 한국도로공사 1시간 구간속도, 결과가 확정된 항차의 이력). 대상 선박의 도착 시각과 갈 터미널, 그보다 먼저 올 예정 선박은 미리 안다고 가정했습니다(정기선 일정을 실제 값으로 대체한 낙관적 가정).",
        "",
        "**결과 1 — 선박별 '12시간 넘게 기다릴까'** (PR-AUC / Brier 기술점수, 기준: 터미널별 기후값)",
        "",
        *lead_rows,
        "",
        f"- 도착 24시간 전, 시험 기간 예측 상위 5%: 정밀도 {_p(h['top5']['precision'])}(무작위 {_p(tc['base_rate'])}의 {h['top5']['lift']:.1f}배), 재현율 {_p(h['top5']['recall'])}. 상위 10%: 정밀도 {_p(h['top10']['precision'])}, 재현율 {_p(h['top10']['recall'])}. 검증 기간에서 미리 정한 문턱으로는 경보 {_p(h['valid_f1']['alarm_rate'])}, 정밀도 {_p(h['valid_f1']['precision'])}, 재현율 {_p(h['valid_f1']['recall'])}.",
        f"- 24시간 전 하이브리드 PR-AUC {_f(h['pr_auc'])}(95% {_f(h['pr_auc_ci'][0])}~{_f(h['pr_auc_ci'][1])}), ROC-AUC {_f(h['roc_auc'])}." +
        (f" R-Delay 부품(대기열·번짐 지수) 없이 같은 이력 특징만 쓴 통계 GBM(PR-AUC {_f(S['t2_lead']['24']['S2_gbm']['pr_auc'])})이 R-Delay GBM({_f(S['t2_lead']['24']['R3_gbm']['pr_auc'])})과 같거나 높았습니다." if F["s2gbm_ge_r3gbm"] else ""),
        "- 도착 순간·2시간 전 값은 라벨 정의 때문에 일부가 저절로 맞습니다(정박지를 거치지 않은 배는 도착 시각이 곧 접안 시각이라 그때 빈 선석이 있게 마련). 주 결과는 24·12·6시간 전입니다.",
        *([f"- 민감도(라벨 상한 336시간): 하이브리드 24시간 전 PR-AUC {_f(sens['t2_24_r3_logit']['pr_auc'])}(장기 대기 {sens['t2_24_r3_logit']['pos']}척)."] if sens else []),
        "",
        "**결과 2 — 예측은 어디서 오나** (요인 묶음을 하나씩 뺐을 때 24시간 전 PR-AUC 변화, 시험 기간 사후 분석)",
        "",
        *[f"- {g['group']}: {_chg(g['drop'])}" for g in ab["groups"]],
        "",
        "**결과 3 — 신항 전체 24시간 경보와 번짐 지수** (24시간 안에 장기 대기 선박 1척 이상, 기저율 " + _p(S["t1_base_rate"]) + ")",
        "",
        *t1_rows,
        "",
        f"- 학습 기간 우도로 고른 전파율은 해소율의 {s['beta_over_gamma']}배이고, R<sub>d</sub>는 1 근처에서 움직였습니다(중앙값 {_f(q['0.5'])}, 5~95% {_f(q['0.05'])}~{_f(q['0.95'])}, R<sub>d</sub>>1 비율 {_p(s['p_rd_gt1_share'], 0)}). 물량이 조금만 늘어도 번짐 구간으로 넘어가는 임계 근처라는 뜻입니다.",
        f"- 해상–육상(배후 고속도로) 결합은 자료가 지지하지 않았습니다(결합 강도 {s['kappa_sea_land']}에서 우도 최대). 학습형 모듈 f<sub>ω</sub>(풍속·파고·휴일·태풍)는 검증 우도를 {s['valid_loglik_gain_f_omega']} 높였습니다" + ("(바람·파도가 셀수록 새 대기 발생률이 낮아짐: 악천후에는 입항 자체가 줄어드는 것으로 보임)." if F["fomega_wind_hs_negative"] else "."),
        f"- {sis_line}. 사건 단위(사후 분석, 경보 상위 10%)로 보면 번짐 지수 경보는 에피소드 {post['SIS_p1']['episodes']}개 중 {post['SIS_p1']['detected']}개에서 울렸지만 미리 울린 비율이 {_p(post['SIS_p1']['early_share'], 0)}였고, 하이브리드는 {post['R3_logit']['detected']}개(미리 {_p(post['R3_logit']['early_share'], 0)}, 중앙값 {post['R3_logit']['lead_median_h']}시간 전), 시간대·요일 기후값은 {post['S0']['detected']}개(미리 {_p(post['S0']['early_share'], 0)})였습니다. 이 지표는 경보가 자주 바뀔수록 유리해 예측기 비교는 T1·T2 지표로 합니다." + (f" 미리 정한 문턱(검증 F1 최대)에서는 모든 예측기가 경보를 자주 켜(경보 비율 {_p(F['t3_reg_min_alarm'], 0)} 이상) 에피소드를 거의 다 '탐지'해 변별력이 없었습니다." if F["t3_reg_uninformative"] else "") + " R<sub>d</sub>는 '지금 번지는 중'을 확인하는 지표로 씁니다.",
        "",
        "**해석과 다음 단계**",
        "",
        f"- 공개 자료만으로도 하루 전에 장기 대기 위험 선박을 골라낼 수 있습니다. 힘의 원천은 {', '.join(F['top3'])}입니다" + ("(같은 배·같은 슬롯이 최근 오래 기다렸을수록, 작은 피더선일수록 위험)" if F["small_ship_riskier"] and F["history_positive"] else "") + ". 이 이력 특징을 R-Delay 학습형 모듈에 넣었습니다.",
        f"- 선석 대기열은 단독으로 약했습니다. 정박지에서 기다린 배의 {_p(fa['anchored_with_free_berth'], 0)}(12시간 넘게 기다린 배만 보면 {_p(fa['long_wait_with_free_berth'], 0)})는 도착 순간 그 터미널에 빈 선석(학습 기간 선석 수 기준)이 있었는데도 기다렸습니다. 터미널은 선석을 먼저 온 순서가 아니라 선석 계획(창구)대로 배정하므로, 터미널 선석 계획(ETB)·선사 ETA가 연동되어야 대기열이 제 몫을 합니다. 이 자료 협약이 실증 단계의 핵심입니다.",
        f"- {_bss_sentence(S)}",
    ])


def model_md(S) -> str:
    s = S["sis"]
    fo = s.get("f_omega") or {}
    ko = {"wind_bsn_max6": "부산 풍속(6시간 최대)", "hs_geoje_max6": "거제 유의파고(6시간 최대)", "offday": "휴일", "ty_near500": "태풍 500km 이내"}
    coef = ", ".join(f"{ko.get(n, n)} {c:+.3f}" for n, c in zip(fo.get("features", []), fo.get("coef", [])))
    return "\n".join([
        "## 12. 실자료 적용 (부산신항 백테스트, `realdata/`)",
        "",
        "엔진(`docs/py/rdelay`)은 바꾸지 않고, 같은 `sis`·`stats` 함수를 장기 자료에 맞게 부르는 실자료판을 `realdata/`에 두었다.",
        "",
        "- **노드**: 해상 S(신항 정박지 대기)와 육상 L(배후 고속도로 콘존). 항공은 자료가 없어 뺐다.",
        "- **해상 관측**: x<sub>S</sub> = 대기 척수 / (대기 + 선석 체류 척수). H<sub>S</sub> ~ 베타-이항(분모 = 그 시각 체류 척수), Y<sub>S</sub>(2시간 신규 투묘) ~ 음이항.",
        "- **육상 관측**: 콘존별 기준속도(학습 기간 요일 구분·시간대 85분위)의 60% 미만을 혼잡으로 보고 H<sub>L</sub> ~ 베타-이항. 교통량 자료가 없어 ξ<sub>L</sub> = 1.",
        "- **물동량 보정** ξ<sub>S</sub> = 최근 24시간 총톤수 가중 도착량 / 최근 28일 평균(1절 정의를 실자료로).",
        f"- **정적 모수**: γ<sub>S</sub> = 1/평균 대기(학습 기간 {s['mean_wait_h']}시간), ε<sub>S</sub>는 학습 기간 신규 투묘율과 맞춤. β̄<sub>S</sub> = r·γ<sub>S</sub>와 결합 강도 κ를 학습 기간 입자필터 우도 격자로 골랐다: r = {s['beta_over_gamma']}, κ = {s['kappa_sea_land']}.",
        f"- **f<sub>ω</sub>**: 고정시차(6시간) 평활 E[z|y]를 레이블로 릿지(2회 반복, `train_ai.py`와 같은 방식). 계수(고정 척도로 맞춘 특징): {coef}. 검증 우도 +{s['valid_loglik_gain_f_omega']}.",
        "- **연속 필터**: 엔진의 `particle_filter`는 전체 경로를 메모리에 담으므로, 3.8년 자료는 한 번 흘려 보내는 필터(입자 512, Δt 0.5시간, 관측 2시간)로 돌리고 τ마다 필터 요약(x̂, ẑ, R̂<sub>d</sub>, P(R<sub>d</sub>>1))만 남긴다.",
        "- **선석 대기열(실자료판)**: 터미널(부두)별 서버 = 학습 기간 선석 이름 수, 서비스 = 학습 기간 실제 체류시간 경험분포, 대 있는 선박의 남은 체류 = 경과시간 조건부 표본, 순서 = 정박지 대기(도착순) → 예정 도착(도착순). 몬테카를로 400회로 대상 선박의 P(대기 > 12h).",
        "- **학습형 모듈(하이브리드)**: 로지스틱 회귀(표준화, L2, C는 검증 기간에서 리드별로 선택) — 대기열 확률, SIS 상태, 같은 선박의 이전 기항 이력, 같은 요일·시간대 슬롯의 최근 8주 장기 대기율, 선박 크기, 터미널 대기열·예정 도착, 기상·태풍·도로. 이력은 판단 시각 12시간 전까지 결과('대기 > 12시간')가 확정된 항차만 쓴다.",
        "",
        "결과와 해석은 [REPORT.md](REPORT.md#검증-실제-공개-자료-백테스트), 설계는 [realdata/PROTOCOL.md](realdata/PROTOCOL.md).",
    ])


def _replace_between(path: pathlib.Path, tag: str, body: str, anchor: str | None = None) -> bool:
    s = path.read_text(encoding="utf-8")
    start, end = f"<!-- {tag}:start -->", f"<!-- {tag}:end -->"
    block = f"{start}\n{body}\n{end}"
    if start in s and end in s:
        s = s[: s.index(start)] + block + s[s.index(end) + len(end):]
    elif anchor and anchor in s:
        i = s.index(anchor)
        s = s[:i] + block + "\n\n" + s[i:]
    else:
        return False
    path.write_text(s, encoding="utf-8")
    return True


def update_docs(S) -> dict:
    R = paths.ROOT
    return {
        "README": _replace_between(R / "README.md", "realdata-readme", readme_md(S), anchor="## 전체 개발 구조"),
        "REPORT": _replace_between(R / "REPORT.md", "realdata-report", report_md(S), anchor="## 핵심 수식"),
        "MODEL": _replace_between(R / "MODEL.md", "realdata-model", model_md(S), anchor="## 참고문헌"),
    }


# ── 발표 문안(presentation/, gitignore). Clarksons 숫자는 넣지 않고 비공개 파일을 가리킨다 ──
def presentation_md(S) -> None:
    h, tc, p, d = S["t2_24"], S["test_counts"], S["periods"], S["data"]
    F = facts(S)
    ab = S["ablation_posthoc"]["groups"]
    s = S["sis"]
    fa = S["free_at_arrival"]
    L24 = S["t2_lead"]["24"]
    by = d["by_year"]
    exc = ", ".join(f"{y}년 {v['excess_hours']:,}시간" for y, v in by.items())
    last_y = max(by)
    slides = f"""# 발표용 — 실자료 검증 슬라이드 문안 (10분 발표 중 2~3장)

숫자 출처: realdata/results/summary.json (생성 {S['generated']}, 커밋 {S['commit']}). 그림: presentation/*.png (2배 해상도).
시험 기간 {p['test'][0]}~{p['test'][1][:10]} · 신항 컨테이너선 {tc['voyages']:,}항차 · 12시간 초과 대기 {tc['long_waits']}척(기저율 {_p(tc['base_rate'])}).

---

## 슬라이드 A. "실제 부산신항 자료로 검증했습니다"
- 그림: `fig_alarm.png`
- 제목: **하루 전, 위험 상위 5% 선박만 골라도 — 무작위의 {h['top5']['lift']:.1f}배**
- 본문(3줄)
  - PORT-MIS 관제정보로 잰 신항 컨테이너선 {d['voyages']:,}항차, {d['period'][0][:4]}~{d['period'][1][:4]}
  - 도착 24시간 전 위험 상위 5% → 실제 장기 대기 선박의 {_p(h['top5']['recall'])} 포착, 정밀도 {_p(h['top5']['precision'])}
  - 기간·지표는 시험 기간을 보기 전에 정함(학습 2023~24 / 검증 2025 상반기 / 시험 2025-07~)
- 각주: 공개 실자료 후향 검증 · 상위 5%는 시험 기간 예측 분포 기준(미리 정한 문턱으로는 정밀도 {_p(h['valid_f1']['precision'])}, 재현율 {_p(h['valid_f1']['recall'])}) · PR-AUC {_f(h['pr_auc'])}(95% {_f(h['pr_auc_ci'][0])}~{_f(h['pr_auc_ci'][1])}, 무작위 {_f(tc['base_rate'])}) · 출처 해양수산부 PORT-MIS, 기상청, 한국도로공사
- 말할 것(30초): "12시간은 신항 터미널의 수출 반입 마감이 접안 12시간 전이라는 규정에서 왔습니다. 배가 정박지에서 12시간 넘게 기다리면 화주·운송사 계획이 흔들립니다. {_ym(_months(d['period'][0], d['period'][1]))}치 실제 기록으로, 모형을 만들 때 보지 않은 {_ym(_months(p['test'][0], p['test'][1]))}을 맞혀 봤습니다. 하루 전에 위험 상위 5%만 골라도 실제로 오래 기다린 배의 {_tenths(h['top5']['recall'], ("이", "가"))} 그 안에 있었습니다."

## 슬라이드 B. "예측은 어디서 오나 — 그리고 무엇이 더 필요한가"
- 그림: `fig_drivers.png`(요인 묶음 제거 실험)
- 제목: **같은 배·같은 항로의 이력이 핵심, 선석 계획이 다음 열쇠**
- 본문
  - 가장 강한 신호: {ab[0]['group']}, {ab[1]['group']}, {ab[2]['group']}{" — 같은 배·같은 슬롯이 최근 오래 기다렸을수록, 작은 피더선일수록 위험" if F['small_ship_riskier'] and F['history_positive'] else ""}
  - {"공개 자료만으로는 선석 대기열·번짐 지수가 더한 하루 전 예측력이 작음" if F['mech_small'] else "선석 대기열·번짐 지수도 일부 기여"} (하나씩 빼 보면 PR-AUC 변화: 선석 대기열 {_chg(F['mech_parts']['queue'])}, 번짐 지수 {_chg(F['mech_parts']['sis'])}){"; R-Delay 부품 없는 통계 GBM(" + _f(L24['S2_gbm']['pr_auc']) + ")도 R-Delay GBM(" + _f(L24['R3_gbm']['pr_auc']) + ")과 비슷하거나 높음" if F['s2gbm_ge_r3gbm'] else ""}
  - 정박지에서 기다린 배의 {_p(fa['anchored_with_free_berth'], 0)}(12시간 넘게 기다린 배는 {_p(fa['long_wait_with_free_berth'], 0)})는 도착 순간 그 터미널에 빈 선석이 있었는데도 기다림 → 배정은 순서가 아니라 선석 계획(ETB)대로 → **ETB·선사 ETA 연동 = 사업화 핵심 데이터 파트너십**
- 말할 것(30초): "솔직하게 말씀드리면, 감염병 모형 부분은 공개 자료만으로는 하루 전 예측을 거의 더하지 못했습니다. 이유도 분명합니다. 정박지에서 기다린 배의 {_tenths(fa['anchored_with_free_berth'], ("은", "는"))} 도착했을 때 그 터미널에 빈 선석이 있었는데도 기다렸습니다. 선석은 먼저 온 순서가 아니라 계획대로 배정되기 때문입니다. 터미널 선석 계획이 들어오면 대기열 모형이 그 계획을 따라 미래를 그릴 수 있습니다."

## 슬라이드 C. "실제 사례" (선택)
- 그림: `fig_case_peak.png`(또는 `fig_case_typhoon.png`, 놓친 사례 `fig_case_miss.png`)
- 제목: **대기가 몰린 2주 — 경보와 번짐 지수**
- 본문
  - 대기 척수가 늘며 R-Delay 경보가 경보선을 넘음(경보선 = 시험 기간 예측 상위 10%)
  - 번짐 지수 R<sub>d</sub> 중앙값 {_f(s['rd_quantiles']['0.5'], 2)} — 신항 대기는 늘 임계 근처(물량이 조금만 늘어도 번짐)
  - 놓친 사례도 함께 공개
- 말할 것(20초): "R<sub>d</sub>는 미래를 맞히는 숫자라기보다 '지금 번지는 중'을 알려 주는 계기판입니다. 실제 자료에 맞추니 신항 대기는 늘 1 근처에서 움직였습니다."

## 슬라이드 D. 사업 가치 숫자 (선택, 사업화 장표에 한 줄)
- 공개 자료: 신항 12시간 초과분 대기 시간 합계 — {exc}({last_y}년은 자료 끝 {d['period'][1]}까지)
- 선박 쪽 비용(용선료 기준)은 Clarksons 자료로 계산했습니다 → `비공개_Clarksons_점검.md` 참고. 발표에 쓸지는 이용 조건을 확인한 뒤 정하고, 쓸 때는 요청서 6절 인용 문구를 붙입니다.
- 화물·트럭 쪽 비용은 합성 가정(시간당 3만 원)이라 '가정'으로 표시합니다.
"""
    post = S["t3_posthoc_top10"]
    qa = f"""# 예상 질문과 답 — 실자료 검증 (근거 숫자 포함)

숫자 출처: realdata/results/summary.json · compare.md (Clarksons 관련은 비공개_Clarksons_점검.md)

1. **실제 데이터로 검증했나요?**
   네. 해양수산부 PORT-MIS 관제정보로 부산신항 컨테이너선 {d['voyages']:,}항차({d['period'][0]}~{d['period'][1]})의 정박지 대기를 재고, 학습 2023~2024 / 검증 2025 상반기 / 시험 {p['test'][0]}~{p['test'][1][:10]}로 나눴습니다. 기간·목표·지표·경보 기준은 시험 기간을 보기 전에 PROTOCOL.md에 정했습니다. 시험 뒤 누설을 더 엄격하게 고친 1건이 있어 시험 기간을 두 번 계산했고, 두 결과를 모두 기록했습니다.
2. **기준선보다 얼마나 낫나요?**
   도착 24시간 전 PR-AUC는 {_f(h['pr_auc'])}(95% {_f(h['pr_auc_ci'][0])}~{_f(h['pr_auc_ci'][1])})이고, 터미널별 평균({_f(L24['S0']['pr_auc'])})과 무작위({_f(tc['base_rate'])})보다 높습니다. 위험 상위 5%의 정밀도는 {_p(h['top5']['precision'])}(무작위의 {h['top5']['lift']:.1f}배), 재현율은 {_p(h['top5']['recall'])}입니다(상위 5%는 시험 기간 예측 분포 기준; 미리 정한 문턱으로는 정밀도 {_p(h['valid_f1']['precision'])}, 재현율 {_p(h['valid_f1']['recall'])}). Brier 기술점수는 {h['bss']:+.3f}(95% {h['bss_ci'][0]:+.3f}~{h['bss_ci'][1]:+.3f})입니다.
3. **감염병 모형(R<sub>d</sub>)은 실제로 맞았나요?**
   실자료에 맞추니 R<sub>d</sub>가 임계 근처에서 움직였습니다(중앙값 {_f(s['rd_quantiles']['0.5'], 2)}, 1을 넘는 시간 {_p(s['p_rd_gt1_share'], 0)}). 다만 P(R<sub>d</sub>>1) 하나로 24시간 뒤를 미리 맞히는 힘은 {"기저율 수준" if F['sis_alone_at_base'] else "기저율보다 조금 나은 수준"}이었습니다(PR-AUC {_f(S['t1']['SIS_p1']['pr_auc'])} vs 기저율 {_f(S['t1_base_rate'])}). 그래서 R<sub>d</sub>는 '지금 번지는 중'을 확인하는 계기판으로 쓰고, 하루 전 예측은 이력·대기열과 결합한 하이브리드가 맡습니다.
4. **선석 대기열 모형은 왜 약했나요?**
   터미널은 먼저 온 순서가 아니라 선석 계획(창구)대로 배정합니다. 정박지에서 기다린 배의 {_p(fa['anchored_with_free_berth'], 0)}(12시간 넘게 기다린 배만 보면 {_p(fa['long_wait_with_free_berth'], 0)})는 도착 순간 그 터미널에 빈 선석(학습 기간 선석 수 기준)이 있었는데도 기다렸습니다. 거꾸로, 정박지를 거치지 않고 바로 댄 배는 {_p(fa['direct_with_free_berth'], 0)}가 빈 선석이 있었습니다(라벨 정의상 당연한 쪽이라 도착 순간 점수는 주 결과로 쓰지 않습니다). 공개 자료에는 그 계획(ETB)이 없으니, 실증에서는 터미널 선석 계획·선사 ETA를 연동해 대기열이 계획을 따라 미래를 그리게 합니다.
5. **무엇이 예측을 만들었나요?**
   요인 묶음을 하나씩 빼 보면 PR-AUC가 {ab[0]['group']}에서 {_chg(ab[0]['drop'])}, {ab[1]['group']}에서 {_chg(ab[1]['drop'])}, {ab[2]['group']}에서 {_chg(ab[2]['drop'])} 순으로 가장 많이 떨어졌습니다.{" 작은 피더선일수록, 그리고 같은 배가 지난번에도 오래 기다렸을수록 위험합니다." if F['small_ship_riskier'] and F['history_positive'] else ""}
6. **데이터 누설은 없나요?**
   판단 시각까지 알 수 있는 자료만 씁니다. 구간 집계는 [τ−w, τ), 태풍은 분석 3시간 뒤부터, 이력은 결과가 확정된 항차만 씁니다. 원래 2시간 집계 파일이 앞쪽 구간을 세고 있어 새로 만들었습니다. 컷오프 뒤 자료를 지워도 특징이 같은지 보는 누설 테스트를 격자·선박 표·대기열·T1 예정 도착 합계에 둡니다(시험 뒤 고친 누설을 되돌리면 이 테스트가 실패하는 것도 확인). 시험 뒤 더 엄격하게 고친 1건(이력 특징이 '168시간 초과 제외' 표시를 쓰던 것, 4척)도 프로토콜에 적었습니다.
7. **도착 시각을 미리 안다고 가정한 건 공정한가요?**
   정기선은 선석 창구와 ETA가 며칠 전에 정해지지만, 실제 도착 시각을 그대로 쓴 것은 낙관적 가정이라 한계로 적었습니다. 공개 운항정보에 신고 시각·예정 시각이 없어서입니다. 실증에서는 선사 ETA 피드로 바꿉니다.
8. **항계 밖에서 기다린 시간은요?**
   관제정보에는 입항 신고 전 바다 위 대기가 잡히지 않아 대기를 과소추정할 수 있습니다(한계로 공개). 외부 AIS 지표와의 비교는 비공개 파일에 있습니다.
9. **실시간으로 돌릴 수 있나요?**
   관제정보·기상청·도로공사 모두 API가 있어 2시간 주기로 갱신할 수 있습니다. 전체 백테스트 계산이 노트북에서 몇 분이고, 실시간은 최근 창만 다시 계산하면 됩니다.
10. **돈으로 얼마나 큰 문제인가요?**
    신항에서 12시간을 넘긴 대기 시간만 {exc}({last_y}년은 자료 끝까지)입니다(공개 자료). 선박 쪽 비용(용선료 기준)은 비공개 파일 숫자를 이용 조건 확인 뒤 인용하고, 화물 쪽(공장 라인·항공 마감) 손실은 별도입니다.
11. **다른 항만에도 쓸 수 있나요?**
    PORT-MIS는 전국 항만이 같은 형식이라(항만청 코드만 바꿈) 울산·광양·인천으로 같은 절차를 옮길 수 있습니다. 모형은 항만별로 다시 맞춥니다.
12. **GBM이 더 좋아 보이는데 왜 로지스틱이 최종인가요?**
    시험 전에 최종 모형을 하이브리드 로지스틱으로 정했고, 시험 결과를 보고 바꾸지 않는 것이 원칙이라 그대로 두었습니다. 대신 모두 공개했습니다: 24시간 전 R-Delay GBM {_f(L24['R3_gbm']['pr_auc'])}, R-Delay 부품 없는 통계 GBM {_f(L24['S2_gbm']['pr_auc'])}. 하루 전 예측력은 R-Delay 기계론이 아니라 이력 특징에서 나온다는 결론과 같은 방향입니다.
13. **사건(혼잡 에피소드)을 몇 시간 전에 알렸나요?**
    사후 분석(경보 상위 10%)에서 하이브리드는 에피소드 {post['R3_logit']['episodes']}개 중 {post['R3_logit']['detected']}개를 중앙값 {post['R3_logit']['lead_median_h']}시간 전에 알렸습니다. 다만 시간대·요일 평균도 {post['S0']['detected']}개를 '탐지'할 만큼 이 지표는 경보가 자주 바뀌는 쪽에 유리해, 비교는 선박 단위 지표로 합니다.
"""
    pr = paths.PRESENTATION
    pr.mkdir(parents=True, exist_ok=True)
    (pr / "slides_backtest.md").write_text(slides, encoding="utf-8")
    (pr / "qa_backtest.md").write_text(qa, encoding="utf-8")


def build_all():
    _font()
    res, cal, sens, p1, g = _load()
    S = summary(res, cal, sens, p1, g)
    (paths.RESULTS / "summary.json").write_text(json.dumps(S, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    (paths.RESULTS / "compare.md").write_text(compare_md(S), encoding="utf-8")
    fig_leads(S)
    fig_alarm(S)
    fig_reliability(S)
    fig_drivers(S)
    cases, thr = pick_cases(res, p1)
    cases_data = {}
    for name, c in cases.items():
        x = case_series(c, p1, g)
        fig_case(name, c, x, thr)
        cases_data[name] = {"title": c["title"], "start": str(c["start"]), "end": str(c["end"]), "threshold": _r(thr),
                            "t": [t.strftime("%Y-%m-%dT%H:%M") for t in x.index],
                            **{k: [None if pd.isna(v_) else _r(v_, 3) for v_ in x[k]] for k in ("n_wait", "pos_arr", "p_r3", "rd", "hs", "wind")}}
    out = paths.ROOT / "docs" / "data" / "backtest.json"
    out.write_text(json.dumps(web_json(S, cases_data), ensure_ascii=False, separators=(",", ":"), default=str), encoding="utf-8")
    docs = update_docs(S)
    presentation_md(S)
    print(f"summary → {paths.RESULTS / 'summary.json'} · web → {out} ({out.stat().st_size / 1024:.0f} KB) · figs → {paths.REPORTS} · docs {docs}")
    return S
