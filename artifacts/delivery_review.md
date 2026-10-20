# v0.1 전달 및 검수 범위

## 실제 확인한 산출물
문서 생성 워크플로 https://github.com/jaewansh/R-Delay/actions/runs/39461229224 는 success로 완료되었다. 생성 원본 커밋은 `9004ca120ec75bc93958f0159292cdbbe0fd5dda`이고, 산출물 커밋은 `915787d952a19fedb1810ef6e5fa7b2810f8887a`이다. GitHub의 실제 파일 메타데이터와 document_check.md/json을 다시 조회했다.

- deliverables/RDelay_참가신청서_v0.1.docx: 45,448 bytes. Word OMML 수식 3개. 자동 검사상 팀 개인정보 공란 유지, 요약 138자·지원동기 150자·키워드 5개.
- deliverables/RDelay_참가신청서_v0.1.pdf: 256,453 bytes. 실제 LibreOffice 렌더 결과 5쪽(신청서 1+컨셉 4).
- deliverables/RDelay_종합설계서_v0.1.pdf: 527,965 bytes. 실제 렌더 결과 21쪽.
- deliverables/RDelay_종합설계서_v0.1.docx: 59,256 bytes. 종합 PDF의 편집 원본.
- deliverables/RDelay_v0.1_문서및생성원본.zip: 636,398 bytes. 문서·생성원본 묶음이며 서비스 최종 코드가 아니다.

공식 원본의 픽셀 단위 복제나 서명·증빙 완료를 의미하지 않는다. Word의 페이지 수는 설치 글꼴·Office 버전에 따라 달라질 수 있다.

## 생성 원본과 별도 참고 문안
실제 산출물 생성에 사용된 원본은 `scripts/build_documents.py`이다. `docs/document_content.py`는 같은 작업에서 추가로 정리한 참고 문안이며, 위 산출물의 생성 입력으로 사용되지 않았다. 파일 존재를 실제 생성에 사용된 것으로 혼동하지 않는다.

## 렌더링과 육안 확인의 차이
모든 26페이지는 artifacts/rendered에 PNG로 렌더링되었다. 자동 검사에서 페이지 바깥 텍스트 span·대체문자·노출된 LaTeX 명령을 발견하지 않았다. application-03.txt도 확인하여 SIS 핵심 엔진 설명과 수식 번호 (1)~(3), 기호 설명이 있는 위치를 점검했다. 실제 수식 구조는 Word XML OMML 검사로 확인했다.

그러나 이 대화에서 로컬 이미지 열기 환경이 시작되지 않았고, 새 GitHub raw 이미지/PDF를 web 도구로 열려는 시도는 Cache miss/접근 불가였다. 따라서 한글·수식 글리프·표·겹침을 모든 이미지에서 직접 본 육안 검수는 **미실행**이다. 자동 통과·렌더 파일 생성 사실을 육안 검수 완료로 바꾸지 않는다. 실제 이미지는 artifacts/rendered에서 검토 가능하다.

## 환경·안전
현재 대화의 container/Python은 코드 실행 전 InvalidArgumentError로 실패했다. 이후 성공 기록은 별도의 GitHub Actions runner에서 실행된 것이다. 지침 파일의 실제 열람 불가도 environment_check.md에 남겼다.

공고·참가양식 PDF는 최초 저장소에 없었다. 대화의 첨부 7쪽 공고·3쪽 양식을 읽은 사실과 저장소 원본 부재를 구분한다. 최초 10쪽 초안을 저장소에서 읽었다고 주장하지 않는다.

빈 저장소 초기화를 위한 기본 README 최초 커밋을 제외한 문서 작업은 codex/rdelay-bootstrap에서 수행했다. main 자동 병합, 다른 연구 저장소 수정, 외부 배포, 공개 설정 변경, 유료 서비스 결제는 하지 않았다. 이미 공개 상태인 저장소에는 개인정보·서명·증명서·비밀키를 추가하지 않았다.

## 미완료 항목
- SIS·로그-OU·입자필터·시간가변 선석 대기·계수 학습·배차 엔진의 실제 구현 및 수치검사
- 웹/API 구현·로컬 시연·온라인 배포
- 실자료·고객·구매 의사·현장 예측력·비용 절감 검증
- 문서의 페이지별 육안 검수

위 모델들은 모두 이번 대회 구현 목표이며 임의로 대회 이후 연구로 제외하지 않는다. 현재는 실제 문서 생성이 완료된 설계 1차본이다.
