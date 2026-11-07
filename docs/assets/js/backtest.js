// 실제 자료로 되돌려 본 결과(backtest.html): docs/data/backtest.json 하나만 읽어 표와 그림을 그린다.
// - 숫자는 JSON 값을 toFixed로 반올림해 옮기기만 한다(새 숫자를 만들지 않음). answer·limits 문장은 글자 그대로 쓴다.
// - 결과는 부산신항 전체 집계값이다. 배 단위로 내는 것은 사례 그림의 12시간 초과 대기 선박뿐이며, 그것도 시 단위로 내린 도착 시각과
//   대기 시간 구간(case_bands)만 있다(선박 이름·호출부호·터미널 없음). 보류해 둔 시험 기간은 화면에서 「평가 기간」으로 쓴다.
// - DOM 없이 쓰는 순수 함수는 이름을 붙여 내보낸다(tests/backtest.test.mjs). 화면은 document가 있을 때만 그린다.
import { svgEl, niceTicks } from "./charts.js?v=20261107a";

const DASH = "–";
const HOUR = 3600e3;
const DAY = 24 * HOUR;

// ---------- 자료 모양 ----------
export const REQUIRED_KEYS = [
  "schema", "generated_kst", "built_from_commit", "source_digest", "protocol", "source_files", "question", "answer", "target", "periods",
  "test_pos_rate", "train_pos_rate", "labels", "pretest_patterns", "anchorage_choice_train", "data_ranges", "setup", "alarm_rule",
  "models", "pairs", "subgroups", "vessel", "posthoc", "rd_reference", "cases", "case_note", "case_bands", "limits", "sources", "constants",
];
export const SERIES_KEYS = ["anchor", "prob", "p_rd1", "y", "alarm", "wind", "wave", "road"];
// 공개 사례의 도착 기록에 있어도 되는 키(이 밖의 키가 있으면 모양 점검이 알린다)
export const ARRIVAL_KEYS = ["band", "t"];
// 「2026-09-18 17:00」처럼 시 단위로 내린 시각
export const ON_HOUR = /^\d{4}-\d{2}-\d{2} \d{2}:00$/;

// 빠진 키·어긋난 길이를 글로 돌려준다(빈 배열이면 화면이 기대하는 모양). 화면은 이 결과와 상관없이 그릴 수 있는 것만 그린다.
export function checkShape(B) {
  if (!B || typeof B !== "object") return ["JSON이 비었습니다"];
  const out = REQUIRED_KEYS.filter((k) => !(k in B)).map((k) => `${k} 없음`);
  for (const m of B.models || []) {
    for (const k of ["key", "name", "group", "pr_auc", "roc_auc", "alarm"]) if (!(k in m)) out.push(`models.${m.key}.${k} 없음`);
  }
  const bands = caseBands(B);
  for (const c of B.cases || []) {
    const s = c.series || {};
    if (!isNum(parseTime(s.t0)) || !isNum(s.step_h) || !isNum(s.n)) out.push(`cases.${c.id}.series 시간축 없음`);
    for (const k of SERIES_KEYS) if (!Array.isArray(s[k]) || s[k].length !== s.n) out.push(`cases.${c.id}.series.${k} 길이 ≠ n`);
    for (const k of ["start", "end"]) if (!ON_HOUR.test(String(c[k] ?? ""))) out.push(`cases.${c.id}.${k}가 시 단위가 아님`);
    (c.arrivals || []).forEach((a, i) => {
      const keys = Object.keys(a || {}).sort();
      if (keys.join() !== ARRIVAL_KEYS.join()) out.push(`cases.${c.id}.arrivals[${i}] 키가 ${keys.join("·")}`);
      if (!ON_HOUR.test(String(a?.t ?? ""))) out.push(`cases.${c.id}.arrivals[${i}].t가 시 단위가 아님`);
      if (!bands.includes(a?.band)) out.push(`cases.${c.id}.arrivals[${i}].band가 case_bands에 없음`);
    });
  }
  return out;
}

// ---------- 숫자 ----------
export const isNum = (v) => typeof v === "number" && Number.isFinite(v);
const noNegZero = (s) => (/^-0(\.0+)?%?$/.test(s) ? s.slice(1) : s);
// 저장값을 d자리로 반올림한 글자. toFixed와 같되, 저장된 이진값이 딱 절반일 때만 Python format()처럼 짝수 쪽으로 간다
// (toFixed는 0.3125 → 0.313, Python은 0.312). answer 문장·compare.md·그림은 Python으로 만들었으므로 화면 숫자를 그와 맞춘다.
export function toFixedPy(v, d) {
  const s = v.toFixed(d);
  if (Math.abs(v) >= 1e21) return s;
  const exact = Math.abs(v).toFixed(100); // 이 범위의 double은 소수 100자리 안에서 정확히 펼쳐진다
  const dot = exact.indexOf(".");
  if (!/^50*$/.test(exact.slice(dot + 1 + d))) return s;
  const kept = exact.slice(0, d ? dot + 1 + d : dot);
  return Number(kept.slice(-1)) % 2 === 0 ? `${v < 0 ? "-" : ""}${kept}` : s;
}
export const fx = (v, d = 3) => (isNum(v) ? noNegZero(toFixedPy(v, d)) : DASH);
export function fsign(v, d = 3) {
  if (!isNum(v)) return DASH;
  const s = fx(v, d);
  return s.startsWith("-") ? s : `+${s}`;
}
export const fpct = (v, d = 1) => (isNum(v) ? noNegZero(`${toFixedPy(v * 100, d)}%`) : DASH);
export const fint = (v) => (isNum(v) ? String(Math.round(v)).replace(/\B(?=(\d{3})+(?!\d))/g, ",") : DASH);
// 시간 수: 시 단위로 잰 값(41.0)은 「41」, 아니면 소수 한 자리
export const fhour = (v) => (!isNum(v) ? DASH : Number.isInteger(v) ? fint(v) : fx(v, 1));
export const isCi = (ci) => Array.isArray(ci) && ci.length === 2 && isNum(ci[0]) && isNum(ci[1]);
export function fci(ci, d = 3, signed = false) {
  if (!isCi(ci)) return DASH;
  const f = signed ? fsign : fx;
  return `${f(ci[0], d)}~${f(ci[1], d)}`;
}
// 「0.407 [0.323~0.500]」: 구간이 없으면 값만
export const valCi = (v, ci, d = 3) => (isCi(ci) ? `${fx(v, d)} [${fci(ci, d)}]` : fx(v, d));
const ratio = (a, b) => (isNum(a) && isNum(b) ? `${fint(a)}/${fint(b)}` : DASH);
// 축 눈금 글자: 0.20 → 「0.2」, 6 → 「6」
export const tickText = (v) => String(+Number(v).toFixed(4));

// 축 범위: charts.js의 niceTicks로 간격을 고르고, 양 끝을 그 간격에 맞춰 넓힌다.
export function axisTicks(lo, hi, count = 5, pad = 0) {
  const span = hi - lo || Math.abs(hi) || 1;
  const a = lo - span * pad, b = hi + span * pad;
  const t = niceTicks(a, b, count);
  const step = t.length > 1 ? +(t[1] - t[0]).toFixed(10) : span / count;
  const d0 = +(Math.floor(a / step + 1e-9) * step).toFixed(10);
  const d1 = +(Math.ceil(b / step - 1e-9) * step).toFixed(10);
  const ticks = [];
  for (let k = 0; d0 + k * step <= d1 + step * 1e-6; k++) ticks.push(+(d0 + k * step).toFixed(10));
  return { d0, d1, step, ticks };
}

// ---------- 말 ----------
// 조사: 끝의 괄호 설명을 떼고 마지막 글자로 고른다(한글 받침, 숫자 읽기; 로마자는 받침 없음으로 본다 — briefing.js와 같은 규칙).
export function josa(word, pair) {
  const w = String(word);
  const base = w.replace(/\s*\([^()]*\)\s*$/, "");
  const ch = base.charAt(base.length - 1);
  let jong = 0;
  if (/[가-힣]/.test(ch)) jong = (ch.charCodeAt(0) - 0xac00) % 28;
  else if (/[0-9]/.test(ch)) jong = "2459".includes(ch) ? 0 : ch === "1" || ch === "7" || ch === "8" ? 8 : 1; // 일·칠·팔은 ㄹ 받침
  if (pair[0] === "으로") return w + (jong === 0 || jong === 8 ? "로" : "으로");
  return w + (jong ? pair[0] : pair[1]);
}

// 짝 비교 판정(pr_verdict·roc_verdict): 95% 구간이 0보다 크면 앞 모형(a), 작으면 뒤 모형(b), 0을 포함하면 차이 없음.
export const SAME_WORD = "차이 없음(95% 구간이 0을 포함)";
export function verdictWord(pair, which = "pr") {
  const v = pair?.[`${which}_verdict`];
  if (v === "a") return `${josa(pair.a_name, ["이", "가"])} 낫다`;
  if (v === "b") return `${josa(pair.b_name, ["이", "가"])} 낫다`;
  if (v === "same") return SAME_WORD;
  return DASH;
}

// 공개 문구: 보류해 둔 시험 기간은 「평가 기간」으로 쓴다(method.html은 「시험에서」를 합성 세계 시험에만 쓴다).
export function publicWording(s) {
  return String(s ?? "")
    .replace(/시험\(평가\)\s*기간/g, "평가 기간")
    .replace(/검증·시험 기간/g, "검증·평가 기간")
    .replace(/시험 기간/g, "평가 기간")
    .replace(/시험을 본 뒤/g, "평가 기간 결과를 본 뒤");
}

// 첫 문장과 나머지(한계 목록에서 첫 문장만 굵게). 둘을 이으면 원문과 글자 하나까지 같다.
export function splitFirstSentence(s) {
  const t = String(s ?? "");
  const m = /^(.+?\.)(\s+)(\S[\s\S]*)$/.exec(t);
  return m ? [m[1], m[2] + m[3]] : [t, ""];
}

// 기준 시간은 문장에서 읽는다(숫자를 새로 적지 않음): target의 「12시간 넘게」「(168시간 이하)」, alarm_rule의 「경보 비율 10%」.
export const waitThreshold = (B) => { const m = /(\d+)시간 넘게/.exec(B?.target || ""); return m ? Number(m[1]) : null; };
export const waitCap = (B) => { const m = /\((\d+)시간 이하\)/.exec(B?.target || ""); return m ? Number(m[1]) : null; };
export const alarmRatePct = (B) => { const m = /경보 비율 (\d+)%/.exec(B?.alarm_rule?.rule || ""); return m ? Number(m[1]) : null; };
const typhoonKm = (c) => { const m = /(\d+)km 안/.exec(c?.rule || ""); return m ? m[1] : null; };
const isTyphoon = (c) => c?.kind === "typhoon";

// ---------- 시각 ----------
// 「2026-09-14 18:00」(한국시간, 시간대 없음) → 밀리초. 브라우저 시간대의 영향을 받지 않도록 UTC 칸에 그대로 넣고 UTC로 읽는다.
export function parseTime(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::(\d{2}))?)?$/.exec(String(s ?? "").trim());
  if (!m) return NaN;
  return Date.UTC(+m[1], +m[2] - 1, +m[3], +(m[4] || 0), +(m[5] || 0), +(m[6] || 0));
}
const p2 = (n) => String(n).padStart(2, "0");
export const fmtMD = (ms) => { const d = new Date(ms); return `${p2(d.getUTCMonth() + 1)}-${p2(d.getUTCDate())}`; };
export const fmtMDH = (ms) => `${fmtMD(ms)} ${p2(new Date(ms).getUTCHours())}시`;
// 「2026-09-18 17시」: 사례의 시작·끝(시 단위로 내린 값)
export const fmtYMDH = (ms) => (isNum(ms) ? `${new Date(ms).getUTCFullYear()}-${fmtMDH(ms)}` : DASH);
const day10 = (s) => String(s ?? "").slice(0, 10) || DASH;

// 시계열 칸 i의 시각: series.t0 + i × step_h시간
export function seriesTimes(series) {
  const t0 = parseTime(series?.t0), step = series?.step_h, n = series?.n;
  if (!isNum(t0) || !isNum(step) || !isNum(n)) return [];
  return Array.from({ length: n }, (_, i) => t0 + i * step * HOUR);
}
export const seriesLabel = (t0, stepH, i) => fmtMDH(parseTime(t0) + i * stepH * HOUR);

// 자정 눈금. 글자가 겹치지 않게 maxLabels개 이하가 되도록 하루·이틀·사흘… 간격을 고른다.
export function dayTicks(t0, t1, maxLabels = 8) {
  const first = Math.ceil(t0 / DAY) * DAY;
  if (!(t1 >= first)) return [];
  const days = Math.floor((t1 - first) / DAY) + 1;
  const every = [1, 2, 3, 4, 7, 14, 28].find((k) => Math.ceil(days / k) <= Math.max(1, maxLabels)) || 28;
  const out = [];
  for (let t = first; t <= t1; t += every * DAY) out.push(t);
  return out;
}

// 0/1 배열에서 1이 이어진 구간 [첫 칸, 끝 칸] 목록(null은 0으로 본다).
export function runs(arr, pred = (v) => v === 1 || v === true) {
  const out = [];
  let s = -1;
  const a = arr || [];
  a.forEach((v, i) => {
    if (pred(v)) { if (s < 0) s = i; } else if (s >= 0) { out.push([s, i - 1]); s = -1; }
  });
  if (s >= 0) out.push([s, a.length - 1]);
  return out;
}
// 계단(다음 칸까지 같은 값)으로 그릴 점. 값이 없는 칸(null)에서 선을 끊는다([x, null]).
export function stepPoints(xs, ys) {
  const out = [];
  for (let i = 0; i < xs.length; i++) {
    const y = ys[i];
    if (!isNum(y)) { out.push([xs[i], null]); continue; }
    out.push([xs[i], y]);
    if (i + 1 < xs.length) out.push([xs[i + 1], y]);
  }
  return out;
}

