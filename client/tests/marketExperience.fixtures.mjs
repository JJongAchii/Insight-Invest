// Synthetic UI fixtures. These values are not observations or research results.
export const date = "2026-09-07";
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
const series = (name, value) => ({
  name,
  latest: value,
  data: [
    { date: "2026-08-01", value: value * 0.98 },
    { date, value },
  ],
});
export const macro = {
  usdkrw: series("달러/원 환율", 1324.5),
  base_rate: series("한국 기준금리", 2.5),
  ktb_3y: series("국고채 3년", 2.7),
  ktb_10y: series("국고채 10년", 2.9),
  cpi_yoy: series("소비자물가 전년비", 2.1),
  cli_kor: series("한국 경기선행지수", 100.2),
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
const article = {
  url: "https://example.com/news",
  source: "UI 검증용 뉴스",
  published_at: `${date}T08:00:00+09:00`,
  cluster_count: 4,
  sources: ["fixture"],
  related_topics: ["금리", "환율"],
};
export const news = {
  active: true,
  as_of: `${date}T09:00:00+09:00`,
  edition: "morning",
  sections: {
    economy: [
      {
        ...article,
        title: "금리와 환율의 변화, 이번 주 경제 지표에서 확인할 것",
        why: "정책 기대의 변화가 채권과 외환 시장에 어떻게 나타나는지 살펴봅니다.",
      },
      {
        ...article,
        url: "https://example.com/news/2",
        title: "주요 기업의 실적 발표를 앞두고 확인할 산업별 흐름",
        why: "매출과 이익 전망의 변화가 어느 업종에 집중되는지 확인할 수 있습니다.",
      },
    ],
    general: [{ ...article, title: "종합 뉴스 테스트 항목" }],
  },
};
export function fixtureFor(path, params, mode) {
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
  if (path === "news/briefing")
    return mode === "empty" ? { active: false } : news;
  if (path === "news")
    return {
      articles:
        mode === "empty"
          ? []
          : [
              {
                ...article,
                id: "live",
                title: "최신 경제 헤드라인 테스트",
                summary: null,
              },
            ],
      fetched_at: date,
    };
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
