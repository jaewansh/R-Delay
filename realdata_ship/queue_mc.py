"""R-Delay 선석 대기열의 실자료판: 부두(터미널)별 꼬리표 선박 몬테카를로.

엔진의 queue.tagged_ship과 같은 생각(현재 대기열 + 선석 서비스로 대상 선박의 작업 시작 시각을 구함)을
실자료에 맞게 바꿨다.
- 서버 = 그 부두의 선석 수(학습 기간에 쓰인 선석 이름 수). τ에 그보다 많이 대 있으면 그 수를 쓴다.
- 서비스 시간 = 학습 기간 그 부두의 실제 체류시간 분포(지수 근사 대신 경험분포).
- 대 있는 선박의 남은 체류시간 = 경과시간 조건부 표본(D | D > 경과) − 경과.
- 순서 = 정박지 대기 선박(도착순) → τ 뒤 예정 도착(도착순). 실제 터미널은 선석 계획 순서를 따르므로 근사다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import grid, ship

H = np.timedelta64(1, "h")


class PierSim:
    def __init__(self, train_end: str = "2025-01-01", samples: int = 400, seed: int = 20261108, cap_h: float = grid.CAP_H):
        self.S = samples
        self.rng = np.random.default_rng(seed)
        self.cap_h = cap_h
        self.cap, self.durs = ship.pier_table(train_end)
        st = grid.berth_stays()
        v = ship._voyages()
        self.p = {}
        for pier in self.cap:
            s = st[st["pier"] == pier].sort_values("start")
            a = v[(v["pier"] == pier) & v["anchored"]].sort_values("arrival_t")
            arr = np.sort(v.loc[v["pier"] == pier, "arrival_t"].to_numpy())
            self.p[pier] = {
                "s_start": s["start"].to_numpy(), "s_end": s["end"].fillna(pd.Timestamp("2100-01-01")).to_numpy(),
                "a_arr": a["arrival_t"].to_numpy(), "a_berth": a["berth_t"].to_numpy(), "arr": arr,
            }

    def _residual(self, D: np.ndarray, elapsed: float) -> np.ndarray:
        i0 = np.searchsorted(D, elapsed, side="right")
        if i0 >= len(D):
            return self.rng.exponential(1.0, self.S)
        return D[self.rng.integers(i0, len(D), self.S)] - elapsed

    def simulate(self, pier: str, tau: np.datetime64, t_end: np.datetime64, include_end: bool = True):
        """τ 뒤 (τ, t_end] 예정 도착 선박들의 대기시간 표본 (S, k)과 도착 시각(시간, τ 기준)."""
        P = self.p[pier]
        D = self.durs[pier]
        occ = (P["s_start"] <= tau) & (P["s_end"] > tau)
        elapsed = (tau - P["s_start"][occ]) / H
        c = max(int(self.cap[pier]), int(occ.sum()))
        free = np.zeros((self.S, c))
        for i, e in enumerate(elapsed):
            free[:, i] = self._residual(D, float(e))
        q = (P["a_arr"] <= tau) & (P["a_berth"] > tau) & ((tau - P["a_arr"]) / H <= self.cap_h)
        rows = np.arange(self.S)
        for _ in range(int(q.sum())):           # 대기 중인 선박은 도착순으로 먼저 선석을 받는다
            j = free.argmin(axis=1)
            start = free[rows, j]
            free[rows, j] = start + D[self.rng.integers(0, len(D), self.S)]
        arr = P["arr"]
        lo = np.searchsorted(arr, tau, side="right")
        hi = np.searchsorted(arr, t_end, side="right" if include_end else "left")
        t_arr = (arr[lo:hi] - tau) / H
        waits = np.zeros((self.S, len(t_arr)))
        for k, ta in enumerate(t_arr):
            j = free.argmin(axis=1)
            start = np.maximum(ta, free[rows, j])
            waits[:, k] = start - ta
            free[rows, j] = start + D[self.rng.integers(0, len(D), self.S)]
        return waits, t_arr


def ship_probs(sim: PierSim, d: pd.DataFrame, thr_h: float = grid.WAIT_H) -> pd.DataFrame:
    """T2: 각 행(항차, L)의 P(대기 > 12h)와 기대 대기."""
    p12 = np.full(len(d), np.nan)
    ew = np.full(len(d), np.nan)
    piers, taus, tas = d["pier"].to_numpy(), d["tau"].to_numpy(), d["arrival_t"].to_numpy()
    for i in range(len(d)):
        if piers[i] not in sim.p:
            continue
        w, _ = sim.simulate(piers[i], taus[i], tas[i])
        if w.shape[1] == 0:
            continue
        wv = w[:, -1]                     # 마지막 = 대상 선박(같은 분 도착이 있으면 근사)
        p12[i] = float((wv > thr_h).mean())
        ew[i] = float(wv.mean())
    return pd.DataFrame({"r1_p": p12, "r1_ewait": ew}, index=d.index)


def system_probs(sim: PierSim, taus: pd.DatetimeIndex, horizon_h: float = 24, thr_h: float = grid.WAIT_H) -> pd.DataFrame:
    """T1: τ마다 (τ, τ+24h] 도착 선박 중 하나라도 12h 초과 대기할 확률(부두 독립 가정으로 결합)."""
    out = np.zeros(len(taus))
    exp_n = np.zeros(len(taus))
    for i, t in enumerate(taus.to_numpy()):
        p_none = 1.0
        en = 0.0
        for pier in sim.p:
            w, _ = sim.simulate(pier, t, t + np.timedelta64(int(horizon_h * 3600), "s"))
            if w.shape[1] == 0:
                continue
            anyw = (w > thr_h).any(axis=1)
            p_none *= 1.0 - float(anyw.mean())
            en += float((w > thr_h).sum(axis=1).mean())
        out[i] = 1.0 - p_none
        exp_n[i] = en
    return pd.DataFrame({"r1_sys_p": out, "r1_sys_n": exp_n}, index=taus)