// ---------- 모형 ----------
export const GROUPS = {
  base: { label: "단순 기준선", color: "var(--truth)" },
  rdelay: { label: "R-Delay", color: "var(--s1)" },
  hybrid: { label: "기준선 + R-Delay 상태", color: "var(--s3)" },
  oracle: { label: "참고: S2 + 앞으로의 실제 기상(실제로는 알 수 없음)", color: "var(--ink-2)", hollow: true },
};
export const modelByKey = (B, k) => (B?.models || []).find((m) => m.key === k) || null;
export const modelLabel = (m) => (!m ? DASH : m.group === "oracle" ? m.name : `${m.key} ${m.name}`);
const bssText = (m) => (m.key === "S0" ? `${fx(m.bss, 3)}(기준)` : valCi(m.bss, m.bss_ci, 3));

// ---------- 문장(숫자는 모두 JSON 값) ----------
// 쉬운 말 요약: 짝 비교 판정과 에피소드 수로만 만든다(판정이 바뀌면 문장도 바뀐다).
// 말줄기(「낫」「못하」「없」)에 「지만」「고」「습니다」를 붙여 잇는다.
const endS = (stem) => (stem.endsWith("못하") ? `${stem.slice(0, -1)}합니다` : `${stem}습니다`);
export function plainSummary(B) {
  const pair = (a, b) => (B?.pairs || []).find((p) => p.a === a && p.b === b);
  const out = [];
  const p0 = pair("R1", "S0"), p1 = pair("R1", "S1"), p3 = pair("R3b", "S3");
  const stem0 = (p) => (p.pr_verdict === "a" ? `${p.b_name}보다 낫` : p.pr_verdict === "b" ? `${p.b_name}보다 못하` : `${josa(p.b_name, ["과", "와"])} 차이가 없`);
  const stem1 = (p) => (p.pr_verdict === "a" ? `${p.b_name}보다도 낫` : p.pr_verdict === "b" ? `${p.b_name}보다는 못하` : `${josa(p.b_name, ["과", "와"])}는 차이가 없`);
  if (p0 && p1) out.push(`R-Delay는 ${stem0(p0)}${p0.pr_verdict === p1.pr_verdict ? "고" : "지만"}, 지금 정박지 대기만 보는 ${endS(stem1(p1))}.`);
  else if (p0) out.push(`R-Delay는 ${endS(stem0(p0))}.`);
  else if (p1) out.push(`R-Delay는 지금 정박지 대기만 보는 ${endS(stem1(p1))}.`);
  const al = modelByKey(B, B?.alarm_rule?.model)?.alarm;
  if (al && isNum(al.episodes) && isNum(al.caught_72h)) {
    const missed = al.episodes - al.caught_72h;
    out.push(missed * 2 > al.episodes ? "대기 에피소드 대부분은 시작 전에 경보가 없어, 미리 알리는 경보로는 아직 부족합니다."
      : missed > 0 ? "대기 에피소드 가운데 일부는 시작 전에 경보가 없었습니다." : "모든 대기 에피소드에서 시작 전에 경보가 있었습니다.");
  }
  if (p3) {
    out.push(p3.pr_verdict === "a" ? `${p3.b_name} 기준선에 R-Delay 상태를 더하면 나아집니다.`
      : p3.pr_verdict === "b" ? `${p3.b_name} 기준선에 R-Delay 상태를 더하면 오히려 못합니다.` : `${p3.b_name} 기준선에 R-Delay 상태를 더해도 차이가 없습니다.`);
  }
  return out.join(" ");
}

// 경보 표 아래 한 문장: 72시간 창은 경보를 자주 켜는 모형에 유리하다(가장 자주 켠 모형과 R-Delay 경보를 견준다).
export function windowNote(B) {
  const ms = (B?.models || []).filter((m) => m.alarm && m.group !== "oracle" && isNum(m.alarm.onsets));
  if (!ms.length) return "";
  const often = ms.reduce((a, b) => (b.alarm.onsets > a.alarm.onsets ? b : a));
  const lowest = ms.every((m) => !(m.alarm.precision < often.alarm.precision));
  const a = often.alarm;
  let s = `72시간 창은 경보를 자주 켜는 모형에 유리합니다. ${josa(often.name, ["은", "는"])} 경보를 ${fint(a.onsets)}번 켜서 에피소드 ${fint(a.episodes)}개 중 ${fint(a.caught_72h)}개에서 시작 전 72시간 안에 경보가 있었지만, 정밀도는 ${josa(fx(a.precision, 2), ["으로", "로"])}${lowest ? " 가장 낮습니다" : " 낮은 편입니다"}.`;
  const r = modelByKey(B, B?.alarm_rule?.model);
  if (r && r !== often && r.alarm) s += ` ${r.name}의 경보는 ${fint(r.alarm.onsets)}번 켜져 ${fint(r.alarm.caught_72h)}개를 잡았습니다(시작 전 24시간 안의 덮는 경보로는 ${fint(r.alarm.caught_cover)}개).`;
  return s;
}

// 숫자 뒤 「였/이었」: 마지막 숫자를 읽은 소리로 고른다(0.35였고 · 0.36이었고).
const was = (numText) => josa(numText, ["이었", "였"]);

// 평가 기간의 R_d 분포 한 문장(rd_reference). 앱의 확산 경보는 P(R_d>1) ≥ 0.5에서 울린다.
// P(R_d>1)은 0이 아니었으므로(최대값이 있음) 「늘 0」이라 하지 않고 「경보 기준 0.5에 한 번도 닿지 않았다」고 쓴다.
export const SPREAD_ALARM_P = 0.5;
export function rdSentence(B) {
  const r = B?.rd_reference;
  if (!r) return "";
  let s = `평가 기간 판단 시각 ${fint(r.tau)}개에서 번짐 지수 R_d는 중앙값 ${fx(r.rd_median, 2)}(5~95% ${fx(r.rd_q05, 2)}~${fx(r.rd_q95, 2)}), 가장 높을 때 ${was(fx(r.rd_max, 2))}습니다.`;
  if (!isNum(r.p_rd1_max)) return s;
  if (r.p_rd1_max < SPREAD_ALARM_P) {
    s += ` 앱의 확산 경보(P(R_d>1) ≥ ${SPREAD_ALARM_P})는 실자료에서 한 번도 울리지 않았습니다(평가 기간 P(R_d>1) 최대 ${fx(r.p_rd1_max, 4)}). 그래서 경보는 검증 기간에서 고른 정박지 지연 비율 예측 점수로 냈습니다.`;
  } else {
    s += ` P(R_d>1)은 가장 높을 때 ${was(fx(r.p_rd1_max, 4))}습니다.`;
  }
  return s;
}

// 사후 순위상관: 「R1~S1」 → 이름 쌍과 값
export function spearmanRows(B) {
  const sp = B?.posthoc?.spearman || {};
  return Object.entries(sp).map(([k, v]) => {
    const [a, b] = k.split("~");
    const na = modelByKey(B, a)?.name || a, nb = modelByKey(B, b)?.name || b;
    return { key: k, a, b, label: `${na} ~ ${nb}`, value: v };
  });
}
// 순위가 겹치는 정도: [잇는 꼴, 끝맺는 꼴]
const overlap = (r) => (Math.abs(r) >= 0.6 ? ["많이 겹치고", "많이 겹칩니다"] : Math.abs(r) >= 0.3 ? ["어느 정도 겹치고", "어느 정도 겹칩니다"]
  : Math.abs(r) < 0.1 ? ["거의 겹치지 않고", "거의 겹치지 않습니다"] : ["조금 겹치고", "조금 겹칩니다"]);
export function spearmanSentence(B) {
  const rows = spearmanRows(B);
  const r1 = rows.find((x) => x.key === "R1~S1"), r3 = rows.find((x) => x.key === "R1~S3");
  const n1 = modelByKey(B, "R1")?.name || "R1", s1 = modelByKey(B, "S1")?.name || "S1", s3 = modelByKey(B, "S3")?.name || "S3";
  const ok1 = r1 && isNum(r1.value), ok3 = r3 && isNum(r3.value);
  if (ok1 && ok3) return `${n1}의 순위는 ${josa(s1, ["과", "와"])} ${overlap(r1.value)[0]}(${fx(r1.value, 3)}), ${josa(s3, ["과", "와"])}는 ${overlap(r3.value)[1]}(${fx(r3.value, 3)}).`;
  if (ok1) return `${n1}의 순위는 ${josa(s1, ["과", "와"])} ${overlap(r1.value)[1]}(${fx(r1.value, 3)}).`;
  if (ok3) return `${n1}의 순위는 ${josa(s3, ["과", "와"])} ${overlap(r3.value)[1]}(${fx(r3.value, 3)}).`;
  return "";
}

