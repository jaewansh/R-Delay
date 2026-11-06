"""평가 지표: PR-AUC(주), ROC-AUC, Brier·기술점수, 신뢰도 곡선, 검증 기간 F1 최대 문턱, 주 단위 블록 부트스트랩."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

PERIODS = {
    "train": ("2023-01-30", "2025-01-01"),
    "valid": ("2025-01-01", "2025-07-01"),
}


def test_period(data_end) -> tuple[str, str]:
    return "2025-07-01", str((pd.Timestamp(data_end) - pd.Timedelta(hours=96)).floor("h"))


def split(df: pd.DataFrame, col: str, period: tuple[str, str]) -> pd.DataFrame:
    a, b = pd.Timestamp(period[0]), pd.Timestamp(period[1])
    return df[(df[col] >= a) & (df[col] < b)]


def brier(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    return float(np.mean((p - y) ** 2))


def metrics(y, p, p_ref=None) -> dict:
    y, p = np.asarray(y, float), np.asarray(p, float)
    out = {"n": int(len(y)), "pos": int(y.sum()), "base_rate": float(y.mean())}
    if 0 < y.sum() < len(y):
        out["pr_auc"] = float(average_precision_score(y, p))
        out["roc_auc"] = float(roc_auc_score(y, p))
    out["brier"] = brier(y, p)
    if p_ref is not None:
        b0 = brier(y, p_ref)
        out["bss"] = float(1 - out["brier"] / b0) if b0 > 0 else None
    return out


def best_f1_threshold(y, p) -> float:
    """검증 기간 F1 최대 문턱. 후보는 예측값 분위 0~99.5%(처음 구현은 50% 이상만 봐서 경보 비율이 50%로 묶였다 → 부록 C)."""
    y, p = np.asarray(y, float), np.asarray(p, float)
    qs = np.unique(np.quantile(p, np.linspace(0.0, 0.995, 400)))
    best, thr = -1.0, float(qs[-1]) if len(qs) else 0.5
    for t in qs:
        a = p >= t
        tp = float((a & (y == 1)).sum())
        if a.sum() == 0 or tp == 0:
            continue
        prec, rec = tp / a.sum(), tp / y.sum()
        f1 = 2 * prec * rec / (prec + rec)
        if f1 > best:
            best, thr = f1, float(t)
    return thr


def alarm_stats(y, p, thr) -> dict:
    y, p = np.asarray(y, float), np.asarray(p, float)
    a = p >= thr
    tp = float((a & (y == 1)).sum())
    return {"threshold": float(thr), "alarm_rate": float(a.mean()),
            "precision": float(tp / a.sum()) if a.sum() else None,
            "recall": float(tp / y.sum()) if y.sum() else None,
            "lift": float((tp / a.sum()) / y.mean()) if a.sum() and y.mean() else None}


def reliability(y, p, bins: int = 10) -> list[dict]:
    d = pd.DataFrame({"y": np.asarray(y, float), "p": np.asarray(p, float)})
    try:
        d["b"] = pd.qcut(d["p"], bins, duplicates="drop")
    except ValueError:
        return []
    g = d.groupby("b", observed=True).agg(p_mean=("p", "mean"), y_rate=("y", "mean"), n=("y", "size"))
    return [{"p_mean": float(r.p_mean), "y_rate": float(r.y_rate), "n": int(r.n)} for r in g.itertuples()]


def block_bootstrap(y, p, times, stat: str = "pr_auc", n_boot: int = 1000, p_ref=None, seed: int = 7) -> tuple[float, float]:
    """주 단위 블록을 복원추출해 지표의 95% 구간."""
    y, p = np.asarray(y, float), np.asarray(p, float)
    wk = pd.to_datetime(pd.Series(times)).dt.to_period("W").astype(str).to_numpy()
    blocks = {}
    for i, w in enumerate(wk):
        blocks.setdefault(w, []).append(i)
    keys = list(blocks)
    idx_lists = [np.array(blocks[k]) for k in keys]
    rng = np.random.default_rng(seed)
    vals = []
    pr = None if p_ref is None else np.asarray(p_ref, float)
    for _ in range(n_boot):
        pick = rng.integers(0, len(keys), len(keys))
        ii = np.concatenate([idx_lists[k] for k in pick])
        yy, pp = y[ii], p[ii]
        if not (0 < yy.sum() < len(yy)):
            continue
        if stat == "pr_auc":
            vals.append(average_precision_score(yy, pp))
        elif stat == "roc_auc":
            vals.append(roc_auc_score(yy, pp))
        elif stat == "bss" and pr is not None:
            b0 = brier(yy, pr[ii])
            vals.append(1 - brier(yy, pp) / b0 if b0 > 0 else np.nan)
    vals = np.asarray(vals, float)
    vals = vals[np.isfinite(vals)]
    return (float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))) if len(vals) else (np.nan, np.nan)


def episodes(pos_times: np.ndarray, gap_h: float = 48.0) -> list[tuple[pd.Timestamp, pd.Timestamp, int]]:
    """장기 대기 선박 도착 시각을 gap_h 안에 이어지면 한 에피소드로 묶는다."""
    t = np.sort(pd.to_datetime(pos_times).to_numpy())
    eps, start, last, n = [], None, None, 0
    for x in t:
        if start is None:
            start, last, n = x, x, 1
        elif (x - last) <= np.timedelta64(int(gap_h * 3600), "s"):
            last, n = x, n + 1
        else:
            eps.append((pd.Timestamp(start), pd.Timestamp(last), n))
            start, last, n = x, x, 1
    if start is not None:
        eps.append((pd.Timestamp(start), pd.Timestamp(last), n))
    return eps


def event_stats(alarm_times: pd.DatetimeIndex, alarm_on: np.ndarray, eps, pre_h: float = 72, post_h: float = 12,
                fa_h: float = 48) -> dict:
    """T3: 탐지(첫 도착 72h 전~12h 뒤 경보), 선행시간, 오경보(켜진 뒤 48h 안에 에피소드 없음) 비율."""
    t = pd.DatetimeIndex(alarm_times)
    on = np.asarray(alarm_on, bool)
    leads, missed = [], 0
    for s, _, _ in eps:
        w = on & (t >= s - pd.Timedelta(hours=pre_h)) & (t <= s + pd.Timedelta(hours=post_h))
        if w.any():
            leads.append((s - t[w][0]).total_seconds() / 3600)
        else:
            missed += 1
    rises = t[on & ~np.r_[False, on[:-1]]]
    starts = np.array([s for s, _, _ in eps], dtype="datetime64[ns]")
    ends = np.array([e for _, e, _ in eps], dtype="datetime64[ns]")
    false = 0
    for r in rises.to_numpy():
        inside = ((starts <= r) & (ends + np.timedelta64(int(fa_h * 3600), "s") >= r)).any()
        upcoming = ((starts > r) & (starts <= r + np.timedelta64(int(fa_h * 3600), "s"))).any()
        if not (inside or upcoming):
            false += 1
    leads = np.asarray(leads)
    return {"episodes": len(eps), "detected": int(len(leads)), "missed": int(missed),
            "lead_median_h": float(np.median(leads)) if len(leads) else None,
            "lead_q25_h": float(np.quantile(leads, 0.25)) if len(leads) else None,
            "lead_q75_h": float(np.quantile(leads, 0.75)) if len(leads) else None,
            "early_share": float((leads >= 0).mean()) if len(leads) else None,
            "alarms": int(len(rises)), "false_alarms": int(false),
            "false_alarm_share": float(false / len(rises)) if len(rises) else None}
