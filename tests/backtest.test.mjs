// 실자료 검증 페이지(docs/backtest.html · docs/assets/js/backtest.js) 점검: node --test tests/backtest.test.mjs
// docs/data/backtest.json의 모양(키·구간·시계열 길이·NaN 없음)과, 화면 문장을 만드는 순수 함수가
// 숫자를 새로 만들지 않고 JSON 값을 같은 규칙(toFixed)으로 옮기는지 본다. 공개 문구 규칙(평가 기간, 이름 없음)도 확인한다.
//
// 시간대: 화면의 시각 글자는 한국시간 글자를 그대로 옮기므로 실행하는 곳의 시간대와 상관없어야 한다.
// 기본 실행 환경(CI의 UTC, 이 컴퓨터의 한국시간)에서는 지역 시각 함수(getHours 등)를 잘못 써도 시험이 통과할 수 있으므로,
// 무엇보다 먼저 UTC도 한국시간도 아닌 서머타임 시간대로 바꾼 뒤에 화면 모듈을 불러온다(정적 import는 이 줄보다 먼저 실행되므로 동적 import).
process.env.TZ = "America/Los_Angeles";

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const {
  REQUIRED_KEYS, SERIES_KEYS, ARRIVAL_KEYS, ON_HOUR, checkShape, fx, fsign, fpct, fint, fhour, fci, valCi, josa, verdictWord, SAME_WORD,
  publicWording, splitFirstSentence, parseTime, fmtMD, fmtMDH, fmtYMDH, seriesTimes, seriesLabel, dayTicks, runs, stepPoints, modelByKey,
  modelLabel, GROUPS, plainSummary, windowNote, rdSentence, SPREAD_ALARM_P, spearmanRows, spearmanSentence, vesselNote, scoresNote,
  labelsSentence, anchorageSentence, pretestSentence, pretestRows, pretestTop, pretestNote, filesLead, commitNote, DIRTY_MARK, dataScopeText, subgroupBest,
  caseTabLabel, caseBands, bandCountText, caseFactsLines, caseTipRows, caseTableRows, arrivalSlots, arrivalTableRows, bandAxisLabel,
  compareTipRows, reliabilitySeries, relTip, waitThreshold, waitCap, alarmRatePct, axisTicks, tickText,
} = await import("../docs/assets/js/backtest.js");

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const RAW = readFileSync(join(root, "docs", "data", "backtest.json"), "utf8");
const B = JSON.parse(RAW);
const HTML = readFileSync(join(root, "docs", "backtest.html"), "utf8");
const JS = readFileSync(join(root, "docs", "assets", "js", "backtest.js"), "utf8");
const HOUR = 3600e3;

// 화면에 나가는 문장 모두(순수 함수 결과). DOM 없이 만들 수 있는 것만 모은다.
function allScreenText() {
  const parts = [plainSummary(B), windowNote(B), rdSentence(B), spearmanSentence(B), vesselNote(B), scoresNote(B), publicWording(B.case_note),
    labelsSentence(B), anchorageSentence(B), pretestSentence(B), pretestNote(B), filesLead(B), commitNote(B), dataScopeText(B)];
  for (const r of pretestRows(B)) parts.push(r.band, fx(r.arrivals_pct, 1), fx(r.gt12_pct, 1));
  for (const c of B.cases) {
    parts.push(c.title, publicWording(c.rule), publicWording(c.attribution?.text), caseTabLabel(c), ...caseFactsLines(c, B));
    parts.push(fmtYMDH(parseTime(c.start)), fmtYMDH(parseTime(c.end)), bandCountText(c.facts.wait_bands_event, B));
    for (let i = 0; i < c.series.n; i++) parts.push(...caseTipRows(c, i).flatMap((r) => [r.name, r.value]));
    parts.push(...caseTableRows(c).flat(), ...arrivalTableRows(c).flat());
  }
  for (const b of caseBands(B)) parts.push(bandAxisLabel(b));
  for (const m of B.models) parts.push(modelLabel(m), ...compareTipRows(m).flatMap((r) => [r.name, r.value]));
  for (const g of Object.values(GROUPS)) parts.push(g.label);
  for (const p of B.pairs) parts.push(verdictWord(p, "pr"), verdictWord(p, "roc"), fci(p.pr_ci, 3, true), fci(p.roc_ci, 3, true));
  for (const s of reliabilitySeries(B)) for (const b of s.pts) parts.push(...relTip(s, b).flatMap((r) => [r.name, r.value]));
  for (const r of spearmanRows(B)) parts.push(r.label);
  return parts.join("\n");
}