// 선박 단위 표 아래 문장: R-Delay 대기열이 기준선보다 낮았는지, Brier가 가장 크게 나빠진 판단
export function vesselNote(B) {
  const rows = (B?.vessel || []).filter((v) => v.baseline && v.rdelay_queue);
  if (!rows.length) return "";
  const lower = rows.filter((v) => v.rdelay_queue.pr_auc < v.baseline.pr_auc).length;
  const code = (v) => String(v.name).replace(/\(.*$/, "");
  let s = lower === rows.length ? `R-Delay 대기열 확률은 ${rows.length}개 판단 모두에서 기준선보다 PR-AUC가 낮았습니다.`
    : `R-Delay 대기열 확률은 ${rows.length}개 판단 중 ${lower}개에서 기준선보다 PR-AUC가 낮았습니다.`;
  const worst = rows.reduce((a, b) => (b.rdelay_queue.brier - b.baseline.brier > a.rdelay_queue.brier - a.baseline.brier ? b : a));
  if (worst.rdelay_queue.brier > worst.baseline.brier) s += ` ${code(worst)}에서는 Brier(낮을수록 좋음)가 ${fx(worst.rdelay_queue.brier, 3)}로 기준선 ${fx(worst.baseline.brier, 3)}보다 크게 나빴습니다.`;
  return s;
}

// 점수 표 아래 문장: R1(점수)·R2(확률)의 관계와 Brier 기술점수
export function scoresNote(B) {
  const r1 = modelByKey(B, "R1"), r2 = modelByKey(B, "R2");
  const out = ["Brier 기술점수는 기후값 대비이며 0보다 크면 기후값보다 확률이 정확하다는 뜻입니다. 매일 10시 판단만 뽑은 PR-AUC는 앱의 판단 시각에 맞춘 보조 값입니다."];
  if (r1 && r2 && r1.pr_auc === r2.pr_auc && r1.roc_auc === r2.roc_auc) out.push(`${josa(r2.name, ["은", "는"])} ${josa(r1.name, ["을", "를"])} 확률로 바꾼 것이라 순위로 재는 PR-AUC·ROC-AUC가 같습니다.`);
  if (r1 && r2 && isNum(r1.bss) && r1.bss < 0 && isNum(r2.bss)) out.push(`${josa(r1.name, ["은", "는"])} 확률이 아닌 점수라 Brier 기술점수가 ${josa(fx(r1.bss, 3), ["으로", "로"])} 낮고, 확률로 바꾼 ${josa(r2.name, ["은", "는"])} ${fx(r2.bss, 3)}입니다.`);
  return out.join(" ");
}

// 정답 자료 한 문장(labels): 12시간 초과 건수와, 168시간 넘는 대기를 양성에서 뺀 수
export function labelsSentence(B) {
  const L = B?.labels || {};
  const lp = Array.isArray(L.label_period) ? `${L.label_period[0]}~${L.label_period[1]}` : DASH;
  const X = waitThreshold(B), cap = waitCap(B);
  let s = `PORT-MIS 관제정보로 만든 신항 컨테이너선 ${fint(L.voyages)}항차(${lp})의 정박지 대기 기록입니다.`;
  if (isNum(L.gt12)) {
    const capped = cap && isNum(L.n_gt_168) && isNum(L.gt12_capped) ? `(${cap}시간 넘는 ${fint(L.n_gt_168)}건은 양성에서 빼 ${fint(L.gt12_capped)}건)` : "";
    s += ` ${X ? `${X}시간 초과` : "오래 기다린 배"} ${fint(L.gt12)}건${capped}이며, 항계 밖 대기는 들어 있지 않습니다.`;
  } else s += " 항계 밖 대기는 들어 있지 않습니다.";
  return s;
}

// 해상층 정박지 범위를 고른 근거(anchorage_choice_train, 학습 기간)
export function anchorageSentence(B) {
  const a = B?.anchorage_choice_train || {};
  const np = a.newport_anchorages, all = a.all_anchorages;
  if (!np || !isNum(np.corr_with_label_n_waiting)) return "";
  const corr = was(fx(np.corr_with_label_n_waiting, 3));
  const share = isNum(np.share_ships_later_newport_pct) ? `, 그 정박지에서 기다린 배의 ${fx(np.share_ships_later_newport_pct, 1)}%가 나중에 신항에 댔습니다` : "";
  let s = `해상층은 신항 정박지만 셉니다. 학습 기간에 판단 시각까지의 관제 이벤트로 센 신항 정박지 대기 척수는, 나중에 신항에 댄 배만 센 대기 척수와 상관이 ${share ? `${corr}고${share}` : `${corr}습니다`}`;
  if (all && isNum(all.corr_with_label_n_waiting)) s += `(모든 정박지로 넓히면 상관 ${fx(all.corr_with_label_n_waiting, 3)}${isNum(all.share_ships_later_newport_pct) ? `, ${fx(all.share_ships_later_newport_pct, 1)}%` : ""})`;
  return `${s}.`;
}

// 평가 기간 전(학습+검증) 12시간 초과 대기의 모양(pretest_patterns): 문장과 총톤수 구간 표
export function pretestSentence(B) {
  const p = B?.pretest_patterns;
  if (!p) return "";
  const X = waitThreshold(B), cap = waitCap(B);
  const per = Array.isArray(p.period) ? `${p.period[0]}~${p.period[1]}` : DASH;
  const what = `${X ? `${X}시간 넘게` : "오래"}${cap ? `(${cap}시간 이하)` : ""} 기다린 배`;
  let s = `평가 기간 전 자료(학습+검증 기간 ${per}, ${fint(p.days)}일, ${fint(p.voyages)}항차)에서 ${what}는 ${fint(p.gt12_capped)}건, 하루 평균 ${fx(p.daily_mean, 3)}건이었습니다.`;
  const vm = p.daily_var_over_mean;
  if (isNum(vm)) {
    // 날마다 서로 상관없이(무작위로) 일어나면 분산/평균이 1 근처, 몰려서 일어나면 1보다 크다
    const how = Math.abs(vm - 1) <= 0.1 ? "날마다 무작위로 일어날 때의 값 1에 가깝습니다" : vm > 1 ? "1보다 커서 며칠에 몰려 일어나는 편입니다" : "1보다 작습니다";
    s += ` 하루 건수의 분산/평균은 ${josa(fx(vm, 3), ["으로", "로"])}, ${how}.`;
  }
  const top = pretestTop(B);
  if (top) s += ` 총톤수 ${top.band} 톤 배는 도착의 ${fx(top.arrivals_pct, 1)}%였지만 ${X ? `${X}시간 초과` : "오랜"} 대기의 ${fx(top.gt12_pct, 1)}%였습니다.`;
  return s;
}
// 총톤수 구간(작은 배부터, JSON 순서 그대로)과 그 구간의 도착 중 비율·초과 대기 중 비율(%)
export const pretestRows = (B) => Object.entries(B?.pretest_patterns?.grt_bands || {})
  .filter(([, v]) => isNum(v?.arrivals_pct) && isNum(v?.gt12_pct)).map(([band, v], i) => ({ band, i, arrivals_pct: v.arrivals_pct, gt12_pct: v.gt12_pct }));
// 초과 대기 중 비율이 가장 높은 구간
export const pretestTop = (B) => pretestRows(B).reduce((a, b) => (!a || b.gt12_pct > a.gt12_pct ? b : a), null);
// 표 아래 설명: 초과 대기가 작은 배 쪽(앞의 두 구간)에 도착 비율의 두 배 넘게 몰렸을 때만 그 해석을 붙인다
export function pretestNote(B) {
  const rows = pretestRows(B);
  if (!rows.length) return "";
  const top = pretestTop(B);
  const small = top && top.i <= 1 && top.gt12_pct > 2 * top.arrivals_pct;
  return `${small ? "작은 배에 몰린 것은 혼잡이 번져서라기보다 선석 예약 시각보다 일찍 와 기다린 배가 많아서일 수 있지만, 공개 자료로는 둘을 가를 수 없습니다. " : ""}이 값은 평가 기간 앞의 자료로만 잰 것입니다.`;
}

// 출처 표시: 입력 결과 파일 해시(source_digest)가 주 출처이고, 만든 때의 커밋은 보조로 적는다.
// 커밋 끝의 「+수정」은 입력 결과 파일(또는 만드는 스크립트)이 그 커밋과 달랐다는 뜻이다(scripts/build_backtest.py).
export const DIRTY_MARK = "+수정";
export function filesLead(B) {
  const d = B?.source_digest;
  return `이 페이지의 숫자와 문장은 모두 data/backtest.json에서 옵니다(${B?.generated_kst || DASH} 생성). 이 파일은 저장소의 scripts/build_backtest.py가 아래 결과 파일로만 만듭니다.`
    + (d ? ` 입력 결과 파일 해시 ${d}는 아래 파일들의 이름과 내용을 차례로 이어 SHA-256으로 잰 값의 앞 ${String(d).length}자리로, 결과 파일이 같으면 어디서 다시 만들어도 같습니다.` : "");
}
export function commitNote(B) {
  const c = B?.built_from_commit;
  if (!c) return "";
  const s = String(c);
  if (!s.endsWith(DIRTY_MARK)) return `참고로 이 파일을 만든 때의 저장소 커밋은 ${s}입니다.`;
  const base = s.slice(0, -DIRTY_MARK.length);
  return `참고로 이 파일을 만든 때의 저장소 커밋은 ${josa(base, ["이고", "고"])} 뒤에 ‘${DIRTY_MARK}’이 붙어 있습니다. 입력 결과 파일이나 만드는 스크립트가 아직 커밋되지 않은 채 그 커밋과 달랐다는 뜻이라, 그 커밋만으로는 이 파일을 똑같이 다시 만들 수 없습니다. 그래서 출처는 입력 결과 파일 해시로 밝힙니다.`;
}

// 저장소·페이지에 담은 자료의 범위(원자료와 전체 기간 가공 자료는 넣지 않음)
export function dataScopeText(B) {
  const X = waitThreshold(B);
  const cases = B?.cases || [];
  const step = cases[0]?.series?.step_h;
  return `원자료와 전체 기간 가공 자료는 저장소에 넣지 않았습니다. 시간 순서가 있는 자료는 사례 ${fint(cases.length)}개 구간의 그림용${isNum(step) ? ` ${fint(step)}시간 간격` : ""} 부산신항 집계와, ${X ? `${X}시간 넘게` : "오래"} 기다린 배의 도착 시각(시 단위)·대기 시간 구간만 담았습니다(선박 이름·호출부호·터미널 없음).`;
}

// 묶음별 표: 해석하는 묶음에서 가장 높은 모형(같으면 모두)
export function subgroupBest(sg) {
  if (!sg?.interpretable || !sg.pr_auc) return [];
  const ent = Object.entries(sg.pr_auc).filter(([, v]) => isNum(v));
  if (!ent.length) return [];
  const max = Math.max(...ent.map(([, v]) => v));
  return ent.filter(([, v]) => v === max).map(([k]) => k);
}

// 사례 탭 이름
export function caseTabLabel(c) {
  if (c?.kind === "most_ships") return "대기가 가장 몰린 때";
  if (c?.kind === "typhoon") return c.typhoon?.name ? `태풍 ${c.typhoon.name}` : "태풍이 가까이 온 때";
  if (c?.kind === "missed") return "경보가 시작을 놓친 때";
  return c?.title || String(c?.id ?? "사례");
}

// 사례의 대기 시간 구간 이름(case_bands, 짧은 쪽부터). 없으면 도착 기록에 나온 순서대로.
export function caseBands(B) {
  if (Array.isArray(B?.case_bands) && B.case_bands.length) return B.case_bands;
  const seen = [];
  for (const c of B?.cases || []) for (const a of c?.arrivals || []) if (typeof a?.band === "string" && !seen.includes(a.band)) seen.push(a.band);
  return seen;
}
// 사례 그림의 대기 시간 구간 줄 이름: 「48~168시간」 → 「48~168」(단위는 칸 제목에)
export const bandAxisLabel = (b) => String(b ?? "").replace(/\s*시간$/, "");
// 구간별 척수 글(facts.wait_bands_event): 「12~24시간 4척, 24~48시간 5척, 48~168시간 7척」(case_bands 순서)
export function bandCountText(counts, B) {
  const c = counts && typeof counts === "object" ? counts : {};
  const bands = caseBands(B);
  const keys = [...bands.filter((b) => b in c), ...Object.keys(c).filter((b) => !bands.includes(b))];
  return keys.filter((b) => isNum(c[b])).map((b) => `${b} ${fint(c[b])}척`).join(", ");
}

// 사례 사실 요약(case.facts만 씀). 숫자 뒤 조사를 피하려고 단위·괄호로 끝맺는다.
// 대기 시간은 시 단위 값(중앙값·최대)과 구간별 척수만 쓴다. 풍속·파고는 사건 동안(에피소드, 태풍은 500km 안)의 최대를 앞에 두고,
// 그림 기간 전체의 최대는 「그림 기간 전체로는」이라고 밝혀 괄호에만 둔다.
export function caseFactsLines(c, B) {
  const f = c?.facts || {};
  const X = waitThreshold(B);
  const long = X ? `${X}시간 넘게 기다린 배` : "오래 기다린 배";
  const typh = isTyphoon(c);
  const km = typhoonKm(c);
  const during = typh ? (km ? `태풍이 ${km}km 안에 있던 동안` : "태풍이 가까이 있던 동안") : "에피소드 동안";
  const W = typh ? "태풍 진입" : "시작";
  const lines = [];
  if (f.ships_event > 0) {
    const bands = bandCountText(f.wait_bands_event, B);
    const stats = [isNum(f.wait_h_median) ? `중앙값은 ${fhour(f.wait_h_median)}시간` : null, isNum(f.wait_h_max) ? `가장 길게는 ${fhour(f.wait_h_max)}시간` : null].filter(Boolean);
    let s = `${during} 도착해 ${long}는 ${fint(f.ships_event)}척입니다(그림 기간 전체 ${fint(f.ships_window)}척).`;
    if (bands && stats.length) s += ` 대기 시간 구간별로는 ${bands}이고, 대기 시간 ${stats.join(", ")}이었습니다.`;
    else if (bands) s += ` 대기 시간 구간별로는 ${bands}입니다.`;
    else if (stats.length) s += ` 대기 시간 ${stats.join(", ")}이었습니다.`;
    lines.push(s);
  } else {
    lines.push(`${during} 도착해 ${long}는 없었습니다(그림 기간 전체 ${fint(f.ships_window)}척${isNum(f.wait_h_max_window) ? `, 가장 길게는 ${fhour(f.wait_h_max_window)}시간` : ""}).`);
  }
  if (f.alarm_tau > 0) {
    lines.push(`그림 기간 판단 시각 ${fint(f.tau)}개 중 ${fint(f.alarm_tau)}개에서 경보가 켜졌고, 그중 ${fint(f.alarm_tau_correct)}개가 맞았습니다(정답이 ‘옴’인 판단 시각 ${fint(f.y_tau)}개 · R-Delay 확률 최대 ${fx(f.prob_max, 3)} · 경보 기준 ${fx(f.alarm_threshold, 3)}).`);
  } else {
    lines.push(`그림 기간 판단 시각 ${fint(f.tau)}개 동안 경보는 한 번도 켜지지 않았습니다(R-Delay 확률 최대 ${fx(f.prob_max, 3)} · 경보 기준 ${fx(f.alarm_threshold, 3)} · 정답이 ‘옴’인 판단 시각 ${fint(f.y_tau)}개).`);
  }
  if (!(typh && !(f.alarm_tau > 0))) {
    let s = isNum(f.first_alarm_lead_h)
      ? `${W} 전 72시간 안의 첫 경보는 ${W} ${fhour(f.first_alarm_lead_h)}시간 전이었${f.alarm_in_24h_before === false ? `지만, ${W} 전 24시간 안에는 경보가 없었습니다.` : "습니다."}`
      : `${W} 전 72시간 안에는 경보가 없었습니다.`;
    if (isNum(f.first_alarm_after_start_h)) s += ` ${W} 뒤 첫 경보는 ${fhour(f.first_alarm_after_start_h)}시간 뒤였습니다.`;
    lines.push(s);
  }
  if (typh && c.typhoon && isNum(c.typhoon.min_km)) lines.push(`${josa(`태풍 ${c.typhoon.name}`, ["은", "는"])} 신항에 가장 가까이 왔을 때도 ${fint(c.typhoon.min_km)}km 떨어져 있었습니다.`);
  const wx = (wind, wave) => [isNum(wind) ? `부산 풍속은 최대 ${fx(wind, 1)}m/s` : null, isNum(wave) ? `거제도 유의파고는 최대 ${fx(wave, 1)}m` : null].filter(Boolean);
  const ev = wx(f.wind_max_event, f.wave_max_event);
  const win = [isNum(f.wind_max) ? `풍속 최대 ${fx(f.wind_max, 1)}m/s` : null, isNum(f.wave_max) ? `파고 최대 ${fx(f.wave_max, 1)}m` : null].filter(Boolean);
  if (ev.length) lines.push(`${during} ${ev.join(", ")}였습니다${win.length ? `(그림 기간 전체로는 ${win.join(", ")})` : ""}.`);
  else if (win.length) lines.push(`그림 기간 전체에서 ${wx(f.wind_max, f.wave_max).join(", ")}였습니다.`);
  const road = isNum(f.road_share_missing) && f.road_share_missing > 0 ? `(판단 시각의 ${fpct(f.road_share_missing, 1)}는 도로 자료 없음)` : "";
  lines.push(`그림 기간에 정박지에서 기다린 배는 최대 ${fint(f.anchor_max)}척, 도로 혼잡 콘존 비율은 평균 ${fpct(f.road_mean, 1)}입니다${road}.`);
  return lines;
}

// 사례 그림의 시각 i 값(툴팁·화면낭독·표에 같이 씀). 도착한 배는 시 단위 도착 시각과 대기 시간 구간만 보인다.
export function caseTipRows(c, i) {
  const s = c?.series || {};
  const at = (k) => (Array.isArray(s[k]) ? s[k][i] : null);
  const none = "자료 없음";
  const rows = [{ name: "정박지 대기", value: isNum(at("anchor")) ? `${fint(at("anchor"))}척` : none, color: "var(--ink-2)" }];
  for (const a of arrivalsAt(c, i)) rows.push({ name: `${fmtMDH(a.t)} 도착 배의 대기 시간 구간`, value: a.band, color: "var(--s2)" });
  rows.push({ name: "R-Delay 확률", value: isNum(at("prob")) ? `${fx(at("prob"), 3)}${at("alarm") === 1 ? " · 경보" : ""}` : none, color: "var(--s1)" });
  rows.push({ name: "정답(앞으로 24시간 안에 옴)", value: at("y") === 1 ? "옴" : at("y") === 0 ? "안 옴" : none, color: "var(--truth)" });
  rows.push({ name: "P(R_d>1)", value: isNum(at("p_rd1")) ? fx(at("p_rd1"), 4) : none, color: "var(--muted)" });
  rows.push({ name: "풍속(부산)", value: isNum(at("wind")) ? `${fx(at("wind"), 1)} m/s` : none, color: "var(--ink-2)" });
  rows.push({ name: "유의파고(거제도)", value: isNum(at("wave")) ? `${fx(at("wave"), 1)} m` : none, color: "var(--ink-2)" });
  rows.push({ name: "도로 혼잡 콘존", value: isNum(at("road")) ? fpct(at("road"), 1) : none, color: "var(--ink-2)" });
  return rows;
}

// 도착(시 단위로 내린 시각)을 가장 가까운 판단 시각 칸에 하나씩 붙인다(칸 번호는 0~n−1로 자름: 툴팁용).
export function arrivalSlots(c) {
  const s = c?.series || {};
  const t0 = parseTime(s.t0), step = (s.step_h || 2) * HOUR, n = s.n || 0;
  return (c?.arrivals || []).map((a) => ({ t: parseTime(a?.t), band: typeof a?.band === "string" ? a.band : null }))
    .filter((a) => isNum(a.t) && a.band)
    .map((a) => ({ ...a, i: Math.min(n - 1, Math.max(0, Math.round((a.t - t0) / step))) }));
}
const arrivalsAt = (c, i) => arrivalSlots(c).filter((a) => a.i === i);
// 사례의 도착 표: [도착 시각(시 단위), 대기 시간 구간]
export const arrivalTableRows = (c) => arrivalSlots(c).map((a) => [fmtMDH(a.t), a.band]);

// 사례 표(판단 시각별 값)
export function caseTableRows(c) {
  const s = c?.series || {};
  const times = seriesTimes(s);
  const v = (k, i, f) => (Array.isArray(s[k]) && isNum(s[k][i]) ? f(s[k][i]) : DASH);
  return times.map((t, i) => [fmtMDH(t), v("anchor", i, fint), v("prob", i, (x) => fx(x, 3)), s.alarm?.[i] === 1 ? "켜짐" : s.alarm?.[i] === 0 ? "" : DASH,
    s.y?.[i] === 1 ? "옴" : s.y?.[i] === 0 ? "" : DASH, v("p_rd1", i, (x) => fx(x, 4)), v("wind", i, (x) => fx(x, 1)), v("wave", i, (x) => fx(x, 1)),
    v("road", i, (x) => fpct(x, 1))]);
}

// 비교 그림 툴팁
export function compareTipRows(m) {
  return [
    { name: "PR-AUC", value: fx(m.pr_auc, 3) },
    { name: "95% 구간", value: fci(m.pr_ci, 3) },
    { name: "ROC-AUC", value: valCi(m.roc_auc, m.roc_ci, 3) },
    { name: "Brier 기술점수", value: bssText(m) },
  ];
}

// 신뢰도 곡선: 표본이 기준(constants.reliability_min_n) 이상인 구간만
export const REL_SERIES = [
  { key: "S0", color: "var(--truth)", dash: "5 4", marker: "square" },
  { key: "S1", color: "var(--s2)", dash: "7 3 2 3", marker: "triangle" },
  { key: "R2", color: "var(--s1)", marker: "circle" },
  { key: "R3b", color: "var(--s3)", marker: "diamond" },
];
export function reliabilitySeries(B) {
  const minN = B?.constants?.reliability_min_n ?? 0;
  return REL_SERIES.map((s) => {
    const m = modelByKey(B, s.key);
    if (!m) return null;
    return { ...s, model: m, pts: (m.reliability || []).filter((b) => b.n >= minN && isNum(b.mean_p) && isNum(b.obs)) };
  }).filter(Boolean);
}
export const relTip = (s, b) => [
  { name: "구간", value: `${fx(b.bin?.[0], 1)}~${fx(b.bin?.[1], 1)}`, color: s.color },
  { name: "예측 확률 평균", value: fx(b.mean_p, 3) },
  { name: "실제로 일어난 비율", value: fx(b.obs, 3) },
  { name: "판단 시각", value: `${fint(b.n)}개` },
];

// ======================================================================
// 아래는 화면(DOM) 코드
// ======================================================================
const $ = (id) => document.getElementById(id);
const STATE = { B: null, caseIdx: 0 };

function el(tag, cls, text, parent) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  if (parent) parent.appendChild(n);
  return n;
}
function frag(...parts) {
  const f = document.createDocumentFragment();
  for (const p of parts) f.append(p instanceof Node ? p : document.createTextNode(String(p)));
  return f;
}
const bold = (t) => el("b", null, t);
const tag = (t) => el("span", "tag", t);

