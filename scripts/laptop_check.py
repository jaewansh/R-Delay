"""내 컴퓨터(Windows·Mac)에서 실자료 분석을 돌리기 전 점검. 표준 라이브러리만으로 먼저 돈다.

  python scripts/laptop_check.py          # Windows
  python3 scripts/laptop_check.py         # Mac

점검: 파이썬·패키지 → .env와 자료 폴더 → 필요한 자료 파일 → 발표 숫자를 만든 자료와 같은지 → 한글 글꼴 → 디스크.
끝에 이 컴퓨터에서 쓸 실행 명령을 보여 준다. 아무것도 고치거나 내려받지 않는다.
"""
from __future__ import annotations

import ast
import csv
import importlib
import json
import os
import pathlib
import platform
import shutil
import subprocess
import sys
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parents[1]
WIN = platform.system() == "Windows"
PY = "python" if WIN else "python3"

for _s in (sys.stdout, sys.stderr):  # 콘솔이 CP949여도 멈추지 않게
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass

PROBLEMS: list[str] = []
NOTES: list[str] = []


def ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def warn(msg: str) -> None:
    print(f"  [!!] {msg}")
    NOTES.append(msg)


def bad(msg: str) -> None:
    print(f"  [XX] {msg}")
    PROBLEMS.append(msg)


def head(title: str) -> None:
    print(f"\n== {title}")


# ── 1. 파이썬·패키지 ─────────────────────────────────────────────────────────
def check_python() -> bool:
    head("1. 파이썬과 패키지")
    v = sys.version_info
    where = sys.executable
    if v < (3, 10):
        bad(f"Python {platform.python_version()} — 3.11 이상이 필요합니다. 실행 파일: {where}")
    elif v < (3, 11):
        warn(f"Python {platform.python_version()} — 3.11 이상을 권합니다(pandas 3은 3.11부터). 실행 파일: {where}")
    else:
        ok(f"Python {platform.python_version()} ({platform.system()} {platform.machine()}) · {where}")
    if sys.prefix == sys.base_prefix:
        warn("가상환경(.venv) 밖입니다. 다른 프로젝트와 패키지가 섞이지 않게 .venv를 권합니다(RUN_LOCAL.md 2절).")
    need = [("numpy", "numpy"), ("pandas", "pandas"), ("scikit-learn", "sklearn"), ("scipy", "scipy"),
            ("matplotlib", "matplotlib"), ("pyarrow", "pyarrow"), ("holidays", "holidays"), ("openpyxl", "openpyxl"),
            ("pytest", "pytest")]
    missing = []
    vers = []
    have: dict[str, tuple[int, int]] = {}
    for pip_name, mod in need:
        try:
            m = importlib.import_module(mod)
            ver = str(getattr(m, "__version__", "?"))
            vers.append(f"{pip_name} {ver}")
            have[pip_name] = _mm(ver)
        except Exception:
            missing.append(pip_name)
    if vers:
        ok(" · ".join(vers))
    if missing:
        bad(f"없는 패키지: {', '.join(missing)} → {py_cmd()} -m pip install -r requirements.txt -r requirements-backtest.txt")
        return False
    # 발표·웹 숫자가 소수 끝자리까지 같게 나오는 것을 확인한 판(Python 3.11·3.13). 더 오래된 판도 돌지만
    # (예: pandas 2.2·scikit-learn 1.5) 일부 숫자가 셋째 자리에서 달라진다(PR-AUC 0.193 → 0.192 등).
    old = [f"{k} {'.'.join(map(str, have[k]))} < {'.'.join(map(str, v))}" for k, v in VERIFIED.items() if have.get(k, v) < v]
    if old:
        warn(f"발표 숫자 재현을 확인한 판보다 오래됨({', '.join(old)}). 돌기는 하지만 숫자가 셋째 자리에서 조금 다를 수 있습니다. "
             f"같게 하려면: {py_cmd()} -m pip install -U -r requirements.txt -r requirements-backtest.txt")
    else:
        ok("발표·웹 숫자를 그대로 재현한 것을 확인한 판(numpy 2.4 이상 · pandas 3 · scikit-learn 1.9 이상)")
    return True


VERIFIED = {"numpy": (2, 4), "pandas": (3, 0), "scikit-learn": (1, 9)}


