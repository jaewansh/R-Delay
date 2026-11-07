# 내 컴퓨터에서 실행하기 (Windows · Mac)

이 저장소의 모형 코드를 노트북에서 돌리는 순서입니다. 원자료는 저장소에 없으므로, 각자 컴퓨터에 있는 자료 폴더를 `.env`로 연결합니다.

| 무엇 | 명령 | 걸리는 시간(참고) |
|---|---|---|
| 선박별 하루 전 경보(두 번째 분석, `realdata_ship/`) | `python -m realdata_ship.run_all` | 약 10분 안팎(시험 환경 8분) |
| 항만 전체 24시간 경보(주 분석, `realdata/`) | `python -m realdata.run_all` | 새 자료가 있을 때만 다시 계산 |
| 엔진·합성 검증(웹 시연 자료) | `python scripts/build_data.py` 등 | 수 초~1분 |
| 웹 화면 | <https://jaewansh.github.io/R-Delay/> | — |

아래 명령의 `python`은 2절에서 만든 가상환경의 파이썬입니다. Windows는 `.venv\Scripts\python`, Mac은 `.venv/bin/python`으로 바꿔 쓰거나, 가상환경을 켠 뒤 그대로 씁니다.

## 1. 코드 받기

- 저장소 폴더가 이미 있으면 그 폴더에서 `git pull`.
- zip으로 받았으면 새 폴더에 풀고, 기존 저장소 폴더의 `.env` 파일을 새 폴더 맨 위로 복사합니다.

## 2. 설치 (한 번, 인터넷이 될 때)

Python 3.11 이상이 필요합니다. 주 분석을 이미 돌린 가상환경이 있으면 그대로 써도 됩니다(같은 패키지).

발표·웹 숫자가 끝자리까지 같게 나오는 것은 numpy 2.4 이상 · pandas 3 · scikit-learn 1.9 이상(Python 3.11·3.13)에서 확인했습니다. 2024년 판(pandas 2.2 · scikit-learn 1.5)에서도 돌지만 일부 숫자가 셋째 자리에서 달라집니다(예: PR-AUC 0.193 → 0.192). 가상환경이 오래됐으면 아래 설치 명령에 `-U`를 붙여 올립니다. 주 분석은 새 자료가 없으면 다시 계산하지 않으므로 판을 올려도 숫자가 그대로입니다.

Windows (PowerShell, 저장소 폴더에서):

```powershell
py -m venv .venv          # py가 없으면 python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-backtest.txt
```