test("backtest.json: 화면이 쓰는 키가 모두 있고 모양 점검이 깨끗하다", () => {
  for (const k of REQUIRED_KEYS) assert.ok(k in B, `${k} 없음`);
  assert.deepEqual(checkShape(B), []);
  assert.ok(Array.isArray(B.answer) && B.answer.length > 0);
  assert.ok(Array.isArray(B.limits) && B.limits.length > 0);
  assert.ok(B.models.length > 0 && B.pairs.length > 0 && B.cases.length > 0 && B.sources.length > 0);
  for (const k of ["train", "val", "test"]) {
    assert.equal(B.periods[k].length, 2);
    assert.ok(Number.isInteger(B.periods.n_tau[k]) && B.periods.n_tau[k] > 0);
  }
  assert.match(B.source_digest, /^[0-9a-f]{12}$/, "입력 결과 파일 해시는 16진수 12자리");
  assert.ok(Array.isArray(B.case_bands) && B.case_bands.length > 0 && new Set(B.case_bands).size === B.case_bands.length);
  // 모양 점검은 사례 도착 기록의 어긋남(키·시 단위·구간)을 잡는다
  const bad = structuredClone(B);
  bad.cases[0].arrivals.push({ t: "2026-09-20 16:24", band: "12~24시간", wait_h: 13.4 });
  bad.cases[0].arrivals.push({ t: "2026-09-20 16:00", band: "5~6시간" });
  bad.cases[0].start = "2026-09-18 17:32";
  const probs = checkShape(bad);
  assert.ok(probs.some((p) => /키가 band·t·wait_h/.test(p)), probs.join(" / "));
  assert.ok(probs.some((p) => /\.t가 시 단위가 아님/.test(p)) && probs.some((p) => /band가 case_bands에 없음/.test(p)) && probs.some((p) => /start가 시 단위가 아님/.test(p)));
});

test("모형: PR·ROC 95% 구간이 [아래, 위] 두 값이고 점 추정값을 감싼다(참고 모형만 구간 없음)", () => {
  for (const m of B.models) {
    for (const k of ["pr", "roc"]) {
      const ci = m[`${k}_ci`];
      if (m.group === "oracle") { assert.ok(ci === null || Array.isArray(ci), `${m.key}.${k}_ci`); continue; }
      assert.ok(Array.isArray(ci) && ci.length === 2, `${m.key}.${k}_ci가 배열이 아님`);
      assert.ok(ci[0] <= m[`${k}_auc`] && m[`${k}_auc`] <= ci[1], `${m.key}.${k}_auc가 구간 밖`);
    }
    assert.ok(["base", "rdelay", "hybrid", "oracle"].includes(m.group), m.group);
    for (const k of ["rate", "precision", "recall", "episodes", "caught_72h", "caught_cover", "onsets"]) assert.equal(typeof m.alarm[k], "number", `${m.key}.alarm.${k}`);
    assert.ok(m.alarm.caught_cover <= m.alarm.caught_72h && m.alarm.caught_72h <= m.alarm.episodes, `${m.key} 에피소드 수`);
  }
  for (const p of B.pairs) {
    assert.ok(modelByKey(B, p.a) && modelByKey(B, p.b), `${p.a}-${p.b} 모형 없음`);
    assert.ok(["a", "b", "same", "na"].includes(p.pr_verdict) && ["a", "b", "same", "na"].includes(p.roc_verdict));
  }
  // 참고 모형 범례: 'S2 + 앞으로의 실제 기상'(모든 모형의 상한이 아니다)
  assert.equal(GROUPS.oracle.label, "참고: S2 + 앞으로의 실제 기상(실제로는 알 수 없음)");
  assert.doesNotMatch(Object.values(GROUPS).map((g) => g.label).join(" "), /상한/);
});

test("사례 시계열: 모든 계열 길이가 n이고, 시각·도착·시작·끝을 읽을 수 있다", () => {
  for (const c of B.cases) {
    const s = c.series;
    assert.ok(Number.isFinite(parseTime(s.t0)), `${c.id} t0`);
    for (const k of SERIES_KEYS) assert.equal(s[k].length, s.n, `${c.id}.${k} 길이`);
    for (const k of ["alarm", "y"]) assert.ok(s[k].every((v) => v === 0 || v === 1 || v === null), `${c.id}.${k}는 0/1`);
    assert.equal(seriesTimes(s).length, s.n);
    assert.ok(Number.isFinite(parseTime(c.start)) && Number.isFinite(parseTime(c.end)) && parseTime(c.start) <= parseTime(c.end), `${c.id} 시작·끝`);
    // 도착은 그림 기간 안: 자르기 전 칸 위치(t − t0)/(2시간)가 [0, n]이어야 한다(마지막 판단 시각 뒤 한 칸, 그 2시간 안 도착까지)
    for (const a of c.arrivals) {
      const off = (parseTime(a.t) - parseTime(s.t0)) / (s.step_h * HOUR);
      assert.ok(Number.isFinite(off) && off >= 0 && off <= s.n, `${c.id} 도착 ${a.t}가 그림 기간 밖(칸 ${off}, n=${s.n})`);
    }
    const slots = arrivalSlots(c);
    assert.equal(slots.length, c.arrivals.length, `${c.id} 도착 시각`);
    assert.ok(slots.every((a) => Number.isInteger(a.i) && a.i >= 0 && a.i < s.n), `${c.id} 툴팁 칸`);
    assert.equal(caseTableRows(c).length, s.n);
    assert.equal(arrivalTableRows(c).length, c.arrivals.length);
  }
});

