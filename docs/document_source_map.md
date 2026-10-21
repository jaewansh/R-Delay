# v0.1 문서 생성 원본 안내

## 실제 실행 순서
`.github/workflows/documents.yml`에서 다음을 실행한다.

1. `python scripts/build_native_documents.py`
2. `python scripts/audit_rendering.py`

`build_native_documents.py`는 Pandoc OMML의 실제 PDF 표시를 검사한 뒤 `build_documents.py`의 문안·레이아웃·문서 생성 함수를 호출한다. `build_documents.py`의 Python 상수·문단·표가 현재 생성 파일의 직접 원본이다.

## 다른 설계 자료
- `AGENTS.md`: 작업 안전·모델 보존·검증 기준
- `docs/project_spec.md`: 프로젝트 설계 명세
- `docs/source_audit.md`: 실제 확인한 공식 첨부자료·공개 원문 및 적용 범위
- `docs/implementation_status.md`: 문서와 서비스의 구현·실행·검증 상태 구분
- `docs/content.json`: 편집·확장용 문안 초안으로 보존. 현재 실행 스크립트의 직접 입력은 아니다. 이 JSON의 문안·글자 수·예상 쪽수를 실제 PDF 결과라고 보고하면 안 된다.

## 실제 산출물과 검사
`deliverables/`의 요청 파일 2종 및 검토용 PDF/Word, `artifacts/document_check.md`, `artifacts/math_render_probe.json`, `artifacts/review_limitations.md`를 함께 확인한다.

압축파일은 생성 단계의 문서·원본 스냅샷이다. 이후 추가한 검토 한계 문서와 이 안내는 저장소의 최신 파일을 기준으로 확인한다.

## 범위
이 원본은 **문서 생성 코드**다. SIS·로그-OU·필터·대기·계수 학습·배차·웹 서비스 엔진의 최종 구현 코드가 아니다. 실제 서비스 구현은 이번 대회 목표로 유지하며 현재 미구현/미실행으로 표시한다.
