"""2시간 판단 격자: τ마다 그때까지 알 수 있는 특징과 τ 뒤의 정답을 만든다.

누설 방지 원칙
- 특징은 τ 이전 자료만 쓴다: 구간 집계는 [τ-w, τ), 상태는 τ 시점 값, 기상은 τ 시각까지의 관측.
- τ 시점에 이미 168시간을 넘겨 기다린 선박은 대기 척수에서 뺀다(그 시각에 알 수 있는 사실).
- 정답만 τ 뒤를 본다: (τ, τ+h]에 도착한 선박의 대기시간.
- 기존 derived/newport_waiting_2h.csv의 도착·접안 수는 [t, t+2h) 앞쪽 구간이라 특징으로 쓰지 않는다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import load
from .io import cached

NEWPORT = (35.08, 128.83)          # 부산신항 대략 위치(위도, 경도)
CAP_H = 168.0                       # 라벨 상한: 이보다 긴 대기는 혼잡이 아닌 장기 체류로 보고 정답에서 뺀다
WAIT_H = 12.0                       # 신항 터미널 수출 반입 마감(접안 12시간 전) 기준
NEWPORT_BERTH = r"^신항 (?:\d부두 \d선석|다목적부두)"
ASOS_BUSAN, ASOS_CHANGWON = 159, 155
BUOY_GEOJE = 22104


def voyages(cap_h: float = CAP_H) -> pd.DataFrame:
    v = load.voyages().copy()
    v["anchored"] = v["wait_kind"].ne("바로 접안")
    v["excluded"] = v["wait_h"] > cap_h
    v["pos12"] = (v["wait_h"] > WAIT_H) & ~v["excluded"]
    return v.sort_values("arrival_t").reset_index(drop=True)


def berth_stays() -> pd.DataFrame:
    """관제정보에서 컨테이너선의 신항 선석 체류 구간(시작=입항·접안, 끝=다음 이안·출항)."""
    c = load.cntl()
    files = sorted((load.P() / "portmis" / "cntl" / "daily").glob("*.csv"))

    def build():
        d = c[c["vsslKndNm"].str.contains("컨테이너", na=False)].copy()
        d["key"] = d["clsgn"] + "|" + d["etryptYear"] + "|" + d["etryptCo"]
        d["newb"] = d["fcltyNm"].str.contains(NEWPORT_BERTH, regex=True, na=False)
        d = d.sort_values(["key", "t"], kind="stable")
        rows = []
        for k, g in d.groupby("key", sort=False):
            ev = g[["t", "cntrlNm", "newb", "gt", "fcltyNm"]].to_numpy()
            for i, (t, nm, nb, gt, fac) in enumerate(ev):
                if nb and nm in ("입항", "접안"):
                    end = next((e[0] for e in ev[i + 1:] if e[1] in ("이안", "출항")), pd.NaT)
                    rows.append((k, t, end, gt, fac))
        out = pd.DataFrame(rows, columns=["key", "start", "end", "gt", "fac"])
        out["pier"] = out["fac"].str.extract(r"신항 (\d부두|다목적)", expand=False)
        return out

    return cached("berth_stays", files, build, version=2)


def _count_before(sorted_times: np.ndarray, t: np.ndarray) -> np.ndarray:
    return np.searchsorted(sorted_times, t, side="left")  # 개수: times < t


def _window(times: np.ndarray, t: np.ndarray, hours: float, weights: np.ndarray | None = None) -> np.ndarray:
    """[t-h, t) 구간에 든 사건 수(또는 가중합)."""
    order = np.argsort(times)
    ts = times[order]
    lo = _count_before(ts, t - np.timedelta64(int(hours * 3600), "s"))
    hi = _count_before(ts, t)
    if weights is None:
        return (hi - lo).astype(float)
    cw = np.concatenate([[0.0], np.cumsum(np.nan_to_num(weights[order]))])
    return cw[hi] - cw[lo]


def _haversine(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def _weather(tau: pd.DatetimeIndex) -> pd.DataFrame:
    a = load.asos()
    b = load.buoy()
    out = pd.DataFrame(index=tau)
    hourly = pd.date_range(tau.min() - pd.Timedelta(hours=12), tau.max(), freq="1h")
    for stn, tag in ((ASOS_BUSAN, "bsn"), (ASOS_CHANGWON, "cw")):
        s = a[a["stn"] == stn].set_index("t").reindex(hourly)
        out[f"wind_{tag}"] = s["wind"].reindex(tau).to_numpy()
        out[f"wind_{tag}_max6"] = s["wind"].rolling(7, min_periods=1).max().reindex(tau).to_numpy()
        if tag == "bsn":
            out["rain_bsn_6h"] = s["rain"].fillna(0).rolling(7, min_periods=1).sum().reindex(tau).to_numpy()
    s = b[b["stn"] == BUOY_GEOJE].set_index("t").reindex(hourly)
    # 부이는 결측이 잦다: 최근 3시간 안의 마지막 값까지 허용(앞쪽 값만 씀)
    for col, name in (("hs", "hs_geoje"), ("wind", "wind_geoje"), ("gust", "gust_geoje")):
        ser = s[col].ffill(limit=3)
        out[name] = ser.reindex(tau).to_numpy()
        out[name + "_max6"] = ser.rolling(7, min_periods=1).max().reindex(tau).to_numpy()
    return out


def _typhoon(tau: pd.DatetimeIndex) -> pd.DataFrame:
    tr = load.typhoon_track()
    tr = tr.assign(dist=_haversine(NEWPORT[0], NEWPORT[1], tr["lat"].to_numpy(), tr["lon"].to_numpy()))
    tr = tr.assign(avail=tr["t"] + pd.Timedelta(hours=3))  # 분석 시각 3시간 뒤부터 쓸 수 있다고 본다
    out = np.full(len(tau), 3000.0)
    appr = np.zeros(len(tau))
    tv = tau.to_numpy()
    for (_, _), g in tr.groupby(["year", "no"]):
        g = g.sort_values("avail")
        av = g["avail"].to_numpy()
        idx = np.searchsorted(av, tv, side="right") - 1          # τ 이전 마지막 분석
        ok = idx >= 0
        last_t = np.where(ok, av[np.clip(idx, 0, None)], np.datetime64("NaT", "ns"))
        fresh = ok & ((tv - last_t) <= np.timedelta64(12, "h"))  # 12시간 안에 분석이 있으면 활동 중
        d = g["dist"].to_numpy()[np.clip(idx, 0, None)]
        prev = g["dist"].to_numpy()[np.clip(idx - 1, 0, None)]
        better = fresh & (d < out)
        out = np.where(better, d, out)
        appr = np.where(better, (prev - d) > 0, appr)
    return pd.DataFrame({"ty_dist_km": out, "ty_near500": (out <= 500).astype(float),
                         "ty_approach": appr.astype(float)}, index=tau)


def road_reference(train_end: str) -> tuple[pd.DataFrame, list[str]]:
    """학습 기간으로 콘존별 기준속도(요일 구분·시간대 85분위)와 쓸 콘존(학습 기간 측정률 80% 이상)을 정한다."""
    r = load.road()
    tr = r[r["t"] < pd.Timestamp(train_end)]
    cov = tr.groupby("zone")["speed"].apply(lambda s: s.notna().mean())
    zones = sorted(cov[cov >= 0.8].index)
    tr = tr[tr["zone"].isin(zones)].assign(we=tr["t"].dt.dayofweek >= 5, hr=tr["t"].dt.hour)
    ref = tr.groupby(["zone", "we", "hr"])["speed"].quantile(0.85).rename("ref").reset_index()
    return ref, zones


def _road(tau: pd.DatetimeIndex, train_end: str, ratio: float = 0.6) -> pd.DataFrame:
    ref, zones = road_reference(train_end)
    r = load.road()
    r = r[r["zone"].isin(zones)].assign(we=lambda d: d["t"].dt.dayofweek >= 5, hr=lambda d: d["t"].dt.hour)
    r = r.merge(ref, on=["zone", "we", "hr"], how="left")
    r["rel"] = r["speed"] / r["ref"]
    wide = r.pivot_table(index="t", columns="zone", values="rel", aggfunc="mean")
    hourly = pd.date_range(tau.min() - pd.Timedelta(hours=4), tau.max(), freq="1h")
    wide = wide.reindex(hourly)
    # τ에서 쓸 수 있는 것은 τ-2h, τ-1h 시간대(끝난 시간대) 값의 평균
    rel2 = wide.shift(1).rolling(2, min_periods=1).mean()
    cong = (rel2 < ratio).astype(float).where(rel2.notna())
    out = pd.DataFrame(index=tau)
    out["road_n"] = rel2.notna().sum(axis=1).reindex(tau).to_numpy()
    out["road_cong"] = cong.sum(axis=1).reindex(tau).to_numpy()
    out["road_cong_frac"] = (out["road_cong"] / out["road_n"].replace(0, np.nan))
    out["road_rel_med"] = rel2.median(axis=1).reindex(tau).to_numpy()
    out.loc[out["road_n"] < 10, ["road_cong_frac", "road_rel_med"]] = np.nan  # 측정 콘존이 너무 적으면 결측
    out.attrs["zones"] = zones
    return out


def _calendar(tau: pd.DatetimeIndex) -> pd.DataFrame:
    import holidays
    kr = holidays.KR(years=sorted(set(tau.year)))
    d = pd.DataFrame(index=tau)
    d["hour"] = tau.hour
    d["dow"] = tau.dayofweek
    d["month"] = tau.month
    d["weekend"] = (tau.dayofweek >= 5).astype(float)
    d["holiday"] = np.array([dt.date() in kr for dt in tau], dtype=float)
    d["offday"] = np.maximum(d["weekend"], d["holiday"])
    d["h_sin"], d["h_cos"] = np.sin(2 * np.pi * tau.hour / 24), np.cos(2 * np.pi * tau.hour / 24)
    return d


def build(start: str = "2023-01-30", end: str | None = None, train_end: str = "2025-01-01",
          cap_h: float = CAP_H) -> pd.DataFrame:
    v = voyages(cap_h)
    st = berth_stays()
    data_end = max(v["berth_t"].max(), load.cntl()["t"].max())
    end_ts = pd.Timestamp(end) if end else (data_end - pd.Timedelta(hours=24)).floor("2h")
    tau = pd.date_range(pd.Timestamp(start), end_ts, freq="2h")
    tv = tau.to_numpy()
    g = pd.DataFrame(index=tau)
    # 대기 상태(τ 시점): 정박지에서 기다리는 중이고 대기가 아직 상한 이하인 선박
    an = v[v["anchored"]]
    a, b = an["arrival_t"].to_numpy(), an["berth_t"].to_numpy()
    waiting = (a[None, :] <= tv[:, None]) & (b[None, :] > tv[:, None])
    age_h = (tv[:, None] - a[None, :]) / np.timedelta64(1, "h")
    live = waiting & (age_h <= cap_h)
    g["n_wait"] = live.sum(axis=1).astype(float)
    g["n_wait6"] = (live & (age_h > 6)).sum(axis=1).astype(float)
    g["max_wait_h"] = np.where(live, age_h, 0.0).max(axis=1)
    # 선석 체류(컨테이너선, 신항)
    s_sorted = np.sort(st["start"].to_numpy())
    e_sorted = np.sort(st["end"].fillna(pd.Timestamp("2100-01-01")).to_numpy())
    g["n_berth"] = (np.searchsorted(s_sorted, tv, side="right") - np.searchsorted(e_sorted, tv, side="right")).astype(float)
    g["n_present"] = g["n_berth"] + g["n_wait"]
    # 구간 집계 [τ-w, τ)
    at = v["arrival_t"].to_numpy()
    g["arr_2h"] = _window(at, tv, 2)
    g["arr_24h"] = _window(at, tv, 24)
    g["gt_arr_24h"] = _window(at, tv, 24, v["gt"].to_numpy(dtype=float))
    g["anch_2h"] = _window(an["arrival_t"].to_numpy(), tv, 2)
    g["anch_24h"] = _window(an["arrival_t"].to_numpy(), tv, 24)
    g["berthings_24h"] = _window(v["berth_t"].to_numpy(), tv, 24)
    g["departs_24h"] = _window(st["end"].dropna().to_numpy(), tv, 24)
    # 28일 기준선 대비 물동량 비율 ξ(총톤수 가중 도착량)
    gt28 = _window(at, tv, 24 * 28, v["gt"].to_numpy(dtype=float)) / 28.0
    g["xi_sea"] = g["gt_arr_24h"] / gt28.clip(min=1.0)
    # 정답: (τ, τ+h]에 도착한 선박 중 12시간 초과 대기(상한 이하)
    pos = v[v["pos12"]]["arrival_t"].to_numpy()
    for h in (12, 24, 48):
        lo = np.searchsorted(np.sort(pos), tv, side="right")
        hi = np.searchsorted(np.sort(pos), tv + np.timedelta64(h, "h"), side="right")
        g[f"y{h}"] = (hi - lo > 0).astype(int)
        g[f"npos{h}"] = (hi - lo).astype(int)
    g = g.join(_weather(tau)).join(_typhoon(tau)).join(_road(tau, train_end)).join(_calendar(tau))
    g.index.name = "tau"
    g.attrs["data_end"] = str(data_end)
    return g


def hourly_context(train_end: str = "2025-01-01") -> pd.DataFrame:
    """시간 단위 기상·태풍·도로 특징(정시 t에서 쓸 수 있는 값). 임의 시각 τ는 τ.floor('h')로 읽는다."""
    v = load.voyages()
    start = pd.Timestamp("2023-01-01")
    end = (v["berth_t"].max()).ceil("h")
    hours = pd.date_range(start, end, freq="1h")
    files = [load.P() / "derived" / "ex_speed_busan.csv", load.P() / "derived" / "newport_voyages.csv"]
    files += sorted((load.P() / "manual" / "kma_asos").glob("*.csv")) + sorted((load.P() / "manual" / "kma_buoy").glob("*.csv"))
    files += sorted((load.P() / "manual" / "kma_typhoon").glob("*.csv"))

    def build():
        h = _weather(hours).join(_typhoon(hours)).join(_road(hours, train_end))
        h.index.name = "t"
        return h.reset_index()

    return cached(f"hourly_context_{train_end[:10]}", files, build, version=1).set_index("t")