test("공개 사례 자료: 시작·끝·도착은 시 단위, 도착은 시각과 대기 시간 구간만(정확한 대기 시간 없음)", () => {
  const bands = caseBands(B);
  assert.deepEqual(bands, B.case_bands);
  for (const c of B.cases) {
    for (const k of ["start", "end"]) {
      assert.match(c[k], ON_HOUR, `${c.id}.${k} = ${c[k]}`);
      assert.ok(c[k].endsWith(":00"));
    }
    for (const a of c.arrivals) {
      assert.deepEqual(Object.keys(a).sort(), ARRIVAL_KEYS, `${c.id} 도착 키 ${Object.keys(a)}`);
      assert.deepEqual(ARRIVAL_KEYS, ["band", "t"]);
      assert.match(a.t, ON_HOUR, `${c.id} 도착 ${a.t}`);
      assert.ok(a.t.endsWith(":00"));
      assert.ok(B.case_bands.includes(a.band), `${c.id} 구간 ${a.band}`);
    }
    assert.ok(!("wait_h" in c) && c.arrivals.every((a) => !("wait_h" in a)));
    assert.doesNotMatch(JSON.stringify(c.arrivals), /wait_h|\d{2}:(?!00)\d{2}/, `${c.id} 도착 기록에 대기 시간·분 단위 시각이 없다`);
    // 사실 요약의 척수·구간별 척수는 공개한 도착 기록(시 단위로 내린 시각)과 맞는다
    const f = c.facts;
    const st = parseTime(c.start), en = parseTime(c.end);
    const inside = c.arrivals.filter((a) => parseTime(a.t) >= st && parseTime(a.t) <= en);
    assert.equal(f.ships_window, c.arrivals.length, `${c.id} 그림 기간 척수`);
    assert.equal(f.ships_event, inside.length, `${c.id} 사건 동안 척수`);
    assert.deepEqual(Object.keys(f.wait_bands_event), B.case_bands, `${c.id} 구간 이름`);
    for (const b of B.case_bands) assert.equal(f.wait_bands_event[b], inside.filter((a) => a.band === b).length, `${c.id} ${b} 척수`);
    // 대기 시간 요약은 시 단위(정수)
    for (const k of ["wait_h_median", "wait_h_max", "wait_h_max_window"]) assert.ok(f[k] === null || Number.isInteger(f[k]), `${c.id}.${k} = ${f[k]}`);
  }
  // 줄 이름은 단위를 뗀 구간: 「48~168시간」 → 「48~168」
  assert.equal(bandAxisLabel("48~168시간"), "48~168");
  assert.deepEqual(B.case_bands.map(bandAxisLabel), B.case_bands.map((b) => b.replace(/시간$/, "")));
  // 표·툴팁: 도착은 「MM-DD HH시」와 구간만
  for (const c of B.cases) {
    for (const [t, band] of arrivalTableRows(c)) {
      assert.match(t, /^\d{2}-\d{2} \d{2}시$/);
      assert.ok(B.case_bands.includes(band));
    }
    for (const a of arrivalSlots(c)) {
      const row = caseTipRows(c, a.i).find((r) => r.name === `${fmtMDH(a.t)} 도착 배의 대기 시간 구간`);
      assert.ok(row && row.value === a.band, `${c.id} 툴팁 ${fmtMDH(a.t)}`);
    }
  }
});

