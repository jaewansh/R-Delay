// 선박별 검증 페이지(두 번째 분석): data/backtest_ship.json(부산신항 공개 자료 집계)만 읽어 표·그래프를 그린다.
// 숫자는 모두 이 파일에서 온다(화면 문구에 숫자를 박지 않음). 실자료라 차트의 '합성 데이터' 표시는 끈다.
import { timeChart, barList, legend, niceTicks } from "./charts.js?v=20261107a";

const $ = (id) => document.getElementById(id);
const pct = (x, d = 1) => (x == null ? "—" : `${(x * 100).toFixed(d)}%`);
const f3 = (x) => (x == null ? "—" : Number(x).toFixed(3));
const f1 = (x) => (x == null ? "—" : Number(x).toFixed(1));
const sgn = (x, d = 3) => (x == null ? "—" : `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(d)}`);
const chg = (drop) => (Math.abs(drop) < 5e-4 ? "0.000" : sgn(-drop));
const LEADS = ["24", "12", "6", "2", "0"];
const leadLabel = (L) => (L === "0" ? "도착 순간" : `${L}시간 전`);
const SERIES = [
  { k: "S0", color: "var(--muted)", width: 1.6 },
  { k: "R1", color: "var(--s2)", width: 1.6 },
  { k: "S2_gbm", color: "var(--ink-2)", width: 1.6, dash: "5 4" },
  { k: "R3_logit", color: "var(--s1)", width: 2.6 },
  { k: "R3_gbm", color: "var(--ink)", width: 2 },
];
const SHORT = { S0: "터미널 평균", R1: "대기열만", S2_logit: "통계(로지스틱)", S2_gbm: "통계(GBM)", R3_logit: "R-Delay 하이브리드", R3_gbm: "R-Delay GBM" };

function el(tag, attrs = {}, parent = null, text = null) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (text != null) n.textContent = text;
  if (parent) parent.appendChild(n);
  return n;
}

function table(target, head, rows, opts = {}) {
  const t = $(target);
  t.replaceChildren();
  if (opts.caption) {
    // 표가 가로로 넘칠 때(휴대폰) 캡션이 잘리지 않게 표 밖, 바로 위에 둔다.
    const wrap = t.closest(".m-table-wrap") || t;
    let cap = wrap.previousElementSibling;
    if (!cap || !cap.classList.contains("b-cap")) {
      cap = el("p", { class: "m-note b-cap" });
      wrap.parentNode.insertBefore(cap, wrap);
    }
    cap.textContent = opts.caption;
  }
  const thead = el("thead", {}, t);
  const tr = el("tr", {}, thead);
  head.forEach((h, i) => el("th", { scope: "col", class: i ? "num" : "" }, tr, h));
  const tb = el("tbody", {}, t);
  for (const r of rows) {
    const row = el("tr", { class: r.best ? "best" : "" }, tb);
    r.cells.forEach((c, i) => el(i ? "td" : "th", i ? { class: "num" } : { scope: "row" }, row, c));
  }
}

