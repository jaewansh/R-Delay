"""문서에 적은 실자료 백테스트 숫자가 docs/data/backtest.json과 맞는지 본다. 표준 라이브러리만 쓴다(웹앱용 CI에서도 돈다).

결과를 다시 만든 뒤 README·REPORT·작동 원리 페이지에 옛 숫자가 남지 않게, 문서마다 꼭 적는 머리 숫자만 확인한다.
- R-Delay(R1)·지속성(S1)·기후값(S0) PR-AUC(소수 셋째 자리)
- 평가 기간 시작·끝 날짜(periods.test)
- R-Delay 경보의 대기 에피소드 수와 그중 시작 전 72시간 안에 경보가 없었던 수(가까이 함께 적는다. 예: 'N개 중 M개')
실자료 백테스트를 언급하는 문서('backtest.html'이나 '실자료'가 있는 문서)만 본다.
숫자가 더 긴 숫자의 일부로만 있으면 없는 것으로 본다(0.407은 0.4071·10.407 안에서는 세지 않는다).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "data" / "backtest.json"
DOCS = ("README.md", "REPORT.md", "docs/method.html")
MENTIONS = ("backtest.html", "실자료")
NEAR = 40  # 에피소드 수와 놓친 수 사이 최대 글자 수


def _num(s: str) -> str:
    """s가 더 긴 숫자의 일부가 아닐 때만 맞는 정규식(앞에 숫자·소수점·'숫자,'가 없고 뒤에 숫자·'.숫자'·',숫자'가 없음)."""
    return rf"(?<![\d.])(?<!\d,){re.escape(s)}(?!\d|[.,]\d)"


@pytest.fixture(scope="module")
def key_numbers() -> dict[str, str]:
    d = json.loads(DATA.read_text(encoding="utf-8"))
    m = {x["key"]: x for x in d["models"]}
    a = m["R1"]["alarm"]
    t0, t1 = d["periods"]["test"]
    return {
        "R-Delay PR-AUC": f"{m['R1']['pr_auc']:.3f}",
        "지속성 PR-AUC": f"{m['S1']['pr_auc']:.3f}",
        "기후값 PR-AUC": f"{m['S0']['pr_auc']:.3f}",
        "평가 기간 시작": t0[:10],
        "평가 기간 끝": t1[:10],
        "대기 에피소드": str(a["episodes"]),
        "72시간 안 경보 없음": str(a["episodes"] - a["caught_72h"]),
    }


@pytest.mark.parametrize("rel", DOCS)
def test_doc_quotes_current_backtest_numbers(rel, key_numbers):
    path = ROOT / rel
    if not path.exists():
        pytest.skip(f"{rel} 없음")
    text = path.read_text(encoding="utf-8")
    if not any(w in text for w in MENTIONS):
        pytest.skip(f"{rel}: 실자료 백테스트를 언급하지 않음")
    missing = {k: v for k, v in key_numbers.items() if not re.search(_num(v), text)}
    assert not missing, f"{rel}에 지금 backtest.json의 숫자가 없음(옛 숫자가 남았는지 확인): {missing}"
    n_ep, n_miss = key_numbers["대기 에피소드"], key_numbers["72시간 안 경보 없음"]
    ep, miss = _num(n_ep), _num(n_miss)
    near = rf"{ep}.{{0,{NEAR}}}?{miss}|{miss}.{{0,{NEAR}}}?{ep}"
    assert re.search(near, text, re.S), \
        f"{rel}: 대기 에피소드 수({n_ep})와 72시간 안 경보가 없던 수({n_miss})를 {NEAR}자 안에 함께 적은 곳이 없음(예: '{n_ep}개 중 {n_miss}개')"
