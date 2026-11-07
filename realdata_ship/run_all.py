"""실자료 백테스트 전체 실행(한 명령).

  python -m realdata_ship.run_all              # 캐시 갱신 → 격자·선박 표 → 대기열 → SIS → 검증 → 시험 → 그림·backtest.json
  python -m realdata_ship.run_all --relabel    # 새 관제정보가 들어왔을 때: data-kit 라벨부터 다시 만든다
  python -m realdata_ship.run_all --skip-calibrate   # SIS 우도 격자를 다시 돌리지 않고 저장된 값을 쓴다

모형·기준은 PROTOCOL.md대로 고정이고, 자료가 늘면 시험 기간만 늘어난다.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import warnings

import numpy as np
import pandas as pd

from . import backtest as bt
from . import evaluate as ev
from . import grid, load, models as M, paths, queue_mc, ship, sis_pf

warnings.filterwarnings("ignore")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def relabel():
    env = dict(os.environ, RDELAY_DATA_DIR=str(paths.public()))
    kit = paths.ROOT / "data-kit"
    log("라벨 다시 만들기(data-kit/build_wait_labels.py)")
    subprocess.run([sys.executable, str(kit / "build_wait_labels.py")], cwd=kit, env=env, check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--relabel", action="store_true")
    ap.add_argument("--skip-calibrate", action="store_true")
    ap.add_argument("--n-boot", type=int, default=1000)
    a = ap.parse_args()
    t0 = time.time()
    paths.ensure_dirs()
    if a.relabel:
        relabel()
    log("1/7 원자료 읽기(바뀐 것만)")
    for name in ("voyages", "asos", "buoy", "typhoon_track", "typhoon_list", "road", "cntl"):
        getattr(load, name)()
    log("2/7 2시간 판단 격자·선박 단위 표")
    g = grid.build()
    d = ship.build()
    log("3/7 R-Delay 선석 대기열(부두별 몬테카를로)")
    d = d.join(queue_mc.ship_probs(queue_mc.PierSim(samples=400), d))
    g = g.join(queue_mc.system_probs(queue_mc.PierSim(samples=400, seed=11), g.index))
    log("4/7 SIS 입자필터(학습 기간 우도로 모수, f_ω 학습 → 전 기간 필터)")
    G = g.reset_index()
    tr = ev.split(G, "tau", ev.PERIODS["train"]).set_index("tau")
    va = ev.split(G, "tau", ev.PERIODS["valid"]).set_index("tau")
    cal_path = paths.RESULTS / "sis_calibration.json"
    if a.skip_calibrate and cal_path.exists():
        cal = json.loads(cal_path.read_text(encoding="utf-8"))
    else:
        v = grid.voyages()
        an = v[v["anchored"] & ~v["excluded"] & (v["arrival_t"] < pd.Timestamp(ev.PERIODS["train"][1]))]
        gamma_s = 1.0 / an["wait_h"].mean()
        cal = sis_pf.calibrate(tr, gamma_s, ratios=(0.0, 0.3, 0.6, 0.9, 1.2, 1.5, 2.0), kappas=(0.0, 0.5))
        b = cal["best"]
        p = sis_pf.params(tr, beta_s=b["beta_ratio"] * gamma_s, kappa=b["kappa"], gamma_s=gamma_s)
        model = None
        for _ in range(2):
            o = sis_pf.run(tr, p, zbar=sis_pf.zbar_from(model, tr))
            model = sis_pf.fit_fomega(tr, o["z_smooth"])
        ll0 = sis_pf.run(va, p)["total_loglik"]
        ll1 = sis_pf.run(va, p, zbar=sis_pf.zbar_from(model, va))["total_loglik"]
        cal.update({"f_omega": model, "valid_loglik_without": ll0, "valid_loglik_with": ll1, "use_f_omega": bool(ll1 > ll0)})
        bt.save("sis_calibration.json", cal)
    b, gamma_s = cal["best"], cal["gamma_s"]
    p = sis_pf.params(tr, beta_s=b["beta_ratio"] * gamma_s, kappa=b["kappa"], gamma_s=gamma_s)
    zb_model = cal["f_omega"] if cal.get("use_f_omega") else None
    o = sis_pf.run(g, p, zbar=sis_pf.zbar_from(zb_model, g))
    s = pd.DataFrame({"sis_x": o["x_s"], "sis_xl": o["x_l"], "sis_z": o["z_s"], "sis_rd": o["rd"], "sis_p1": o["p_rd1"]}, index=g.index)
    g = g.join(s)
    idx = np.searchsorted(s.index.to_numpy(), d["tau"].to_numpy(), side="right") - 1
    for c in ("sis_x", "sis_z", "sis_rd", "sis_p1"):
        d[c] = np.where(idx >= 0, s[c].to_numpy()[np.clip(idx, 0, None)], np.nan)
    d.to_parquet(paths.CACHE / "ship_r1s.parquet")
    g.to_parquet(paths.CACHE / "grid_r1s.parquet")
    log("5/7 검증 기간 선택")
    d = M.prep_ship(d)
    val_t2, t2_choice = bt.t2_validate(d, cols_sis=M.SIS)
    l24 = d[d["L"] == 24]  # 예정 도착·이력에는 모든 항차(제외 여부는 그 시각에 알 수 없음)
    GG = M.prep_grid(g, l24)
    for c in ("sis_p1", "sis_x"):
        GG["logit_" + c] = M.logit(GG[c].clip(1e-4, 1 - 1e-4))
    GG = GG.reset_index()
    val_t1, t1_choice = bt.t1_validate(GG, cols_sis=M.SIS)
    log(f"   선택한 C: T2 {t2_choice} · T1 {t1_choice}")
    bt.save("valid_results.json", {"t2": {str(k): v for k, v in val_t2.items()}, "t1": val_t1,
                                   "t2_choice": {str(k): v for k, v in t2_choice.items()}, "t1_choice": t1_choice})
    log("6/7 시험 기간(학습+검증으로 다시 맞춤, 한 번)")
    data_end = max(load.voyages()["berth_t"].max(), load.cntl()["t"].max())
    res, p2, p1 = bt.final_test(d, GG, data_end, t2_choice, t1_choice, n_boot=a.n_boot)
    res.update({"t2_choice": {str(k): v for k, v in t2_choice.items()}, "t1_choice": t1_choice, "data_end": str(data_end),
                "sis": {"beta_ratio": b["beta_ratio"], "kappa": b["kappa"], "gamma_s": gamma_s,
                        "f_omega": cal.get("f_omega"), "valid_loglik_gain": cal.get("valid_loglik_with", 0) - cal.get("valid_loglik_without", 0)}})
    bt.save("test_results.json", res)
    bt.save("sensitivity.json", bt.sensitivity_cap(d, data_end, t2_choice, cap_h=336.0))
    p2.to_parquet(paths.CACHE / "test_preds_t2.parquet")
    p1.to_parquet(paths.CACHE / "test_preds_t1.parquet")
    log("7/7 그림·요약·웹 자료")
    from . import report
    report.build_all()
    log(f"끝 ({(time.time() - t0) / 60:.1f}분). 결과: {paths.RESULTS}, 그림: {paths.REPORTS}")


if __name__ == "__main__":
    main()