function kpis(d) {
  const h = d.headline;
  const tc = d.test_counts;
  const box = $("b-kpis");
  box.replaceChildren();
  const card = (big, small) => {
    const c = el("div", { class: "b-kpi" }, box);
    el("b", {}, c, big);
    el("span", {}, c, small);
  };
  card(pct(h.top5.recall, 1), `도착 하루 전, 위험 상위 5% 선박만 골라도 실제 12시간 초과 대기 선박의 이만큼이 그 안에 있었습니다`);
  card(`${f1(h.top5.lift)}배`, `경보 받은 배의 ${pct(h.top5.precision)}가 실제로 12시간 넘게 기다렸습니다(무작위로 고르면 ${pct(tc.base_rate)})`);
  card(f3(h.pr_auc), `24시간 전 PR-AUC(95% 구간 ${f3(h.pr_auc_ci[0])}~${f3(h.pr_auc_ci[1])}) · 무작위 ${f3(tc.base_rate)} · ROC-AUC ${f3(h.roc_auc)}`);
  card(`${tc.long_waits.toLocaleString("ko-KR")}척`, `시험 기간 신항 컨테이너선 ${tc.voyages.toLocaleString("ko-KR")}항차 중 12시간 넘게 기다린 배(에피소드 ${tc.episodes}개)`);
  $("b-kpi-note").textContent = `상위 5%는 시험 기간 예측값 분포의 상위 5%입니다(사후 기준). 검증 기간에서 미리 정한 문턱으로는 경보 ${pct(h.valid_f1.alarm_rate)}, 정밀도 ${pct(h.valid_f1.precision)}, 재현율 ${pct(h.valid_f1.recall)}입니다.`;
  const p = d.periods_label;
  const fr = d.first_run;
  const bp = $("b-period");
  bp.replaceChildren();
  [["학습", p.train], ["검증", p.valid], ["시험", p.test]].forEach(([k, v], i) => {
    if (i) bp.append(" · ");
    el("span", { class: "b-nw" }, bp, `${k} ${v}`);
  });
  bp.append(`. 시험 기간은 모형을 만들 때 보지 않았고, 검증 기간에서 고른 설정을 학습+검증 기간으로 다시 맞춰 계산했습니다. 시험 뒤 누설을 더 엄격하게 고친 1건이 있어 시험 기간을 두 번 계산했습니다(첫 계산 24시간 전 PR-AUC ${f3(fr?.pr_auc)}, 두 결과 모두 프로토콜에 기록).`);
}

function bssSentence(d) {
  const raw = d.bss_raw;
  const reached = d.bss_reached_leads || [];
  const under = LEADS.filter((L) => !reached.includes(L));
  const fmt = (L) => `${leadLabel(L)}(${sgn(raw[L], 4)})`;
  let body;
  if (!under.length) body = "모든 리드에서 넘었습니다";
  else if (!reached.length) body = `어느 리드에서도 넘지 못했습니다(${under.map(fmt).join(", ")})`;
  else body = `${reached.map(fmt).join("·")}에서 넘었고, ${under.map(fmt).join("·")}은 못 미쳤습니다`;
  const tail = reached.includes("2") || reached.includes("0") ? " 2시간 전·도착 순간 값에는 라벨 정의 효과가 섞여 있습니다." : "";
  return `로드맵 ① 통과 기준(Brier 기술점수 ≥ 0.1, 반올림 전 값): 하이브리드는 ${body}.${tail} 비교 기준은 터미널별 기후값입니다.`;
}

