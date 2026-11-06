"""예측기 학습·예측: S0 기후값, S1 지속성, S2 통계 기준선(로지스틱·GBM), R1 R-Delay 대기열, R2 재보정, R3 하이브리드."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

PIERS = ["1부두", "2부두", "3부두", "4부두", "5부두", "6부두", "7부두", "다목적"]

T2_S1 = ["free", "queue"]
T2_S2 = (["free", "queue", "sched_ahead", "occ", "n_wait_all", "max_wait_all", "log_gt", "arr_h_sin", "arr_h_cos",
          "arr_offday", "wind_bsn_max6", "hs_geoje_max6", "gust_geoje_max6", "rain_bsn_6h", "ty_near500", "log_ty_dist",
          "road_cong_frac", "road_rel_med", "slot_rate", "log_slot_n", "prev_pos", "prev_known", "prev_n180", "recent7_pos"]
         + [f"pier_{p}" for p in PIERS])
T2_R1 = ["logit_r1", "r1_ewait"]
SIS = ["sis_x", "sis_z", "sis_rd"]

T1_S1 = ["n_wait", "max_wait_h"]
T1_S2 = ["n_wait", "n_wait6", "max_wait_h", "n_berth", "n_present", "arr_2h", "arr_24h", "anch_2h", "anch_24h",
         "berthings_24h", "departs_24h", "xi_sea", "wind_bsn_max6", "hs_geoje_max6", "gust_geoje_max6", "rain_bsn_6h",
         "ty_near500", "log_ty_dist", "road_cong_frac", "road_rel_med", "h_sin", "h_cos", "offday",
         "sched_n24", "sched_slot_sum", "sched_prev_pos", "recent7_pos"]
T1_R1 = ["logit_r1_sys", "r1_sys_n"]


def logit(p, eps=1e-4):
    p = np.clip(np.asarray(p, float), eps, 1 - eps)
    return np.log(p / (1 - p))


def prep_ship(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    for p in PIERS:
        d[f"pier_{p}"] = (d["pier"] == p).astype(float)
    d["log_ty_dist"] = np.log(d["ty_dist_km"].clip(lower=50))
    d["log_slot_n"] = np.log1p(d["slot_n"])
    if "r1_p" in d:
        d["logit_r1"] = logit(d["r1_p"].fillna(0.0))
    return d


def prep_grid(g: pd.DataFrame, ship_l24: pd.DataFrame) -> pd.DataFrame:
    """T1 격자 + 앞으로 24시간 도착 예정 선박의 이력 합계(각 선박의 도착 24시간 전 기준 값 → τ보다 이르다)."""
    g = g.copy()
    g["log_ty_dist"] = np.log(g["ty_dist_km"].clip(lower=50))
    s = ship_l24.sort_values("arrival_t")
    ta = s["arrival_t"].to_numpy()
    cs_slot = np.r_[0.0, np.cumsum(s["slot_rate"].to_numpy())]
    cs_prev = np.r_[0.0, np.cumsum(s["prev_pos"].to_numpy())]
    tv = g.index.to_numpy()
    lo = np.searchsorted(ta, tv, side="right")
    hi = np.searchsorted(ta, tv + np.timedelta64(24, "h"), side="right")
    g["sched_n24"] = (hi - lo).astype(float)
    g["sched_slot_sum"] = cs_slot[hi] - cs_slot[lo]
    g["sched_prev_pos"] = cs_prev[hi] - cs_prev[lo]
    tp = np.sort(s.loc[s["wait_h"] > 12.0, "arrival_t"].to_numpy())  # 도착 12시간 뒤면 확정되는 사실만
    rb = tv - np.timedelta64(12, "h")
    g["recent7_pos"] = (np.searchsorted(tp, rb, side="right") - np.searchsorted(tp, rb - np.timedelta64(7, "D"), side="right")).astype(float)
    if "r1_sys_p" in g:
        g["logit_r1_sys"] = logit(g["r1_sys_p"])
    return g


class Logit:
    def __init__(self, cols, C=1.0):
        self.cols, self.C = cols, C

    def fit(self, X: pd.DataFrame, y):
        Z = X[self.cols]
        self.med = Z.median()
        self.sc = StandardScaler().fit(Z.fillna(self.med))
        self.m = LogisticRegression(C=self.C, max_iter=2000).fit(self.sc.transform(Z.fillna(self.med)), y)
        return self

    def predict(self, X):
        return self.m.predict_proba(self.sc.transform(X[self.cols].fillna(self.med)))[:, 1]


class GBM:
    def __init__(self, cols, max_iter=300, lr=0.05, depth=3, seed=0):
        self.cols = cols
        self.m = HistGradientBoostingClassifier(max_iter=max_iter, learning_rate=lr, max_depth=depth,
                                                l2_regularization=1.0, min_samples_leaf=40, random_state=seed)

    def fit(self, X, y):
        self.m.fit(X[self.cols], y)
        return self

    def predict(self, X):
        return self.m.predict_proba(X[self.cols])[:, 1]


class PierClim:
    """S0(T2): 부두별 학습 기간 비율."""

    def fit(self, X, y):
        self.r = pd.Series(np.asarray(y, float), index=X.index).groupby(X["pier"]).mean()
        self.base = float(np.mean(y))
        return self

    def predict(self, X):
        return X["pier"].map(self.r).fillna(self.base).to_numpy()


class HourDowClim:
    """S0(T1): 시간대×요일 기저율(+전체 평균으로 수축)."""

    def fit(self, X, y):
        d = pd.DataFrame({"h": X["hour"].to_numpy(), "w": X["dow"].to_numpy(), "y": np.asarray(y, float)})
        self.base = float(d["y"].mean())
        g = d.groupby(["h", "w"])["y"].agg(["sum", "size"])
        self.r = (g["sum"] + 10 * self.base) / (g["size"] + 10)
        return self

    def predict(self, X):
        idx = pd.MultiIndex.from_arrays([X["hour"].to_numpy(), X["dow"].to_numpy()])
        return self.r.reindex(idx).fillna(self.base).to_numpy()
