# R-Delay v0.1 전달 기록

## 실제 산출물 스냅샷

문서·생성 코드 스냅샷: `1f5ab0f9887239d4498426f88af8890526b07b15`.

- `deliverables/RDelay_참가신청서_v0.1.docx`: 45,396 bytes. 네이티브 Office Math 수식 3개.
- `deliverables/RDelay_참가신청서_v0.1.pdf`: 274,741 bytes. 신청서1+컨셉4=5쪽.
- `deliverables/RDelay_종합설계서_v0.1.pdf`: 576,731 bytes. 21쪽.
- `deliverables/RDelay_종합설계서_v0.1.docx`: 59,215 bytes. 종합설계서 편집 원본.
- 문서 생성 원본: `scripts/build_documents.py`.
- 프로젝트 기준: `AGENTS.md`, `docs/project_spec.md`, `docs/implementation_status.md`.

## 실제 확인한 검사

- 요약138자 / 지원동기150자(공백 포함), 키워드5개.
- 팀정보의 이름·출생연도·소속·학년·연락처 공란, 학적 미선택 자동검사 통과.
- Word 수식 OMML 3개, 본문에 LaTeX 명령 문자열을 인쇄하지 않음.
- LibreOffice 변환 결과의 실제 쪽수5/21, 전26쪽 PNG 렌더링 완료.
- 전 페이지 한글 문자 검출, 대체문자 U+FFFD 없음, 페이지 밖 텍스트 없음.
- PDF 한글 추출의 띄어쓰기를 정규화해 필수 섹션이 실제 페이지에 존재하는지 점검.

## 수식 소실 오류의 발견과 수정

처음 만든 PDF는 Word 내부 수식 개수 검사는 통과했지만, PDF 수식 영역에서는 식 자체가 누락됐다. 3쪽의 객체·픽셀·문자 검사에서 이를 발견했다. 초기 변환 파일을 최종 전달본으로 사용하지 않는다.

Writer와 별도로 LibreOffice Math를 설치하고, 네이티브 Office Math의 inline/paragraph 배치를 작은 예제로 실제 변환·비교했다. inline OMML 방식으로 생성기를 수정하고 문서 전체를 재생성했다. 최종 신청서 PDF 3쪽에서 SIS·C·R_d 식의 미분·행렬·그리스 문자가 추출되는지 별도로 검사했고 통과했다. 단순 OMML 개수만으로 PDF 표시 성공을 선언하지 않았다.

실행: https://github.com/jaewansh/R-Delay/actions/runs/39463804717
최종 수식 확인: `artifacts/equation_repair/final_check.json`
배치별 시험: `artifacts/equation_repair/probe_results.json`

## 아직 하지 못한 검사

**모든 렌더 이미지를 사람이/모델이 픽셀로 직접 보는 육안 검수는 미완료다.** GitHub 원본 이미지의 web 접근은 cache miss, 로컬 container/Python은 초기화 오류, ZIP/OOXML 수신 파일의 페이지 이미지 추출도 실패했다. 수식의 실제 출력은 독립 PDF 문자·래스터 시험으로 보강했지만, 모든 표·수식의 시각적 균형과 겹침이 없는지를 보증하는 것으로 확대하지 않는다. 개별 렌더 PNG는 `artifacts/rendered/`에 보존돼 있다.

원격 확인용 OOXML 재포장·페이지 이미지 proof는 보조 검토 수단이며 위 문서 스냅샷을 대체하지 않는다. 원격 artifact 재다운로드 검사의 401 실패도 서비스/모델 테스트 실패로 바꾸어 설명하지 않는다.

수리모델 엔진 수치시험·웹/API 실행·실제 현장자료·구매 의사·비용 절감 검증은 이번 문서 생성 작업에서 미실행이다. 모든 핵심 모듈은 이번 대회 구현 목표로 유지하며, 전체 서비스 완료본으로 표시하지 않는다.

## 저장소 범위

최초 빈 저장소의 브랜치 시작점을 만들기 위해 main에는 최소 README 초기 커밋만 만들었다. 이후 문서·워크플로·검사·산출물은 codex/rdelay-bootstrap에서 작업했다. main 자동 병합·기존 연구 저장소 변경·공개 범위 변경·웹 배포·유료 결제는 하지 않았다. 서명·증명서·개인정보·비밀키·폰트 바이너리는 산출물에 포함하지 않는다.

공고·참가양식 원본은 저장소에 없었으므로 대화 첨부자료의 본문과 이미지를 사용했다. `docs/source_audit.md`의 자료 위치 제한을 유지한다. 문서·PDF 관련 local skill 읽기는 초기화 실패로 완료하지 못했고, GitHub runner에는 해당 파일이 없었다. 읽지 않은 지침을 읽었다고 기록하지 않는다.
