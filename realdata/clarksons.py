"""Clarksons 자료 비공개 분석(결과는 local_only/에만). 원자료·파생 수치는 저장소·웹에 넣지 않는다.

  python -m realdata.clarksons
1) A2 부산 체류 척수(AIS 기반)와 PORT-MIS로 잰 신항 체류·대기 척수의 일별 상관 → 라벨 타당성의 외부 근거
2) C1 정기용선료(USD/일)로 본 선박 쪽 대기 비용: 12시간 초과분 대기 시간 × 일 용선료
"""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd

from . import grid, paths

warnings.filterwarnings("ignore")


def _sin(path) -> pd.DataFrame:
    raw = pd.read_excel(path, header=None)
    hdr = next(i for i in range(15) if str(raw.iat[i, 0]).strip().lower() == "date")
    ids = [str(x).replace(".0", "") for x in raw.iloc[hdr - 2, 1:]]
    df = raw.iloc[hdr + 1:].copy()
    df.columns = ["date"] + ids
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).set_index("date")
    return df.apply(pd.to_numeric, errors="coerce")


def run() -> dict:
    d = paths.clarksons_dir()
    if d is None:
        raise SystemExit("Clarksons 자료 폴더를 찾지 못했습니다(RDELAY_CLARKSONS_DIR).")
    files = {p.name: p for p in d.rglob("CLK_*.xlsx")}
    out = {}
    # 1) 부산 체류 척수 대 PORT-MIS 신항
    f = next(p for n, p in files.items() if "incl_Busan" in n)
    a2 = _sin(f)
    busan_n = a2["547834"].rename("clk_busan_ships_7dma")
    g = pd.read_parquet(paths.CACHE / "grid_r1s.parquet")
    daily = g[["n_present", "n_wait", "n_berth"]].resample("1D").mean()
    daily_7 = daily.rolling(7, min_periods=5).mean()
    j = daily_7.join(busan_n, how="inner").dropna()
    out["busan_overlap_days"] = int(len(j))
    out["busan_period"] = [str(j.index.min().date()), str(j.index.max().date())]
    out["corr_busan_vs_newport_present"] = round(float(j["clk_busan_ships_7dma"].corr(j["n_present"])), 3)
    out["corr_busan_vs_newport_wait"] = round(float(j["clk_busan_ships_7dma"].corr(j["n_wait"])), 3)
    jm = j.resample("1MS").mean()
    out["corr_monthly_busan_vs_newport_present"] = round(float(jm["clk_busan_ships_7dma"].corr(jm["n_present"])), 3)
    # 2) 용선료로 본 대기 비용
    rates = {}
    for key, pat in (("1000TEU_6-12m", "C1_1000TEU_6-12m"), ("1700TEU_3yr", "C1_1700TEU"), ("9000TEU_6-12m", "C1_9000TEU_6-12m")):
        p = next(pp for n, pp in files.items() if pat in n)
        s = _sin(p).iloc[:, 0].dropna()
        rates[key] = {"latest": [str(s.index.max().date()), round(float(s.iloc[-1]))],
                      "mean_2025_07_on": round(float(s[s.index >= "2025-07-01"].mean()))}
    out["timecharter_usd_per_day"] = rates
    v = grid.voyages()
    pos = v[v["pos12"]]
    by_year = pos.groupby(pos["arrival_t"].dt.year)["wait_h"].agg(lambda s: float((s - 12).sum()))
    feeder = rates["1700TEU_3yr"]["mean_2025_07_on"]
    out["excess_wait_hours_by_year"] = {int(k): round(x) for k, x in by_year.items()}
    out["ship_side_cost_usd_by_year_at_1700TEU_rate"] = {int(k): round(x / 24 * feeder) for k, x in by_year.items()}
    out["note"] = ("선박 쪽 비용 근사: (대기 − 12시간) × 1,700TEU급 3년 정기용선료(시험 기간 평균, USD/일) ÷ 24. "
                   "선형별 차이·연료비·항비는 넣지 않았다. Clarksons Research 학술 구독 자료 — 외부 공개 금지.")
    paths.LOCAL_ONLY.mkdir(parents=True, exist_ok=True)
    (paths.LOCAL_ONLY / "clarksons_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["# Clarksons 비공개 점검 (외부 공개 금지)", "",
          f"- 부산 체류 척수(Clarksons A2, 7일 평균) 대 PORT-MIS 신항 체류 척수(7일 평균): 일별 상관 {out['corr_busan_vs_newport_present']}, 월별 {out['corr_monthly_busan_vs_newport_present']} ({out['busan_period'][0]}~{out['busan_period'][1]}, {out['busan_overlap_days']}일)",
          f"- 같은 비교, 신항 정박지 대기 척수: 일별 상관 {out['corr_busan_vs_newport_wait']}",
          f"- 정기용선료(USD/일): {json.dumps(rates, ensure_ascii=False)}",
          f"- 12시간 초과분 대기 시간 합계(연도별): {out['excess_wait_hours_by_year']}",
          f"- 선박 쪽 대기 비용 근사(USD, 1,700TEU급 용선료 기준): {out['ship_side_cost_usd_by_year_at_1700TEU_rate']}",
          f"- 주의: {out['note']}"]
    (paths.LOCAL_ONLY / "clarksons_check.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=1))