Mac (터미널, 저장소 폴더에서):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-backtest.txt
```

가상환경 켜기(선택): Windows `.venv\Scripts\Activate.ps1`, Mac `source .venv/bin/activate`. PowerShell이 스크립트 실행을 막으면 켜지 말고 `.venv\Scripts\python`을 직접 씁니다.

## 3. 자료 연결 (`.env`)

저장소 맨 위 폴더의 `.env`(주 분석 때 이미 만들었으면 그대로)에 자료 폴더를 적습니다. 따옴표는 없어도 됩니다.

```
RDELAY_DATA_ROOT=D:\RDelay_Data\Raw_data
```

Mac 예: `RDELAY_DATA_ROOT=/Users/<이름>/RDelay_Data/Raw_data`. 이 폴더 아래 구조는 다음과 같아야 합니다.

```
Raw_data/
├─ public_data/
│  ├─ derived/   newport_voyages.csv · newport_waiting_2h.csv · ex_speed_busan.csv
│  ├─ portmis/   cntl/daily/*.csv · vssl/daily/*.csv
│  └─ manual/    kma_asos/ · kma_buoy/ · kma_typhoon/ · bpa_vessel_calls/ …
└─ A1_… A2_… C1_… E1_… meta/   Clarksons(선택, 외부 공개 금지)
```

공개 자료가 다른 곳에 있으면 `RDELAY_PUBLIC_DIR=<폴더>`, Clarksons가 다른 곳에 있으면 `RDELAY_CLARKSONS_DIR=<폴더>`를 더 적습니다.

## 4. 점검

```
python scripts/laptop_check.py
```

파이썬·패키지, `.env`, 필요한 자료 파일, 한글 글꼴, 디스크를 확인하고 이 컴퓨터에서 쓸 명령을 보여 줍니다. `[XX]`가 없으면 준비가 끝난 것입니다. "같은 자료로 보입니다"가 나오고 패키지도 확인한 판이면, 다시 돌려도 발표·웹과 같은 숫자가 나옵니다.

## 5. 실행

```
python -m realdata_ship.run_all
```

- 7단계 진행 상황이 시각과 함께 나옵니다. 처음에는 원자료를 읽어 `realdata_ship/cache/`(저장소에 올리지 않음)를 만들고, 다음부터는 바뀐 파일만 다시 읽습니다.
- 메모리는 최대 약 2.5GB를 씁니다. 부족하면 `--workers 1`을 붙입니다(결과는 같음).
- 다시 쓰는 파일: `realdata_ship/results/`, `realdata_ship/reports/`, `docs/data/backtest_ship.json`, `image/backtest_ship_*.png`, README·REPORT·MODEL의 선박별 절(표시 사이만).
- 같은 자료로 돌리면 숫자는 그대로이고 생성 시각·그림 글꼴만 바뀝니다. 바뀐 파일은 `git status`로 보고, 되돌리려면 `git restore realdata_ship/results realdata_ship/reports docs/data/backtest_ship.json "image/backtest_ship_*.png" README.md REPORT.md MODEL.md`.
- 새 자료(관제정보 11/5 이후분 등)를 넣고 돌리면 시험 기간이 늘어 숫자가 바뀝니다. 실행 로그의 '자료 끝 … → 시험 기간 …' 줄로 확인합니다. 새 관제정보로 라벨부터 다시 만들 때는 `--relabel`.
- 주 분석은 `python -m realdata.run_all --dry-run`으로 무엇이 바뀔지 먼저 보고 `python -m realdata.run_all`로 반영합니다(README '실자료 백테스트').
- Clarksons 비교(선택): `python -m realdata_ship.clarksons` → 결과는 `local_only/`에만 생기고 저장소에 올라가지 않습니다.

## 6. 테스트

```
python -m pytest -q
```

자료가 연결되어 있으면 미래 정보 누설 검사까지 돕니다. Node.js가 있으면 `node --test tests/*.test.mjs`(화면 규칙)도 돌릴 수 있습니다.

## 7. 문제가 생기면

| 증상 | 할 일 |
|---|---|
| `git pull`이 로컬 변경 때문에 멈춤 | 이전에 다시 만든 결과 파일 때문이면 `git stash` 뒤 다시 `git pull`(되살리기는 `git stash pop`) |
| `ModuleNotFoundError` | 2절 설치를 가상환경의 파이썬으로 했는지 확인 |
| `[중단] RDELAY_DATA_ROOT…` | 3절 `.env` 경로 확인(메모장은 UTF-8로 저장) |
| 그림의 한글이 네모 | 숫자 결과는 같음. Windows는 맑은 고딕, Mac은 AppleGothic이 기본으로 있음. 다른 글꼴은 `.env`에 `RDELAY_FONT_DIR=<글꼴 폴더>` |
| 메모리 부족·멈춤 | 다른 프로그램을 닫고 `--workers 1` |
| 파일을 쓸 수 없음(Windows) | 저장소를 OneDrive 동기화 폴더 밖에 두고, 결과 그림·JSON을 연 프로그램을 닫기 |
| 숫자가 발표와 다름 | 4절 점검에서 자료 끝·항차 수가 같은지, 패키지가 확인한 판인지(2절) 확인 |

인터넷이 없는 곳(배 위 등): 설치(2절)는 미리 해 둡니다. 실행 자체는 인터넷이 필요 없습니다. 웹 화면은 인터넷이 될 때 한 번 열어 두면 그 뒤로는 오프라인에서도 열립니다.