test("NaN·Infinity·undefined가 자료와 화면 문장 어디에도 없다", () => {
  const walk = (o, path) => {
    if (typeof o === "number") assert.ok(Number.isFinite(o), `${path} = ${o}`);
    else if (Array.isArray(o)) o.forEach((v, i) => walk(v, `${path}[${i}]`));
    else if (o && typeof o === "object") for (const [k, v] of Object.entries(o)) walk(v, `${path}.${k}`);
  };
  walk(B, "B");
  assert.doesNotMatch(RAW, /NaN|Infinity/);
  assert.doesNotMatch(allScreenText(), /NaN|Infinity|undefined|\[object|null/);
});

test("시각 글자: 시간대와 상관없이 한국시간 글자 그대로, t0에서 2시간 칸으로 읽고 월말·연말을 넘긴다", () => {
  // 맨 위에서 바꾼 시간대가 정말 적용됐는지(UTC면 이 시험이 지역 시각 함수 실수를 잡지 못한다)
  assert.equal(process.env.TZ, "America/Los_Angeles");
  assert.notEqual(new Date(Date.UTC(2026, 0, 15)).getTimezoneOffset(), 0);
  const check = (tz) => {
    process.env.TZ = tz;
    const m = `TZ=${tz}`;
    assert.equal(seriesLabel("2026-09-14 18:00", 2, 0), "09-14 18시", m);
    assert.equal(seriesLabel("2026-09-14 18:00", 2, 3), "09-15 00시", m);
    assert.equal(seriesLabel("2026-02-28 20:00", 2, 2), "03-01 00시", m);
    assert.equal(seriesLabel("2025-12-31 22:00", 2, 1), "01-01 00시", m);
    // 미국 서머타임이 시작·끝나는 시각(지역 시각으로 읽으면 02시가 없거나 01시가 두 번)
    assert.equal(seriesLabel("2026-03-08 00:00", 2, 1), "03-08 02시", m);
    assert.equal(seriesLabel("2026-11-01 00:00", 1, 1), "11-01 01시", m);
    assert.equal(fmtMD(parseTime("2026-07-02 04:24:00")), "07-02", m);
    assert.equal(fmtMDH(parseTime("2025-08-21 09:00")), "08-21 09시", m);
    assert.equal(fmtYMDH(parseTime("2026-09-18 17:00")), "2026-09-18 17시", m);
    assert.equal(fmtYMDH(parseTime("2025-12-31 23:00")), "2025-12-31 23시", m);
    assert.equal(fmtYMDH(NaN), "–");
    assert.ok(Number.isNaN(parseTime("2026/09/14")), m);
    const a = B.cases.find((c) => c.id === "a") || B.cases[0];
    const times = seriesTimes(a.series);
    assert.equal(fmtMDH(times[0]), seriesLabel(a.series.t0, a.series.step_h, 0), m);
    assert.equal(times[1] - times[0], a.series.step_h * HOUR, m);
    // 사례의 시작·끝 글자는 JSON의 「YYYY-MM-DD HH:00」을 「YYYY-MM-DD HH시」로만 바꾼 것
    for (const c of B.cases) for (const k of ["start", "end"]) assert.equal(fmtYMDH(parseTime(c[k])), `${c[k].slice(0, 13)}시`, `${m} ${c.id}.${k}`);
    // 자정 눈금: 겹치지 않게 개수를 줄이고, 모두 자정이다
    const tk = dayTicks(parseTime("2026-09-14 18:00"), parseTime("2026-10-01 22:00"), 5);
    assert.ok(tk.length <= 5 && tk.length >= 2, m);
    assert.deepEqual(tk.map(fmtMD).slice(0, 2), ["09-15", "09-19"], m);
    assert.ok(tk.every((t) => new Date(t).getUTCHours() === 0), m);
  };
  try {
    for (const tz of ["America/Los_Angeles", "Asia/Seoul", "UTC", "Pacific/Chatham"]) check(tz);
  } finally {
    process.env.TZ = "America/Los_Angeles";
  }
});

test("숫자 형식: 저장값을 toFixed로 반올림하고 -0은 쓰지 않는다", () => {
  assert.equal(fx(0.0465, 3), "0.046");
  assert.equal(fx(0.4071, 3), "0.407");
  // 저장된 이진값이 딱 절반이면 Python format()처럼 짝수 쪽(answer·compare.md·그림과 같게). toFixed만 쓰면 0.313이 된다.
  assert.equal(fx(0.3125, 3), "0.312");
  assert.equal(fx(0.375, 2), "0.38");
  assert.equal(fx(0.125, 2), "0.12");
  assert.equal(fx(-0.0625, 3), "-0.062");
  assert.equal(fx(12.5, 0), "12");
  assert.equal(fx(0.0025, 3), "0.003", "0.0025는 이진값이 절반보다 조금 커서 올린다(Python과 같음)");
  assert.equal(fx(-0.0003, 3), "0.000");
  assert.equal(fx(null), "–");
  assert.equal(fx(0.0019, 4), "0.0019");
  assert.equal(fsign(0.0429, 3), "+0.043");
  assert.equal(fsign(-0.0123, 3), "-0.012");
  assert.equal(fpct(0.1072, 1), "10.7%");
  assert.equal(fpct(-0.0001, 1), "0.0%");
  assert.equal(fint(5821), "5,821");
  assert.equal(fint(24177), "24,177");
  // 시 단위로 잰 시간은 소수점 없이(71.0 → 「71」), 그렇지 않으면 소수 한 자리
  assert.equal(fhour(71.0), "71");
  assert.equal(fhour(122), "122");
  assert.equal(fhour(37.6), "37.6");
  assert.equal(fhour(null), "–");
  assert.equal(fci([0.2442, 0.3469], 3), "0.244~0.347");
  assert.equal(fci(null), "–");
  assert.equal(valCi(0.4071, [0.3226, 0.5], 3), "0.407 [0.323~0.500]");
  assert.equal(valCi(0.3313, null, 3), "0.331");
  assert.equal(tickText(0.2 + 0.1), "0.3");
  const ax = axisTicks(0.2442, 0.5, 6, 0.03);
  assert.ok(ax.d0 <= 0.2442 && ax.d1 >= 0.5 && ax.ticks[0] === ax.d0 && ax.ticks.at(-1) === ax.d1);
});

test("요약 문장(answer)의 숫자와 같은 규칙으로 옮긴다", () => {
  const r1 = modelByKey(B, "R1"), s1 = modelByKey(B, "S1"), s0 = modelByKey(B, "S0");
  const p = (a, b) => B.pairs.find((x) => x.a === a && x.b === b);
  assert.ok(B.answer[0].includes(`R-Delay ${fx(r1.pr_auc, 3)}`));
  assert.ok(B.answer[0].includes(`지속성 ${fx(s1.pr_auc, 3)}`));
  assert.ok(B.answer[0].includes(`기후값 ${fx(s0.pr_auc, 3)}`));
  assert.ok(B.answer[0].includes(fx(B.test_pos_rate, 3)));
  assert.ok(B.answer[0].includes(fint(B.periods.n_tau.test)));
  assert.ok(B.answer[1].includes(fci(p("R1", "S0").pr_ci, 3, true)));
  assert.ok(B.answer[1].includes(fci(p("R1", "S1").pr_ci, 3, true)));
  assert.ok(B.answer[3].includes(fci(p("R3b", "S3").pr_ci, 3, true)));
  assert.ok(B.answer[2].includes(fx(r1.alarm.precision, 2)));
  assert.ok(B.answer[2].includes(`${r1.alarm.episodes - r1.alarm.caught_72h}개`));
});

test("판정 말: 앞·뒤 모형 이름에 맞는 조사, 0을 포함하면 차이 없음", () => {
  assert.equal(verdictWord({ a_name: "R-Delay 점수", b_name: "기후값", pr_verdict: "a" }, "pr"), "R-Delay 점수가 낫다");
  assert.equal(verdictWord({ a_name: "R-Delay 점수", b_name: "기후값", roc_verdict: "b" }, "roc"), "기후값이 낫다");
  assert.equal(verdictWord({ a_name: "R-Delay+S3", b_name: "스케줄", pr_verdict: "a" }, "pr"), "R-Delay+S3이 낫다");
  assert.equal(verdictWord({ a_name: "스케줄", b_name: "로지스틱", pr_verdict: "same" }, "pr"), SAME_WORD);
  assert.equal(SAME_WORD, "차이 없음(95% 구간이 0을 포함)");
  assert.equal(verdictWord({ pr_verdict: "na" }, "pr"), "–");
  assert.equal(josa("지속성", ["과", "와"]), "지속성과");
  assert.equal(josa("R-Delay 확률", ["은", "는"]), "R-Delay 확률은");
  assert.equal(josa("0.28", ["으로", "로"]), "0.28로");
  assert.equal(josa("0.30", ["으로", "로"]), "0.30으로");
  // 짝 판정은 95% 구간과 맞아야 한다
  for (const p of B.pairs) {
    for (const k of ["pr", "roc"]) {
      const [lo, hi] = p[`${k}_ci`];
      const want = lo > 0 ? "a" : hi < 0 ? "b" : "same";
      assert.equal(p[`${k}_verdict`], want, `${p.a}-${p.b} ${k}`);
    }
  }
});

test("쉬운 말 요약·경보 문장은 판정과 JSON 숫자에서 나온다", () => {
  const p = (a, b) => B.pairs.find((x) => x.a === a && x.b === b);
  const plain = plainSummary(B);
  if (p("R1", "S0").pr_verdict === "a") assert.match(plain, /기후값보다 낫/);
  if (p("R1", "S1").pr_verdict === "same") assert.match(plain, /지속성과는 차이가 없습니다/);
  if (p("R3b", "S3").pr_verdict === "a") assert.match(plain, /스케줄 기준선에 R-Delay 상태를 더하면 나아집니다/);
  assert.doesNotMatch(plain, /\d/, "쉬운 말 요약에는 숫자를 쓰지 않는다");
  const often = B.models.filter((m) => m.group !== "oracle").reduce((a, b) => (b.alarm.onsets > a.alarm.onsets ? b : a));
  const w = windowNote(B);
  assert.ok(w.includes(`${often.alarm.onsets}번`) && w.includes(`${often.alarm.caught_72h}개`) && w.includes(fx(often.alarm.precision, 2)));
  const al = modelByKey(B, B.alarm_rule.model);
  assert.ok(w.includes(`${al.alarm.onsets}번`) && w.includes(`${al.alarm.caught_72h}개를`));
  assert.equal(waitThreshold(B), 12);
  assert.equal(waitCap(B), 168);
  assert.equal(alarmRatePct(B), 10);
  assert.ok(spearmanSentence(B).includes(fx(B.posthoc.spearman["R1~S1"], 3)));
  assert.match(vesselNote(B), /기준선보다 PR-AUC가 낮았습니다/);
  assert.match(scoresNote(B), /Brier 기술점수/);
});

test("R_d 문장: P(R_d>1)은 늘 0이 아니라 경보 기준 0.5에 한 번도 닿지 않았다(평가 기간 최대값 그대로)", () => {
  const r = B.rd_reference;
  const rd = rdSentence(B);
  assert.ok(rd.includes(fx(r.rd_median, 2)) && rd.includes(fx(r.rd_max, 2)), rd);
  assert.equal(SPREAD_ALARM_P, 0.5);
  assert.ok(r.p_rd1_max > 0 && r.p_rd1_max < SPREAD_ALARM_P, "지금 자료: 0보다 크고 0.5보다 작음");
  assert.ok(rd.includes(`(평가 기간 P(R_d>1) 최대 ${fx(r.p_rd1_max, 4)})`), rd);
  assert.match(rd, /P\(R_d>1\) ≥ 0\.5\)는 실자료에서 한 번도 울리지 않았습니다/);
  assert.doesNotMatch(rd, /0\.00(?!\d)/, "최대값을 0.00으로 줄여 쓰지 않는다");
  // 한계 문장(limits)의 표현·숫자와 같다
  const lim = B.limits.find((x) => x.includes("P(R_d>1) ≥ 0.5"));
  assert.ok(lim && lim.includes(`P(R_d>1) 최대 ${fx(r.p_rd1_max, 4)}`) && lim.includes("한 번도 울리지 않았다"), lim);
  // 「늘 0」·「늘 1보다 작아」 같은 말을 쓰지 않는다
  assert.doesNotMatch(allScreenText(), /늘 1보다 작|늘 0|항상 0/);
  // 사례 툴팁·표의 P(R_d>1)은 저장된 소수 4자리 그대로
  const c = B.cases[0];
  assert.equal(caseTipRows(c, 0).find((x) => x.name === "P(R_d>1)").value, fx(c.series.p_rd1[0], 4));
  assert.equal(caseTableRows(c)[0][5], fx(c.series.p_rd1[0], 4));
});

