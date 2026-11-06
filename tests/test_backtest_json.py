"""docs/data/backtest.json(웹 '실자료 검증' 화면의 자료) 점검. 표준 라이브러리만 쓴다(웹앱용 CI에서도 돈다).

- 브라우저 JSON.parse로 읽히는지(NaN·Infinity 없음), 크기 한도, 필수 키, 사례 시계열 길이
- 공개 범위: 호출부호·선박명 열 이름·상용 자료원·부두 표기가 없고, 사례에서 배 하나에 대한 값은 시 단위 도착 시각과 대기 구간뿐인지
- 모형 숫자가 realdata/results/rdelay.json과, 라벨 수가 audit.json과 같은지
- 요약 문장(answer)의 판정 표현이 차이 구간 판정(pairs[].pr_verdict)과, 문장 속 숫자가 모형·라벨 숫자와 맞는지
- 사례 숫자(facts)가 공개한 시계열·도착 점에서 다시 센 값과 같은지
- source_digest가 입력 결과 파일 해시와 같고, scripts/build_backtest.py로 다시 만들면 같은지(생성 시각·커밋 제외)
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data" / "backtest.json"
RES = ROOT / "realdata" / "results"
BUILDER = ROOT / "scripts" / "build_backtest.py"
MAX_BYTES = 500_000  # scripts/build_backtest.py와 같은 한도
VOLATILE = ("generated_kst", "built_from_commit")  # 다시 만들 때마다 바뀌는 값
REQUIRED = ("schema", "generated_kst", "built_from_commit", "source_digest", "protocol", "source_files", "question", "answer",
            "target", "periods", "test_pos_rate", "train_pos_rate", "labels", "pretest_patterns", "anchorage_choice_train",
            "data_ranges", "setup", "alarm_rule", "models", "pairs", "subgroups", "vessel", "posthoc", "rd_reference", "cases",
            "case_note", "case_bands", "limits", "sources", "constants")
SERIES = ("anchor", "prob", "p_rd1", "y", "alarm")  # 사례 그림에 꼭 있어야 하는 시계열
FORBIDDEN = ("clsgn", "vsslnm", "clarksons")  # 소문자로 바꾼 본문에서 찾는다(호출부호·선박명 열 이름, 상용 자료원)
PIER = re.compile(r"\d\s?부두|다목적부두")  # PORT-MIS 시설 이름의 부두(터미널) 표기
PUBLIC_PAGES = ("docs/backtest.html", "docs/assets/js/backtest.js")
TIME_FMT = "%Y-%m-%d %H:%M"
ON_HOUR = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:00")  # 사례 시각은 시 단위로 내린 값만
STAMP = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:(\d{2})")  # 본문 어디서든 찾는 시각(분 자리를 본다)
ARRIVAL_KEYS = {"t", "band"}  # 도착 점(배 하나)에 허용하는 값: 시 단위 도착 시각, 대기 구간
LEAD_H = 72  # 사례 선행시간 창 [시작 − 72h, 시작)(PROTOCOL v1 7절, realdata.metrics.LEAD_WINDOW_H)
# 요약 문장의 판정 표현. 판정 = 앞 모형 − 뒤 모형 PR-AUC 차이 95% 구간이 0보다 큼('a') / 0을 포함('same') / 0보다 작음('b')
VERDICT_WORDS = {
    ("R1", "S0"): {"a": "기후값보다 확실히 낫", "same": "기후값과 차이가 없", "b": "기후값보다 확실히 못하"},
    ("R1", "S1"): {"a": "지속성보다도 확실히 낫", "same": "지속성과는 차이가 없", "b": "지속성보다 확실히 못하"},
    ("R3b", "S3"): {"a": "더하면 확실히 나아진다", "same": "더하면 차이가 없다", "b": "더하면 오히려 나빠진다"},
}


def _reject_constant(name: str):
    raise ValueError(f"{name}: 브라우저 JSON.parse가 읽지 못하는 값")


def _num(s: str) -> str:
    """s가 더 긴 숫자의 일부가 아닐 때만 맞는 정규식(0.407은 0.4071·10.407 안에서는 맞지 않는다)."""
    return rf"(?<![\d.])(?<!\d,){re.escape(s)}(?!\d|[.,]\d)"


def _verdict(ci) -> str:
    """차이 95% 구간 → 판정(scripts/build_backtest.py와 따로 계산한다)."""
    if not ci:
        return "na"
    return "a" if ci[0] > 0 else ("b" if ci[1] < 0 else "same")


def _hour(s, what: str) -> dt.datetime:
    assert isinstance(s, str) and ON_HOUR.fullmatch(s), f"{what} {s!r}: 시 단위('YYYY-MM-DD HH:00') 형식이 아님"
    return dt.datetime.strptime(s, TIME_FMT)


@pytest.fixture(scope="module")
def raw() -> bytes:
    return OUT.read_bytes()


@pytest.fixture(scope="module")
def data(raw) -> dict:
    return json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)


@pytest.fixture(scope="module")
def audit() -> dict:
    return json.loads((RES / "audit.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def builder():
    """scripts/build_backtest.py를 경로로 읽은 모듈(패키지가 아니므로)."""
    spec = importlib.util.spec_from_file_location("build_backtest", BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------- 형식 ----------
def test_strict_json_and_size(raw, data):
    assert isinstance(data, dict)
    assert len(raw) < MAX_BYTES, f"{len(raw):,}바이트(한도 {MAX_BYTES:,})"


def test_required_keys(data):
    missing = [k for k in REQUIRED if k not in data]
    assert not missing, f"빠진 키 {missing}"
    for k in ("answer", "limits"):
        assert data[k] and all(isinstance(s, str) and s for s in data[k]), k
    assert data["models"] and data["pairs"] and data["cases"]


def test_case_series_lengths(data):
    for c in data["cases"]:
        s = c["series"]
        n = s["n"]
        assert isinstance(n, int) and n > 0, c["id"]
        arrays = {k: v for k, v in s.items() if isinstance(v, list)}
        assert set(SERIES) <= set(arrays), f"사례 {c['id']}: 빠진 시계열 {sorted(set(SERIES) - set(arrays))}"
        bad = {k: len(v) for k, v in arrays.items() if len(v) != n}
        assert not bad, f"사례 {c['id']}: n={n}인데 길이가 다른 시계열 {bad}"


# ---------- 공개 범위 ----------
def _forbidden_in(text: str) -> list[str]:
    return [w for w in FORBIDDEN if w in text.lower()] + PIER.findall(text)


def test_no_forbidden_names(raw):
    found = _forbidden_in(raw.decode("utf-8"))
    assert not found, f"backtest.json에 있으면 안 되는 이름: {found}"


@pytest.mark.parametrize("rel", PUBLIC_PAGES)
def test_public_page_has_no_forbidden_names(rel):
    p = ROOT / rel
    if not p.exists():
        pytest.skip(f"{rel} 없음")
    found = _forbidden_in(p.read_text(encoding="utf-8"))
    assert not found, f"{rel}에 있으면 안 되는 이름: {found}"


def test_case_ship_values_are_hour_and_band_only(data):
    """사례에서 배 하나에 대한 값은 시 단위로 내린 도착 시각과 대기 구간뿐이다(분 단위 시각·배별 정확한 대기 시간 없음).
    에피소드 시작·끝도 시 단위, 그림 시계열은 짝수 시에서 시작하는 2시간 격자, 대기 시간 요약값은 시 단위로 반올림한 값."""
    bands = data["case_bands"]
    assert isinstance(bands, list) and bands and all(isinstance(b, str) and b for b in bands), bands
    for c in data["cases"]:
        cid, s, f = c["id"], c["series"], c["facts"]
        _hour(c["start"], f"사례 {cid} start")
        _hour(c["end"], f"사례 {cid} end")
        t0 = _hour(s["t0"], f"사례 {cid} series.t0")
        assert t0.hour % 2 == 0 and s["step_h"] == 2, f"사례 {cid}: 시계열이 짝수 시 2시간 격자가 아님(t0 {s['t0']}, step_h {s['step_h']})"
        assert list(f["wait_bands_event"]) == bands, f"사례 {cid}: wait_bands_event 구간 {list(f['wait_bands_event'])} ≠ case_bands {bands}"
        for k in ("wait_h_median", "wait_h_max", "wait_h_max_window"):
            assert f.get(k) is None or float(f[k]).is_integer(), f"사례 {cid}: {k}={f[k]}, 시 단위로 반올림한 값이 아님"
        for a in c["arrivals"]:
            assert isinstance(a, dict) and set(a) == ARRIVAL_KEYS, f"사례 {cid}: 도착 점 키 {sorted(a)}(허용 {sorted(ARRIVAL_KEYS)})"
            assert "wait_h" not in json.dumps(a, ensure_ascii=False), f"사례 {cid}: 도착 점에 대기 시간이 있음 {a}"
            _hour(a["t"], f"사례 {cid} 도착 시각")
            assert a["band"] in bands, f"사례 {cid}: case_bands {bands}에 없는 도착 점 구간 {a['band']!r}"


def test_no_minute_level_times(data):
    """만든 시각(generated_kst) 말고는 어디에도 분이 00이 아닌 시각이 없다(배 하나의 분 단위 도착 시각이 드러나지 않게)."""
    body = json.dumps({k: v for k, v in data.items() if k != "generated_kst"}, ensure_ascii=False)
    bad = sorted({m.group(0) for m in STAMP.finditer(body) if m.group(1) != "00"})
    assert not bad, f"분 단위 시각 {len(bad)}개: {bad[:10]}"


# ---------- 숫자 출처 ----------
def test_model_numbers_match_rdelay_json(data):
    r = json.loads((RES / "rdelay.json").read_text(encoding="utf-8"))
    ci = r["bootstrap_95"]
    assert {"S0", "S1", "R1"} <= {m["key"] for m in data["models"]}
    for k in ("S0", "S1", "R1"):
        assert ci.get(f"{k}.pr_auc"), f"{k}: rdelay.json에 PR-AUC 부트스트랩 구간이 없음"
    for m in data["models"]:
        k = m["key"]
        t = r["models"][k]["test"]
        assert (m["pr_auc"], m["roc_auc"]) == (t["pr_auc"], t["roc_auc"]), k
        assert (m["pr_ci"], m["roc_ci"]) == (ci.get(f"{k}.pr_auc"), ci.get(f"{k}.roc_auc")), k
    for p in data["pairs"]:
        k = f"{p['a']}-{p['b']}"
        assert (p["pr_ci"], p["roc_ci"]) == (ci.get(f"{k}.pr_auc"), ci.get(f"{k}.roc_auc")), k
    assert data["test_pos_rate"] == r["test_pos_rate"]


def test_labels_match_audit(data, audit):
    lab, al = data["labels"], audit["labels"]
    rows = [x for x in audit["sensitivity"]["rows"] if x["thr"] == 12 and x["cap"] == 168]
    assert len(rows) == 1, f"audit.json 민감도 표에서 12시간 초과·168시간 상한 줄이 {len(rows)}개"
    assert lab["gt12_capped"] == rows[0]["ships"], f"labels.gt12_capped {lab['gt12_capped']} ≠ audit 민감도 표 {rows[0]['ships']}"
    assert (lab["voyages"], lab["gt12"], lab["n_gt_168"]) == (al["n"], al["gt12"], al["n_gt_168"])
    # 12시간 초과(상한 없음) = 라벨 양성(12시간 초과 168시간 이하) + 168시간 초과(비운영 체류로 보고 양성에서만 뺌)
    assert lab["gt12"] == lab["gt12_capped"] + lab["n_gt_168"], lab


# ---------- 요약·한계 문장 ----------
def test_pair_verdicts_match_intervals(data):
    for p in data["pairs"]:
        k = f"{p['a']}-{p['b']}"
        assert p["pr_verdict"] == _verdict(p["pr_ci"]), (k, p["pr_ci"], p["pr_verdict"])
        assert p["roc_verdict"] == _verdict(p["roc_ci"]), (k, p["roc_ci"], p["roc_verdict"])


def test_answer_verdict_words_match_pairs(data):
    """요약 문장의 판정 표현이 pairs[].pr_verdict와 맞는지(맞는 판정의 표현이 있고, 다른 판정의 표현은 없다)."""
    text = " ".join(data["answer"])
    verdict = {(p["a"], p["b"]): p["pr_verdict"] for p in data["pairs"]}
    for pair, words in VERDICT_WORDS.items():
        v = verdict.get(pair)
        assert v in words, f"{pair}: 판정 {v!r}(pairs에 없거나 차이 구간이 없음)"
        assert words[v] in text, f"{pair}: 판정 '{v}'인데 요약 문장에 없는 표현 '{words[v]}'"
        wrong = [w for k, w in words.items() if k != v and w in text]
        assert not wrong, f"{pair}: 판정 '{v}'인데 요약 문장에 다른 판정의 표현 {wrong}"


def test_answer_numbers_match_models(data):
    """요약 문장의 숫자는 periods·models·pairs 값을 같은 자릿수로 적은 것이다.
    정밀도가 '가장 높'다고 하면 참고 상한(기상 완벽 예보)을 뺀 비교 모형 중 R-Delay가 가장 높아야 한다."""
    text = " ".join(data["answer"])
    m = {x["key"]: x for x in data["models"]}
    p = {(x["a"], x["b"]): x for x in data["pairs"]}
    a = m["R1"]["alarm"]
    t0, t1 = data["periods"]["test"]
    want = [t0[:10], t1[:10], f"{data['periods']['n_tau']['test']:,}", f"{data['test_pos_rate']:.3f}",
            *(f"{m[k]['pr_auc']:.3f}" for k in ("R1", "S1", "S0")),
            *(f"{p[k]['pr_ci'][0]:+.3f}~{p[k]['pr_ci'][1]:+.3f}" for k in VERDICT_WORDS),
            f"{a['precision']:.2f}", str(a["episodes"]), str(a["episodes"] - a["caught_72h"])]
    missing = [w for w in want if not re.search(_num(w), text)]
    assert not missing, f"요약 문장에 없는 숫자 {missing}"
    best = max(x["alarm"]["precision"] for x in data["models"] if x["group"] != "oracle")
    for s in data["answer"]:
        if "정밀도" in s and "가장 높" in s:
            assert a["precision"] >= best, f"'가장 높'다고 했지만 R-Delay 정밀도 {a['precision']} < {best}: {s}"


def test_limits_quote_current_numbers(data):
    """한계 문장의 숫자: 168시간 초과 대기 수, P(R_d>1) 최대(경보 0.5에 한 번도 닿지 않음. '늘 0'이라고 하지 않는다),
    태풍 사례는 태풍이 500km 안에 있던 동안의 최댓값(그림 기간 최댓값이 아님)."""
    text = " ".join(data["limits"])
    n168 = data["labels"]["n_gt_168"]
    assert re.search(_num(str(n168)) + "건", text), f"한계 문장에 168시간 초과 대기 수({n168}건) 없음"
    ref = data["rd_reference"]
    if ref["p_rd1_max"] < 0.5:
        s = next((x for x in data["limits"] if "P(R_d>1)" in x), "")
        assert "한 번도 울리지 않았" in s, f"확산 경보가 울리지 않았다는 한계 문장이 없음: {s!r}"
        assert re.search(_num(f"{ref['p_rd1_max']:.4f}"), s), f"한계 문장에 P(R_d>1) 최대 {ref['p_rd1_max']:.4f} 없음: {s!r}"
    ty = next((c for c in data["cases"] if c["kind"] == "typhoon"), None)
    s = next((x for x in data["limits"] if "태풍" in x and "m/s" in x), None)
    if ty and s:
        f = ty["facts"]
        assert re.search(_num(str(f["wind_max_event"])) + "m/s", s), f"한계 문장에 태풍 기간 최대 풍속 {f['wind_max_event']}m/s 없음: {s}"
        assert re.search(_num(str(f["wave_max_event"])) + r"m(?!/)", s), f"한계 문장에 태풍 기간 최대 파고 {f['wave_max_event']}m 없음: {s}"


# ---------- 사례 ----------
def test_case_facts_match_public_series(data):
    """사례 숫자(facts)는 공개한 시계열·도착 점(시 단위)에서 다시 세어도 같다.
    선행시간은 시 단위로 내린 시작으로 잰다: [시작 − 72h, 시작)의 첫 경보, 시작 뒤 첫 경보, [시작 − 24h, 시작)의 경보 여부."""
    h = dt.timedelta(hours=1)
    for c in data["cases"]:
        s, f = c["series"], c["facts"]
        st, en = _hour(c["start"], "start"), _hour(c["end"], "end")
        t0 = _hour(s["t0"], "series.t0")
        alarms = [t0 + i * s["step_h"] * h for i, a in enumerate(s["alarm"]) if a]
        before = [t for t in alarms if st - LEAD_H * h <= t < st]
        after = [t for t in alarms if t >= st]
        arr = [(_hour(a["t"], "도착 시각"), a["band"]) for a in c["arrivals"]]
        inside = [b for t, b in arr if st <= t <= en]
        got = {
            "ships_window": len(arr), "ships_event": len(inside),
            "wait_bands_event": {b: inside.count(b) for b in data["case_bands"]},
            "first_alarm_lead_h": (st - before[0]) / h if before else None,
            "first_alarm_after_start_h": (after[0] - st) / h if after else None,
            "alarm_in_24h_before": any(t >= st - 24 * h for t in before),
            "tau": s["n"], "alarm_tau": sum(s["alarm"]), "y_tau": sum(y == 1 for y in s["y"]),
            "alarm_tau_correct": sum(bool(a) and y == 1 for a, y in zip(s["alarm"], s["y"])),
            "alarm_threshold": data["alarm_rule"]["threshold"],
        }
        diff = {k: (v, f.get(k)) for k, v in got.items() if f.get(k) != v}
        assert not diff, f"사례 {c['id']}: 공개 시계열에서 다시 센 값(앞)과 facts(뒤)가 다름 {diff}"


# ---------- 출처·재현 ----------
def test_source_digest_matches_inputs(data, builder):
    assert data["source_files"] == builder.SOURCE_FILES
    assert isinstance(data["source_digest"], str) and re.fullmatch(r"[0-9a-f]{12}", data["source_digest"]), data["source_digest"]
    assert data["source_digest"] == builder.source_digest(), \
        "입력 결과 파일(source_files)이 backtest.json을 만든 뒤 바뀜: python scripts/build_backtest.py로 다시 만드세요"
    bfc = data["built_from_commit"]  # 커밋(입력이 커밋과 다르면 '+수정'). git 밖에서 만들면 없음
    assert bfc is None or (isinstance(bfc, str) and re.fullmatch(r"[0-9a-f]{4,40}(\+수정)?", bfc)), bfc


def test_rebuild_reproduces_file(data, builder, monkeypatch):
    monkeypatch.setattr(builder, "git_commit", lambda: None)  # 커밋은 비교하지 않으므로 git을 부르지 않는다
    built = builder.build()
    built = json.loads(json.dumps(built, ensure_ascii=False, allow_nan=False))  # 파일과 같은 JSON 값으로 맞춘다
    assert set(VOLATILE) <= set(built)
    a = {k: v for k, v in built.items() if k not in VOLATILE}
    b = {k: v for k, v in data.items() if k not in VOLATILE}
    diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    assert not diff, f"다시 만든 결과와 다른 키 {diff}: python scripts/build_backtest.py로 다시 만드세요"
