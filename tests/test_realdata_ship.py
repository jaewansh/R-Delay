"""선박 단위 실자료 백테스트(realdata_ship/) 단위 테스트. 실자료 없이 도는 테스트와, 자료가 있을 때만 도는 누설 검사로 나뉜다.

pandas·scikit-learn이 없으면(엔진 전용 CI) 통째로 건너뛴다.
"""
import os
import pathlib

import numpy as np
import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("sklearn")

from realdata_ship import evaluate as ev  # noqa: E402
from realdata_ship import grid  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _has_data() -> bool:
    try:
        from realdata_ship import paths
        return (paths.public() / "derived" / "newport_voyages.csv").exists()
    except SystemExit:
        return False


# ── 실자료 없이 도는 테스트 ────────────────────────────────────────────────
def test_window_counts_only_past():
    t = np.array(["2024-01-01T00:00", "2024-01-01T01:00", "2024-01-01T02:00", "2024-01-01T03:00"], dtype="datetime64[ns]")
    tau = np.array(["2024-01-01T02:00"], dtype="datetime64[ns]")
    # [τ-2h, τ) = 00:00, 01:00 → 2건. τ 자신(02:00)과 미래(03:00)는 세지 않는다.
    assert grid._window(t, tau, 2)[0] == 2
    w = np.array([1.0, 2.0, 4.0, 8.0])
    assert grid._window(t, tau, 2, w)[0] == 3.0


def test_episodes_grouping():
    times = pd.to_datetime(["2025-01-01 00:00", "2025-01-02 00:00", "2025-01-05 00:00", "2025-01-10 00:00", "2025-01-11 12:00"])
    eps = ev.episodes(times.to_numpy(), gap_h=48)
    assert [n for _, _, n in eps] == [2, 1, 2]


def test_event_stats_lead_and_false_alarm():
    eps = [(pd.Timestamp("2025-01-03 00:00"), pd.Timestamp("2025-01-03 00:00"), 1)]
    t = pd.date_range("2025-01-01", "2025-01-10", freq="2h")
    on = np.zeros(len(t), bool)
    on[(t >= "2025-01-02 00:00") & (t < "2025-01-02 06:00")] = True    # 24시간 앞선 경보
    on[(t >= "2025-01-08 00:00") & (t < "2025-01-08 04:00")] = True    # 뒤따르는 사건 없음 → 오경보
    s = ev.event_stats(t, on, eps)
    assert s["detected"] == 1 and s["missed"] == 0
    assert s["lead_median_h"] == pytest.approx(24.0)
    assert s["alarms"] == 2 and s["false_alarms"] == 1


def test_metrics_and_threshold():
    y = np.array([0, 0, 0, 1, 0, 1, 0, 0, 1, 0])
    p = np.array([.1, .2, .1, .9, .3, .8, .2, .1, .7, .4])
    m = ev.metrics(y, p, np.full(10, y.mean()))
    assert m["roc_auc"] == pytest.approx(1.0)
    assert m["bss"] > 0
    thr = ev.best_f1_threshold(y, p)
    a = ev.alarm_stats(y, p, thr)
    assert a["recall"] == pytest.approx(1.0) and a["precision"] == pytest.approx(1.0)


def test_pier_queue_tagged_ship():
    """선석 1개, 대 있는 배가 경과 0시간·체류 20시간 고정 → 5시간 뒤 도착한 배는 15시간 기다린다."""
    from realdata_ship import queue_mc
    sim = queue_mc.PierSim.__new__(queue_mc.PierSim)
    sim.S, sim.cap_h, sim.rng = 50, 168.0, np.random.default_rng(0)
    sim.cap = {"X": 1}
    sim.durs = {"X": np.full(10, 20.0)}
    t0 = np.datetime64("2025-01-01T00:00")
    sim.p = {"X": {"s_start": np.array([t0]), "s_end": np.array([np.datetime64("2100-01-01")]),
                   "a_arr": np.array([], dtype="datetime64[ns]"), "a_berth": np.array([], dtype="datetime64[ns]"),
                   "arr": np.array([t0 + np.timedelta64(5, "h")])}}
    w, ta = sim.simulate("X", t0, t0 + np.timedelta64(5, "h"))
    assert ta.tolist() == [5.0]
    assert np.allclose(w[:, 0], 15.0)