// 표: head는 글자 또는 [글자, 설명(title)]. 첫 칸은 행 머리(th scope=row).
// 머리글의 「PR-AUC」「R-Delay」는 줄이 하이픈에서 끊기지 않게 줄바꿈 없는 하이픈(U+2011)으로 쓴다(validation-tables.js와 같음).
const nobreak = (s) => String(s).replace(/([A-Za-z])-([A-Za-z])/g, "$1‑$2");
function buildTable(tbl, head, rows, numCols = []) {
  tbl.replaceChildren();
  const hr = tbl.createTHead().insertRow();
  head.forEach((h, i) => {
    const [text, title] = Array.isArray(h) ? h : [h, null];
    const th = el("th", numCols.includes(i) ? "num" : null, nobreak(text), hr);
    th.scope = "col";
    if (title) th.title = title;
  });
  const body = tbl.createTBody();
  for (const r of rows) {
    const tr = body.insertRow();
    if (r.cls) tr.className = r.cls;
    r.cells.forEach((v, i) => {
      const cls = [numCols.includes(i) ? "num" : null, r.best?.includes(i) ? "best" : null, r.wrap?.includes(i) ? "wrap" : null].filter(Boolean).join(" ");
      const c = el(i === 0 ? "th" : "td", cls || null, null, tr);
      if (i === 0) c.scope = "row";
      if (v instanceof Node) c.appendChild(v); else c.textContent = v;
    });
  }
}

// ---------- 범례·툴팁·마커 ----------
function marker(parent, shape, x, y, r, color, ringW = 2) {
  const st = { fill: color, stroke: ringW ? "var(--halo, var(--surface))" : "none" };
  const a = { "stroke-width": ringW };
  if (shape === "square") return svgEl("rect", { ...a, x: x - r * 0.9, y: y - r * 0.9, width: r * 1.8, height: r * 1.8, rx: 1 }, parent, st);
  if (shape === "triangle") return svgEl("path", { ...a, d: `M${x},${y - r * 1.15}L${x + r * 1.05},${y + r * 0.8}L${x - r * 1.05},${y + r * 0.8}Z` }, parent, st);
  if (shape === "diamond") return svgEl("path", { ...a, d: `M${x},${y - r * 1.25}L${x + r * 1.1},${y}L${x},${y + r * 1.25}L${x - r * 1.1},${y}Z` }, parent, st);
  return svgEl("circle", { ...a, cx: x, cy: y, r }, parent, st);
}

// 범례: 표식은 그림과 같은 모양(선·점선·점·속 빈 점·띠·세로선)으로 그리고, 글자는 늘 글자 색으로 둔다.
function legendKeys(box, items) {
  box.replaceChildren();
  for (const it of items) {
    const key = el("span", "key", null, box);
    const svg = svgEl("svg", { viewBox: "0 0 20 12", width: 20, height: 12, class: "bt-key", "aria-hidden": "true", focusable: "false" }, key);
    const c = it.color || "var(--ink-2)";
    if (it.kind === "dot") svgEl("circle", { cx: 10, cy: 6, r: 4 }, svg, { fill: c });
    else if (it.kind === "ring") svgEl("circle", { cx: 10, cy: 6, r: 3.6, "stroke-width": 2 }, svg, { fill: "var(--halo, var(--surface))", stroke: c });
    else if (it.kind === "whisker") {
      svgEl("line", { x1: 2, x2: 18, y1: 6, y2: 6, "stroke-width": 2 }, svg, { stroke: c });
      for (const x of [2, 18]) svgEl("line", { x1: x, x2: x, y1: 2, y2: 10, "stroke-width": 2 }, svg, { stroke: c });
    } else if (it.kind === "band") svgEl("rect", { x: 1, y: 1, width: 18, height: 10, rx: 2 }, svg, { fill: c, opacity: it.opacity ?? 0.16 });
    else if (it.kind === "strip") svgEl("rect", { x: 1, y: 7, width: 18, height: 5, rx: 1 }, svg, { fill: c, opacity: it.opacity ?? 0.65 });
    else if (it.kind === "vline" || it.kind === "vdash") {
      const a = { x1: 10, x2: 10, y1: 0, y2: 12, "stroke-width": 2 };
      if (it.kind === "vdash") a["stroke-dasharray"] = "3 2";
      svgEl("line", a, svg, { stroke: c });
    } else {
      const a = { x1: 1, x2: 19, y1: 6, y2: 6, "stroke-width": it.width || 2 };
      if (it.dash) a["stroke-dasharray"] = it.dash;
      svgEl("line", a, svg, { stroke: c });
      if (it.marker) marker(svg, it.marker, 10, 6, 3.4, c, 1);
    }
    el("span", null, it.label, key);
  }
}

