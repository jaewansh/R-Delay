"""Package source only after actual pytest and browser checks have succeeded."""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime,timezone
from pathlib import Path
from engine.calibration import synthetic_observations

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/"artifacts/runtime"
OUT=ROOT/"deliverables"
ART.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
report=ET.parse(ART/"pytest.xml").getroot()
suites=list(report.iter("testsuite"))
counts={key:sum(int(s.get(key,0)) for s in suites) for key in ("tests","failures","errors","skipped")}
browser=json.loads((ART/"browser_check.json").read_text())
if counts["failures"] or counts["errors"] or not browser.get("passed"):
    raise RuntimeError("Failed tests: do not generate a success package")
commit=os.environ.get("RDELAY_SOURCE_COMMIT") or subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
checks=[]
for case in report.iter("testcase"):
    checks.append({"name":case.get("name"),"module":case.get("classname"),
                   "seconds":float(case.get("time",0)),"passed":case.find("failure") is None and case.find("error") is None})
summary={"created_at":datetime.now(timezone.utc).isoformat(),"source_commit":commit,
    "python":platform.python_version(),"platform":platform.platform(),
    "dependencies":{p:importlib.metadata.version(p) for p in ["numpy","scipy","fastapi","pydantic","uvicorn","pytest","httpx","playwright","Pillow"]},
    "pytest":counts,"browser_passed":True,"browser_checks":len(browser["checks"]),
    "human_visual_review":"not performed","field_validation":"not performed",
    "docker_execution":"not performed","external_deployment":"not performed",
    "checks":checks}
(ART/"validation_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
text=("# 실제 실행 검증 기록 — 서비스 v0.2\n\n"
      f"- 소스 커밋: `{commit}`\n- Python: {summary['python']}\n"
      f"- pytest: {counts['tests']}개, 실패 {counts['failures']}, 오류 {counts['errors']}, 건너뜀 {counts['skipped']}\n"
      f"- 실제 Chromium UI/API 검사: {len(browser['checks'])}개 통과\n"
      "- API 응답을 모킹하지 않음. JSON 저장값과 실제 응답 동일성 검사 포함.\n"
      "- 화면 PNG·GIF·WebM은 실행한 브라우저에서 생성. 그림/문서 목업이 아님.\n"
      "- 원래 Word/PDF를 이번 실행결과로 재작성하지 않음. v0.1은 설계 스냅샷.\n"
      "- 사람/모델의 전 화면 육안 검수·Docker 실행·공개 배포·현장 성능은 미실행.\n\n"
      "상세: validation_summary.json / browser_check.json / pytest.xml / sample_run.json\n")
(ART/"validation_summary.md").write_text(text,encoding="utf-8")
sampledir=ROOT/"data/synthetic";sampledir.mkdir(parents=True,exist_ok=True)
for mode in ("clean","noise_a","noise_b"):
    (sampledir/("calibration-"+mode+".json")).write_text(json.dumps({"data_type":"synthetic","mode":mode,"observations":synthetic_observations(mode)},ensure_ascii=False,indent=2),encoding="utf-8")
paths=[]
for directory in ["engine","api","web","tests","data/synthetic","image/runtime"]:
    for path in (ROOT/directory).rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix not in (".pyc",):paths.append(path)
for name in ["README.md","AGENTS.md","requirements-service.txt","requirements-test.txt","Dockerfile","compose.yaml",".gitignore","docs/runtime_contract.md","docs/implementation_status.md","scripts/check_runtime_browser.py","scripts/package_runtime.py",".github/workflows/service-ci.yml"]:
    path=ROOT/name
    if path.exists():paths.append(path)
for name in ["validation_summary.json","validation_summary.md","browser_check.json","pytest.xml","sample_run.json"]:
    paths.append(ART/name)
manifest={"source_commit":commit,"contains":"runtime source + executed synthetic tests + actual browser captures; no fonts or personal documents",
          "files":[{"path":str(p.relative_to(ROOT)),"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(set(paths))]}
(ART/"runtime_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
paths.append(ART/"runtime_manifest.json")
archive=OUT/"RDelay_runtime_v0.2.zip"
with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as z:
    for path in sorted(set(paths)):z.write(path,str(path.relative_to(ROOT)))
print(text)
print("Runtime archive bytes:",archive.stat().st_size)
