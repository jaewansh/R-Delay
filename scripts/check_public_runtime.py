"""Test the actual public entrypoint locally, or an explicitly supplied HTTPS URL.

Uses real HTTP and Chromium. No result mocking. Local success is NOT a hosted
Render deployment. This command does not create any cloud resource.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/public_deploy"
OUT.mkdir(parents=True, exist_ok=True)
parser = argparse.ArgumentParser()
parser.add_argument("--url", help="Actual allocated HTTPS service URL, never a guessed hostname")
args = parser.parse_args()
base = args.url.rstrip("/") if args.url else "http://127.0.0.1:8766"
if args.url and (urlsplit(base).scheme != "https" or urlsplit(base).username):
    raise SystemExit("An explicitly supplied public URL must be HTTPS without credentials")
process = None
report = {"started_at": datetime.now(timezone.utc).isoformat(), "base_url": base,
          "hosted_url_requested": bool(args.url), "public_url_verified": False,
          "source_commit": os.environ.get("RDELAY_SOURCE_COMMIT", "unavailable"),
          "checks": [], "api_mocked": False, "visual_review": "not performed"}

def check(name, condition):
    report["checks"].append({"name": name, "passed": bool(condition)})
    if not condition:
        raise AssertionError(name)

try:
    if not args.url:
        process = subprocess.Popen([sys.executable, "scripts/start_public.py"],
            cwd=ROOT, env={**os.environ, "PORT": "8766"})
    for attempt in range(60):
        try:
            with urllib.request.urlopen(base + "/health", timeout=10) as response:
                health = json.load(response)
            break
        except Exception:
            if process and process.poll() is not None:
                raise RuntimeError("local server exited")
            time.sleep(1)
    else:
        raise RuntimeError("health check did not become ready")
    check("public entrypoint health", health.get("deployment_mode") == "public-demo")
    report["runtime_health"] = health
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(base, wait_until="networkidle", timeout=120000)
        expect(page.get_by_text("공개용 합성 데모", exact=True)).to_be_visible()
        page.get_by_text("계산 재현 설정", exact=True).click()
        page.locator("#particles").select_option("64")
        with page.expect_response(lambda r: r.url.endswith("/api/v1/runs") and r.request.method == "POST", timeout=120000) as awaited:
            page.locator("#run-button").click()
        result_response = awaited.value
        check("actual public API calculation", result_response.status == 201)
        result = result_response.json()
        expect(page.locator("#results")).to_be_visible(timeout=120000)
        expect(page.locator("#candidate-body tr")).to_have_count(3)
        check("native SIS math visible", page.locator("math").is_visible())
        with page.expect_download(timeout=30000) as awaited_download:
            page.locator("#download-button").click()
        download_path = OUT / "public_download.json"
        awaited_download.value.save_as(str(download_path))
        check("download equals actual Python response", json.loads(download_path.read_text()) == result)
        page.screenshot(path=str(OUT / "public_desktop.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.screenshot(path=str(OUT / "public_mobile.png"), full_page=True)
        check("mobile page has no horizontal overflow", page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"))
        check("no uncaught JavaScript error", not errors)
        report["browser_version"] = browser.version
        browser.close()
    report["passed"] = True
    report["public_url_verified"] = bool(args.url)
except Exception as exc:
    report["passed"] = False
    report["error"] = repr(exc)
    raise
finally:
    if process:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    (OUT / "smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