function tipBox(box) {
  let t = box.querySelector(":scope > .tooltip");
  if (!t) {
    t = el("div", "tooltip", null, box);
    t.hidden = true;
    t.setAttribute("aria-hidden", "true"); // 화면낭독기는 아래 bt-live로 읽는다
  }
  return t;
}
// 툴팁 줄: 값이 앞(굵게), 이름이 뒤. 색 표식은 짧은 선(차트 표식과 같은 색).
function fillTip(tip, title, rows) {
  tip.replaceChildren();
  el("div", "t", title, tip);
  for (const r of rows) {
    const row = el("div", "r", null, tip);
    const k = el("span", "k", null, row);
    if (r.color) k.style.background = r.color; else k.style.visibility = "hidden";
    el("b", null, r.value, row);
    el("span", null, r.name, row);
  }
}
function placeTip(box, tip, px, py) {
  const cw = box.clientWidth;
  tip.hidden = false;
  const w = tip.offsetWidth;
  let left = px + 14;
  if (left + w > cw) left = Math.max(0, px - w - 14);
  tip.style.left = `${left}px`;
  tip.style.top = `${Math.max(0, py - 10)}px`;
}
const tipText = (title, rows) => `${title}: ${rows.map((r) => `${r.name} ${r.value}`).join(", ")}`;
function announce(text) {
  const n = $("bt-live");
  if (n) n.textContent = text;
}
// 글자 폭: 그린 뒤에는 실제 폭, 아니면 어림(한글 1em, 숫자·로마자 0.6em)
function textWidth(node, size) {
  try {
    const w = node.getComputedTextLength();
    if (w > 0) return w;
  } catch { /* 아직 그리기 전 */ }
  return [...(node.textContent || "")].reduce((a, ch) => a + (/[가-힣]/.test(ch) ? size : ch === " " ? size * 0.3 : size * 0.6), 0);
}
function freshSvg(box, W, H, label) {
  box.querySelectorAll(":scope > svg, :scope > .m-loading, :scope > .m-error").forEach((n) => n.remove());
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", tabindex: 0, "aria-label": label });
  box.prepend(svg);
  return svg;
}
const relPos = (box, e) => { const r = box.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
// 선·점 위에 놓이는 글자는 바탕색 테두리(halo)를 둘러 읽히게 한다(charts.js networkChart와 같은 방식).
const HALO_INK = { fill: "var(--ink)", stroke: "var(--halo, var(--surface))", "stroke-width": "3px", "paint-order": "stroke" };
const HALO_INK2 = { ...HALO_INK, fill: "var(--ink-2)" };
const HALO_MUTED = { ...HALO_INK, fill: "var(--muted)" };

// ---------- 머리 ----------
// 출처는 입력 결과 파일 해시로 밝힌다(커밋은 9절 「이 페이지의 숫자는 어디서 오나」에 보조로 적음).
function renderMeta(B) {
  const box = $("bt-meta");
  box.replaceChildren();
  const h = el("span", null, "입력 결과 파일 해시 ", box);
  el("code", "bt-hash", B.source_digest || DASH, h);
  el("span", null, `${B.generated_kst || DASH} 생성`, box);
  el("span", null, `검증 프로토콜 ${B.protocol || DASH}`, box);
}

// ---------- 1. 한눈에 ----------
function renderSummary(B) {
  $("bt-question").textContent = B.question || DASH;
  const ul = $("bt-answer");
  ul.replaceChildren();
  for (const line of B.answer || []) el("li", null, line, ul);

  const tiles = $("bt-tiles");
  tiles.replaceChildren();
  const tile = (label, value, sub, color, kind) => {
    const t = el("div", "bt-tile", null, tiles);
    t.setAttribute("role", "listitem");
    if (kind) t.dataset.kind = kind;
    const lab = el("p", "lab", null, t);
    const sw = el("span", `sw ${kind === "base-rate" ? "sw-rule" : ""}`, null, lab);
    sw.setAttribute("aria-hidden", "true");
    if (color) sw.style.setProperty("--sw", color);
    lab.append(label);
    el("p", "val", value, t);
    if (sub) el("p", "sub", sub, t);
  };
  for (const k of ["R1", "S1", "S0"]) {
    const m = modelByKey(B, k);
    if (!m) continue;
    const short = m.group === "rdelay" ? "R-Delay" : m.name;
    tile(short, fx(m.pr_auc, 3), `${modelLabel(m)} · 95% 구간 ${fci(m.pr_ci, 3)}`, (GROUPS[m.group] || GROUPS.base).color, m.group);
  }
  if (isNum(B.test_pos_rate)) tile("아무 정보 없이 찍으면", fx(B.test_pos_rate, 3), "평가 기간 양성 비율(이보다 높아야 쓸모 있음)", "var(--ink-2)", "base-rate");
  $("bt-tiles-note").textContent = "PR-AUC는 점수가 높은 판단 시각일수록 정말로 12시간 넘게 기다린 배가 왔는지 보는 값으로, 높을수록 좋습니다. 아무 정보 없이 찍으면 양성 비율과 같습니다. 95% 구간은 주 단위 블록 부트스트랩으로 구했습니다.";
  const plain = plainSummary(B);
  const p = $("bt-plain");
  p.replaceChildren(frag(bold("쉬운 말로: "), plain));
  p.hidden = !plain;
}

// ---------- 2. 무엇을 어떻게 ----------
function renderDesign(B) {
  const dl = $("bt-design");
  dl.replaceChildren();
  const item = (dt, ...dd) => { el("dt", null, dt, dl); const d = el("dd", null, null, dl); d.append(frag(...dd)); };
  item("맞힐 것", B.target || DASH);
  item("정답 자료", labelsSentence(B));
  const ar = B.alarm_rule || {};
  const am = modelByKey(B, ar.model);
  item("경보 기준", `${josa(am ? modelLabel(am) : ar.model || DASH, ["이", "가"])} ${fx(ar.threshold, 3)} 이상이면 경보를 냅니다. `, el("span", "m-sub", ar.rule || ""));
  const su = B.setup || {};
  item("R-Delay 설정", `${(su.nodes || []).join(" · ")}. 판단 시각마다 지난 ${fint(su.window_h)}시간 관측으로 입자 ${fint(su.particles)}개 필터를 돌렸습니다. 선석 대기열의 선석 수는 ${fint(su.servers)}개로 두었습니다.`);
  const anc = anchorageSentence(B);
  if (anc) item("정박지 범위", anc);
  item("AI 보정", `${su.ai || DASH}${isNum(su.ai_r2_val) ? ` · 검증 R² ${fx(su.ai_r2_val, 3)}` : ""}`);

  const P = B.periods || {};
  const n = P.n_tau || {};
  const row = (name, k, rate) => ({ cells: [name, Array.isArray(P[k]) ? `${day10(P[k][0])} ~ ${day10(P[k][1])}` : DASH, `${fint(n[k])}개`, isNum(rate) ? fx(rate, 3) : DASH] });
  buildTable($("bt-periods"), ["구분", "기간(판단 시각 기준)", "판단 시각", "양성 비율"], [
    row("학습", "train", B.train_pos_rate), row("검증", "val", null), row("평가 기간", "test", B.test_pos_rate),
  ], [2, 3]);
  $("bt-once").textContent = `모형·특징·경보 기준은 학습·검증 기간에서 정해 검증 프로토콜(${B.protocol || DASH})에 적은 뒤, 평가 기간을 한 번만 계산했습니다. 평가 기간 결과를 본 뒤에는 모형·설정·경보 기준을 바꾸지 않았습니다. 양성 비율은 그 기간 판단 시각 가운데 정답이 ‘옴’인 비율입니다.`;

  const box = $("bt-models");
  box.replaceChildren();
  for (const [g, st] of Object.entries(GROUPS)) {
    const ms = (B.models || []).filter((m) => m.group === g);
    if (!ms.length) continue;
    const h = el("p", "bt-group", null, box);
    const sw = el("span", `sw${st.hollow ? " sw-ring" : ""}`, null, h);
    sw.setAttribute("aria-hidden", "true");
    sw.style.setProperty("--sw", st.color);
    h.append(st.label);
    const ul = el("ul", "m-bullets bt-model-list", null, box);
    for (const m of ms) { const li = el("li", null, null, ul); li.append(bold(modelLabel(m)), ` — ${m.desc || ""}`); }
  }

  // 평가 기간 전(학습+검증) 12시간 초과 대기의 모양
  $("bt-pretest-lead").textContent = pretestSentence(B);
  const pr = pretestRows(B);
  const X = waitThreshold(B);
  if (pr.length) {
    buildTable($("bt-pretest"), ["총톤수(톤)", "도착 중 비율", `${X ? `${X}시간 초과` : "오랜"} 대기 중 비율`],
      pr.map((r) => ({ cells: [r.band, `${fx(r.arrivals_pct, 1)}%`, `${fx(r.gt12_pct, 1)}%`] })), [1, 2]);
  } else fail("bt-pretest", "평가 기간 전 자료 요약이 결과 파일에 없습니다.");
  $("bt-pretest-note").textContent = pretestNote(B);
}

// ---------- 3. 비교 ----------
function renderCompare(B) {
  $("bt-compare-lead").textContent = "판단 시각마다 모형이 낸 점수로 평가 기간 PR-AUC를 쟀습니다. 점은 평가 기간 값, 가로 막대는 95% 구간입니다. 어느 모형이 나은지는 막대가 겹치는지가 아니라, 같은 표본으로 차이를 계산한 아래 「두 모형의 차이」 표로 판단합니다.";
  const groups = [...new Set((B.models || []).map((m) => m.group))];
  legendKeys($("bt-compare-legend"), [
    ...groups.filter((g) => GROUPS[g]).map((g) => ({ kind: GROUPS[g].hollow ? "ring" : "dot", color: GROUPS[g].color, label: GROUPS[g].label })),
    { kind: "whisker", color: "var(--ink-2)", label: "95% 구간" },
    { kind: "vdash", color: "var(--ink-2)", label: `아무 정보 없이 찍을 때(${fx(B.test_pos_rate, 3)})` },
  ]);
  drawCompare($("bt-compare-chart"), B);
  $("bt-compare-cap").textContent = `가로축은 PR-AUC(높을수록 좋음)입니다. 세로 점선은 평가 기간 양성 비율 ${fx(B.test_pos_rate, 3)}로, 아무 정보 없이 찍을 때의 값입니다. 그림을 누르거나 ↑/↓ 키로 모형별 값을 볼 수 있고, 같은 값이 아래 표에 있습니다.`;

  buildTable($("bt-scores"), ["모형", "PR-AUC", "ROC-AUC", ["Brier 기술점수(기후값 대비)", "Brier 기술점수: 기후값(S0)의 Brier 대비 개선. 0보다 크면 기후값보다 확률이 정확함"], "매일 10시 판단만: PR-AUC"],
    (B.models || []).map((m) => ({ cells: [modelLabel(m), valCi(m.pr_auc, m.pr_ci, 3), valCi(m.roc_auc, m.roc_ci, 3), bssText(m), fx(m.pr_auc_10am, 3)] })), [1, 2, 3, 4]);
  $("bt-scores-note").textContent = scoresNote(B);

  buildTable($("bt-pairs"), ["비교", "PR-AUC 차이 95% 구간", "판정(PR-AUC)", "ROC-AUC 차이 95% 구간", "판정(ROC-AUC)"],
    (B.pairs || []).map((p) => ({ cells: [`${p.a_name} − ${p.b_name}`, fci(p.pr_ci, 3, true), verdictWord(p, "pr"), fci(p.roc_ci, 3, true), verdictWord(p, "roc")], wrap: [2, 4] })), [1, 3]);
  $("bt-pairs-note").textContent = "앞 모형 점수에서 뒤 모형 점수를 뺀 값의 95% 구간입니다(같은 부트스트랩 표본으로 계산). 구간이 0을 포함하면 어느 쪽이 낫다고 하지 않습니다.";
}

function drawCompare(box, B) {
  const ms = (B.models || []).filter((m) => isNum(m.pr_auc));
  if (!ms.length) { box.replaceChildren(el("p", "m-error", "비교할 모형 값이 없습니다.")); return; }
  const W = Math.max(280, Math.round(box.clientWidth || 640));
  const narrow = W < 560;
  const labelW = narrow ? 0 : 172;
  const rowH = narrow ? 40 : 30;
  const top = 26, bottom = 24, room = 44;
  const H = top + rowH * ms.length + bottom;
  const vals = [];
  ms.forEach((m) => { vals.push(m.pr_auc); if (isCi(m.pr_ci)) vals.push(...m.pr_ci); });
  if (isNum(B.test_pos_rate)) vals.push(B.test_pos_rate);
  const { d0, d1, ticks } = axisTicks(Math.min(...vals), Math.max(...vals), narrow ? 4 : 6, 0.03);
  const x0 = narrow ? 10 : labelW, x1 = W - room;
  const X = (v) => x0 + ((v - d0) / (d1 - d0 || 1)) * (x1 - x0);
  const svg = freshSvg(box, W, H, `평가 기간 PR-AUC와 95% 구간, 모형 ${ms.length}개(↑/↓ 키로 모형별 값 보기)`);
  const g = svgEl("g", {}, svg);
  const hl = svgEl("rect", { x: 0, y: top, width: W, height: rowH, rx: 6, visibility: "hidden" }, g, { fill: "var(--surface-2)" });
  for (const v of ticks) {
    svgEl("line", { x1: X(v), x2: X(v), y1: top - 4, y2: H - bottom, "stroke-width": 1 }, g, { stroke: "var(--grid)" });
    svgEl("text", { x: X(v), y: H - 7, "text-anchor": "middle", "font-size": 11 }, g, { fill: "var(--muted)" }).textContent = tickText(v);
  }
  svgEl("line", { x1: x0, x2: x1, y1: H - bottom, y2: H - bottom, "stroke-width": 1 }, g, { stroke: "var(--axis)" });
  if (isNum(B.test_pos_rate)) {
    const xr = X(B.test_pos_rate);
    svgEl("line", { x1: xr, x2: xr, y1: top - 10, y2: H - bottom, "stroke-width": 1.5, "stroke-dasharray": "4 3" }, g, { stroke: "var(--ink-2)" });
    const t = svgEl("text", { x: xr + 5, y: 12, "font-size": 11 }, g, { fill: "var(--ink-2)" });
    t.textContent = `아무 정보 없이 찍을 때 ${fx(B.test_pos_rate, 3)}`;
    if (xr + 5 + textWidth(t, 11) > W) { t.setAttribute("x", xr - 5); t.setAttribute("text-anchor", "end"); }
  }
  ms.forEach((m, i) => {
    const yRow = top + i * rowH;
    const cy = narrow ? yRow + 27 : yRow + rowH / 2;
    const st = GROUPS[m.group] || GROUPS.base;
    if (narrow) svgEl("text", { x: x0, y: yRow + 12, "font-size": 12 }, g, HALO_INK).textContent = modelLabel(m);
    else svgEl("text", { x: labelW - 14, y: cy + 4, "text-anchor": "end", "font-size": 12.5 }, g, { fill: "var(--ink)" }).textContent = modelLabel(m);
    if (isCi(m.pr_ci)) {
      svgEl("line", { x1: X(m.pr_ci[0]), x2: X(m.pr_ci[1]), y1: cy, y2: cy, "stroke-width": 2 }, g, { stroke: st.color });
      for (const v of m.pr_ci) svgEl("line", { x1: X(v), x2: X(v), y1: cy - 4, y2: cy + 4, "stroke-width": 2 }, g, { stroke: st.color });
    }
    if (st.hollow) svgEl("circle", { cx: X(m.pr_auc), cy, r: 4.5, "stroke-width": 2 }, g, { fill: "var(--halo, var(--surface))", stroke: st.color });
    else svgEl("circle", { cx: X(m.pr_auc), cy, r: 5, "stroke-width": 2 }, g, { fill: st.color, stroke: "var(--halo, var(--surface))" });
    const vx = (isCi(m.pr_ci) ? X(m.pr_ci[1]) : X(m.pr_auc) + 5) + 7;
    svgEl("text", { x: vx, y: cy + 4, "font-size": 12 }, g, { fill: "var(--ink)" }).textContent = fx(m.pr_auc, 3);
  });

  const tip = tipBox(box);
  let cur = -1;
  const show = (i, py) => {
    cur = i;
    hl.setAttribute("y", top + i * rowH);
    hl.setAttribute("visibility", "visible");
    const rows = compareTipRows(ms[i]);
    fillTip(tip, modelLabel(ms[i]), rows);
    const k = (svg.getBoundingClientRect().width || W) / W;
    placeTip(box, tip, X(ms[i].pr_auc) * k, py ?? (top + (i + 1) * rowH) * k);
    return rows;
  };
  const hide = () => { tip.hidden = true; hl.setAttribute("visibility", "hidden"); };
  const rowAt = (py) => Math.floor((py / ((svg.getBoundingClientRect().width || W) / W) - top) / rowH);
  const onPointer = (e) => {
    const [, py] = relPos(box, e);
    const i = rowAt(py);
    if (i >= 0 && i < ms.length) show(i, py); else hide();
  };
  svg.addEventListener("pointermove", onPointer);
  svg.addEventListener("pointerdown", onPointer);
  svg.addEventListener("pointerleave", hide);
  svg.addEventListener("focus", () => {
    const i = cur >= 0 ? cur : Math.max(0, ms.findIndex((m) => m.group === "rdelay"));
    announce(tipText(modelLabel(ms[i]), show(i)));
  });
  svg.addEventListener("blur", () => { hide(); cur = -1; });
  svg.addEventListener("keydown", (e) => {
    const step = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 }[e.key];
    if (!step && e.key !== "Home" && e.key !== "End") return;
    e.preventDefault();
    const i = e.key === "Home" ? 0 : e.key === "End" ? ms.length - 1 : Math.min(ms.length - 1, Math.max(0, (cur < 0 ? 0 : cur) + step));
    announce(tipText(modelLabel(ms[i]), show(i)));
  });
}

// ---------- 4. 경보 ----------
function renderAlarm(B) {
  const pct = alarmRatePct(B);
  const ar = B.alarm_rule || {};
  const am = modelByKey(B, ar.model);
  $("bt-alarm-lead").textContent = `모형마다 검증 기간에 경보가${pct ? ` ${pct}%쯤` : ""} 울리도록 기준을 정하고, 그 기준을 평가 기간에 그대로 썼습니다. 그래서 평가 기간의 실제 경보 비율은 모형마다 조금 다릅니다.${am ? ` R-Delay 경보는 ${josa(modelLabel(am), ["이", "가"])} ${fx(ar.threshold, 3)} 이상일 때 켜집니다.` : ""}`;
  const head = ["모형", "실제 경보 비율", "정밀도", "재현율", "경보 횟수", "오경보율", ["72시간 창에서 잡은 에피소드", "에피소드 시작 전 72시간 안에 경보가 있었던 에피소드 수 / 전체"],
    ["덮는 경보로 잡은 에피소드", "에피소드 시작 전 24시간 안에 경보가 있었던 에피소드 수 / 전체"], "선행시간 중앙값(25~75%)"];
  const rows = (B.models || []).filter((m) => m.alarm).map((m) => {
    const a = m.alarm;
    const lead = isNum(a.lead_h_median) ? `${fx(a.lead_h_median, 1)}시간(${fx(a.lead_h_q25, 1)}~${fx(a.lead_h_q75, 1)})` : DASH;
    return { cells: [modelLabel(m), fpct(a.rate, 1), fx(a.precision, 2), fx(a.recall, 2), fint(a.onsets), fx(a.false_alarm_rate, 2), ratio(a.caught_72h, a.episodes), ratio(a.caught_cover, a.episodes), lead] };
  });
  buildTable($("bt-alarm"), head, rows, [1, 2, 3, 4, 5, 6, 7, 8]);
  const note = windowNote(B);
  const n = $("bt-window-note");
  n.textContent = note;
  n.hidden = !note;
}

