"""Render/native runtime entrypoint. Starts one process; never starts a tunnel."""
from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
port = int(os.environ.get("PORT", "10000"))
if not 1 <= port <= 65535:
    raise SystemExit("PORT must be in 1..65535")
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(key, "1")
os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "api.public:app",
    "--host", "0.0.0.0", "--port", str(port), "--workers", "1",
    "--limit-concurrency", "24", "--backlog", "32", "--timeout-keep-alive", "5",
    "--no-access-log"])
