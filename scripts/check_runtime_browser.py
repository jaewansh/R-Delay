"""Run the live local service in Chromium; never mock API answers or draw fake UI."""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime,timezone
from pathlib import Path
import httpx
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"artifacts/runtime"
IMAGES=ROOT/"image/runtime"
OUT.mkdir(parents=True,exist_ok=True);IMAGES.mkdir(parents=True,exist_ok=True)
URL="http://127.0.0.1:8765"
proof={"started_at":datetime.now(timezone.utc).isoformat(),"mocked_api":False,
       "external_network_during_ui":[],"checks":[],"human_visual_review":"not performed"}
log=(OUT/"server.log").open("w",encoding="utf-8")
process=subprocess.Popen([sys.executable,"-m","uvicorn","api.main:app","--host","127.0.0.1","--port","8765"],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)


def record(name,condition,detail=None):
    proof["checks"].append({"name":name,"passed":bool(condition),"detail":detail})
    if not condition:
        raise AssertionError(name+": "+str(detail))

try:
    for _ in range(120):
        try:
            if httpx.get(URL+"/health",timeout=1).status_code==200:break
        except httpx.HTTPError:pass
        time.sleep(.25)
    else:raise RuntimeError("local API did not start")
    with sync_playwright() as p:
        browser=p.chromium.launch()
        proof["browser_version"]=browser.version
        context=browser.new_context(viewport={"width":1440,"height":1100},device_scale_factor=1,
            record_video_dir=str(OUT/"video"),record_video_size={"width":1440,"height":1100},accept_downloads=True)
        page=context.new_page();errors=[]
        page.on("pageerror",lambda e:errors.append(str(e)))
        page.on("request",lambda r:proof["external_network_during_ui"].append(r.url) if not r.url.startswith(URL) else None)
        page.goto(URL,wait_until="networkidle")
        page.wait_for_function("window.__rdelayReady === true")

        def execute():
            page.locator("#run-button").click()
            page.wait_for_function("window.__rdelayResult !== null && window.__rdelayResult !== undefined",timeout=120000)
            return page.evaluate("window.__rdelayResult")

        base=execute()
        record("browser called the actual Python API",bool(base.get("source_commit")) and base["model_version"]=="0.2.0")
        record("native SIS equation and generated SVG visible",page.locator("math").count()==1 and page.locator("#state-chart svg").count()==1)
        record("three actual dispatch candidates rendered",page.locator("#candidate-body tr").count()==3)
        record("response ID matches rendered result",page.locator("#results").get_attribute("data-run-id")==base["run_id"])
        page.screenshot(path=str(IMAGES/"dashboard.png"),full_page=True)
        page.screenshot(path=str(IMAGES/"step-01.png"))
        (OUT/"sample_run.json").write_text(json.dumps(base,ensure_ascii=False,indent=2),encoding="utf-8")
        with page.expect_download() as info:
            page.locator("#download-button").click()
        downloaded=info.value
        downloaded.save_as(str(OUT/"downloaded_run.json"))
        restored=json.loads((OUT/"downloaded_run.json").read_text())
        record("JSON export exactly matches the real response",restored==base)

        page.locator('[data-preset="congestion"]').click()
        changed=execute()
        record("new observation changes posterior",changed["filter"]["posterior_mean"][1]>base["filter"]["posterior_mean"][1])
        page.screenshot(path=str(IMAGES/"posterior.png"),full_page=True)
        page.evaluate("window.scrollTo(0,0)")
        page.screenshot(path=str(IMAGES/"step-02.png"))

        page.locator('[data-preset="closure"]').click()
        closed=execute()
        record("shutdown changes predicted readiness",closed["events"]["ready_quantiles_h"]!=base["events"]["ready_quantiles_h"])
        page.screenshot(path=str(IMAGES/"closure.png"),full_page=True)
        page.evaluate("window.scrollTo(0,0)")
        page.screenshot(path=str(IMAGES/"step-03.png"))

        page.locator('[data-preset="restricted"]').click()
        restricted=execute()
        record("unconfirmed reservation excluded",not restricted["candidates"][2]["eligible"] and "예약 미확인" in restricted["candidates"][2]["reasons"])

        page.locator("#count").fill("21")
        page.locator("#sample").fill("20")
        page.locator("#run-button").click()
        page.locator("#error").wait_for(state="visible",timeout=30000)
        record("invalid observation removes stale recommendation",not page.locator("#results").is_visible() and page.evaluate("window.__rdelayResult === null"))

        page.locator('[data-preset="base"]').click()
        page.set_viewport_size({"width":390,"height":844})
        mobile=execute()
        page.screenshot(path=str(IMAGES/"mobile.png"),full_page=True)
        record("mobile has no document-wide horizontal overflow",page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"))
        record("no uncaught JavaScript exceptions",not errors,errors)
        record("UI uses no external network/CDN",not proof["external_network_during_ui"])
        video=page.video
        context.close()
        if video:
            shutil.copyfile(video.path(),IMAGES/"demo.webm")
        browser.close()
    frames=[]
    for name in ("step-01.png","step-02.png","step-03.png"):
        with Image.open(IMAGES/name) as image:
            frame=image.convert("RGB");frame.thumbnail((1080,825));frames.append(frame.convert("P",palette=Image.Palette.ADAPTIVE,colors=128))
    frames[0].save(IMAGES/"demo.gif",save_all=True,append_images=frames[1:],duration=1800,loop=0,optimize=False)
    proof["passed"]=True
except Exception as exc:
    proof["passed"]=False;proof["error"]=repr(exc)
    raise
finally:
    process.terminate()
    try:process.wait(timeout=10)
    except subprocess.TimeoutExpired:process.kill()
    log.close()
    proof["completed_at"]=datetime.now(timezone.utc).isoformat()
    proof["source_commit"]=os.environ.get("RDELAY_SOURCE_COMMIT","unknown")
    (OUT/"browser_check.json").write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(proof,ensure_ascii=False,indent=2))
