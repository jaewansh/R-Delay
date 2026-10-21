# 실제 실행 검증 기록 — 서비스 v0.2

- 소스 커밋: `ea397d3267d88763baba9430409352f662d62693`
- Python: 3.12.3
- pytest: 40개, 실패 0, 오류 0, 건너뜀 0
- 실제 Chromium UI/API 검사: 12개 통과
- API 응답을 모킹하지 않음. JSON 저장값과 실제 응답 동일성 검사 포함.
- 화면 PNG·GIF·WebM은 실행한 브라우저에서 생성. 그림/문서 목업이 아님.
- 원래 Word/PDF를 이번 실행결과로 재작성하지 않음. v0.1은 설계 스냅샷.
- 사람/모델의 전 화면 육안 검수·Docker 실행·공개 배포·현장 성능은 미실행.

상세: validation_summary.json / browser_check.json / pytest.xml / sample_run.json
