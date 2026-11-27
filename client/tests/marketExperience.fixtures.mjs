// Synthetic UI fixtures. These values are not observations or research results.
import { readFileSync } from "node:fs";

export const date = "2026-09-07";
// The map is computed from a real 2026-11-27 11:05 KRX snapshot and dated to the fixture day.
export const marketMap = JSON.parse(readFileSync(new URL("./fixtures/market_map_1105.json", import.meta.url))).map;
const wireSource = { title: "코스닥 매수 사이드카 발동", publisher: "시황통신", url: "https://example.org/sidecar",
  published_at: `${date}T10:25:00+09:00` };
export const note = {
  id: `note/${date}/morning`, kind: "scheduled", slot: "morning", trigger: null,
  observed_at: `${date}T11:05:00+09:00`, published_at: `${date}T11:09:00+09:00`,
  headline: "코스닥 5%대 급등, 10:22 매수 사이드카", since_last: "코스닥은 개장 노트 뒤 +3.0%에서 +5.7%로 상승폭을 키웠다.",
  watch: ["사이드카 뒤 상승폭이 유지되는지"],
  drivers: [
    { text: "상승 1,461개·하락 219개로 시장 전체가 올랐다", label: "데이터", sources: [] },
    { text: "10시 22분 코스닥 매수 사이드카가 발동됐다", label: "보도", sources: [wireSource] },
    { text: "52주 최저 뒤 저가 매수가 들어온 것으로 보인다", label: "해석", sources: [] },
  ],
  stocks: [{ name: "레인보우로보틱스", ticker: "277810", chg_pct: 12.21, reason: "로봇주가 함께 상한가에 오르며 테마 매수가 몰렸을 가능성",
    label: "해석", sources: [] }],
  sources: [wireSource],
};
export const sinceNote = { from: `${date}T11:05:00+09:00`, to: `${date}T11:35:00+09:00`,
  indices: { KOSPI: { from: 1.77, to: 1.9, delta: 0.13 }, KOSDAQ: { from: 5.69, to: 6.4, delta: 0.71 } },
  new_limit_up: [{ ticker: "277810", name: "레인보우로보틱스" }], new_limit_down: [], new_leaders: [], new_spikes: [] };
