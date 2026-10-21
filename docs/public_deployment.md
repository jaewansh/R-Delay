# 웹 + Python 공개 배포 준비

사용자가 2026-10-21 웹 화면과 Python 계산 서버의 함께 공개 배포를 요청했다.
기존의 공개 배포 금지는 이번 요청 범위에 한해 해제한다. 유료 결제, 저장소 공개범위 변경,
자동 main 병합, 다른 연구 저장소 수정은 이 요청에 포함하지 않는다.

## 실제 상태

Render 연결이 아직 승인되지 않아 **클라우드 서비스와 공개 URL은 생성되지 않았다**.
이 문서는 배포 완료 보고서가 아니다. Render 플러그인 연결 요청을 표시했고,
연결과 대상 워크스페이스가 확인되면 Free 서비스 1개만 생성하는 방향으로 준비했다.
기존 main과 Word/PDF는 변경하지 않고 `codex/render-public-deploy` 브랜치에서 준비한다.

## 한 서비스에 웹과 계산 서버를 함께 배치

- 배포 설정: `render.yaml` (runtime python / plan free / Singapore / 자동 재배포 off).
- 런타임: `.python-version`의 Python 3.12 계열. 실제 patch는 실행 로그로 확인한다.
- 설치: `python -m pip install -r requirements-service.txt`.
- 시작: `python scripts/start_public.py`.
- 이 명령은 `api.public:app`을 0.0.0.0:$PORT에 단일 worker로 실행한다.
- `/`는 웹, `/static/`은 화면 자원, `/api/v1/`은 기존 Python 수리모델이다.
- 수식/엔진 계산 변경 없음. SIS를 브라우저 모형으로 대체하지 않는다.
- `/health`는 모형 버전, 소스 커밋, 합성자료 상태, 요청 제한을 반환한다.
- `RENDER_EXTERNAL_HOSTNAME`과 `RENDER_GIT_COMMIT`은 Render가 공급한다.
- 공인 URL은 Render가 실제로 반환한 값을 사용하고 추측해서 기재하지 않는다.

## 공개 데모 보호 범위

- 32 KiB의 실제 수신 본문 제한, JSON 요청만 허용, 10초 본문 수신 제한.
- 단일 worker의 전체 POST 예산 12회/분, 초과 시 429/Retry-After.
- 기존 엔진의 동시 계산 슬롯1개·입자/큐/후보 크기 제한 유지.
- 호스트 허용목록, 다른 출처에서 시작한 브라우저 계산 요청 거부.
- 공개 Swagger/ReDoc/OpenAPI 차단, CSP 유지, no-store/no-referrer/noindex.
- 모델 입력은 합성으로 고정. 개인정보·실제 고객 운송자료 입력 금지 안내.
- 기존 임시 저장 최대32건 유지. 재시작/대기 전환 시 기록은 사라질 수 있다.
- 실행 ID는 로그인 없는 임시 접근 링크다. 사용자 인증·데이터 격리가 구현된 것으로 설명하지 않는다.
- 전역 요청 제한은 작은 시연의 과도한 부하 억제일 뿐 완전한 DDoS 방어가 아니다.
- 환경 변수/패키지 설치/호스팅 공급자의 메타데이터·접속로그 처리와 애플리케이션 데이터를 구분한다.

## 비용과 대기 전환

`plan: free`는 무료 인스턴스만 요청한다. DB, 디스크, 유료 인스턴스, 자동 확장은 요청하지 않는다.
무료 서비스도 결제수단이 연결된 워크스페이스에서 대역폭/빌드 할당을 넘기면 비용이 발생할 수 있다.
결제수단 없는 무료 워크스페이스 사용 또는 비용설정 확인 전에는 0원 보장을 하지 않는다.
무료 웹서비스는 15분 비활동 후 대기하고 다음 요청에서 약 1분 재시작될 수 있다.
이는 공급자 조건이며 우회용 주기 핑이나 GitHub Actions 장기 터널을 사용하지 않는다.

## 검사와 공개 완료 기준

1. `python -m pytest tests -q`: 기존 수리/API 검사와 추가 보호장치 검사.
2. `python scripts/check_public_runtime.py`: localhost에서 실제 API/Chromium 계산·다운로드 비교.
3. Render 연결, 워크스페이스·비용·Git 접근 확인 후 Free web service 생성.
4. 실제 반환된 HTTPS 주소에 대해 `/health`, `/`, `/api/v1/runs`, JSON 저장 확인.
5. `python scripts/check_public_runtime.py --url 실제_HTTPS_주소`로 외부 배포 결과 검사.
6. 배포 ID·URL·소스 SHA·검사 결과를 기록한 뒤에만 '공개 배포 완료'로 표시.

1~2의 성공은 3~6의 완료를 의미하지 않는다. 이번 CI는 localhost 검사이며 외부 서비스가 아니다.
문서 파일의 자동 검사·육안 검수나 현장 예측 성능을 새로 완료한 것으로 표시하지 않는다.

## 확인한 공식 문서 (2026-10-21)

- https://render.com/docs/deploy-fastapi — Python 웹서비스와 0.0.0.0:$PORT
- https://render.com/docs/blueprint-spec — plan, region, branch, autoDeployTrigger, healthCheckPath
- https://render.com/docs/python-version — .python-version에서 minor 지정 지원
- https://render.com/docs/environment-variables — Render 호스트명과 Git 커밋
- https://render.com/docs/free — 무료 인스턴스 대기·시간·초과 사용 제한

애플리케이션 보호 설정은 이번 작업의 추가 설계이며 공급자가 모든 보호를 보장한다는 뜻이 아니다.