def _mm(ver: str) -> tuple[int, int]:
    """'3.1.1' → (3, 1). 숫자가 아니면 (0, 0)."""
    parts = []
    for p in ver.split(".")[:2]:
        digits = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple((parts + [0, 0])[:2])  # type: ignore[return-value]


# ── 2. .env와 자료 폴더 ───────────────────────────────────────────────────────
def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    p = ROOT / ".env"
    if p.exists():
        try:
            text = p.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            bad(".env를 UTF-8로 읽지 못했습니다. 메모장에서 '다른 이름으로 저장' → 인코딩 UTF-8로 다시 저장하세요.")
            return env
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("RDELAY_DATA_ROOT", "RDELAY_PUBLIC_DIR", "RDELAY_CLARKSONS_DIR", "RDELAY_FONT_DIR"):
        if os.environ.get(k):
            env.setdefault(k, os.environ[k])
    return env


def check_env(env: dict[str, str]) -> tuple[pathlib.Path | None, pathlib.Path | None]:
    head("2. .env와 자료 폴더")
    for d in ("realdata", "realdata_ship", "docs/py/rdelay", "data-kit"):
        if not (ROOT / d).is_dir():
            bad(f"저장소 폴더에 {d}/가 없습니다. 저장소 맨 위 폴더에서 실행했는지, 최신 코드인지 확인하세요({ROOT}).")
    if not (ROOT / ".env").exists():
        bad(f"{ROOT / '.env'} 파일이 없습니다. 첫 줄에 RDELAY_DATA_ROOT=<RDelay_Data/Raw_data 폴더>를 적어 만드세요.")
        return None, None
    v = env.get("RDELAY_DATA_ROOT", "")
    if not v:
        bad(".env에 RDELAY_DATA_ROOT=<RDelay_Data/Raw_data 폴더>가 없습니다.")
        return None, None
    root = pathlib.Path(v).expanduser()
    if not root.is_dir():
        bad(f"RDELAY_DATA_ROOT 폴더가 없습니다: {root}")
        return None, None
    ok(f"RDELAY_DATA_ROOT = {root}")
    pv = env.get("RDELAY_PUBLIC_DIR", "")
    pub = pathlib.Path(pv).expanduser() if pv else (root / "public_data" if (root / "public_data").is_dir() else root)
    if not pub.is_dir():
        bad(f"공개 자료 폴더가 없습니다: {pub}")
        return root, None
    ok(f"공개 자료 폴더 = {pub}")
    return root, pub


# ── 3. 자료 파일 ──────────────────────────────────────────────────────────
def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def files(folder: pathlib.Path, suffix: str = ".csv", contains: str = "") -> list[pathlib.Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir()
                  if p.is_file() and p.name.lower().endswith(suffix) and nfc(contains) in nfc(p.name) and p.stat().st_size > 0)