test("사례 문장: case.facts 숫자를 그대로 옮기고, 대기는 시 단위·구간, 태풍은 500km 안에 있던 동안의 기상을 쓴다", () => {
  for (const c of B.cases) {
    const lines = caseFactsLines(c, B);
    const text = lines.join(" ");
    const f = c.facts;
    assert.ok(text.includes(`${f.tau}개`), `${c.id} 판단 시각 수`);
    assert.ok(text.includes(fx(f.prob_max, 3)) && text.includes(fx(f.alarm_threshold, 3)), `${c.id} 확률·기준`);
    assert.ok(text.includes(`${f.ships_window}척`), `${c.id} 그림 기간 척수`);
    assert.doesNotMatch(text, /\d+\.0시간/, `${c.id} 시 단위 값에 「.0」을 붙이지 않는다`);
    if (f.ships_event > 0) {
      assert.ok(text.includes(`${f.ships_event}척`), `${c.id} 사건 동안 척수`);
      assert.ok(text.includes(`중앙값은 ${f.wait_h_median}시간`) && text.includes(`가장 길게는 ${f.wait_h_max}시간`), `${c.id} 대기 시간(시 단위)`);
      for (const b of B.case_bands) assert.ok(text.includes(`${b} ${f.wait_bands_event[b]}척`), `${c.id} ${b}`);
      assert.equal(bandCountText(f.wait_bands_event, B), B.case_bands.map((b) => `${b} ${f.wait_bands_event[b]}척`).join(", "));
    } else if (Number.isFinite(f.wait_h_max_window)) assert.ok(text.includes(`가장 길게는 ${f.wait_h_max_window}시간`));
    if (f.alarm_tau > 0) assert.ok(text.includes(`${f.alarm_tau}개에서 경보가 켜졌고`) && text.includes(`${f.alarm_tau_correct}개가 맞았습니다`));
    else assert.match(text, /경보는 한 번도 켜지지 않았습니다/);
    if (Number.isFinite(f.first_alarm_lead_h)) assert.ok(text.includes(`${fhour(f.first_alarm_lead_h)}시간 전이었`));
    else if (c.kind !== "typhoon") assert.match(text, /72시간 안에는 경보가 없었습니다/);
    if (Number.isFinite(f.first_alarm_after_start_h) && !(c.kind === "typhoon" && !(f.alarm_tau > 0))) assert.ok(text.includes(`${fhour(f.first_alarm_after_start_h)}시간 뒤였습니다`));
    // 풍속·파고: 사건 동안의 최대가 앞, 그림 기간 전체의 최대는 「그림 기간 전체로는」 괄호 안에만
    const wx = lines.find((l) => l.includes("부산 풍속은 최대"));
    assert.ok(wx, `${c.id} 기상 문장`);
    assert.ok(wx.startsWith(c.kind === "typhoon" ? "태풍이 500km 안에 있던 동안 " : "에피소드 동안 "), wx);
    assert.ok(wx.includes(`부산 풍속은 최대 ${fx(f.wind_max_event, 1)}m/s`) && wx.includes(`거제도 유의파고는 최대 ${fx(f.wave_max_event, 1)}m`), wx);
    assert.ok(wx.includes(`(그림 기간 전체로는 풍속 최대 ${fx(f.wind_max, 1)}m/s, 파고 최대 ${fx(f.wave_max, 1)}m)`), wx);
    assert.ok(text.indexOf(`${fx(f.wind_max, 1)}m/s`) > text.indexOf("그림 기간 전체로는") || fx(f.wind_max, 1) === fx(f.wind_max_event, 1), `${c.id} 그림 기간 최대는 표시한 뒤에만`);
    if (c.kind === "typhoon") {
      assert.ok(text.includes(`${c.typhoon.min_km}km`) && text.includes(c.typhoon.name));
      // 한계 문장과 같은 값(태풍이 500km 안에 있던 동안 부산 풍속·거제도 파고 최대)
      const lim = B.limits.find((x) => x.includes(`${c.typhoon.min_km}km`));
      assert.ok(lim && lim.includes(`${f.wind_max_event}m/s`) && lim.includes(`${f.wave_max_event}m`), lim);
    }
    assert.ok(caseTabLabel(c).length > 0);
  }
  // 문서에 적힌 값: 사례 a 첫 경보 71시간 전·시작 15시간 뒤, 사례 c 시작 전 없음·38시간 뒤(시 단위로 내린 시작 기준)
  const A = B.cases.find((c) => c.id === "a"), C = B.cases.find((c) => c.id === "c");
  if (A && A.facts.first_alarm_lead_h === 71) assert.match(caseFactsLines(A, B).join(" "), /시작 71시간 전이었지만, 시작 전 24시간 안에는 경보가 없었습니다\. 시작 뒤 첫 경보는 15시간 뒤였습니다/);
  if (C && C.facts.first_alarm_after_start_h === 38) assert.match(caseFactsLines(C, B).join(" "), /시작 전 72시간 안에는 경보가 없었습니다\. 시작 뒤 첫 경보는 38시간 뒤였습니다/);
});

