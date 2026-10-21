"""Local, bounded synthetic prototype API. No authentication or public deployment.

Run: python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
A bounded synchronous computation is used in v0.2, not a production job queue.
"""
from __future__ import annotations
import copy
import json
import os
import subprocess
import threading
import time
import uuid
from collections import OrderedDict
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from engine import __version__
from engine.simulation import run_simulation
from engine.calibration import estimate_gamma
from .schemas import RunRequest, Observation, CalibrationRequest

ROOT=Path(__file__).resolve().parents[1]
app=FastAPI(title="R-Delay",version=__version__,description="Synthetic prototype; not for real dispatch")
app.mount("/static",StaticFiles(directory=ROOT/"web"),name="static")
STORE: OrderedDict[str,dict]=OrderedDict()
STORE_LOCK=threading.Lock()
COMPUTE_SLOT=threading.BoundedSemaphore(1)
MAX_RUNS=32


def source_commit():
    if os.environ.get("RDELAY_SOURCE_COMMIT"):
        return os.environ["RDELAY_SOURCE_COMMIT"]
    try:
        return subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True,timeout=2).strip()
    except (OSError,subprocess.SubprocessError):
        return "unavailable"

COMMIT=source_commit()

@app.middleware("http")
async def security_headers(request, call_next):
    response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["Referrer-Policy"]="no-referrer"
    response.headers["Cache-Control"]="no-store"
    # /docs is FastAPI's optional online-CDN Swagger interface. The actual
    # product UI at / uses local assets only and does not rely on /docs.
    if request.url.path!="/docs":
        response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
    return response

@app.get("/",include_in_schema=False)
def home():
    return FileResponse(ROOT/"web/index.html")

@app.get("/health")
def health():
    return {"status":"ok","version":__version__,"source_commit":COMMIT,
            "data_type":"synthetic","public_deployment":False}

@app.get("/api/v1/defaults")
def defaults():
    return RunRequest().model_dump(mode="json")


def compute(request: RunRequest, parent_id: str|None=None):
    if not COMPUTE_SLOT.acquire(blocking=False):
        raise HTTPException(429,"Calculation in progress; retry after completion")
    try:
        start=time.perf_counter()
        config=request.model_dump(mode="json")
        result=run_simulation(config)
        result.update({"run_id":uuid.uuid4().hex,"parent_id":parent_id,
                       "source_commit":COMMIT,"elapsed_seconds":time.perf_counter()-start,
                       "storage":"in-memory, maximum 32 runs; download JSON to preserve"})
        with STORE_LOCK:
            STORE[result["run_id"]]=copy.deepcopy(result)
            while len(STORE)>MAX_RUNS:
                STORE.popitem(last=False)
        return result
    except (ValueError,FloatingPointError) as exc:
        raise HTTPException(422,detail=str(exc)) from exc
    finally:
        COMPUTE_SLOT.release()

@app.post("/api/v1/runs",status_code=201)
def create_run(request:RunRequest):
    return compute(request)

@app.get("/api/v1/runs/{run_id}")
def get_run(run_id:str):
    with STORE_LOCK:
        value=STORE.get(run_id)
        if value is None:
            raise HTTPException(404,"Run not found or evicted from temporary memory")
        return copy.deepcopy(value)

@app.post("/api/v1/runs/{run_id}/observations",status_code=201)
def revise_observation(run_id:str,observation:Observation):
    old=get_run(run_id)
    config=copy.deepcopy(old["input"])
    # v0.2 explicitly reruns from the same seed replacing the single 10:00
    # observation. It does not claim arbitrary multi-time online assimilation.
    config["observation"]=observation.model_dump(mode="json")
    return compute(RunRequest.model_validate(config),parent_id=run_id)

@app.get("/api/v1/runs/{run_id}/artifacts")
def download_run(run_id:str):
    result=get_run(run_id)
    body=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False).encode("utf-8")
    return Response(body,media_type="application/json",headers={
        "Content-Disposition":f'attachment; filename="rdelay-{run_id}.json"'})

@app.post("/api/v1/calibrations")
def calibrate(request:CalibrationRequest):
    try:
        return {"data_type":"synthetic",**estimate_gamma(
            [o.model_dump() for o in request.observations],
            request.known_beta_land,request.known_coupling_lp)}
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from exc