const evidence = (key, title, detail, tone = "neutral", link = "/insight") => ({
  key,
  title,
  detail,
  tone,
  link,
  as_of: date,
  changed: true,
});
export const overview = {
  generated_at: `${date}T20:00:00+09:00`,
  tone: "mixed",
  tone_label: "엇갈림",
  horizons: [
    {
      key: "intraday",
      label: "장중",
      window: "당일 스냅샷",
      tone: "positive",
      summary: "지수 상승과 종목 참여가 함께 나타납니다.",
      evidence: [
        evidence(
          "intraday",
          "지수와 시장 참여의 동반 상승",
          "장중 지연 스냅샷에서 지수 방향과 상승 종목 수를 확인합니다.",
          "positive",
          "/insight?tab=intraday",
        ),
      ],
    },
    {
      key: "tactical",
      label: "전술",
      window: "최근 20거래일",
      tone: "neutral",
      summary: "수급과 시장폭이 서로 다른 방향을 가리킵니다.",
      evidence: [
        evidence(
          "flow",
          "외국인 매수세와 기관 매도세",
          "주체별 자금 흐름을 비교하고 시장 전반의 확산 여부를 살펴봅니다.",
        ),
        evidence(
          "breadth",
          "20일 이동평균 위 종목 비중 확대",
          "상승이 일부 대형주에만 집중되는지 개별 종목의 참여를 확인합니다.",
        ),
        evidence(
          "extra",
          "추가 관측 근거",
          "숨겨진 근거도 키보드와 터치로 읽을 수 있어야 합니다.",
        ),
      ],
    },
    {
      key: "structural",
      label: "구조",
      window: "월간 경기 지표",
      tone: "negative",
      summary: "성장과 물가의 발표 시차를 함께 확인해야 합니다.",
      evidence: [
        evidence(
          "phase",
          "성장 둔화와 물가 압력",
          "서로 다른 발표 시점을 가진 거시 지표의 기준월을 비교합니다.",
          "negative",
          "/regime",
        ),
        evidence(
          "gauge",
          "시장 위험 압력 관측",
          "금리차, 크레딧, 변동성과 고용의 변화가 반영됩니다.",
          "neutral",
          "/regime",
        ),
      ],
    },
  ],
  conflicts: [
    "지수 상승과 외국인 수급의 방향이 다릅니다.",
    "KR 시장폭과 월간 경기 지표의 기준일이 다릅니다.",
  ],
  data_status: [],
  calculation_contracts: [],
  method: "테스트용 관측 근거입니다. 시간축별 지표를 분리해 제공합니다.",
};
overview.evidence = overview.horizons.flatMap((horizon) => horizon.evidence);
export const intraday = {
  active: true,
  is_open: false,
  trade_date: date,
  as_of: `${date} 15:30`,
  indices: [
    { key: "KOSPI", level: 2701.24, chg_pct: 0.71, sparkline: [] },
    { key: "KOSDAQ", level: 812.56, chg_pct: -0.24, sparkline: [] },
  ],
  breadth: { advancers: 1400, decliners: 980, unchanged: 120 },
};
const series = (name, value, asOf = "2026-09-03", frequency = "daily", source = "ECOS") => ({
  name,
  latest: value,
  as_of: asOf,
  frequency,
  source,
  data: [
    { date: "2026-07-01", value: value * 0.98 },
    // Weekly chart labels must never become the latest observation date.
    { date: frequency === "monthly" ? `${asOf}-01` : "2026-09-04", value },
  ],
});
export const macro = {
  usdkrw: series("달러/원 환율", 1324.5),
  base_rate: series("한국 기준금리", 2.5, "2026-09-02"),
  ktb_3y: series("국고채 3년", 2.7),
  ktb_10y: series("국고채 10년", 2.9),
  cpi_yoy: series("소비자물가 전년비", 2.1, "2026-08", "monthly"),
  cli_kor: series("한국 경기선행지수", 100.2, "2026-07", "monthly", "OECD"),
};
export const researchItems = [
  [
    "시장 변동성의 구조와 자산 간 연결을 읽는 방법",
    "시장 간 관계가 시기에 따라 어떻게 달라지는지, 관측 데이터와 검증 방법을 함께 살펴보는 자료입니다.",
  ],
  [
    "경제 지표의 발표 시차가 분석에 미치는 영향",
    "발표 시점과 관측 시점을 구분해 경제 데이터의 변화를 해석하는 연구입니다.",
  ],
  [
    "주식 시장의 업종 순환과 자금 흐름",
    "산업별 성과와 투자자 수급을 연결할 때 확인해야 할 가정과 한계를 정리합니다.",
  ],
].map(([title, summary], index) => ({
  entry_id: `fixture-${index}`,
  source_id: "fixture",
  source_name: "UI 검증용 자료",
  title,
  summary,
  authors: ["테스트 저자"],
  url: "https://example.com/research",
  published_at: date,
  discovered_at: date,
  record_schema_version: 3,
  quality_profile: "strict",
  research_lane: "core",
  relevance_reason: "",
  relevance_terms: ["시장 구조", "거시경제"],
  notification_eligible: true,
  item_type: "evidence_update",
  content_provenance: "full_body",
  evidence_dimensions: ["method", "data"],
  evidence_excerpts: {
    method: ["방법의 가정과 적용 범위를 확인하는 테스트 발췌문입니다."],
    data: ["발표 시점과 관측 시점을 구분한 테스트 자료입니다."],
  },
  is_read: false,
  is_saved: false,
}));
const article = (id, time, fields) => ({
  id, kind: "news", origin: "reporter", status: "reported", category: null, priority: "major", update: false,
  attribution: null, summary: "", significance: "", change: "", interpretation: "", watch: "", body: null,
  sources: [], followups: [], licenses: [], published_at: time, publisher: null,
  ...fields, title: fields.title ?? fields.headline,
});
// 최신순. 어제 글 하나는 분류·요약 없이 발행 원문만 가진 판본이다.
export const deskNews = [
  article("firm", `${date}T10:30:00+09:00`, {
    kind: "filing", origin: "desk", status: "analysis", priority: null, headline: "단일기업 공급계약", publisher: "금융감독원 DART",
    summary: "공급 조건이 공시됐습니다.", interpretation: "기업 매출에 영향을 줍니다.",
  }),
  article("report", `${date}T10:15:00+09:00`, {
    category: "경제", headline: "시험 기관: 한은, 기준금리 동결", title: "한은, 기준금리 연 2.50%로 동결", publisher: "시험 기관",
    summary: "확인된 뉴스 본문",
    significance: "대출금리와 환율에 영향을 줍니다.",
    sources: [{ title: "", url: "https://example.com/announcement", publisher: "시험 기관", published_at: `${date}T10:00:00+09:00` }],
    licenses: [{ url: "https://example.com/licence", name: "공공누리 제1유형" }],
  }),
  // 장중 노트가 근거로 인용한 시황 원문. 지도의 레인보우로보틱스 옆에 '기사 1'로 이어진다.
  article("market", `${date}T09:50:00+09:00`, {
    origin: "desk", category: "시장", headline: "레인보우로보틱스, 로봇주 강세에 12% 급등", publisher: "시황통신",
    summary: "11:09 장중 노트가 근거로 인용한 원문입니다.",
    sources: [{ title: "레인보우로보틱스, 로봇주 강세에 12% 급등", url: "https://example.org/robot", publisher: "시황통신",
      published_at: `${date}T09:50:00+09:00` }],
  }),
  article("urgent", `${date}T09:40:00+09:00`, {
    category: "세계정세", priority: "urgent", update: true, attribution: "시험 통신", headline: "해협 통항 재개", publisher: "시험 통신",
    summary: "통항이 다시 시작됐습니다.", change: "봉쇄 해제가 공식 확인됐습니다.",
  }),
  article("old", "2026-09-06T18:00:00+09:00", {
    priority: null, headline: "이전 소식", body: "*[주요] 앞서 발행한 본문*\n<https://example.com/source|공식 발표>",
  }),
];
/** `seen`은 뉴스를 마지막으로 본 시각이다. 화면이 기록하면 테스트가 다음 응답에 넘겨준다. */
export function fixtureFor(path, params, mode, seen) {
  if (path === "ipo") return {
    status: { next_session: date, calendar: [{ planned_listing_date: date, decision_missing: mode === "stale" }] },
    open: [], history: [],
  };
  if (path === "market-desk") {
    const notes = mode === "empty" || mode === "company" ? [] : [note];
    const desk = { map: mode === "empty" || mode === "company" ? { state: "awaiting" } : { state: "latest", ...marketMap },
      notes, since_note: notes.length ? sinceNote : null };
    if (mode === "empty") return { ...desk, state: "awaiting", today: date, session: null, session_state: "awaiting", policy_coverage: [], board: null };
    const stamp = `${date}T10:15:00+09:00`;
    const filing = { id: "firm", origin: "desk", kind: "filing", status: "analysis", headline: "단일기업 공급계약",
      fact: "공급 조건이 공시됐습니다.", observation: "", interpretation: "기업 매출에 영향을 줍니다.", watch: "",
      published_at: `${date}T10:30:00+09:00`, observed_at: null, sources: [] };
    const wire = { title: "코스피, 외국인 매도세에 장중 반락", publisher: "시황통신", published_at: `${date}T09:23:00+09:00`, url: "https://example.org/index-report" };
    return { ...desk, state: mode === "stale" ? "stale" : "ready", today: date,
      lead: mode === "lead" ? { phase: "close", trade_date: date, as_of: `${date}T16:05:00+09:00`,
        cutoff: `${date}T16:15:00+09:00`, published_at: `${date}T16:18:00+09:00`, close_at: `${date}T15:30:00+09:00`,
        headline: "기관이 지킨 반등, 외국인은 매도 전환", reading: { text: "전일 낙폭에서 회복한 폭은 제한적입니다.", sources: [wire] },
        qualification: { text: "마감 집계에서 기관과 외국인의 수급이 갈렸습니다.", sources: [wire] },
        watch: "다음 거래일 외국인 수급을 확인합니다.", comparison: { index: "코스피", previous_points: -100, current_points: 10, share_pct: 10 } } : null,
      session: mode === "company" ? null : { observed_at: stamp, headline: "코스피는 상승, 코스닥은 하락", market: "두 시장의 전일 대비 방향이 갈렸습니다.",
        sectors: "업종 등락률의 격차를 확인했습니다.", watch: "업종 간 차이가 이어지는지 확인합니다." },
      session_state: mode === "company" ? "awaiting" : "latest", policy_coverage: [], board: {
      checked_at: stamp, market_at: stamp, filings_at: stamp, monitoring: true,
      market_reports: [wire, { ...wire, title: "관측 이후 보도", published_at: stamp, url: "https://example.org/later" }],
      issues: mode === "company" ? [filing] : [filing,
        { id: "prior", origin: "desk", kind: "move", status: "analysis", headline: "지난 거래일의 지수 배경",
          fact: "지난 거래일의 변동", observation: "", interpretation: "이전 거래일의 원인", watch: "",
          published_at: stamp, observed_at: "2026-09-04T14:10:00+09:00", sources: [wire] },
        { id: "move", origin: "desk", kind: "move", status: "unconfirmed", headline: "코스피 장중 변화",
        fact: "직전 관측 대비 변화가 감지됐습니다.", observation: "", interpretation: "", watch: "",
        published_at: stamp, observed_at: stamp, sources: [] },
        ...(mode === "explained" ? [{ id: "cause", origin: "desk", kind: "move", status: "analysis", headline: "수급 보도로 확인한 코스피 반락",
          fact: "시장 보도가 외국인 순매도를 확인했습니다.", observation: "10시 관측", interpretation: "해당 변동 구간의 설명", watch: "",
          published_at: stamp, observed_at: stamp, sources: [wire] }] : []),
        { id: "report", origin: "reporter", kind: "news", status: "reported", headline: "한은, 기준금리 동결",
          fact: "확인된 뉴스 본문", observation: "", interpretation: "", watch: "",
          published_at: stamp, observed_at: null, sources: [] }],
      briefings: [{ id: "morning", kind: "am", as_of: `${date}T07:00:00+09:00`,
        published_at: `${date}T07:30:00+09:00`, body: "아침 발행본 요약\n\n주요 숫자\n\n<https://example.com/source|공식 발표>" }],
    } };
  }
  if (path === "overview")
    return mode === "empty"
      ? { ...overview, horizons: [], evidence: [], conflicts: [] }
      : overview;
  if (path === "intraday/market")
    return mode === "empty"
      ? { active: false }
      : mode === "stale"
        ? { ...intraday, trade_date: "2026-09-01", as_of: "2026-09-01 15:30" }
        : intraday;
  if (path === "insight/index")
    return {
      rows:
        mode === "empty"
          ? []
          : ["KOSPI", "KOSDAQ"].flatMap((index) => [
              { index, date: "2026-09-03", close: 2600 },
              {
                index,
                date: mode === "stale" ? date : "2026-09-04",
                close: 2626,
              },
            ]),
    };
  if (path === "regime/kr") return mode === "empty" ? {} : macro;
  if (path === "regime/info")
    return ["USRECD", "T10Y2Y", "UNRATE", "PAYEMS", "FEDFUNDS", "CPIAUCSL"].map(
      (fred) => ({ macro_id: fred, fred, description: fred }),
    );
  if (path === "regime/data")
    return mode === "empty"
      ? []
      : [
          { macro_id: "T10Y2Y", base_date: date, value: 0.4 },
          { macro_id: "UNRATE", base_date: "2026-08-01", value: 4.1 },
          { macro_id: "FEDFUNDS", base_date: "2026-08-01", value: 4.25 },
          { macro_id: "CPIAUCSL", base_date: "2026-08-01", value: 0.021 },
        ];
  if (path === "regime/phase")
    return {
      current: {
        phase: "Goldilocks",
        growth_dir: "up",
        inflation_dir: "down",
        as_of: "2026-07",
        cli: 100.2,
        cli_delta: 0.1,
        cpi_yoy: 2.1,
        cpi_yoy_delta: -0.1,
      },
      history: [],
    };
  if (path === "regime/gauge")
    return { score: 45, as_of: date, components: [] };
  if (path.startsWith("research/status") || path.startsWith("research/seen"))
    return {
      initialized: true,
      unseen: 3,
      generated_at: date,
      seen_through: null,
    };
  if (path === "research")
    return {
      schema_version: 1,
      generated_at: date,
      total: 3,
      unread: 3,
      read: 0,
      saved: 0,
      view: "all",
      lane: params.get("lane") || "core",
      lane_counts: { core: 3, discovery: 3, context: 0, all: 6 },
      sources: [
        { source_id: "fixture", source_name: "UI 검증용 자료", count: 3 },
      ],
      items:
        mode === "empty"
          ? []
          : researchItems.map((item) => ({
              ...item,
              research_lane: params.get("lane") || "core",
            })),
    };
  if (path.startsWith("market-desk/news")) {
    const items = mode === "empty" ? [] : mode === "company" ? deskNews.slice(0, 1) : deskNews;
    const seenThrough = items.length ? seen ?? "2026-09-06T23:00:00+09:00" : null;
    const unseen = items.filter(item => Date.parse(item.published_at) > Date.parse(seenThrough)).length;
    if (path !== "market-desk/news")
      return { unseen, latest_at: items[0]?.published_at ?? null, seen_through: seenThrough };
    return { state: items.length ? "ready" : "awaiting", checked_at: items.length ? `${date}T10:35:00+09:00` : null,
      items, seen_through: seenThrough, unseen };
  }
  if (path === "actions")
    return { items: [], counts: { badge: 4, actionable: 4 } };
  if (path === "insight/spotlight") return { active: false, groups: [] };
  if (path === "meta") return [];
  if (path === "insight/flows/top") {
    const row = {
      rank: 1,
      ticker: "005930",
      name:
        params.get("investor") === "inst"
          ? "기관 수급 예시 기업"
          : "외국인 수급 예시 기업",
      market: "KOSPI",
      net_value: 13000000000,
      chg_pct: 1.2,
    };
    return {
      as_of: date,
      buys: mode === "empty" ? [] : [row],
      sells:
        mode === "empty"
          ? []
          : [{ ...row, name: "순매도 예시 기업", net_value: -5000000000 }],
    };
  }
  if (path === "insight/breadth" || path === "insight/flows/market")
    return { as_of: date, rows: [] };
  return {};
}
