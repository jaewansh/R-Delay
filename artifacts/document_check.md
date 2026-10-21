# 문서 검사 — 실제 실행 기록

- 생성 입력 커밋: `b25b4715b75c341746d35e476504027c669b2ae4`
- 신청서 PDF: 5쪽 (신청1+컨셉4)
- 종합설계 PDF: 21쪽
- 요약 138자 / 지원동기 150자 (공백 포함)
- 키워드 5개 / 신청서 OMML 수식 3개
- 종합설계서 네이티브 수식 26개
- 팀정보 공란 오류: []
- 본문 LaTeX 소스 노출: False
- 전체 페이지 PNG 렌더링: 완료
- 쪽수·공란·수식 기호/번호·경계 자동 검사: True
- 육안검수: 미실행. 로컬 초기화 및 원격 이미지 조회 실패. 자동 검사와 구분함.
- 수리모델 수치시험·웹/API 실행·배포·현장 성능: 미실행

## 파일

- `deliverables/RDelay_종합설계서_v0.1.docx` — 59,256 bytes
- `deliverables/RDelay_종합설계서_v0.1.pdf` — 580,489 bytes
- `deliverables/RDelay_참가신청서_v0.1.docx` — 45,500 bytes
- `deliverables/RDelay_참가신청서_v0.1.pdf` — 275,367 bytes

## 수식과 재현
- LibreOffice Math를 설치하고 Pandoc 네이티브 OMML 문단을 보존했다. PDF에서 β·γ·합 기호 및 모든 수식 번호를 검사했다.
- R_d=rho(K), K=diag(beta(1-x)) C Gamma^-1로 동등하게 표현하여 괄호 호환성을 높였다.
- 실제 실행 원본: scripts/build_native_documents.py 및 scripts/build_documents.py.
- 실행: python scripts/build_native_documents.py ; python scripts/audit_rendering.py
- 원본 PNG는 artifacts/rendered/. 문서 검사는 모델의 현실 적합성 검증이 아니다.
- Word의 다른 환경 재페이지화, 서명·증빙·자격·최신 공지는 별도 확인. 공식 HWP 픽셀 복제본이 아니다.