def read_header(path: pathlib.Path) -> list[str]:
    for enc in ("utf-8-sig", "cp949"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return next(csv.reader(f))
        except (UnicodeDecodeError, StopIteration):
            continue
    return []


def check_files(pub: pathlib.Path, root: pathlib.Path) -> dict:
    head("3. 자료 파일")
    info: dict = {}
    vpath = pub / "derived" / "newport_voyages.csv"
    if vpath.exists():
        cols = read_header(vpath)
        need = {"clsgn", "arrival_t", "berth_t", "wait_h", "vsslGrtg", "berth_facility"}
        if need - set(cols):
            bad(f"newport_voyages.csv에 열이 없습니다: {sorted(need - set(cols))}")
        else:
            n, last = 0, ""
            with open(vpath, encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f):
                    n += 1
                    last = max(last, r.get("berth_t") or "")
            info.update(voyages=n, berth_max=last[:16])
            ok(f"대기 라벨 derived/newport_voyages.csv: {n:,}항차, 마지막 접안 {last[:16]}")
    else:
        bad(f"정답 라벨이 없습니다: {vpath} (data-kit/build_wait_labels.py로 만듦)")
    for rel, what, needed in (("derived/ex_speed_busan.csv", "도로 1시간 속도", True),
                              ("derived/newport_waiting_2h.csv", "2시간 대기 척수(주 분석)", False)):
        p = pub / rel
        if p.exists():
            ok(f"{what} {rel} ({p.stat().st_size / 1e6:.0f} MB)")
        elif needed:
            bad(f"{what}가 없습니다: {p}")
        else:
            warn(f"{what}가 없습니다: {p}")
    cntl = files(pub / "portmis" / "cntl" / "daily")
    if cntl:
        ok(f"관제정보 portmis/cntl/daily: {len(cntl):,}일 ({cntl[0].stem} ~ {cntl[-1].stem})")
        info["cntl_last_file"] = cntl[-1].stem
        last_t = ""
        print("  ...  관제정보의 마지막 이벤트 시각 확인 중(파일 전체, 수 초~수십 초)", flush=True)
        for p in cntl:  # 일별 파일은 입항일 기준이라 오래 머문 배의 최근 이벤트가 옛 파일에 들어 있다 → 전부 본다
            for enc in ("utf-8-sig", "cp949"):
                try:
                    with open(p, encoding=enc, newline="") as f:
                        for r in csv.DictReader(f):
                            d = "".join(ch for ch in (r.get("cntrlOpertDt") or "") if ch.isdigit())
                            if len(d) >= 12:
                                last_t = max(last_t, d[:12])
                    break
                except UnicodeDecodeError:
                    continue
        if last_t:
            info["cntl_last_t"] = f"{last_t[:4]}-{last_t[4:6]}-{last_t[6:8]} {last_t[8:10]}:{last_t[10:12]}"
    else:
        bad(f"관제정보 일별 파일이 없습니다: {pub / 'portmis' / 'cntl' / 'daily'}")
    vssl = files(pub / "portmis" / "vssl" / "daily")
    (ok if vssl else warn)(f"선박운항정보 portmis/vssl/daily: {len(vssl):,}일(주 분석에서 씀)")
    for rel, contains, what in (("manual/kma_asos", "", "ASOS 시간자료"), ("manual/kma_buoy", "", "해양기상부이"),
                                ("manual/kma_typhoon", "경로", "태풍경로"), ("manual/kma_typhoon", "목록", "태풍목록")):
        fs = files(pub / rel, contains=contains)
        if fs:
            ok(f"{what} {rel}: 파일 {len(fs)}개")
        else:
            bad(f"{what} 파일이 없습니다: {pub / rel}" + (f" (이름에 '{contains}' 포함)" if contains else ""))
    bpa = files(pub / "manual" / "bpa_vessel_calls")
    (ok if bpa else warn)(f"부산항만공사 입출항 집계 manual/bpa_vessel_calls: 파일 {len(bpa)}개(주 분석에서 씀)")
    clk = [p for p in root.rglob("CLK_*.xlsx")] if root else []
    if clk:
        ok(f"Clarksons(공개 금지, 선택) CLK_*.xlsx {len(clk)}개 — 결과는 local_only/에만")
    else:
        warn("Clarksons 파일(CLK_*.xlsx)을 찾지 못했습니다. 선택 분석이라 다른 실행에는 영향이 없습니다.")
    return info


# ── 4. 발표 숫자를 만든 자료와 같은지 ──────────────────────────────────────────────
def check_snapshot(info: dict) -> None:
    head("4. 발표·웹 숫자를 만든 자료와 비교")
    try:
        ref = json.loads((ROOT / "realdata_ship" / "results" / "test_results.json").read_text(encoding="utf-8"))
        summ = json.loads((ROOT / "realdata_ship" / "results" / "summary.json").read_text(encoding="utf-8"))
    except Exception:
        warn("저장소의 결과 파일(realdata_ship/results)을 읽지 못해 비교를 건너뜁니다.")
        return
    ref_end, ref_n = str(ref.get("data_end", ""))[:16], summ.get("data", {}).get("voyages")
    here_end = max(info.get("berth_max", ""), info.get("cntl_last_t", ""))
    print(f"  저장소 결과: 항차 {ref_n:,} · 자료 끝 {ref_end}")
    print(f"  이 컴퓨터  : 항차 {info.get('voyages', 0):,} · 자료 끝 {here_end or '?'}")
    if info.get("voyages") == ref_n and here_end == ref_end:
        ok("같은 자료로 보입니다(항차 수·자료 끝이 같음). 다시 돌리면 발표·웹과 같은 숫자가 나와야 합니다(그림 글꼴만 다를 수 있음).")
    else:
        warn("자료가 저장소 결과를 만든 것과 다릅니다(보통 더 최신). 다시 돌리면 시험 기간이 늘어 숫자가 조금 바뀌고, "
             "README·REPORT·MODEL·웹 자료(docs/data/backtest_ship.json)도 새 숫자로 다시 써집니다.")


# ── 5. 글꼴·디스크·git ──────────────────────────────────────────────────────
def check_misc(env: dict[str, str], pkgs_ok: bool) -> None:
    head("5. 한글 글꼴 · 디스크 · git")
    if pkgs_ok:
        try:
            from matplotlib import font_manager as fm
            extra = env.get("RDELAY_FONT_DIR", "")
            if extra and pathlib.Path(extra).expanduser().is_dir():
                for f in pathlib.Path(extra).expanduser().glob("*.[ot]tf"):
                    fm.fontManager.addfont(str(f))
            have = {f.name for f in fm.fontManager.ttflist}
            src = (ROOT / "realdata_ship" / "report.py").read_text(encoding="utf-8")  # 그림에 쓰는 글꼴 순서와 같게(가져오지 않고 읽기만)
            fonts = next(ast.literal_eval(n.value) for n in ast.parse(src).body
                         if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "FONTS")
            name = next((n for n in fonts if n in have), None)
            if name:
                ok(f"그림 한글 글꼴: {name}")
            else:
                warn("한글 글꼴을 찾지 못했습니다. 그림 글자가 네모로 보일 수 있습니다(숫자 결과는 같음).")
        except Exception as e:  # noqa: BLE001
            warn(f"글꼴 점검을 건너뜁니다: {e}")
    free = shutil.disk_usage(ROOT).free / 1e9
    (ok if free >= 3 else warn)(f"저장소 디스크 여유 {free:.1f} GB(캐시·중간 결과에 약 1 GB)")
    try:
        head_ = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10)
        if head_.returncode == 0:
            br = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
            ok(f"git {br or '(분리된 HEAD)'} @ {head_.stdout.strip()}")
        else:
            warn("git 저장소가 아닙니다(zip으로 받은 경우). 실행에는 문제없고, 결과의 '커밋' 표시만 비게 됩니다.")
    except Exception:
        warn("git이 없습니다. 실행에는 문제없고, 결과의 '커밋' 표시만 비게 됩니다.")