function leadChart(d) {
  const xs = LEADS.map((_, i) => i);
  const ys = SERIES.flatMap((s) => LEADS.map((L) => d.lead[L][s.k]?.pr_auc ?? 0));
  const yMax = Math.max(...ys, ...LEADS.map((L) => d.lead[L].R3_logit?.pr_auc_ci?.[1] ?? 0)) * 1.08;
  const ci = LEADS.map((L) => d.lead[L].R3_logit.pr_auc_ci);
  legend($("lead-legend"), [
    ...SERIES.map((s) => ({ label: s.k === "S2_gbm" ? "통계 GBM(R-Delay 부품 없음)" : d.names[s.k], color: s.color, kind: s.dash ? "dash" : undefined })),
    { label: "하이브리드 95% 구간", color: "var(--s1)", kind: "band" },
    { label: `무작위(기저율 ${pct(d.test_counts.base_rate)})`, kind: "rule" },
  ]);
  timeChart($("lead-chart"), {
    height: 250, watermark: false, aria: "도착 몇 시간 전 판단인지에 따른 예측기별 PR-AUC",
    x: { domain: [-0.2, LEADS.length - 0.8], ticks: xs, format: (v) => leadLabel(LEADS[Math.round(v)]) },
    y: { domain: [0, yMax], ticks: niceTicks(0, yMax, 4), format: (v) => v.toFixed(2) },
    bands: [{ lo: xs.map((x, i) => [x, ci[i]?.[0]]), hi: xs.map((x, i) => [x, ci[i]?.[1]]), color: "var(--s1)", opacity: 0.12 }],
    refLines: [{ y: d.test_counts.base_rate }],
    lines: SERIES.map((s) => ({ pts: xs.map((x, i) => [x, d.lead[LEADS[i]][s.k]?.pr_auc]), color: s.color, width: s.width, dash: s.dash })),
    tooltip: (x) => SERIES.map((s) => ({ name: SHORT[s.k], value: f3(d.lead[LEADS[Math.round(x)]][s.k]?.pr_auc), color: s.color })),
  });
  const keys = ["S0", "R1", "S2_logit", "S2_gbm", "R3_logit", "R3_gbm"];
  table("lead-table", ["예측기", ...LEADS.map((L) => (L === "0" ? "도착*" : L === "2" ? "2h 전*" : `${L}h 전`)), "ROC 24h"], keys.map((k) => ({
    best: k === "R3_logit",
    cells: [SHORT[k], ...LEADS.map((L) => f3(d.lead[L][k]?.pr_auc)), f3(d.lead["24"][k]?.roc_auc)],
  })), { caption: "PR-AUC(시험 기간). 숫자가 굵은 줄 = 시험 전에 정한 최종 모형" });
  const h = d.headline;
  const g24 = d.lead["24"];
  const gbmSame = d.facts?.s2gbm_ge_r3gbm;
  $("lead-note").textContent = `* 도착 순간·2시간 전 값은 라벨 정의 때문에 일부가 저절로 맞습니다(정박지를 거치지 않은 배는 도착 시각이 곧 접안 시각이라 그때 빈 선석이 있게 마련). 주 결과는 24·12·6시간 전입니다. `
    + `하이브리드 = 이력 특징(같은 선박·같은 요일 슬롯) + 선박 크기 + R-Delay 선석 대기열 확률 + 번짐 지수 상태를 함께 쓰는 로지스틱 모형이고, 시험 전에 최종 모형으로 정했습니다. `
    + `24시간 전 Brier 기술점수 ${sgn(h.bss)}(95% ${sgn(h.bss_ci[0])}~${sgn(h.bss_ci[1])}). ${bssSentence(d)} `
    + (gbmSame ? `R-Delay 부품 없이 같은 이력 특징만 쓴 통계 GBM(${f3(g24.S2_gbm.pr_auc)})이 R-Delay GBM(${f3(g24.R3_gbm.pr_auc)})과 같거나 높았습니다. 하루 전 예측력은 이력 특징에서 나옵니다.`
      : `R-Delay GBM ${f3(g24.R3_gbm.pr_auc)}, 통계 GBM ${f3(g24.S2_gbm.pr_auc)}.`);
}

function why(d) {
  const ab = d.ablation_posthoc;
  barList($("why-chart"), ab.groups.map((g) => ({ label: g.group, value: Math.max(0, g.drop), text: chg(g.drop), color: g.drop > 0.005 ? "var(--s1)" : "var(--axis)" })),
    { labelWidth: 190, aria: "요인 묶음을 뺐을 때 PR-AUC 변화(막대 = 떨어지는 폭)" });
  const F = d.facts;
  const top = F.top3;
  const mech = F.mech_small
    ? `공개 자료만으로는 선석 대기열과 번짐 지수가 더해 주는 하루 전 예측력이 거의 없었습니다(하나씩 빼 보면 PR-AUC 변화: 선석 대기열 ${chg(F.mech_parts.queue)}, 번짐 지수 ${chg(F.mech_parts.sis)}).`
    : `선석 대기열과 번짐 지수는 하루 전 PR-AUC를 ${f3(F.mech_drop)} 더했습니다.`;
  const dir = F.history_positive && F.small_ship_riskier
    ? "같은 배가 지난번에도 오래 기다렸을수록, 같은 요일·시간대에 도착하는 항로가 최근 자주 기다렸을수록, 작은 배(피더선)일수록 위험이 큽니다. " : "";
  const ref = d.main_vessel_24_baseline_pr_auc != null
    ? ` 주 분석의 선박 단위 참고 표(같은 가정, 이력 특징 없음)에서 도착 24시간 전 기준선은 ${f3(d.main_vessel_24_baseline_pr_auc)}였습니다. 차이의 대부분은 이 이력 특징에서 나옵니다.` : "";
  $("why-text").textContent = `하루 전 예측력은 주로 ${top.join(", ")}에서 나왔습니다(전체 PR-AUC ${f3(ab.base_pr_auc)}). ${dir}${mech}${ref}`;
}

