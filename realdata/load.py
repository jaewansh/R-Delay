"""자료별 읽기 함수. 모든 시각은 한국시간(시간대 없는 datetime)이다."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from . import paths
from .io import cached, glob_nfc, read_csv_any

P = paths.public


def _digits_dt(s: pd.Series) -> pd.Series:
    d = s.astype("string").str.replace(r"[^0-9]", "", regex=True)
    return pd.to_datetime(d.str.slice(0, 12).str.pad(12, side="right", fillchar="0"), format="%Y%m%d%H%M", errors="coerce")


# ── 라벨(사용자가 data-kit build_wait_labels.py로 만든 파일) ─────────────────────
def voyages() -> pd.DataFrame:
    src = P() / "derived" / "newport_voyages.csv"

    def build():
        v = read_csv_any(src, dtype={"clsgn": str, "etryptYear": str, "etryptCo": str})
        for c in ("arrival_t", "berth_t"):
            v[c] = pd.to_datetime(v[c], errors="coerce")
        v["wait_h"] = pd.to_numeric(v["wait_h"], errors="coerce")
        v["gt"] = pd.to_numeric(v["vsslGrtg"], errors="coerce")
        return v

    return cached("voyages", [src], build, version=2)


def waiting2h() -> pd.DataFrame:
    src = P() / "derived" / "newport_waiting_2h.csv"

    def build():
        w = read_csv_any(src)
        w["t"] = pd.to_datetime(w["t"])
        return w

    return cached("waiting2h", [src], build)


# ── PORT-MIS ───────────────────────────────────────────────────────────────
_CNTL_KEEP = ["clsgn", "etryptYear", "etryptCo", "vsslKndNm", "vsslNm", "vsslGrtg", "vsslNltyNm",
              "aprtfEtryptDt", "tkoffDt", "cntrlNm", "cntrlSe", "cntrlOpertDt", "fcltyCd", "fcltySubCd", "fcltyNm",
              "harborEntrpsNm"]


def cntl() -> pd.DataFrame:
    files = sorted((P() / "portmis" / "cntl" / "daily").glob("*.csv"))

    def build():
        frames = []
        for f in files:
            if f.stat().st_size < 10:
                continue
            d = read_csv_any(f, dtype=str, keep_default_na=False)
            d = d.reindex(columns=_CNTL_KEEP, fill_value="")
            d["file_date"] = f.stem
            frames.append(d)
        df = pd.concat(frames, ignore_index=True).drop_duplicates()
        df["t"] = _digits_dt(df["cntrlOpertDt"])
        df["gt"] = pd.to_numeric(df["vsslGrtg"], errors="coerce")
        for c in ("aprtfEtryptDt", "tkoffDt"):
            df[c + "_t"] = _digits_dt(df[c])
        return df.dropna(subset=["t"]).sort_values("t", kind="stable").reset_index(drop=True)

    return cached("cntl", files, build, version=2)


def vssl() -> pd.DataFrame:
    files = sorted((P() / "portmis" / "vssl" / "daily").glob("*.csv"))

    def build():
        frames = [read_csv_any(f, dtype=str, keep_default_na=False).assign(file_date=f.stem)
                  for f in files if f.stat().st_size >= 10]
        df = pd.concat(frames, ignore_index=True).drop_duplicates()
        for c in ("etryptDt", "tkoffDt", "tkoffPrrrnDt", "dstnEtryptDt"):
            if c in df:
                df[c + "_t"] = _digits_dt(df[c])
        for c in ("grtg", "intrlGrtg", "ldadngTon", "trnpdtTon", "landngFrghtTon", "ldFrghtTon"):
            if c in df:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        return df

    return cached("vssl", files, build, version=1)


# ── 기상 ─────────────────────────────────────────────────────────────────
def _pick(df: pd.DataFrame, names: dict[str, str]) -> pd.DataFrame:
    out = {}
    for new, pat in names.items():
        col = next((c for c in df.columns if re.search(pat, c)), None)
        out[new] = df[col] if col is not None else np.nan
    return pd.DataFrame(out)


def asos() -> pd.DataFrame:
    """종관기상관측 시간자료(부산 159·울산 152·창원 155). 긴 형식."""
    files = glob_nfc(P() / "manual" / "kma_asos", "*.csv")

    def build():
        frames = []
        for f in files:
            d = read_csv_any(f)
            frames.append(_pick(d, {"stn": r"^지점$", "t": r"^일시$", "temp": r"^기온", "rain": r"^강수량\(", "wind": r"^풍속",
                                    "wdir": r"^풍향", "rh": r"^습도", "pres": r"^현지기압", "slp": r"^해면기압",
                                    "vis": r"^시정"}))
        df = pd.concat(frames, ignore_index=True)
        df["t"] = pd.to_datetime(df["t"], errors="coerce")
        df["stn"] = pd.to_numeric(df["stn"], errors="coerce").astype("Int64")
        for c in ("temp", "rain", "wind", "wdir", "rh", "pres", "slp", "vis"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df.dropna(subset=["t"]).drop_duplicates(["stn", "t"]).sort_values(["stn", "t"]).reset_index(drop=True)

    return cached("asos", files, build, version=1)


def buoy() -> pd.DataFrame:
    """해양기상부이 시간자료(거제도 22104 등). 긴 형식."""
    files = glob_nfc(P() / "manual" / "kma_buoy", "*.csv")

    def build():
        frames = []
        for f in files:
            d = read_csv_any(f)
            frames.append(_pick(d, {"stn": r"^지점$", "t": r"^일시$", "wind": r"^풍속", "gust": r"^GUST", "pres": r"^현지기압",
                                    "hs": r"^유의파고", "hmax": r"^최대파고", "period": r"^파주기", "wdir": r"^풍향"}))
        df = pd.concat(frames, ignore_index=True)
        df["t"] = pd.to_datetime(df["t"], errors="coerce")
        df["stn"] = pd.to_numeric(df["stn"], errors="coerce").astype("Int64")
        for c in ("wind", "gust", "pres", "hs", "hmax", "period", "wdir"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        return df.dropna(subset=["t"]).drop_duplicates(["stn", "t"]).sort_values(["stn", "t"]).reset_index(drop=True)

    return cached("buoy", files, build, version=1)


def _latlon(s: pd.Series, pos: str, neg: str) -> pd.Series:
    x = s.astype("string").str.strip()
    val = pd.to_numeric(x.str.replace(r"[^0-9.]", "", regex=True), errors="coerce")
    return val.where(~x.str.endswith(neg), -val)


def typhoon_track() -> pd.DataFrame:
    files = glob_nfc(P() / "manual" / "kma_typhoon", "*경로*.csv")

    def build():
        d = pd.concat([read_csv_any(f) for f in files], ignore_index=True)
        out = pd.DataFrame({
            "year": pd.to_numeric(d["년도"], errors="coerce").astype("Int64"),
            "no": pd.to_numeric(d["태풍번호"], errors="coerce").astype("Int64"),
            "t": pd.to_datetime(d["분석시각"], errors="coerce"),
            "lat": _latlon(d["위도"], "N", "S"),
            "lon": _latlon(d["경도"], "E", "W"),
            "grade": d["태풍등급"].astype(str),
        })
        return out.dropna(subset=["t", "lat", "lon"]).sort_values(["year", "no", "t"]).reset_index(drop=True)

    return cached("typhoon_track", files, build, version=1)


def typhoon_list() -> pd.DataFrame:
    files = glob_nfc(P() / "manual" / "kma_typhoon", "*목록*.csv")

    def build():
        d = pd.concat([read_csv_any(f) for f in files], ignore_index=True)
        d["start"] = pd.to_datetime(d["발생"], format="%Y.%m.%d %H:%M", errors="coerce")
        d["end"] = pd.to_datetime(d["소멸"], format="%Y.%m.%d %H:%M", errors="coerce")
        d["year"] = d["start"].dt.year.astype("Int64")
        d["no"] = pd.to_numeric(d["태풍번호"], errors="coerce").astype("Int64")
        return d

    return cached("typhoon_list", files, build, version=1)


# ── 도로(한국도로공사 1시간 구간속도, 신항 배후 구간만 추린 파일) ──────────────────
def road() -> pd.DataFrame:
    src = P() / "derived" / "ex_speed_busan.csv"

    def build():
        d = read_csv_any(src, usecols=["집계일자", "집계시", "콘존ID", "콘존명", "차로유형구분코드", "평균속도"],
                         dtype={"콘존ID": str, "콘존명": str})
        hour = pd.to_numeric(d["집계시"], errors="coerce")
        t = pd.to_datetime(d["집계일자"], errors="coerce") + pd.to_timedelta(hour, unit="h")
        sp = pd.to_numeric(d["평균속도"], errors="coerce")
        out = pd.DataFrame({"t": t, "hour_raw": hour, "zone": d["콘존ID"], "name": d["콘존명"],
                            "lane": pd.to_numeric(d["차로유형구분코드"], errors="coerce").astype("Int64"),
                            "speed": sp.where(sp > 0)})  # 0은 측정 없음으로 본다
        return out.dropna(subset=["t"]).reset_index(drop=True)

    return cached("road", [src], build, version=1)


# ── 부산항만공사 선박 입출항 집계(2019~2024) ────────────────────────────────────
def bpa_calls() -> pd.DataFrame:
    files = glob_nfc(P() / "manual" / "bpa_vessel_calls", "*.csv")

    def build():
        d = pd.concat([read_csv_any(f, dtype=str) for f in files], ignore_index=True)
        for c in ("입항일시", "출항일시", "출항예정일시", "전출항지출항일시"):
            d[c + "_t"] = pd.to_datetime(d[c], errors="coerce")
        d["gt"] = pd.to_numeric(d["총톤수"], errors="coerce")
        return d

    return cached("bpa_calls", files, build, version=1)
