"""읽기 공통: 인코딩 판별(utf-8-sig → cp949), 원본이 바뀌었을 때만 다시 만드는 parquet 캐시."""
from __future__ import annotations

import hashlib
import json
import pathlib
import unicodedata
from typing import Callable, Iterable

import pandas as pd

from . import paths


def read_csv_any(path: pathlib.Path, **kw) -> pd.DataFrame:
    last = None
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False, **kw)
        except UnicodeDecodeError as e:
            last = e
    raise last  # type: ignore[misc]


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def glob_nfc(folder: pathlib.Path, pattern: str) -> list[pathlib.Path]:
    """macOS에서 압축한 파일은 한글 이름이 NFD일 수 있어 NFC로 비교한다."""
    pat = nfc(pattern)
    return sorted(p for p in folder.iterdir() if p.is_file() and pathlib.PurePath(nfc(p.name)).match(pat))


def _manifest(sources: Iterable[pathlib.Path]) -> str:
    h = hashlib.sha1()
    for p in sorted(sources):
        st = p.stat()
        h.update(f"{nfc(p.name)}|{st.st_size}|{int(st.st_mtime)}".encode())
    return h.hexdigest()


def cached(name: str, sources: list[pathlib.Path], build: Callable[[], pd.DataFrame], version: int = 1) -> pd.DataFrame:
    """원본 파일 목록·크기·수정시각과 빌더 버전이 같으면 캐시를 쓴다."""
    paths.ensure_dirs()
    pq = paths.CACHE / f"{name}.parquet"
    meta = paths.CACHE / f"{name}.json"
    key = f"v{version}:{_manifest(sources)}"
    if pq.exists() and meta.exists():
        try:
            if json.loads(meta.read_text(encoding="utf-8")).get("key") == key:
                return pd.read_parquet(pq)
        except Exception:
            pass
    df = build()
    df.to_parquet(pq, index=False)
    paths.write_text(meta, json.dumps({"key": key, "rows": int(len(df)), "sources": len(sources)}, ensure_ascii=False))
    return df
