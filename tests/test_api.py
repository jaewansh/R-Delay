from __future__ import annotations
import json
import pytest
from fastapi.testclient import TestClient
from api.main import app,COMPUTE_SLOT
from api.schemas import RunRequest
from engine.calibration import synthetic_observations

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="module")
def saved(client):
    response=client.post("/api/v1/runs",json=RunRequest(particles=64).model_dump(mode="json"))
    assert response.status_code==201,response.text
    return response.json()


def test_local_ui_and_health(client):
    assert client.get("/health").json()["status"]=="ok"
    page=client.get("/")
    assert page.status_code==200 and "SIS" in page.text and "<math" in page.text
    for asset in ("app.js","styles.css"):
        assert client.get("/static/"+asset).status_code==200


def test_result_is_json_and_download_agrees(client,saved):
    result=client.get("/api/v1/runs/"+saved["run_id"]).json()
    raw=client.get("/api/v1/runs/"+saved["run_id"]+"/artifacts")
    assert json.loads(raw.content)==result==saved
    assert "attachment" in raw.headers["content-disposition"]
    assert result["source_commit"]
    assert len(result["reproducibility_sha256"])==64


def test_observation_revision_is_new_immutable_run(client,saved):
    observation=saved["input"]["observation"].copy();observation["value"]=14
    response=client.post("/api/v1/runs/"+saved["run_id"]+"/observations",json=observation)
    assert response.status_code==201,response.text
    new=response.json()
    assert new["run_id"]!=saved["run_id"] and new["parent_id"]==saved["run_id"]
    assert new["filter"]["posterior_mean"][1]>saved["filter"]["posterior_mean"][1]
    assert client.get("/api/v1/runs/"+saved["run_id"]).json()==saved

@pytest.mark.parametrize("patch",[{"particles":100000},{"kappa":-1},{"private_key":"secret"},{"data_type":"real"}])
def test_invalid_and_unpermitted_inputs(client,patch):
    c=RunRequest(particles=64).model_dump(mode="json");c.update(patch)
    assert client.post("/api/v1/runs",json=c).status_code==422


def test_future_data_refused(client):
    c=RunRequest(particles=64).model_dump(mode="json")
    c["observation"]["available_at"]="2026-10-21T11:00:00+09:00"
    assert client.post("/api/v1/runs",json=c).status_code==422


def test_calibration_endpoint_uses_supplied_observations(client):
    data={"observations":synthetic_observations()}
    response=client.post("/api/v1/calibrations",json=data)
    assert response.status_code==200
    assert response.json()["gamma_land_per_h"]==pytest.approx(.8999322754,abs=1e-8)


def test_missing_id_and_busy_guard(client):
    assert client.get("/api/v1/runs/nonexistent").status_code==404
    assert COMPUTE_SLOT.acquire(blocking=False)
    try:
        assert client.post("/api/v1/runs",json={"particles":64}).status_code==429
    finally:
        COMPUTE_SLOT.release()
