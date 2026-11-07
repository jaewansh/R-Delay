"""경로: 자료 위치는 코드에 박지 않고 환경변수·.env에서 읽는다."""
from __future__ import annotations

import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG = ROOT / "realdata_ship"
CACHE = PKG / "cache"
RESULTS = PKG / "results"
REPORTS = PKG / "reports"
LOCAL_ONLY = ROOT / "local_only"          # Clarksons 결과(공개 금지)
PRESENTATION = ROOT / "presentation" / "ship"   # 발표 작업물(gitignore)

for _s in (sys.stdout, sys.stderr):  # Windows 콘솔(CP949)에서도 출력이 멈추지 않게
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass


def _load_env(path: pathlib.Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()


def data_root() -> pathlib.Path:
    v = os.environ.get("RDELAY_DATA_ROOT", "").strip()
    if not v:
        raise SystemExit("[중단] RDELAY_DATA_ROOT가 없습니다. 저장소 루트 .env에 RDELAY_DATA_ROOT=<RDelay_Data/Raw_data 경로>를 적으세요.")
    p = pathlib.Path(v).expanduser()
    if not p.exists():
        raise SystemExit(f"[중단] 자료 폴더가 없습니다: {p}")
    return p


def public() -> pathlib.Path:
    """공개 자료 폴더(derived/ portmis/ manual/). data-kit의 RDELAY_DATA_DIR와 같은 구조."""
    p = data_root() / "public_data"
    return p if p.exists() else data_root()


def clarksons_dir() -> pathlib.Path | None:
    """Clarksons xlsx가 있는 폴더(없으면 None). 하위 폴더 구조가 달라도 찾는다."""
    v = os.environ.get("RDELAY_CLARKSONS_DIR", "").strip()
    if v and pathlib.Path(v).exists():
        return pathlib.Path(v)
    hits = sorted(data_root().rglob("CLK_A1_*.xlsx"))
    return hits[0].parent.parent if hits else None


def ensure_dirs() -> None:
    for d in (CACHE, RESULTS, REPORTS):
        d.mkdir(parents=True, exist_ok=True)