// ---------- 5. 사례 ----------
function renderCases(B) {
  $("bt-case-note").textContent = publicWording(B.case_note || "");
  const cases = B.cases || [];
  const tabs = $("bt-case-tabs");
  tabs.replaceChildren();
  if (!cases.length) { $("bt-case-panel").replaceChildren(el("p", "m-error", "사례 자료가 없습니다.")); return; }
  cases.forEach((c, i) => {
    const b = el("button", null, caseTabLabel(c), tabs);
    b.type = "button";
    b.id = `bt-tab-${c.id}`;
    b.setAttribute("role", "tab");
    b.setAttribute("aria-controls", "bt-case-panel");
    b.addEventListener("click", () => selectCase(i));
  });
  tabs.addEventListener("keydown", (e) => {
    const all = [...tabs.querySelectorAll("[role=tab]")];
    const cur = all.indexOf(document.activeElement);
    if (cur < 0) return;
    const next = { ArrowRight: cur + 1, ArrowLeft: cur - 1, Home: 0, End: all.length - 1 }[e.key];
    if (next == null) return;
    e.preventDefault();
    const i = (next + all.length) % all.length;
    selectCase(i);
    all[i].focus();
  });
  selectCase(0);
}

function selectCase(i) {
  const B = STATE.B;
  const c = B.cases[i];
  STATE.caseIdx = i;
  $("bt-case-tabs").querySelectorAll("[role=tab]").forEach((b, k) => {
    b.setAttribute("aria-selected", String(k === i));
    b.tabIndex = k === i ? 0 : -1;
  });
  const panel = $("bt-case-panel");
  panel.setAttribute("aria-labelledby", `bt-tab-${c.id}`);
  panel.replaceChildren();
  el("h3", "bt-case-title", c.title || caseTabLabel(c), panel);
  const typh = c.kind === "typhoon";
  const km = typhoonKm(c);
  const X = waitThreshold(B);
  const per = el("p", "bt-period", null, panel);
  per.append(bold(`${fmtYMDH(parseTime(c.start))} ~ ${fmtYMDH(parseTime(c.end))}`), " ", el("span", "m-sub", typh
    ? `(태풍 중심이 신항 ${km ? `${km}km` : "가까이"} 안에 들어온 때와 나간 때)`
    : `(에피소드의 시작과 끝 = ${X ? `${X}시간 넘게` : "오래"} 기다린 배의 첫 도착과 마지막 도착, 시 단위로 내림)`));
  el("p", "m-sub bt-rule", `고른 규칙: ${publicWording(c.rule)}`, panel);
  const ul = el("ul", "m-bullets bt-facts", null, panel);
  for (const line of caseFactsLines(c, B)) el("li", null, line, ul);
  if (c.attribution?.text) {
    const call = el("p", "m-callout bt-attr", null, panel);
    call.append(bold("모형상 배분(원인 판정)"), " ", publicWording(c.attribution.text), " ", el("span", "m-sub", "설명용으로 나중에 계산한 값이며 책임 소재 판단에 쓰지 않습니다."));
  }
  const lg = el("div", "legend bt-legend", null, panel);
  legendKeys(lg, [
    { kind: "line", color: "var(--s1)", label: "R-Delay 확률" },
    { kind: "dash", color: "var(--ink-2)", dash: "4 3", width: 1.5, label: "경보 기준" },
    { kind: "band", color: "var(--s1)", opacity: 0.16, label: "경보가 켜진 때" },
    { kind: "strip", color: "var(--truth)", label: `정답: 앞으로 24시간 안에 ${X ? `${X}시간 넘게` : "오래"} 기다릴 배가 옴` },
    { kind: "dash", color: "var(--muted)", dash: "3 3", width: 1.5, label: `P(R_d>1)(앱 확산 경보 기준 ${SPREAD_ALARM_P})` },
    { kind: "dot", color: "var(--s2)", label: `${X ? `${X}시간 넘게` : "오래"} 기다린 배(도착 시각 · 대기 시간 구간)` },
    { kind: "vline", color: "var(--s4)", label: typh ? "태풍 진입·이탈" : "에피소드 시작·끝" },
  ]);
  const chart = el("div", "chart bt-chart bt-case-chart", null, panel);
  chart.id = "bt-case-chart";
  el("p", "m-sub bt-chart-hint", "그림을 누르거나 ←/→ 키(Shift를 함께 누르면 하루씩)로 시각별 값을 볼 수 있습니다.", panel);
  const det = el("details", "bt-details", null, panel);
  el("summary", null, "이 사례를 표로 보기", det);
  det.addEventListener("toggle", () => { if (det.open && !det.dataset.done) { det.dataset.done = "1"; caseTables(det, c, B); updateScrollHints(); } });
  drawCase(chart, c, B);
}

function caseTables(det, c, B) {
  const X = waitThreshold(B);
  const rows = arrivalTableRows(c);
  if (rows.length) {
    const what = `${X ? `${X}시간 넘게` : "오래"} 기다린 배`;
    el("p", "m-sub", `${what}(도착 시각은 시 단위로 내림, 대기 시간은 구간만)`, det);
    const w1 = el("div", "table-wrap m-table-wrap", null, det);
    w1.tabIndex = 0;
    w1.setAttribute("role", "region");
    w1.setAttribute("aria-label", `${what} 표`);
    const t1 = el("table", "m-table", null, w1);
    buildTable(t1, ["도착 시각", "대기 시간 구간"], rows.map((cells) => ({ cells })));
  }
  el("p", "m-sub", "판단 시각별 값", det);
  const w2 = el("div", "table-wrap m-table-wrap bt-scroll-y", null, det);
  w2.tabIndex = 0;
  w2.setAttribute("role", "region");
  w2.setAttribute("aria-label", "판단 시각별 값 표");
  const t2 = el("table", "m-table", null, w2);
  buildTable(t2, ["판단 시각", "정박지 대기(척)", "R-Delay 확률", "경보", "정답", "P(R_d>1)", "풍속(m/s)", "유의파고(m)", "도로 혼잡"],
    caseTableRows(c).map((cells) => ({ cells })), [1, 2, 5, 6, 7, 8]);
}

const CASE_PANELS = [
  { key: "anchor", title: "정박지에서 기다린 배(척)", h: 96 },
  { key: "waits", title: "오래 기다린 배의 대기 시간 구간(시간)", h: 90 },
  { key: "prob", title: "R-Delay 확률과 경보", h: 132 },
  { key: "wind", title: "풍속(부산, m/s)", h: 80 },
  { key: "wave", title: "유의파고(거제도, m)", h: 80 },
  { key: "road", title: "도로 혼잡 콘존(%)", h: 80 },
];

