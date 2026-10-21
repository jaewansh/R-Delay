"""Public entrypoint checks; no hosted-service or field-performance claims."""
from __future__ import annotations
import json
import pytest
from fastapi.testclient import TestClient
from api.public import create_public_app


def client(**kwargs):
    return TestClient(create_public_app(allowed_hosts=["testserver"], **kwargs))


def test_public_ui_and_health():
    with client() as c:
        h = c.get("/health")
        assert h.status_code == 200
        assert h.json()["deployment_mode"] == "public-demo"
        assert h.json()["data_type"] == "synthetic"
        page = c.get("/")
        assert page.status_code == 200 and "공개용 합성 데모" in page.text
        assert "<math" in page.text
        assert "Python 엔진을 같은 컴퓨터에서 실행합니다." not in page.text
        assert c.get("/static/app.js").status_code == 200
        assert "Disallow: /" in c.get("/robots.txt").text
        assert "noindex" in page.headers["x-robots-tag"]
        assert "unsafe-eval" not in page.headers["content-security-policy"]


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"])
def test_online_docs_not_exposed(path):
    with client() as c:
        assert c.get(path).status_code == 404


def test_invalid_host_and_cross_origin():
    with client() as c:
        assert c.get("/health", headers={"host": "evil.invalid"}).status_code == 400
        for origin in ["https://evil.invalid", "null", "https://testserver.evil.invalid"]:
            assert c.post("/api/v1/runs", json={}, headers={"origin": origin}).status_code == 403
        assert c.post("/api/v1/runs", json={}, headers={"sec-fetch-site": "cross-site"}).status_code == 403


def test_json_only_and_declared_body_limit():
    with client() as c:
        assert c.post("/api/v1/runs", content="x=1").status_code == 415
        assert c.post("/api/v1/runs", json={}, headers={"content-length": "32769"}).status_code == 413
        assert c.post("/api/v1/runs", json={}, headers={"content-length": "invalid"}).status_code == 400


def test_streamed_body_limit_cannot_be_bypassed():
    with client() as c:
        chunks = iter([b"x" * 20000, b"x" * 20000])
        response = c.post("/api/v1/runs", content=chunks,
                          headers={"content-type": "application/json"})
        assert response.status_code == 413


def test_shared_rate_budget_and_expiry():
    clock = [0.0]
    with client(requests_per_minute=2, clock=lambda: clock[0]) as c:
        for _ in range(2):
            assert c.post("/api/v1/runs", json={"data_type": "private"}).status_code == 422
        response = c.post("/api/v1/runs", json={"particles": 64})
        assert response.status_code == 429 and response.headers["retry-after"] == "60"
        assert c.get("/health").status_code == 200
        clock[0] = 61
        assert c.post("/api/v1/runs", json={"data_type": "private"}).status_code == 422


def test_real_python_result_and_download_through_public_entry():
    with client() as c:
        response = c.post("/api/v1/runs", json={"particles": 64},
                          headers={"origin": "https://testserver"})
        assert response.status_code == 201, response.text
        value = response.json()
        run_id = value["run_id"]
        artifact = c.get(f"/api/v1/runs/{run_id}/artifacts")
        assert artifact.status_code == 200
        assert json.loads(artifact.content) == value
        assert value["input"]["data_type"] == "synthetic"
        assert len(value["reproducibility_sha256"]) == 64