def main() -> int:
    print(f"R-Delay 노트북 점검 · 저장소 {ROOT}")
    pkgs_ok = check_python()
    env = load_env()
    root, pub = check_env(env)
    if root and pub:
        info = check_files(pub, root)
        check_snapshot(info)
    check_misc(env, pkgs_ok)
    print()
    if PROBLEMS:
        print(f"고칠 것 {len(PROBLEMS)}개(위 [XX]). 고친 뒤 다시 점검하세요.")
        return 1
    py = py_cmd()
    print(f"준비 끝. 저장소 맨 위 폴더({ROOT})에서:")
    print(f"  {py} -m realdata_ship.run_all        # 선박별 하루 전 경보(두 번째 분석), 약 10분 안팎")
    print(f"  {py} -m realdata.run_all --dry-run   # 주 분석(항만 전체 24시간 경보): 새 자료가 있는지만 보기")
    print(f"  {py} -m pytest -q                    # 테스트")
    if NOTES:
        print(f"참고 {len(NOTES)}개(위 [!!])는 실행을 막지 않습니다.")
    return 0


def py_cmd() -> str:
    """이 점검을 돌린 파이썬(패키지가 확인된 것)을 부르는 명령. 저장소 안 .venv면 짧게 쓴다."""
    exe = pathlib.Path(sys.executable)
    try:
        rel = exe.relative_to(ROOT)  # 예: Windows .venv\Scripts\python, Mac .venv/bin/python
        return str(rel.with_suffix("")) if WIN else str(rel)
    except ValueError:
        pass
    on_path = shutil.which(PY)
    if on_path and sys.prefix != sys.base_prefix and pathlib.Path(on_path).resolve() == exe.resolve():
        return PY  # 가상환경을 켠 상태
    return f'"{exe}"' if " " in str(exe) else str(exe)


if __name__ == "__main__":
    sys.exit(main())