function drawCase(box, c, B) {
  const s = c.series || {};
  const times = seriesTimes(s);
  const n = times.length;
  if (!n) { box.replaceChildren(el("p", "m-error", "이 사례의 시계열이 없습니다.")); return; }
  const W = Math.max(280, Math.round(box.clientWidth || 640));
  const m = { l: 38, r: 10 };
  const titleH = 17, gap = 12, topPad = 16, axisH = 22;
  let y = topPad;
  const P = CASE_PANELS.map((p) => { const o = { ...p, y0: y + titleH, y1: y + titleH + p.h }; y = o.y1 + gap; return o; });
  const H = P[P.length - 1].y1 + axisH;
  const step = (s.step_h || 2) * HOUR;
  const arr = arrivalSlots(c);
  const bands = caseBands(B);
  const XW = waitThreshold(B);
  const svg = freshSvg(box, W, H, `${c.title || "사례"}: 정박지 대기, ${XW ? `${XW}시간 넘게` : "오래"} 기다린 배의 도착 시각과 대기 시간 구간, R-Delay 확률과 경보, 풍속, 유의파고, 도로 혼잡을 같은 시간축으로 그린 그림(←/→ 키로 시각별 값 보기)`);
  // 왼쪽 여백: 대기 시간 구간 이름(「48~168」)이 들어가도록 실제 글자 폭을 잰다(모든 칸이 같은 가로축을 쓰므로 함께 넓힌다).
  for (const b of bands) {
    const probe = svgEl("text", { x: 0, y: 0, "font-size": 10.5 }, svg);
    probe.textContent = bandAxisLabel(b);
    m.l = Math.min(64, Math.max(m.l, Math.ceil(textWidth(probe, 10.5)) + 10));
    probe.remove();
  }
  const tA = Math.min(times[0], ...arr.map((a) => a.t)), tB = Math.max(times[n - 1], ...arr.map((a) => a.t));
  const X = (t) => m.l + ((t - tA) / (tB - tA || 1)) * (W - m.l - m.r);
  const Xc = (t) => X(Math.max(tA, Math.min(tB, t)));
  const g = svgEl("g", {}, svg);
  const ticks = dayTicks(tA, tB, Math.max(2, Math.floor((W - m.l - m.r) / 52)));
  const num = (k) => (Array.isArray(s[k]) ? s[k] : []);

  const scaleY = (p, lo, hi) => (v) => p.y1 - ((v - lo) / (hi - lo || 1)) * (p.y1 - p.y0);
  const linePath = (pts, Y) => {
    let d = "", pen = false;
    for (const [t, v] of pts) {
      if (!isNum(v)) { pen = false; continue; }
      d += `${pen ? "L" : "M"}${Xc(t).toFixed(1)},${Y(v).toFixed(1)}`;
      pen = true;
    }
    return d;
  };
  const frame = (p, lo, hi, count, fmt = tickText, intOnly = false) => {
    svgEl("text", { x: m.l, y: p.y0 - 5, "font-size": 11.5, "font-weight": 600 }, g, { fill: "var(--ink-2)" }).textContent = p.titleText || p.title;
    const Y = scaleY(p, lo, hi);
    let tk = niceTicks(lo, hi, count);
    if (intOnly) tk = tk.filter((v) => Number.isInteger(v));
    for (const v of tk) {
      svgEl("line", { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), "stroke-width": 1 }, g, { stroke: "var(--grid)" });
      svgEl("text", { x: m.l - 5, y: Y(v) + 4, "text-anchor": "end", "font-size": 10.5 }, g, { fill: "var(--muted)" }).textContent = fmt(v);
    }
    for (const t of ticks) svgEl("line", { x1: X(t), x2: X(t), y1: p.y0, y2: p.y1, "stroke-width": 1 }, g, { stroke: "var(--grid)" });
    svgEl("line", { x1: m.l, x2: W - m.r, y1: p.y1, y2: p.y1, "stroke-width": 1 }, g, { stroke: "var(--axis)" });
    return Y;
  };
  // 값이 빠진 칸: 옅은 띠와 「자료 없음」
  const missing = (p, vals) => {
    for (const [a, b] of runs(vals, (v) => v == null)) {
      const xa = Xc(times[a]), xb = Xc(times[b] + step);
      svgEl("rect", { x: xa, y: p.y0, width: Math.max(1, xb - xa), height: p.y1 - p.y0 }, g, { fill: "var(--surface-2)" });
      if (xb - xa > 46) svgEl("text", { x: (xa + xb) / 2, y: (p.y0 + p.y1) / 2 + 4, "text-anchor": "middle", "font-size": 10.5 }, g, { fill: "var(--muted)" }).textContent = "자료 없음";
    }
  };
  const maxOf = (vals, fallback) => { const v = vals.filter(isNum); return v.length ? Math.max(...v) : fallback; };

  // (1) 정박지 대기: 계단
  {
    const p = P[0];
    const vals = num("anchor");
    const hi = maxOf(vals, 1) * 1.12 || 1;
    missing(p, vals);
    const Y = frame(p, 0, Math.max(1, hi), 3, tickText, true);
    svgEl("path", { d: linePath(stepPoints(times, vals), Y), fill: "none", "stroke-width": 1.6, "stroke-linejoin": "round" }, g, { stroke: "var(--ink-2)" });
  }
  // (2) 오래 기다린 배: 점(가로 = 시 단위로 내린 도착 시각, 세로 = 대기 시간 구간 줄; 짧은 구간이 아래)
  {
    const p = P[1];
    if (XW) p.titleText = `${XW}시간 넘게 기다린 배의 대기 시간 구간(시간)`;
    svgEl("text", { x: m.l, y: p.y0 - 5, "font-size": 11.5, "font-weight": 600 }, g, { fill: "var(--ink-2)" }).textContent = p.titleText || p.title;
    const rowH = (p.y1 - p.y0) / Math.max(1, bands.length);
    const rowY = (k) => p.y1 - (k + 0.5) * rowH;
    for (const t of ticks) svgEl("line", { x1: X(t), x2: X(t), y1: p.y0, y2: p.y1, "stroke-width": 1 }, g, { stroke: "var(--grid)" });
    bands.forEach((b, k) => {
      svgEl("line", { x1: m.l, x2: W - m.r, y1: rowY(k), y2: rowY(k), "stroke-width": 1 }, g, { stroke: "var(--grid)" });
      svgEl("text", { x: m.l - 5, y: rowY(k) + 4, "text-anchor": "end", "font-size": 10.5 }, g, { fill: "var(--muted)" }).textContent = bandAxisLabel(b);
    });
    svgEl("line", { x1: m.l, x2: W - m.r, y1: p.y1, y2: p.y1, "stroke-width": 1 }, g, { stroke: "var(--axis)" });
    if (!arr.length) svgEl("text", { x: (m.l + W - m.r) / 2, y: (p.y0 + p.y1) / 2 + 4, "text-anchor": "middle", "font-size": 11 }, g, HALO_MUTED).textContent = "이 기간에 도착한 배 없음";
    // 같은 줄에서 겹치는 점(같은 시각에 온 배 등)은 그 줄 안에서 위아래로 비켜 그린다. 가로 위치(도착 시각)는 바꾸지 않는다.
    const R = 4, D = 2 * R + 1; // 비켜 그리는 거리(점 지름보다 조금 크게, 줄 높이의 절반 안)
    const placed = bands.map(() => []);
    for (const a of arr) {
      const k = bands.indexOf(a.band);
      if (k < 0) continue;
      const x = Xc(a.t);
      const dy = [0, -D, D].find((d) => placed[k].every((q) => Math.hypot(q.x - x, q.dy - d) >= 2 * R + 0.5)) ?? 0;
      placed[k].push({ x, dy });
      svgEl("circle", { cx: x, cy: rowY(k) + dy, r: R, "stroke-width": 1.5 }, g, { fill: "var(--s2)", stroke: "var(--halo, var(--surface))" });
    }
  }
  // (3) R-Delay 확률: 경보 띠 + 정답 띠 + 기준선 + 확률선 + P(R_d>1)
  let probY = null;
  {
    const p = P[2];
    const thr = isNum(c.facts?.alarm_threshold) ? c.facts.alarm_threshold : B.alarm_rule?.threshold;
    const top = Math.max(0.6, Math.ceil((Math.max(maxOf(num("prob"), 0), isNum(thr) ? thr : 0) + 0.05) * 10) / 10);
    for (const [a, b] of runs(num("alarm"))) {
      const xa = Xc(times[a]), xb = Xc(times[b] + step);
      svgEl("rect", { x: xa, y: p.y0, width: Math.max(1, xb - xa), height: p.y1 - p.y0 }, g, { fill: "var(--s1)", opacity: 0.12 });
    }
    const Y = frame(p, 0, top, 3);
    probY = Y;
    for (const [a, b] of runs(num("y"))) {
      const xa = Xc(times[a]), xb = Xc(times[b] + step);
      svgEl("rect", { x: xa, y: p.y1 - 7, width: Math.max(1, xb - xa), height: 7 }, g, { fill: "var(--truth)", opacity: 0.65 });
    }
    if (isNum(thr)) {
      svgEl("line", { x1: m.l, x2: W - m.r, y1: Y(thr), y2: Y(thr), "stroke-width": 1.5, "stroke-dasharray": "4 3" }, g, { stroke: "var(--ink-2)" });
      svgEl("text", { x: W - m.r, y: Y(thr) - 5, "text-anchor": "end", "font-size": 10.5 }, g, HALO_INK2).textContent = `경보 기준 ${fx(thr, 3)}`;
    }
    svgEl("path", { d: linePath(times.map((t, i) => [t, num("p_rd1")[i]]), Y), fill: "none", "stroke-width": 1.5, "stroke-dasharray": "3 3" }, g, { stroke: "var(--muted)" });
    svgEl("path", { d: linePath(times.map((t, i) => [t, num("prob")[i]]), Y), fill: "none", "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, g, { stroke: "var(--s1)" });
  }
  // (4)~(6) 기상·도로: 선(값이 없는 칸은 끊고 「자료 없음」)
  const simple = (p, key, f = (v) => v) => {
    const vals = num(key).map((v) => (isNum(v) ? f(v) : null));
    missing(p, vals);
    const hi = maxOf(vals, 0) * 1.15 || 1;
    const Y = frame(p, 0, hi, 2);
    svgEl("path", { d: linePath(times.map((t, i) => [t, vals[i]]), Y), fill: "none", "stroke-width": 1.5, "stroke-linejoin": "round" }, g, { stroke: "var(--ink-2)" });
  };
  simple(P[3], "wind");
  simple(P[4], "wave");
  simple(P[5], "road", (v) => v * 100);

  // 날짜 눈금(맨 아래만)
  for (const t of ticks) svgEl("text", { x: X(t), y: H - 6, "text-anchor": "middle", "font-size": 11 }, g, { fill: "var(--muted)" }).textContent = fmtMD(t);
  // 에피소드(또는 태풍) 시작·끝: 모든 칸을 지나는 세로선. 시작 글자는 선 왼쪽, 끝 글자는 오른쪽(가장자리에 닿으면 반대쪽).
  const ev = [[parseTime(c.start), isTyphoon(c) ? "진입" : "시작", "end"], [parseTime(c.end), isTyphoon(c) ? "이탈" : "끝", "start"]];
  for (const [t, label, anchor] of ev) {
    if (!isNum(t) || t < tA || t > tB) continue;
    const x = X(t);
    svgEl("line", { x1: x, x2: x, y1: P[0].y0 - 2, y2: P[P.length - 1].y1, "stroke-width": 1.5 }, g, { stroke: "var(--s4)" });
    const tx = svgEl("text", { x: x + (anchor === "end" ? -4 : 4), y: 11, "text-anchor": anchor, "font-size": 11, "font-weight": 600 }, g, { fill: "var(--ink)" });
    tx.textContent = label;
    const w = textWidth(tx, 11);
    if (anchor === "end" && x - 4 - w < 0) { tx.setAttribute("x", x + 4); tx.setAttribute("text-anchor", "start"); }
    if (anchor === "start" && x + 4 + w > W) { tx.setAttribute("x", x - 4); tx.setAttribute("text-anchor", "end"); }
  }

  // 십자선: 모든 칸을 지나고, 그 시각의 모든 값을 툴팁 하나에 보인다.
  const cross = svgEl("line", { y1: P[0].y0, y2: P[P.length - 1].y1, "stroke-width": 1, visibility: "hidden" }, svg, { stroke: "var(--ink-2)" });
  const dot = svgEl("circle", { r: 3.5, "stroke-width": 2, visibility: "hidden" }, svg, { fill: "var(--s1)", stroke: "var(--halo, var(--surface))" });
  const tip = tipBox(box);
  const nearest = (t) => Math.min(n - 1, Math.max(0, Math.round((t - times[0]) / step)));
  let cur = nearest(parseTime(c.start));
  const show = (i, py) => {
    cur = i;
    const x = X(times[i]);
    cross.setAttribute("x1", x);
    cross.setAttribute("x2", x);
    cross.setAttribute("visibility", "visible");
    const pv = num("prob")[i];
    if (isNum(pv) && probY) { dot.setAttribute("cx", x); dot.setAttribute("cy", probY(pv)); dot.setAttribute("visibility", "visible"); } else dot.setAttribute("visibility", "hidden");
    const rows = caseTipRows(c, i);
    fillTip(tip, fmtMDH(times[i]), rows);
    const k = (svg.getBoundingClientRect().width || W) / W;
    placeTip(box, tip, x * k, py ?? P[0].y0 * k);
    return rows;
  };
  const hide = () => { tip.hidden = true; cross.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); };
  const onPointer = (e) => {
    const [px, py] = relPos(box, e);
    const k = (svg.getBoundingClientRect().width || W) / W;
    const t = tA + ((px / k - m.l) / (W - m.l - m.r)) * (tB - tA);
    show(nearest(t), py);
  };
  svg.addEventListener("pointermove", onPointer);
  svg.addEventListener("pointerdown", onPointer);
  svg.addEventListener("pointerleave", hide);
  svg.addEventListener("focus", () => announce(tipText(fmtMDH(times[cur]), show(cur))));
  svg.addEventListener("blur", hide);
  svg.addEventListener("keydown", (e) => {
    let i = null;
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") i = cur + (e.key === "ArrowRight" ? 1 : -1) * (e.shiftKey ? Math.max(1, Math.round(DAY / step)) : 1);
    else if (e.key === "Home") i = 0;
    else if (e.key === "End") i = n - 1;
    if (i == null) return;
    e.preventDefault();
    i = Math.min(n - 1, Math.max(0, i));
    announce(tipText(fmtMDH(times[i]), show(i)));
  });
}
// ---------- 6. 신뢰도 ----------
function renderReliability(B) {
  const minN = B.constants?.reliability_min_n;
  $("bt-rel-lead").textContent = `예측 확률을 0.1 간격 구간으로 나눠, 구간마다 예측 확률의 평균(가로)과 실제로 일어난 비율(세로)을 견줬습니다. 점이 대각선 위에 있을수록 확률을 그대로 믿을 수 있습니다.${isNum(minN) ? ` 판단 시각이 ${fint(minN)}개 미만인 구간은 뺐습니다.` : ""}`;
  const ser = reliabilitySeries(B);
  legendKeys($("bt-rel-legend"), [
    ...ser.map((s) => ({ kind: "line", color: s.color, dash: s.dash, marker: s.marker, label: modelLabel(s.model) })),
    { kind: "dash", color: "var(--muted)", dash: "4 4", width: 1.5, label: "대각선 = 확률이 딱 맞을 때" },
    { kind: "dash", color: "var(--muted)", dash: "1 3", width: 1.5, label: `평가 기간 양성 비율(${fx(B.test_pos_rate, 3)})` },
  ]);
  drawReliability($("bt-rel-chart"), B);
  // 표본이 가장 많은 구간에 R-Delay 확률이 얼마나 몰렸는지(그대로 옮김)
  const r2 = ser.find((s) => s.model.group === "rdelay");
  const parts = [];
  const nTest = B.periods?.n_tau?.test;
  if (r2 && r2.pts.length && isNum(nTest)) {
    const big = r2.pts.reduce((a, b) => (b.n > a.n ? b : a));
    if (big.n * 2 > nTest) {
      parts.push(`${josa(modelLabel(r2.model), ["은", "는"])} 평가 기간 판단 시각 ${fint(nTest)}개 중 ${fint(big.n)}개가 ${fx(big.bin?.[0], 1)}~${fx(big.bin?.[1], 1)} 구간에 몰려 있어, 확률값 자체보다 높고 낮음(순위)으로 읽는 편이 맞습니다.`);
    }
  }
  const lim = (B.limits || []).find((x) => x.includes("양성 비율") && x.includes("학습 기간"));
  if (lim) parts.push(lim);
  $("bt-rel-note").textContent = parts.join(" ");
  const rows = [];
  for (const s of ser) for (const b of s.pts) rows.push({ cells: [modelLabel(s.model), `${fx(b.bin?.[0], 1)}~${fx(b.bin?.[1], 1)}`, fint(b.n), fx(b.mean_p, 3), fx(b.obs, 3)] });
  buildTable($("bt-rel-table"), ["모형", "예측 확률 구간", "판단 시각", "예측 확률 평균", "실제로 일어난 비율"], rows, [2, 3, 4]);
}

function drawReliability(box, B) {
  const ser = reliabilitySeries(B);
  if (!ser.length) { box.replaceChildren(el("p", "m-error", "신뢰도 자료가 없습니다.")); return; }
  const W = Math.max(260, Math.min(Math.round(box.clientWidth || 520), 560));
  const H = Math.round(Math.min(440, Math.max(260, W * 0.8)));
  const m = { l: 40, r: 14, t: 26, b: 40 };
  const allV = ser.flatMap((s) => s.pts.flatMap((p) => [p.mean_p, p.obs]));
  const top = Math.max(...allV, B.test_pos_rate || 0) > 0.8 ? 1 : 0.8;
  const X = (v) => m.l + (v / top) * (W - m.l - m.r);
  const Y = (v) => H - m.b - (v / top) * (H - m.t - m.b);
  const svg = freshSvg(box, W, H, `신뢰도 곡선: ${ser.map((s) => s.model.name).join(", ")}(←/→ 키로 점별 값 보기)`);
  const g = svgEl("g", {}, svg);
  for (const v of niceTicks(0, top, 4)) {
    svgEl("line", { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), "stroke-width": 1 }, g, { stroke: "var(--grid)" });
    svgEl("line", { x1: X(v), x2: X(v), y1: m.t, y2: H - m.b, "stroke-width": 1 }, g, { stroke: "var(--grid)" });
    svgEl("text", { x: m.l - 6, y: Y(v) + 4, "text-anchor": "end", "font-size": 11 }, g, { fill: "var(--muted)" }).textContent = tickText(v);
    svgEl("text", { x: X(v), y: H - m.b + 16, "text-anchor": "middle", "font-size": 11 }, g, { fill: "var(--muted)" }).textContent = tickText(v);
  }
  svgEl("line", { x1: m.l, x2: W - m.r, y1: H - m.b, y2: H - m.b, "stroke-width": 1 }, g, { stroke: "var(--axis)" });
  svgEl("line", { x1: m.l, x2: m.l, y1: m.t, y2: H - m.b, "stroke-width": 1 }, g, { stroke: "var(--axis)" });
  svgEl("text", { x: (m.l + W - m.r) / 2, y: H - 6, "text-anchor": "middle", "font-size": 11.5 }, g, { fill: "var(--ink-2)" }).textContent = "예측 확률(구간 평균)";
  svgEl("text", { x: m.l, y: 14, "font-size": 11.5 }, g, { fill: "var(--ink-2)" }).textContent = "↑ 실제로 일어난 비율";
  svgEl("line", { x1: X(0), x2: X(top), y1: Y(0), y2: Y(top), "stroke-width": 1.5, "stroke-dasharray": "4 4" }, g, { stroke: "var(--muted)" });
  if (isNum(B.test_pos_rate)) {
    svgEl("line", { x1: m.l, x2: W - m.r, y1: Y(B.test_pos_rate), y2: Y(B.test_pos_rate), "stroke-width": 1.5, "stroke-dasharray": "1 3" }, g, { stroke: "var(--muted)" });
  }
  const pts = [];
  for (const s of ser) {
    const d = s.pts.map((b, i) => `${i ? "L" : "M"}${X(b.mean_p).toFixed(1)},${Y(b.obs).toFixed(1)}`).join("");
    const a = { d, fill: "none", "stroke-width": 2, "stroke-linejoin": "round" };
    if (s.dash) a["stroke-dasharray"] = s.dash;
    svgEl("path", a, g, { stroke: s.color });
  }
  for (const s of ser) for (const b of s.pts) { marker(g, s.marker, X(b.mean_p), Y(b.obs), 5.5, s.color); pts.push({ s, b, x: X(b.mean_p), y: Y(b.obs) }); }

  const ring = svgEl("circle", { r: 9, "stroke-width": 2, fill: "none", visibility: "hidden" }, svg, { stroke: "var(--ink)" });
  const tip = tipBox(box);
  let cur = -1;
  const show = (i) => {
    cur = i;
    const p = pts[i];
    ring.setAttribute("cx", p.x);
    ring.setAttribute("cy", p.y);
    ring.setAttribute("visibility", "visible");
    const rows = relTip(p.s, p.b);
    fillTip(tip, modelLabel(p.s.model), rows);
    const k = (svg.getBoundingClientRect().width || W) / W;
    placeTip(box, tip, p.x * k, p.y * k);
    return rows;
  };
  const hide = () => { tip.hidden = true; ring.setAttribute("visibility", "hidden"); };
  const onPointer = (e) => {
    const [px, py] = relPos(box, e);
    const k = (svg.getBoundingClientRect().width || W) / W;
    let best = -1, bd = 30;
    pts.forEach((p, i) => { const d = Math.hypot(p.x - px / k, p.y - py / k); if (d < bd) { bd = d; best = i; } });
    if (best >= 0) show(best); else hide();
  };
  svg.addEventListener("pointermove", onPointer);
  svg.addEventListener("pointerdown", onPointer);
  svg.addEventListener("pointerleave", hide);
  svg.addEventListener("focus", () => { const i = cur >= 0 ? cur : 0; announce(tipText(modelLabel(pts[i].s.model), show(i))); });
  svg.addEventListener("blur", () => { hide(); cur = -1; });
  svg.addEventListener("keydown", (e) => {
    const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
    if (!step) return;
    e.preventDefault();
    const i = Math.min(pts.length - 1, Math.max(0, (cur < 0 ? 0 : cur) + step));
    announce(tipText(modelLabel(pts[i].s.model), show(i)));
  });
}

