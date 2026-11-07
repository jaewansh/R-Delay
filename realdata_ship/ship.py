"""선박 단위(T2) 표: 항차마다 도착 L시간 전 판단 시각 τ = 도착 − L의 특징과 정답.

가정: 대상 선박이 갈 부두(터미널)와 도착 시각은 τ에 안다(정기선 선석 계획·ETA를 실제 값으로 대체 → 낙관적).
그 밖의 특징은 τ까지 알 수 있는 것만 쓴다(grid.py의 누설 방지 원칙과 같다).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import grid

LEADS = (24, 12, 6, 2, 0)
PIER_RE = r"신항 (\d부두|다목적)"
SLOT_DAYS = 56
HOUR_BIN = 4


def pier_table(train_end: str = "2025-01-01"):
    """부두별 선석 수(학습 기간에 쓰인 선석 이름 수)와 학습 기간 체류시간 표본."""
    st = grid.berth_stays()
    tr = st[(st["start"] < pd.Timestamp(train_end)) & st["end"].notna()].copy()
    tr["dur_h"] = (tr["end"] - tr["start"]).dt.total_seconds() / 3600
    tr = tr[(tr["dur_h"] > 0.5) & (tr["dur_h"] <= 120)]
    cap = st[st["start"] < pd.Timestamp(train_end)].groupby("pier")["fac"].nunique().to_dict()
    durs = {p: np.sort(g["dur_h"].to_numpy()) for p, g in tr.groupby("pier")}
    return cap, durs


def _voyages():
    v = grid.voyages()
    v["pier"] = v["berth_facility"].str.extract(PIER_RE, expand=False)
    v = v[v["pier"].notna()].copy()
    v["key"] = v["clsgn"].astype(str) + "|" + v["etryptYear"].astype(str) + "|" + v["etryptCo"].astype(str)
    return v.reset_index(drop=True)


def _occupancy(st: pd.DataFrame, pier: str, t: np.ndarray) -> np.ndarray:
    s = st[st["pier"] == pier]
    ss = np.sort(s["start"].to_numpy())
    ee = np.sort(s["end"].fillna(pd.Timestamp("2100-01-01")).to_numpy())
    return np.searchsorted(ss, t, side="right") - np.searchsorted(ee, t, side="right")


def build(leads=LEADS, train_end: str = "2025-01-01", cap_h: float = grid.CAP_H) -> pd.DataFrame:
    v = _voyages()
    st = grid.berth_stays()
    cap, _ = pier_table(train_end)
    hc = grid.hourly_context(train_end)
    rows = []
    for L in leads:
        d = v[["key", "clsgn", "pier", "arrival_t", "berth_t", "wait_h", "gt", "anchored", "excluded", "pos12"]].copy()
        d["L"] = L
        d["tau"] = d["arrival_t"] - pd.Timedelta(hours=L) - (pd.Timedelta(minutes=1) if L == 0 else pd.Timedelta(0))
        rows.append(d)
    d = pd.concat(rows, ignore_index=True)
    tau = d["tau"].to_numpy()
    d["cap"] = d["pier"].map(cap).astype(float)
    d["occ"] = np.nan
    d["queue"] = 0.0
    d["sched_ahead"] = 0.0
    an = v[v["anchored"]]
    for p in d["pier"].unique():
        m = (d["pier"] == p).to_numpy()
        d.loc[m, "occ"] = _occupancy(st, p, tau[m])
        a = an[an["pier"] == p]
        aa, bb = a["arrival_t"].to_numpy(), a["berth_t"].to_numpy()
        tt = tau[m]
        live = (aa[None, :] <= tt[:, None]) & (bb[None, :] > tt[:, None]) & \
               ((tt[:, None] - aa[None, :]) <= np.timedelta64(int(cap_h * 3600), "s"))
        d.loc[m, "queue"] = live.sum(axis=1)
        arr = np.sort(v.loc[v["pier"] == p, "arrival_t"].to_numpy())
        ta = d.loc[m, "arrival_t"].to_numpy()
        d.loc[m, "sched_ahead"] = np.searchsorted(arr, ta, side="left") - np.searchsorted(arr, tt, side="right")
    d["free"] = d["cap"] - d["occ"]
    # 신항 전체 대기 상태(τ 시점)
    a_all, b_all = an["arrival_t"].to_numpy(), an["berth_t"].to_numpy()
    age = (tau[:, None] - a_all[None, :]) / np.timedelta64(1, "h")
    live = (a_all[None, :] <= tau[:, None]) & (b_all[None, :] > tau[:, None]) & (age <= cap_h)
    d["n_wait_all"] = live.sum(axis=1).astype(float)
    d["max_wait_all"] = np.where(live, age, 0).max(axis=1)
    # 이력 특징: τ - 12h 이전에 도착한 항차는 결과가 확정되어 있다
    resolved_by = tau - np.timedelta64(12, "h")
    # 이력은 모든 항차로 만든다. '12시간 초과'는 도착 12시간 뒤면 확정되지만 '168시간 초과 제외'는 그때 알 수 없다.
    vv = v.copy()
    vv["hist_pos"] = vv["wait_h"] > grid.WAIT_H
    vv["dow"] = vv["arrival_t"].dt.day_of_week
    vv["hb"] = vv["arrival_t"].dt.hour // HOUR_BIN
    d["arr_dow"] = d["arrival_t"].dt.day_of_week
    d["arr_hb"] = d["arrival_t"].dt.hour // HOUR_BIN
    d["slot_n"] = 0.0
    d["slot_pos"] = 0.0
    for (p, dw, hb), g in vv.groupby(["pier", "dow", "hb"]):
        m = ((d["pier"] == p) & (d["arr_dow"] == dw) & (d["arr_hb"] == hb)).to_numpy()
        if not m.any():
            continue
        t = np.sort(g["arrival_t"].to_numpy())
        tp = np.sort(g.loc[g["hist_pos"], "arrival_t"].to_numpy())
        hi = resolved_by[m]
        lo = hi - np.timedelta64(SLOT_DAYS, "D")
        d.loc[m, "slot_n"] = np.searchsorted(t, hi, side="right") - np.searchsorted(t, lo, side="right")
        d.loc[m, "slot_pos"] = np.searchsorted(tp, hi, side="right") - np.searchsorted(tp, lo, side="right")
    pier_rate = v[(v["arrival_t"] < pd.Timestamp(train_end)) & ~v["excluded"]].groupby("pier")["pos12"].mean()
    prior = d["pier"].map(pier_rate).fillna(pier_rate.mean())
    d["slot_rate"] = (d["slot_pos"] + 2 * prior) / (d["slot_n"] + 2)
    # 같은 선박(호출부호)의 직전 항차
    d["prev_pos"] = np.nan
    d["prev_n180"] = 0.0
    for cs, g in vv.groupby("clsgn"):
        m = (d["clsgn"] == cs).to_numpy()
        if not m.any():
            continue
        t = g["arrival_t"].to_numpy()
        order = np.argsort(t)
        t, pos = t[order], g["hist_pos"].to_numpy()[order]
        hi = resolved_by[m]
        idx = np.searchsorted(t, hi, side="right") - 1
        d.loc[m, "prev_pos"] = np.where(idx >= 0, pos[np.clip(idx, 0, None)].astype(float), np.nan)
        tp = t[pos]
        d.loc[m, "prev_n180"] = np.searchsorted(tp, hi, side="right") - np.searchsorted(tp, hi - np.timedelta64(180, "D"), side="right")
    d["prev_known"] = d["prev_pos"].notna().astype(float)
    d["prev_pos"] = d["prev_pos"].fillna(0.0)
    # 신항 전체 최근 7일 장기 대기 수(확정된 것만)
    tp_all = np.sort(vv.loc[vv["hist_pos"], "arrival_t"].to_numpy())
    d["recent7_pos"] = (np.searchsorted(tp_all, resolved_by, side="right")
                        - np.searchsorted(tp_all, resolved_by - np.timedelta64(7, "D"), side="right")).astype(float)
    # 도착 시각 달력, τ 시점 기상·태풍·도로
    import holidays
    kr = holidays.KR(years=sorted(set(d["arrival_t"].dt.year)))
    d["arr_offday"] = ((d["arr_dow"] >= 5) | d["arrival_t"].dt.date.map(lambda x: x in kr)).astype(float)
    d["arr_hour"] = d["arrival_t"].dt.hour
    d["arr_h_sin"] = np.sin(2 * np.pi * d["arr_hour"] / 24)
    d["arr_h_cos"] = np.cos(2 * np.pi * d["arr_hour"] / 24)
    ctx = hc.reindex(d["tau"].dt.floor("h")).reset_index(drop=True)
    for c in ("wind_bsn", "wind_bsn_max6", "hs_geoje", "hs_geoje_max6", "gust_geoje_max6", "wind_cw_max6",
              "rain_bsn_6h", "ty_dist_km", "ty_near500", "road_cong_frac", "road_rel_med"):
        d[c] = ctx[c].to_numpy()
    d["log_gt"] = np.log1p(d["gt"].fillna(d["gt"].median()))
    return d