test("정답 자료·정박지 범위·평가 전 모양: labels·anchorage_choice_train·pretest_patterns 값을 그대로 옮긴다", () => {
  const L = B.labels;
  const ls = labelsSentence(B);
  assert.ok(ls.includes(`${fint(L.voyages)}항차(${L.label_period[0]}~${L.label_period[1]})`), ls);
  assert.ok(ls.includes(`12시간 초과 ${fint(L.gt12)}건(168시간 넘는 ${fint(L.n_gt_168)}건은 양성에서 빼 ${fint(L.gt12_capped)}건)`), ls);
  assert.equal(L.gt12 - L.n_gt_168, L.gt12_capped, "양성 = 12시간 초과 − 168시간 넘는 대기");
  const an = anchorageSentence(B);
  const np = B.anchorage_choice_train.newport_anchorages, all = B.anchorage_choice_train.all_anchorages;
  for (const v of [fx(np.corr_with_label_n_waiting, 3), `${fx(np.share_ships_later_newport_pct, 1)}%`, fx(all.corr_with_label_n_waiting, 3), `${fx(all.share_ships_later_newport_pct, 1)}%`]) assert.ok(an.includes(v), `${v} / ${an}`);
  assert.match(an, /학습 기간/);
  const P = B.pretest_patterns;
  const ps = pretestSentence(B);
  assert.ok(ps.includes(`학습+검증 기간 ${P.period[0]}~${P.period[1]}`) && ps.includes(`${fint(P.voyages)}항차`) && ps.includes(`${fint(P.gt12_capped)}건`), ps);
  assert.ok(ps.includes(`분산/평균은 ${fx(P.daily_var_over_mean, 3)}`), ps);
  const rows = pretestRows(B);
  assert.deepEqual(rows.map((r) => r.band), Object.keys(P.grt_bands));
  const top = rows.reduce((a, b) => (b.gt12_pct > a.gt12_pct ? b : a));
  assert.deepEqual(pretestTop(B), top);
  assert.ok(ps.includes(`총톤수 ${top.band} 톤 배는 도착의 ${fx(top.arrivals_pct, 1)}%였지만 12시간 초과 대기의 ${fx(top.gt12_pct, 1)}%였습니다`), ps);
  if (P.grt_bands["5천~1만"]) assert.equal(top.band, "5천~1만");
  // 해석 문장은 값에 따라: 분산/평균이 1 근처일 때만 「무작위」, 작은 배 쪽에 두 배 넘게 몰렸을 때만 「일찍 온 배」 가능성
  if (Math.abs(P.daily_var_over_mean - 1) <= 0.1) assert.match(ps, /무작위로 일어날 때의 값 1에 가깝습니다/);
  const mk = (vm, bands) => ({ ...B, pretest_patterns: { ...P, daily_var_over_mean: vm, grt_bands: bands } });
  assert.match(pretestSentence(mk(1.8, P.grt_bands)), /분산\/평균은 1\.800으로, 1보다 커서 며칠에 몰려 일어나는 편입니다/);
  assert.match(pretestNote(B), top.i <= 1 && top.gt12_pct > 2 * top.arrivals_pct ? /^작은 배에 몰린 것은/ : /^이 값은/);
  const big = { "1만 미만": { arrivals_pct: 50, gt12_pct: 10 }, "1만 이상": { arrivals_pct: 50, gt12_pct: 90 } };
  assert.equal(pretestNote(mk(1, { a: { arrivals_pct: 1, gt12_pct: 1 }, ...big })), "이 값은 평가 기간 앞의 자료로만 잰 것입니다.");
  assert.equal(pretestNote(mk(1, {})), "");
});