// ---------- 7. 어디서 잘하고 못하나 ----------
function renderWhere(B) {
  const keys = [...new Set((B.subgroups || []).flatMap((sg) => Object.keys(sg.pr_auc || {})))];
  const name = (k) => modelByKey(B, k)?.name || k;
  const head = ["묶음", "판단 시각", "양성", "양성 비율", ...keys.map((k) => [name(k), modelLabel(modelByKey(B, k))]), "가장 높은 모형"];
  const rows = (B.subgroups || []).map((sg) => {
    const first = sg.interpretable ? sg.name : frag(sg.name, " ", tag("해석 안 함"));
    const best = subgroupBest(sg);
    return {
      cls: sg.interpretable ? null : "bt-dim",
      best: best.map((k) => 4 + keys.indexOf(k)),
      cells: [first, fint(sg.n), fint(sg.n_pos), fx(sg.pos_rate, 3), ...keys.map((k) => fx(sg.pr_auc?.[k], 3)), best.length ? best.map(name).join(" · ") : DASH],
    };
  });
  buildTable($("bt-sub"), head, rows, [1, 2, 3, ...keys.map((_, i) => 4 + i)]);
  const minPos = B.constants?.min_pos_subgroup;
  $("bt-sub-note").textContent = `${isNum(minPos) ? `양성 판단 시각이 ${fint(minPos)}개 미만인 묶음은 PR-AUC가 몇 개 점에 좌우되므로 해석하지 않습니다(값은 기록용). ` : ""}굵은 숫자는 그 묶음에서 가장 높은 값입니다. 양성 비율이 묶음마다 달라 PR-AUC는 같은 줄 안에서만 견줘 읽어 주세요.`;

  $("bt-vessel-lead").textContent = "배 한 척 한 척이 정박지에서 오래 기다릴지도 따로 맞혀 봤습니다. 기준선은 판단 시각의 공개 특징에 배 크기(총톤수)를 더한 로지스틱 회귀이고, 하이브리드는 여기에 R-Delay 대기열 확률을 더한 것입니다. 도착 전 판단에는 도착 시각을 미리 안다는 낙관적 가정이 들어 있습니다.";
  const trip = (s) => (s ? `${fx(s.pr_auc, 3)} · ${fx(s.roc_auc, 3)} · ${fx(s.brier, 3)}` : DASH);
  const vrows = (B.vessel || []).map((v) => {
    const mm = /^([^()]+)\((.*)\)$/.exec(v.name || "");
    const first = mm ? frag(bold(mm[1]), el("span", "bt-cell-sub", mm[2])) : v.name;
    if (v.note) return { cells: [first, fint(v.n_test), DASH, v.note, DASH, DASH] };
    return { cells: [first, fint(v.n_test), fx(v.pos_rate, 3), trip(v.baseline), trip(v.rdelay_queue), trip(v.hybrid)] };
  });
  buildTable($("bt-vessel"), ["판단", "배 수(평가 기간)", "양성 비율", "기준선: PR-AUC · ROC-AUC · Brier", "R-Delay 대기열: PR-AUC · ROC-AUC · Brier", "하이브리드: PR-AUC · ROC-AUC · Brier"], vrows, [1, 2, 3, 4, 5]);
  $("bt-vessel-note").textContent = `${vesselNote(B)} PR-AUC는 양성 비율과 견줘 읽어야 합니다(아무 정보 없이 찍으면 양성 비율과 같음). Brier는 낮을수록 좋습니다.`.trim();

  const post = B.posthoc || {};
  $("bt-post-lead").textContent = `평가 기간 판단 시각 ${fint(post.n)}개에서 두 모형 점수의 순위가 얼마나 같이 움직이는지(스피어만 순위상관, 1이면 순위가 똑같음) 봤습니다. ${spearmanSentence(B)}`;
  const ul = $("bt-post");
  ul.replaceChildren();
  for (const r of spearmanRows(B)) { const li = el("li", null, null, ul); li.append(`${r.label}: `, bold(fx(r.value, 3))); }
  $("bt-post-note").textContent = publicWording(post.note ? `${post.note}.` : "");
  $("bt-rd").textContent = rdSentence(B);
}

// ---------- 8. 한계 ----------
function renderLimits(B) {
  const ul = $("bt-limits");
  ul.replaceChildren();
  for (const s of B.limits || []) {
    const [a, b] = splitFirstSentence(s);
    const li = el("li", null, null, ul);
    li.append(bold(a), b);
  }
}

// ---------- 9. 출처 ----------
const RANGE_NAME = { cntl: "PORT-MIS 관제정보", asos: "종관기상관측(ASOS)", buoy: "해양기상부이", road: "고속도로 구간통행속도", typhoon_track: "태풍경로" };
function renderSources(B) {
  const ul = $("bt-sources");
  ul.replaceChildren();
  for (const s of B.sources || []) {
    const li = el("li", null, null, ul);
    const h = el("p", "bt-src-h", null, li);
    h.append(bold(s.org || ""), ` ${s.name || ""}`);
    const meta = [s.id ? `데이터 번호 ${s.id}` : null, s.via || null].filter(Boolean).join(" · ");
    if (meta) el("p", "bt-src-meta", meta, li);
    if (s.use) el("p", "bt-src-use", `쓴 곳: ${s.use}`, li);
    if (/^https?:\/\//.test(s.url || "")) {
      const a = el("a", "bt-src-link", "자료 페이지 →", li);
      a.href = s.url;
      a.rel = "noopener";
      a.setAttribute("aria-label", `${s.org || ""} ${s.name || ""} 자료 페이지`);
    }
  }
  const kogl = (B.sources || []).filter((s) => /공공누리/.test(s.via || "")).map((s) => s.name);
  $("bt-kogl").textContent = `${kogl.length ? `‘공공누리 출처표시’로 적은 자료(${kogl.join(", ")})는 그 조건에 따라 출처를 밝혀 씁니다. ` : ""}자료마다 제공 기관과 받은 곳을 밝혔습니다. ${dataScopeText(B)}`;
  const dr = B.data_ranges || {};
  buildTable($("bt-ranges"), ["자료", "기간"], Object.entries(dr).map(([k, v]) => ({ cells: [RANGE_NAME[k] || k, Array.isArray(v) ? `${v[0]} ~ ${v[1]}` : DASH] })));
  $("bt-files-lead").textContent = filesLead(B);
  const fl = $("bt-files");
  fl.replaceChildren();
  for (const f of B.source_files || []) { const li = el("li", null, null, fl); el("code", null, f, li); }
  const cn = $("bt-commit");
  if (cn) { cn.textContent = commitNote(B); cn.hidden = !cn.textContent; }
}

// ---------- 공통 화면 동작(method.js와 같은 방식) ----------
const getJSON = (url) => fetch(url, { cache: "no-cache" }).then((r) => (r.ok ? r.json() : null)).catch(() => null);

function fail(id, text) {
  const t = $(id);
  if (!t) return;
  const wrap = t.closest(".m-table-wrap") || t;
  const p = document.createElement("p");
  p.className = "m-error";
  p.textContent = text;
  wrap.replaceWith(p);
}

function setupToc() {
  const links = [...document.querySelectorAll(".m-toc a[href^='#']")];
  const mobile = $("toc-mobile");
  links.forEach((a) => a.addEventListener("click", () => { if (mobile && mobile.contains(a)) mobile.open = false; }));
  if (!("IntersectionObserver" in window)) return;
  const sections = [...document.querySelectorAll("main section[id]")];
  const visible = new Map();
  const mark = () => {
    let id = null;
    for (const s of sections) if (visible.get(s.id)) { id = s.id; break; }
    if (!id) return;
    for (const a of links) {
      if (a.getAttribute("href") === `#${id}`) a.setAttribute("aria-current", "true");
      else a.removeAttribute("aria-current");
    }
  };
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) visible.set(e.target.id, e.isIntersecting);
    mark();
  }, { rootMargin: "-10% 0px -55% 0px" });
  sections.forEach((s) => io.observe(s));
}

// 「공개 실자료 검증」 안내: Esc나 바깥을 누르면 닫는다.
function setupAbout() {
  const about = $("about");
  if (!about) return;
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && about.open) { about.open = false; about.querySelector("summary").focus(); }
  });
  document.addEventListener("click", (e) => { if (about.open && !about.contains(e.target)) about.open = false; });
}

// 표가 상자보다 넓을 때만 「옆으로 밀어 보세요」 안내를 보인다.
function updateScrollHints() {
  for (const w of document.querySelectorAll(".m-table-wrap")) {
    w.classList.toggle("is-scroll", w.scrollWidth > w.clientWidth + 1);
  }
}

// 그림·표가 그려진 뒤 높이가 바뀌므로, 주소에 #이 있으면 그 위치로 다시 맞춘다(사용자가 이미 움직였으면 두지 않음).
let userMoved = false;
function restoreHash() {
  if (userMoved) return;
  const id = decodeURIComponent(location.hash.slice(1));
  const target = id && document.getElementById(id);
  if (target) target.scrollIntoView({ block: "start" });
}

const SECTIONS = [
  [renderMeta, ["bt-meta"]],
  [renderSummary, ["bt-question"]],
  [renderDesign, ["bt-design", "bt-periods", "bt-models", "bt-pretest"]],
  [renderCompare, ["bt-compare-chart", "bt-scores", "bt-pairs"]],
  [renderAlarm, ["bt-alarm"]],
  [renderCases, ["bt-case-panel"]],
  [renderReliability, ["bt-rel-chart", "bt-rel-table"]],
  [renderWhere, ["bt-sub", "bt-vessel"]],
  [renderLimits, ["bt-limits"]],
  [renderSources, ["bt-sources", "bt-ranges"]],
];

function redrawCharts() {
  const B = STATE.B;
  if (!B) return;
  const run = (fn) => { try { fn(); } catch (err) { console.error(err); } };
  run(() => drawCompare($("bt-compare-chart"), B));
  run(() => drawReliability($("bt-rel-chart"), B));
  const chart = $("bt-case-chart");
  if (chart && B.cases?.[STATE.caseIdx]) run(() => drawCase(chart, B.cases[STATE.caseIdx], B));
  updateScrollHints();
}

async function init() {
  if ("serviceWorker" in navigator && location.protocol !== "file:") {
    navigator.serviceWorker.register("sw.js", { updateViaCache: "none" }).catch(() => {});
  }
  ["wheel", "touchstart", "keydown"].forEach((t) => window.addEventListener(t, () => { userMoved = true; }, { once: true, passive: true }));
  setupToc();
  setupAbout();

  const B = await getJSON("data/backtest.json");
  if (!B) {
    // 맨 위(한눈에)에만 긴 안내를 두고, 나머지 자리에는 짧게 적는다.
    let first = true;
    for (const [, ids] of SECTIONS) {
      for (const id of ids) {
        if (id === "bt-meta") continue;
        fail(id, first ? "실자료 검증 결과(data/backtest.json)를 불러오지 못했습니다. 인터넷 연결을 확인한 뒤 새로 고쳐 주세요." : "결과 파일을 불러오지 못했습니다.");
        first = false;
      }
    }
    $("bt-meta")?.replaceChildren();
    document.body.dataset.ready = "1";
    return;
  }
  STATE.B = B;
  const problems = checkShape(B);
  if (problems.length) console.warn("backtest.json 모양 점검:", problems);
  for (const [fn, ids] of SECTIONS) {
    try { fn(B); } catch (err) {
      console.error(err);
      ids.forEach((id) => fail(id, "이 부분을 그리지 못했습니다. 결과 파일(data/backtest.json)의 모양이 바뀌었을 수 있습니다."));
    }
  }

  updateScrollHints();
  let lastW = window.innerWidth;
  let timer = null;
  window.addEventListener("resize", () => {
    updateScrollHints();
    if (window.innerWidth === lastW) return;
    lastW = window.innerWidth;
    clearTimeout(timer);
    timer = setTimeout(redrawCharts, 150);
  }, { passive: true });
  if (document.fonts?.ready) document.fonts.ready.then(updateScrollHints);
  requestAnimationFrame(restoreHash);
  window.addEventListener("load", () => { updateScrollHints(); restoreHash(); }, { once: true });
  document.body.dataset.ready = "1";
}

if (typeof document !== "undefined" && typeof window !== "undefined") init();