# ── 실자료가 있을 때만: 누설 검사 ───────────────────────────────────────────
@pytest.mark.skipif(not _has_data(), reason="실자료(RDELAY_DATA_ROOT) 없음")
def test_grid_features_do_not_use_future(monkeypatch):
    """컷오프 뒤 자료(도착·접안·출항)를 지워도 컷오프 이전 τ의 특징은 같아야 한다."""
    full = grid.build(start="2024-03-01", end="2024-03-12")
    cut = pd.Timestamp("2024-03-08")
    v = grid.voyages()
    st = grid.berth_stays()
    far = pd.Timestamp("2100-01-01")
    v_cut = v[v["arrival_t"] < cut].copy()
    v_cut["berth_t"] = v_cut["berth_t"].where(v_cut["berth_t"] < cut, far)
    st_cut = st[st["start"] < cut].copy()
    st_cut["end"] = st_cut["end"].where(st_cut["end"] < cut, pd.NaT)
    monkeypatch.setattr(grid, "voyages", lambda cap_h=grid.CAP_H: v_cut)
    monkeypatch.setattr(grid, "berth_stays", lambda: st_cut)
    part = grid.build(start="2024-03-01", end="2024-03-12")
    labels = [c for c in full.columns if c.startswith(("y", "npos"))]
    feats = [c for c in full.columns if c not in labels]
    a = full.loc[full.index <= cut, feats]
    b = part.loc[part.index <= cut, feats]
    pd.testing.assert_frame_equal(a, b, check_dtype=False)


def _has_cache() -> bool:
    if not _has_data():
        return False
    from realdata_ship import paths
    return all((paths.CACHE / f"{n}.parquet").exists() for n in ("voyages", "cntl", "berth_stays", "hourly_context_2025-01-01"))


# 2025-10-11 18:24 도착해 684시간 기다린 배(라벨에서 제외)가 정박지에 있던 때: 컷오프 시각에는 "12시간 초과"만 알고
# "168시간 초과 제외"는 모른다 → 이력 특징이 제외 표시를 쓰면(시험 뒤 고친 누설) 이 테스트가 잡는다.
CUT = pd.Timestamp("2025-10-15 13:00")


