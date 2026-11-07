"""T2(선박 단위)·T1(시스템) 백테스트. 검증 기간에서 고르고, 학습+검증으로 다시 맞춘 뒤 시험 기간을 한 번 계산한다."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import evaluate as ev
from . import models as M
from . import paths

LEADS = (24, 12, 6, 2, 0)
C_GRID = (0.01, 0.1, 1.0)


def _platt(train_x, train_y, x):
    from sklearn.linear_model import LogisticRegression
    m = LogisticRegression(C=100.0, max_iter=1000).fit(np.asarray(train_x).reshape(-1, 1), train_y)
    return m.predict_proba(np.asarray(x).reshape(-1, 1))[:, 1]


def t2_models(cols_sis: list[str] | None = None):
    s2 = M.T2_S2
    r3 = M.T2_S2 + M.T2_R1 + (cols_sis or [])
    return {
        "S0": lambda: M.PierClim(),
        "S1": lambda: M.Logit(M.T2_S1, C=1.0),
        "S2_logit": lambda C=0.1: M.Logit(s2, C=C),
        "S2_gbm": lambda: M.GBM(s2),
        "R3_logit": lambda C=0.1: M.Logit(r3, C=C),
        "R3_gbm": lambda: M.GBM(r3),
    }


def fit_predict_t2(tr: pd.DataFrame, te: pd.DataFrame, choice: dict, cols_sis=None) -> pd.DataFrame:
    """한 리드 L의 학습(tr)→예측(te). choice: 로지스틱 C."""
    mk = t2_models(cols_sis)
    y = tr["pos12"].astype(int).to_numpy()
    out = pd.DataFrame(index=te.index)
    out["S0"] = mk["S0"]().fit(tr, y).predict(te)
    out["S1"] = mk["S1"]().fit(tr, y).predict(te)
    out["S2_logit"] = mk["S2_logit"](choice.get("S2_logit", 0.1)).fit(tr, y).predict(te)
    out["S2_gbm"] = mk["S2_gbm"]().fit(tr, y).predict(te)
    out["R1"] = te["r1_p"].fillna(0.0).to_numpy()
    out["R2"] = _platt(tr["logit_r1"], y, te["logit_r1"])
    out["R3_logit"] = mk["R3_logit"](choice.get("R3_logit", 0.1)).fit(tr, y).predict(te)
    out["R3_gbm"] = mk["R3_gbm"]().fit(tr, y).predict(te)
    return out


def t2_validate(d: pd.DataFrame, cols_sis=None) -> tuple[dict, dict]:
    d = d[~d["excluded"]]
    res, choice = {}, {}
    for L in LEADS:
        x = d[d["L"] == L]
        tr = ev.split(x, "arrival_t", ev.PERIODS["train"])
        va = ev.split(x, "arrival_t", ev.PERIODS["valid"])
        y_tr, y_va = tr["pos12"].astype(int).to_numpy(), va["pos12"].astype(int).to_numpy()
        ch = {}
        for name in ("S2_logit", "R3_logit"):
            best, bestC = -1, 0.1
            for C in C_GRID:
                cols = M.T2_S2 if name == "S2_logit" else M.T2_S2 + M.T2_R1 + (cols_sis or [])
                p = M.Logit(cols, C=C).fit(tr, y_tr).predict(va)
                ap = ev.metrics(y_va, p)["pr_auc"]
                if ap > best:
                    best, bestC = ap, C
            ch[name] = bestC
        choice[L] = ch
        pr = fit_predict_t2(tr, va, ch, cols_sis)
        res[L] = {k: ev.metrics(y_va, pr[k], pr["S0"]) for k in pr.columns}
    return res, choice


def t1_validate(g: pd.DataFrame, cols_sis=None) -> tuple[dict, dict]:
    tr = ev.split(g, "tau", ev.PERIODS["train"])
    va = ev.split(g, "tau", ev.PERIODS["valid"])
    y_tr, y_va = tr["y24"].to_numpy(), va["y24"].to_numpy()
    preds = fit_predict_t1(tr, va, {"S2_logit": 0.1, "R3_logit": 0.1}, cols_sis)
    choice = {}
    for name in ("S2_logit", "R3_logit"):
        best, bestC = -1, 0.1
        for C in C_GRID:
            cols = M.T1_S2 if name == "S2_logit" else M.T1_S2 + M.T1_R1 + (cols_sis or [])
            p = M.Logit(cols, C=C).fit(tr, y_tr).predict(va)
            ap = ev.metrics(y_va, p)["pr_auc"]
            if ap > best:
                best, bestC = ap, C
        choice[name] = bestC
    preds = fit_predict_t1(tr, va, choice, cols_sis)
    return {k: ev.metrics(y_va, preds[k], preds["S0"]) for k in preds.columns}, choice


def fit_predict_t1(tr, te, choice, cols_sis=None, extra_scores: dict | None = None) -> pd.DataFrame:
    y = tr["y24"].to_numpy()
    out = pd.DataFrame(index=te.index)
    out["S0"] = M.HourDowClim().fit(tr, y).predict(te)
    out["S1"] = M.Logit(M.T1_S1).fit(tr, y).predict(te)
    out["S2_logit"] = M.Logit(M.T1_S2, C=choice.get("S2_logit", 0.1)).fit(tr, y).predict(te)
    out["S2_gbm"] = M.GBM(M.T1_S2).fit(tr, y).predict(te)
    out["R1"] = te["r1_sys_p"].to_numpy()
    out["R2"] = _platt(tr["logit_r1_sys"], y, te["logit_r1_sys"])
    cols = M.T1_S2 + M.T1_R1 + (cols_sis or [])
    out["R3_logit"] = M.Logit(cols, C=choice.get("R3_logit", 0.1)).fit(tr, y).predict(te)
    out["R3_gbm"] = M.GBM(cols).fit(tr, y).predict(te)
    for k, col in (extra_scores or {}).items():
        out[k] = _platt(tr[col], y, te[col])
    return out


def save(name: str, obj) -> None:
    paths.ensure_dirs()
    paths.write_text(paths.RESULTS / name, json.dumps(obj, ensure_ascii=False, indent=1, default=float))


def _alarm_rate_stats(y, p, rate):
    thr = float(np.quantile(p, 1 - rate))
    return ev.alarm_stats(y, p, thr)


def final_test(d: pd.DataFrame, G: pd.DataFrame, data_end, t2_choice: dict, t1_choice: dict, n_boot: int = 1000) -> dict:
    """학습+검증으로 다시 맞춰 시험 기간을 한 번 계산한다. 예측값도 돌려준다(사례 그림용)."""
    test = ev.test_period(data_end)
    trva = ("2023-01-30", "2025-07-01")
    out = {"test_period": test, "t2": {}, "t1": {}}
    preds_t2 = []
    d = d[~d["excluded"]]
    for L in LEADS:
        x = d[d["L"] == L]
        tr, va = ev.split(x, "arrival_t", ev.PERIODS["train"]), ev.split(x, "arrival_t", ev.PERIODS["valid"])
        tv, te = ev.split(x, "arrival_t", trva), ev.split(x, "arrival_t", test)
        ch = t2_choice[L]
        pv = fit_predict_t2(tr, va, ch, M.SIS)
        pt = fit_predict_t2(tv, te, ch, M.SIS)
        y = te["pos12"].astype(int).to_numpy()
        res = {}
        for k in pt.columns:
            m = ev.metrics(y, pt[k], pt["S0"])
            thr = ev.best_f1_threshold(va["pos12"].astype(int).to_numpy(), pv[k])
            m["alarm_valid_f1"] = ev.alarm_stats(y, pt[k], thr)
            m["alarm_top5"] = _alarm_rate_stats(y, pt[k].to_numpy(), 0.05)
            m["alarm_top10"] = _alarm_rate_stats(y, pt[k].to_numpy(), 0.10)
            if k in ("S0", "S2_logit", "R1", "R3_logit", "R3_gbm", "S2_gbm"):
                m["pr_auc_ci"] = ev.block_bootstrap(y, pt[k], te["arrival_t"], "pr_auc", n_boot)
                m["roc_auc_ci"] = ev.block_bootstrap(y, pt[k], te["arrival_t"], "roc_auc", n_boot)
                m["bss_ci"] = ev.block_bootstrap(y, pt[k], te["arrival_t"], "bss", n_boot, p_ref=pt["S0"])
            if k in ("R3_logit", "S2_logit") and L in (24, 6, 0):
                m["reliability"] = ev.reliability(y, pt[k])
            res[k] = m
        out["t2"][L] = res
        preds_t2.append(pd.concat([te[["key", "pier", "arrival_t", "L", "pos12", "wait_h"]], pt], axis=1))
    # T1
    tr, va = ev.split(G, "tau", ev.PERIODS["train"]), ev.split(G, "tau", ev.PERIODS["valid"])
    tv, te = ev.split(G, "tau", trva), ev.split(G, "tau", test)
    extra = {"SIS_p1": "logit_sis_p1", "SIS_x": "logit_sis_x"}
    pv = fit_predict_t1(tr, va, t1_choice, M.SIS, extra)
    pt = fit_predict_t1(tv, te, t1_choice, M.SIS, extra)
    y = te["y24"].to_numpy()
    eps = ev.episodes(d.loc[(d["L"] == 0) & d["pos12"], "arrival_t"].to_numpy())
    eps_test = [e for e in eps if pd.Timestamp(test[0]) <= e[0] < pd.Timestamp(test[1])]
    for k in pt.columns:
        m = ev.metrics(y, pt[k], pt["S0"])
        thr = ev.best_f1_threshold(va["y24"].to_numpy(), pv[k])
        m["alarm_valid_f1"] = ev.alarm_stats(y, pt[k], thr)
        if k in ("S0", "S2_logit", "S2_gbm", "R1", "R3_logit", "R3_gbm", "SIS_p1"):
            m["pr_auc_ci"] = ev.block_bootstrap(y, pt[k], te["tau"], "pr_auc", n_boot)
            m["bss_ci"] = ev.block_bootstrap(y, pt[k], te["tau"], "bss", n_boot, p_ref=pt["S0"])
        m["events"] = ev.event_stats(pd.DatetimeIndex(te["tau"]), pt[k].to_numpy() >= thr, eps_test)
        out["t1"][k] = m
    preds_t1 = pd.concat([te[["tau", "y24", "npos24", "n_wait", "max_wait_h", "sis_x", "sis_rd", "sis_p1", "xi_sea",
                              "wind_bsn_max6", "hs_geoje_max6", "road_rel_med", "ty_dist_km"]], pt], axis=1)
    # 소분석: 태풍 근접 기간, 2026년 6~9월
    sub = {}
    tyo = te["ty_near500"].to_numpy() > 0
    sub["t1_typhoon_tau"] = int(tyo.sum())
    summer = (pd.to_datetime(te["tau"]) >= "2026-06-01") & (pd.to_datetime(te["tau"]) < "2026-10-01")
    sub["t1_summer2026"] = {k: ev.metrics(y[summer.to_numpy()], pt[k].to_numpy()[summer.to_numpy()],
                                          pt["S0"].to_numpy()[summer.to_numpy()]) for k in ("S0", "S2_logit", "R3_logit", "SIS_p1")}
    out["subgroups"] = sub
    out["episodes_test"] = len(eps_test)
    return out, pd.concat(preds_t2, ignore_index=True), preds_t1


def sensitivity_cap(d: pd.DataFrame, data_end, t2_choice: dict, cap_h: float = 336.0) -> dict:
    """라벨 상한 민감도(PROTOCOL 1절): 특징은 168시간판 그대로 두고 정답만 cap_h 기준으로 다시 정해
    24시간 전 하이브리드(R3_logit)와 기후값(S0)을 학습+검증으로 다시 맞춰 시험 기간을 계산한다."""
    x = d[d["L"] == 24].copy()
    x["excluded"] = x["wait_h"] > cap_h
    x["pos12"] = (x["wait_h"] > 12.0) & ~x["excluded"]
    x = x[~x["excluded"]]
    test = ev.test_period(data_end)
    tv, te = ev.split(x, "arrival_t", ("2023-01-30", "2025-07-01")), ev.split(x, "arrival_t", test)
    y_tv, y = tv["pos12"].astype(int).to_numpy(), te["pos12"].astype(int).to_numpy()
    p0 = M.PierClim().fit(tv, y_tv).predict(te)
    p3 = M.Logit(M.T2_S2 + M.T2_R1 + M.SIS, C=t2_choice[24]["R3_logit"]).fit(tv, y_tv).predict(te)
    m3, m0 = ev.metrics(y, p3, p0), ev.metrics(y, p0)
    return {"cap_h": cap_h, "excluded": int((d.loc[d["L"] == 24, "wait_h"] > cap_h).sum()),
            "t2_24_r3_logit": {"pr_auc": m3["pr_auc"], "roc_auc": m3["roc_auc"], "bss": m3["bss"], "n": m3["n"], "pos": m3["pos"]},
            "t2_24_s0": {"pr_auc": m0["pr_auc"]}}
