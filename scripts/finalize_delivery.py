#!/usr/bin/env python3
"""Final consistency pass over the code-aligned document builder.
No changes to the actual service, base branch, deployment or original documents.
"""
from __future__ import annotations
import hashlib, json, shutil, zipfile
from pathlib import Path
import build_final_delivery as b

original_report=b.final_report

def revised_report(evidence,example):
    d=original_report(evidence,example)
    b.replace_text(d,{
      '이 파일은 제출 문안과 상세 설계의 1차본이다. 서비스·수리모델 실행·배포·현장 성과는 완료 사실로 기재하지 않았다. 과거 대화의 복원값·마감위험 수치·테스트 통과 기록은 이 단계의 성과로 인용하지 않았다.':
      '이 파일은 현재 구현 코드와 실제 재실행 결과를 반영한 통합 기획서다. 합성 수리모델·로컬 웹/API 실행은 확인했고, 공개 배포·현장 예측력·비용절감은 미검증이다. 과거 대화의 숫자 대신 이번에 다시 계산한 결과만 부록에 제시했다.',
      'artifacts/document_check.md':'artifacts/final_delivery/document_check.md',
      '외부 원문 확인 기준일 2026-10-21.':'외부 원문 재확인 기준일 2026-10-22.',
      '외생변수 머신러닝, 일반 관측 스트리밍, GitHub Pages/Pyodide 전환, 공개 배포·현장 검증':
      '외생변수 학습·관측 확장, Pages/Pyodide·공개배포·현장 검증. 기여도·버퍼 자동설계·연결복원도 미구현',
    })
    return d
b.final_report=revised_report

entries=[]
for line in b.git('ls-tree','-r',b.BASE).decode().splitlines():
    meta,path=line.split('\t',1)
    if path.startswith(('engine/','api/','web/','tests/')) or path in ('requirements-service.txt','requirements-test.txt','Dockerfile','compose.yaml'):
        raw=b.git('show',b.BASE+':'+path)
        entries.append({'path':path,'git_blob_sha':meta.split()[2],
                        'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
b.save_json(b.ART/'code_manifest.json',{'stable_code_commit':b.BASE,'files':entries})

original_package=b.package_code

def package_with_manifest(target,sha,label,evidence):
    original_package(target,sha,label,evidence)
    if sha==b.BASE:
        with zipfile.ZipFile(target,'a',zipfile.ZIP_DEFLATED) as z:
            z.write(b.ART/'code_manifest.json','delivery_checks/code_manifest.json')
b.package_code=package_with_manifest

# These are generated delivery outputs owned by this builder, never source/user data.
# Avoid including a previous aggregate's checksum in its own regenerated manifest.
for name in ('manifest.json','RDelay_기획서와코드_전체전달.zip'):
    p=b.OUT/name
    if p.exists():p.unlink()
b.main()
# Do not publish transient LibreOffice profiles or temporary equation DOCX files.
scratch=b.ART/'build_tmp'
if scratch.exists():shutil.rmtree(scratch)

# The builder functions above must accompany the aggregate delivery too.
with zipfile.ZipFile(b.OUT/'RDelay_기획서와코드_전체전달.zip','a',zipfile.ZIP_DEFLATED) as z:
    z.write(Path(__file__),'scripts/finalize_delivery.py')
    z.write(b.ART/'code_manifest.json','artifacts/final_delivery/code_manifest.json')
print('FINAL_DELIVERY_COMPLETE',b.OUT)