@pytest.fixture(scope="module")
def cut_pair():
    """같은 코드를 (1) 전체 자료와 (2) 컷오프 뒤에야 알 수 있는 것을 지운 자료로 돌린 결과 한 쌍.

    지우는 것: 컷오프 뒤 접안 시각, 아직 접안하지 않은 배의 대기시간(하한만 남기고 장기 대기·제외 표시도 하한으로 다시 정함),
    컷오프 뒤 도착한 배의 정박 여부, 컷오프 뒤 끝난 선석 체류의 끝, 컷오프 뒤 시작한 체류.
    도착 시각과 갈 부두는 남긴다(T2의 '정기선 일정을 안다' 가정).
    """
    from realdata_ship import io as rio, load, paths, queue_mc, ship, models as M

    def ro(name, sources, build, version=1):           # 읽기 전용: 테스트가 캐시를 다시 만들거나 덮어쓰지 않게
        return pd.read_parquet(paths.CACHE / f"{name}.parquet")

    far = pd.Timestamp("2100-01-01")
    taus_sys = pd.DatetimeIndex([CUT - pd.Timedelta(hours=h) for h in (8, 4, 0)])
    g = pd.DataFrame({"ty_dist_km": 3000.0}, index=pd.date_range(CUT - pd.Timedelta(days=10), CUT, freq="2h"))
    out = {}
    with pytest.MonkeyPatch.context() as mp:
        for mod in (rio, load, grid):
            mp.setattr(mod, "cached", ro)
        V, ST = grid.voyages(), grid.berth_stays()
        Vc = V.copy()
        unres = Vc["berth_t"] > CUT
        lb = (CUT - Vc["arrival_t"]).dt.total_seconds() / 3600 + 1e-3
        Vc.loc[unres, "wait_h"] = np.where(Vc.loc[unres, "arrival_t"] <= CUT, lb[unres], np.nan)
        Vc.loc[unres, "berth_t"] = far
        Vc.loc[unres, "excluded"] = Vc.loc[unres, "wait_h"] > grid.CAP_H          # 컷오프 시각에 알 수 있는 만큼만
        Vc.loc[unres, "pos12"] = (Vc.loc[unres, "wait_h"] > grid.WAIT_H) & ~Vc.loc[unres, "excluded"]
        Vc.loc[Vc["arrival_t"] > CUT, "anchored"] = False
        STc = ST[ST["start"] <= CUT].copy()
        STc.loc[STc["end"] > CUT, "end"] = pd.NaT
        rows = None
        for tag, vv, ss in (("full", V, ST), ("cut", Vc, STc)):
            mp.setattr(grid, "voyages", lambda cap_h=grid.CAP_H, vv=vv: vv.copy())
            mp.setattr(grid, "berth_stays", lambda ss=ss: ss.copy())
            d = ship.build(leads=(24, 6, 0))
            if rows is None:
                rows = d[(d["tau"] <= CUT) & (d["tau"] > CUT - pd.Timedelta(hours=36))].head(60)
            q_ship = queue_mc.ship_probs(queue_mc.PierSim(samples=200, seed=5), rows)
            q_sys = queue_mc.system_probs(queue_mc.PierSim(samples=100, seed=6), taus_sys)
            pg = M.prep_grid(g, M.prep_ship(d[d["L"] == 24]))
            out[tag] = (d, q_ship, q_sys, pg)
    return out


@pytest.mark.skipif(not _has_cache(), reason="실자료 캐시(realdata_ship/cache) 없음")
def test_ship_features_do_not_use_future(cut_pair):
    a, b = cut_pair["full"][0], cut_pair["cut"][0]
    labels = {"wait_h", "pos12", "excluded", "berth_t", "anchored"}
    feats = [c for c in a.columns if c not in labels]
    m = (a["tau"] <= CUT).to_numpy()
    assert m.sum() > 50_000
    x, y = a.loc[m, feats].reset_index(drop=True), b.loc[m, feats].reset_index(drop=True)
    bad = {}
    for c in feats:
        if pd.api.types.is_numeric_dtype(x[c].dtype) and not pd.api.types.is_bool_dtype(x[c].dtype):
            diff = ~np.isclose(x[c].astype(float), y[c].astype(float), equal_nan=True)
        else:
            diff = ~((x[c] == y[c]) | (x[c].isna() & y[c].isna()))
        if diff.any():
            bad[c] = int(diff.sum())
    assert not bad, f"컷오프 뒤 자료에 따라 바뀐 특징: {bad}"


@pytest.mark.skipif(not _has_cache(), reason="실자료 캐시(realdata_ship/cache) 없음")
def test_queue_mc_does_not_use_future(cut_pair):
    (_, qa, sa, _), (_, qb, sb, _) = cut_pair["full"], cut_pair["cut"]
    assert len(qa) > 0 and qa["r1_p"].notna().any()
    assert np.allclose(qa.to_numpy(), qb.to_numpy(), equal_nan=True)
    assert np.allclose(sa.to_numpy(), sb.to_numpy())


@pytest.mark.skipif(not _has_cache(), reason="실자료 캐시(realdata_ship/cache) 없음")
def test_t1_schedule_sums_do_not_use_future(cut_pair):
    ga, gb = cut_pair["full"][3], cut_pair["cut"][3]
    for c in ("sched_n24", "sched_slot_sum", "sched_prev_pos", "recent7_pos"):
        assert np.allclose(ga[c], gb[c], equal_nan=True), c
