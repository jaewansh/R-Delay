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
    """공개 자료 폴더(derived/ portmis/ manual/). data-kit의 RDELAY_DATA_DIR와 같은 구조.

    주 분석(realdata/paths.py)과 같은 규칙: RDELAY_PUBLIC_DIR가 있으면 그 폴더, 없으면 RDELAY_DATA_ROOT/public_data.
    """
    v = os.environ.get("RDELAY_PUBLIC_DIR", "").strip()
    if v:
        return pathlib.Path(v).expanduser()
    p = data_root() / "public_data"
    return p if p.exists() else data_root()


def clarksons_dir() -> pathlib.Path | None:
    """Clarksons xlsx(CLK_*.xlsx)가 있는 폴더(없으면 None). A1_…·A2_… 같은 하위 폴더에 나뉘어 있어도 찾는다."""
    v = os.environ.get("RDELAY_CLARKSONS_DIR", "").strip()
    if v and pathlib.Path(v).expanduser().exists():
        return pathlib.Path(v).expanduser()
    root = data_root()
    return root if next(root.rglob("CLK_*.xlsx"), None) is not None else None


def write_text(path: pathlib.Path, text: str) -> None:
    """UTF-8·LF로 쓴다. Windows에서도 줄바꿈이 CRLF로 바뀌어 git에 파일 전체 변경으로 잡히지 않게 한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def ensure_dirs() -> None:
    for d in (CACHE, RESULTS, REPORTS):
        d.mkdir(parents=True, exist_ok=True)