test("출처 표시: 입력 결과 파일 해시가 주 출처이고, 커밋은 보조로 ‘+수정’ 뜻을 밝힌다", () => {
  const lead = filesLead(B);
  assert.ok(lead.includes(`입력 결과 파일 해시 ${B.source_digest}`), lead);
  assert.ok(lead.includes(`앞 ${B.source_digest.length}자리`) && lead.includes("SHA-256"), lead);
  assert.ok(!lead.includes(String(B.built_from_commit).replace(DIRTY_MARK, "")), "커밋은 주 출처 문장에 넣지 않는다");
  const dirty = commitNote({ built_from_commit: `f6338e0${DIRTY_MARK}` });
  assert.match(dirty, /커밋은 f6338e0이고 뒤에 ‘\+수정’이 붙어 있습니다/);
  assert.match(dirty, /아직 커밋되지 않은/);
  assert.match(dirty, /입력 결과 파일 해시로 밝힙니다/);
  assert.equal(commitNote({ built_from_commit: "f6338e0" }), "참고로 이 파일을 만든 때의 저장소 커밋은 f6338e0입니다.");
  assert.equal(commitNote({ built_from_commit: null }), "");
  assert.ok(commitNote(B).includes(String(B.built_from_commit).replace(DIRTY_MARK, "")));
  // 머리의 결과 파일 정보는 해시를 쓰고 커밋은 9절 보조 문장에만
  assert.match(JS, /입력 결과 파일 해시 /);
  assert.doesNotMatch(JS, /`커밋 \$\{B\.built_from_commit/);
});

test("묶음 표: 해석하는 묶음만 가장 높은 모형을 고른다", () => {
  for (const sg of B.subgroups) {
    const best = subgroupBest(sg);
    if (!sg.interpretable) { assert.deepEqual(best, []); continue; }
    const max = Math.max(...Object.values(sg.pr_auc));
    assert.ok(best.length >= 1 && best.every((k) => sg.pr_auc[k] === max));
    assert.ok(sg.n_pos >= B.constants.min_pos_subgroup);
  }
});

test("신뢰도: 표본이 기준 이상인 구간만, 네 모형", () => {
  const ser = reliabilitySeries(B);
  assert.deepEqual(ser.map((s) => s.key), ["S0", "S1", "R2", "R3b"]);
  for (const s of ser) {
    assert.ok(s.pts.length > 0, s.key);
    for (const b of s.pts) assert.ok(b.n >= B.constants.reliability_min_n && b.mean_p >= 0 && b.mean_p <= 1 && b.obs >= 0 && b.obs <= 1);
  }
});

test("작은 함수: 계단 점, 연속 구간, 첫 문장 나누기", () => {
  assert.deepEqual(stepPoints([0, 2, 4], [1, 3, null]), [[0, 1], [2, 1], [2, 3], [4, 3], [4, null]]);
  assert.deepEqual(stepPoints([0, 2], [5, 5]), [[0, 5], [2, 5], [2, 5]]);
  assert.deepEqual(runs([0, 1, 1, 0, 1]), [[1, 2], [4, 4]]);
  assert.deepEqual(runs([1, null, 1, 1]), [[0, 0], [2, 3]]);
  assert.deepEqual(runs([0.1, null, null], (v) => v == null), [[1, 2]]);
  for (const s of B.limits) {
    const [a, b] = splitFirstSentence(s);
    assert.equal(a + b, s, "한계 문장은 글자 그대로");
  }
  assert.deepEqual(splitFirstSentence("R_d 0.22. 그래서 끝."), ["R_d 0.22.", " 그래서 끝."]);
});

test("공개 문구: 평가 기간이라 쓰고, 공공 출처만 밝히며, 선박·터미널 이름 없이 합성 시연 파일을 읽지 않는다", () => {
  const shown = [publicWording(B.case_note), ...B.cases.map((c) => publicWording(c.rule)), ...B.cases.map((c) => publicWording(c.attribution?.text)),
    publicWording(B.posthoc.note)].join("\n");
  assert.doesNotMatch(shown, /시험/, "보류 기간은 「평가 기간」으로 쓴다");
  assert.doesNotMatch(allScreenText(), /시험/, "화면 문장도 「평가 기간」");
  assert.match(publicWording("시험 기간 에피소드"), /^평가 기간 에피소드$/);
  // 출처는 공공기관 공개 포털뿐이다
  for (const s of B.sources) assert.match(new URL(s.url).hostname, /(\.go\.kr|\.ex\.co\.kr)$/, `${s.org} ${s.url}`);
  assert.doesNotMatch(RAW + HTML + JS, /Clarksons|클락슨/i);
  // 결과는 부산신항 전체 집계이고 배 단위는 사례 도착(시 단위 시각·구간)뿐: 선박·호출부호·터미널·선사를 담는 키가 없다
  const keys = [];
  const walk = (o) => {
    if (Array.isArray(o)) o.forEach(walk);
    else if (o && typeof o === "object") for (const [k, v] of Object.entries(o)) { keys.push(k); walk(v); }
  };
  walk(B);
  for (const k of keys) assert.doesNotMatch(k, /^(vsslNm|vessel_?name|clsgn|call_?sign|terminal(_name)?|berth_facility|arrival_facility|carrier|operator)$/i, k);
  assert.doesNotMatch(JS, /precomputed\.json|validation\.json|ai_model\.json/, "합성 시연 자료를 읽지 않는다");
  // 「집계값만 보여 준다」「가공한 시계열은 올리지 않았다」처럼 사례 도착 점과 맞지 않는 말을 쓰지 않는다
  assert.doesNotMatch(HTML + JS, /집계값만|가공한 시계열은 저장소에|시간 단위로 반올림/);
  const scope = dataScopeText(B);
  assert.match(scope, /원자료와 전체 기간 가공 자료는 저장소에 넣지 않았습니다/);
  assert.ok(scope.includes(`사례 ${B.cases.length}개 구간의 그림용 ${B.cases[0].series.step_h}시간 간격 부산신항 집계`) && scope.includes("도착 시각(시 단위)·대기 시간 구간만"), scope);
  assert.match(scope, /선박 이름·호출부호·터미널 없음/);
  assert.match(HTML, /공개 실자료 후향 검증\(실시간 운영 검증 아님\)/);
  // 머리 안내: 상황판·작동 원리 페이지의 검증 표는 합성이고, 작동 원리 페이지의 실자료 요약 숫자는 이 페이지에서 옮김
  const notice = /<p class="m-notice">([\s\S]*?)<\/p>/.exec(HTML)?.[1] || "";
  assert.match(notice, /검증 표는 합성 데이터/);
  assert.match(notice, /실자료 요약 숫자도 이 페이지의 결과 파일\(data\/backtest\.json\)에서 옮긴 것/);
  assert.match(HTML, /<html lang="ko">/);
  assert.match(HTML, /<meta name="description"/);
  assert.match(HTML, /<noscript>/);
  // ?v= 값은 지금 화면 버전과 같아야 한다(sw.js V)
  const V = /const V = "([^"]+)"/.exec(readFileSync(join(root, "docs", "sw.js"), "utf8"))[1];
  for (const text of [HTML, JS]) for (const m of text.matchAll(/\?v=([0-9A-Za-z._-]+)/g)) assert.equal(m[1], V);
});
