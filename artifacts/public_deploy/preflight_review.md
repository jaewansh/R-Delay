# 공개 배포 사전검사 — 실제 실행 기록

## 상태

**배포 준비 코드는 검사했지만 Render 서비스/공개 URL은 아직 생성하지 않았다.**
Render 계정 연결 요청이 표시되어 있으며, 마지막 확인 시 플러그인이 설치·연결되지 않은 상태였다.
클라우드 계정/워크스페이스·비용 설정·접근 권한을 확인한 뒤 서비스 생성과 외부 HTTPS 검사가 필요하다.

## 확인한 원본 실행

- 검사 소스 커밋: `26710b84b440ede22c17fa693f261c6c08c64e06`
- 워크플로: https://github.com/jaewansh/R-Delay/actions/runs/39583949645
- 작업 ID: `119168093024`, 전체 결과 `success`
- Python: `3.12.15`, Chromium: `136.0.7103.25`
- 실제 pytest 로그: `50 passed, 1 warning in 2.83s`
- 경고: Starlette TestClient의 anyio BlockingPortal 별칭 사용 중단 예정 경고. 숨기지 않았다.
- 원래 Word/PDF blob SHA 확인 단계도 성공했다.
- 전체 로그와 XML/JSON/PNG 증거: https://github.com/jaewansh/R-Delay/actions/runs/39583949645/artifacts/12338112959
- Actions artifact 크기 780,006 bytes, SHA-256 `7ba76ab49961bb3e6011a95d7a305862ba130c8839a6f12243f1d207cd79c708`.
- artifact 보존기간은 14일이다. 이 문서는 실제 조회한 로그를 요약한 기록이며 원본 XML/이미지를 직접 대체하지 않는다.

## 실제 브라우저 검사 (6/6 통과)

검사 위치는 **GitHub runner 내부 `http://127.0.0.1:8766`**이다.
`PORT=8766 python scripts/start_public.py`를 통해 실제 배포용 진입점을 실행했다.
웹 API 응답을 모킹하지 않았다.

1. public entrypoint health — 통과
2. actual public API calculation — 통과 (POST 응답 201)
3. native SIS math visible — 통과
4. download equals actual Python response — 통과
5. mobile page has no horizontal overflow — 통과 (390px 화면)
6. no uncaught JavaScript error — 통과

검사 JSON의 `hosted_url_requested=false`, `public_url_verified=false`, `api_mocked=false`를 유지한다.
검사 시작 2026-10-21T10:21:51.058115+00:00, 종료 2026-10-21T10:21:54.319600+00:00.
데스크톱/모바일 PNG는 실제 브라우저 캡처이나 직접 육안 검토는 수행하지 않았다.

## 수정 이력

- 첫 사전검사에서 닫힌 ‘계산 재현 설정’ 안의 select를 조작하려는 검사기 오류가 있었다.
  실제 사용자와 같이 summary를 클릭해 펼친 뒤 입력하도록 고쳤다.
- 다음 검사에서 모바일 전체 페이지의 가로 넘침을 검출했다.
  grid의 자동 최소 너비, input/select 최소 너비, 패널 내 텍스트 줄바꿈을 수정했다.
  전체 문서에 overflow:hidden을 씌워 오류를 감추거나 검사 기준을 삭제하지 않았다.
- 최종 동일 검사를 다시 실행해 모두 통과했다. 이전 실패 실행도 Actions 이력에 남아 있다.

## 완료로 주장하지 않는 것

Render 자원 생성·도메인 할당·인터넷에서의 HTTPS 접속·호스팅 서버에서의 계산은 미수행이다.
무료 워크스페이스의 과금 조건/지급수단 여부는 아직 확인하지 못했다.
main 병합·유료 결제·공개범위 변경·기존 엔진/Word/PDF 수정은 수행하지 않았다.
현장 예측력·고객 구매·실제 물류비용 절감·완전한 DDoS 방어 검증과도 무관하다.