function method(d) {
  const ul = $("method-list");
  ul.replaceChildren();
  const li = (t) => el("li", {}, ul, t);
  const s = d.data;
  li(`정답: 해양수산부 PORT-MIS 관제정보로 부산신항 컨테이너선 ${s.voyages.toLocaleString("ko-KR")}항차(${s.period[0]}~${s.period[1]})의 정박지 대기(정박지 도착 → 신항 선석 첫 접안)를 쟀고, ${d.rule}에 맞춰 12시간 초과를 장기 대기로 봤습니다(${s.long_waits}척, ${pct(s.long_wait_share)}). 168시간을 넘는 ${s.excluded_over_cap}건은 혼잡이 아닌 장기 체류로 보고 뺐습니다${d.sensitivity ? `(상한 ${d.sensitivity.cap_h}시간으로 바꿔도 하이브리드 24시간 전 PR-AUC ${f3(d.sensitivity.t2_24_r3_logit.pr_auc)})` : ""}.`);
  li("특징은 판단 시각까지 알 수 있는 것만 썼습니다: 터미널별 선석 점유·대기열, 신항 전체 대기, 기상청 ASOS(부산·창원)·거제도 부이, 태풍 경로(분석 3시간 뒤부터), 한국도로공사 1시간 구간속도, 같은 선박·같은 요일 슬롯의 이력(결과가 확정된 항차만). 대상 선박의 도착 시각과 갈 터미널은 미리 안다고 가정했습니다(낙관적).");
  li("R-Delay 구성 요소: (1) 터미널별 선석 대기열 몬테카를로(학습 기간 실제 체류시간 분포), (2) 해상·육상 2층 물동량 보정 SIS 입자필터(엔진과 같은 함수, 학습 기간 우도로 모수 선택), (3) 학습형 모듈(로지스틱 회귀, 이력·선박 크기·기상).");
  li("비교 기준: 터미널별 평균(기후값), 현재 터미널 상태, 통계 기준선(같은 이력 특징의 로지스틱·GBM, R-Delay 부품 없음). 지표는 PR-AUC(주), ROC-AUC, Brier 기술점수, 주 단위 블록 부트스트랩 95% 구간.");
  li(d.notice);
  $("b-sources").textContent = `출처: ${d.sources.join(" · ")}. 생성 ${d.generated}${d.commit ? ` · 커밋 ${d.commit}` : ""}.`;
  const fa = d.free_at_arrival;
  if (fa) $("lim-queue").textContent = `정박지에서 기다린 배의 ${pct(fa.anchored_with_free_berth, 0)}는 도착 순간 그 터미널에 빈 선석(학습 기간 선석 수 기준)이 있었습니다. 터미널은 선석을 먼저 온 순서가 아니라 선석 계획(창구)대로 배정하므로, 터미널 선석 계획(ETB)·선사 ETA가 연동되어야 대기열 모형이 제 몫을 할 수 있습니다.`;
}

async function main() {
  let d;
  try {
    const res = await fetch("data/backtest_ship.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(res.status);
    d = await res.json();
  } catch (e) {
    for (const id of ["b-kpis", "lead-table"]) {
      const n = $(id);
      if (n) n.replaceChildren(el("p", { class: "m-error" }, null, "결과 파일(data/backtest_ship.json)을 불러오지 못했습니다. 인터넷 연결을 확인하고 새로 고침하세요."));
    }
    return;
  }
  kpis(d);
  leadChart(d);
  why(d);
  method(d);
  let timer;
  window.addEventListener("resize", () => {
    clearTimeout(timer);
    timer = setTimeout(() => { leadChart(d); why(d); }, 200);
  });
}

main();
