import type { ResearchEntry } from "@/state/api";

const POINTS = [
  ["question", "다루는 질문"],
  ["method_data", "방법·데이터"],
  ["finding", "저자의 설명·주장"],
  ["why_read", "읽어볼 이유"],
  ["limitation", "원문이 밝힌 한계"],
] as const;

export function hasReviewedBrief(item: ResearchEntry) {
  return !!item.analysis && item.analysis_status === "ready"
    && item.editorial_review_status === "accepted";
}

export default function ResearchBrief({ item }: { item: ResearchEntry }) {
  const analysis = item.analysis;
  if (!analysis || !hasReviewedBrief(item)) {
    const academic = item.quality_profile === "academic-discovery-v1";
    const status = academic
      ? item.original_access_status?.startsWith("verified_") && item.access_status !== "abstract_only"
        ? "공개 원문 확인 · 한국어 요약은 아직 제공하지 않습니다"
        : "초록 확인 · 원문 열람 가능 여부는 링크에서 확인해 주세요"
      : item.relevance_reason === "editorial_release_pending"
      ? "한국어 요약 기능 검증 중 · 원문은 읽을 수 있습니다"
      : item.editorial_review_status === "rejected"
      ? "요약 검수 보류 · 원문에서 확인해 주세요"
      : item.analysis_status === "held" ? "요약 확인 필요"
      : item.analysis_status === "not_requested" ? "요약 대상 아님"
      : item.analysis_status === "retry_pending" ? "요약 재시도 대기"
      : analysis ? "요약 원문 대조 중" : "한국어 요약 준비 중";
    return (
      <div className="mt-3 space-y-2">
        {item.record_schema_version === 4 && (
          <p className="text-xs text-ink-muted">
            {item.summary_kind === "publisher_description" ? "발행처 소개문"
              : item.content_provenance === "abstract" || item.summary_kind === "abstract_excerpt" ? "초록 발췌" : "원문 발췌"} · {status}
          </p>
        )}
        <p className="text-sm leading-6 text-ink-secondary">
          {item.summary || "공개 출처에 별도 요약이 없습니다. 원문에서 내용을 확인해 주세요."}
        </p>
      </div>
    );
  }
  return (
    <div className="mt-4 space-y-3">
      <p className="text-xs text-ink-muted">
        AI 읽기 요약 · 원문 대조 완료 · 원문 {analysis.analyzed_chars.toLocaleString("ko-KR")}자 분석
      </p>
      <dl className="space-y-3">
        {POINTS.map(([field, label]) => {
          const point = analysis.brief[field];
          if (!point) return null;
          const pointLabel = field !== "finding" ? label
            : analysis.brief.content_kind === "research" ? "저자가 보고한 결과"
            : analysis.brief.content_kind === "market_commentary" ? "저자의 전망·해석"
            : label;
          return (
            <div key={field} className="grid gap-1 sm:grid-cols-[7.5rem_1fr] sm:gap-3">
              <dt className="text-xs font-medium leading-6 text-ink-muted">{pointLabel}</dt>
              <dd className="min-w-0 text-sm leading-6 text-ink-secondary">
                <p>{point.text_ko}</p>
                <details className="mt-1 text-xs text-ink-muted">
                  <summary className="w-fit cursor-pointer rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary-400">
                    원문 근거 펼치기
                  </summary>
                  {(point.evidence_excerpts ?? [point.evidence]).map((excerpt, index) => (
                    <div key={index} className="mt-2">
                      {index > 0 && <p className="mb-1 pl-3 text-[11px]">중간 원문 생략 · 다음 근거</p>}
                      <blockquote className="break-words border-l-2 border-edge pl-3 leading-5" lang={/[가-힣]/.test(excerpt) ? "ko" : "en"}>
                        {excerpt}
                      </blockquote>
                    </div>
                  ))}
                </details>
              </dd>
            </div>
          );
        })}
      </dl>
      <div className="border-t border-edge pt-3 text-xs leading-5 text-ink-muted">
        <p><span className="font-medium text-ink-secondary">더 읽어볼 점 · AI 메모</span> {analysis.brief.reviewer_note}</p>
        <p className="mt-1">AI가 원문 일부와 요약을 대조한 읽기 도움말입니다. 오류가 남을 수 있으며, 독립 재현·성과 검증 결과가 아닙니다.</p>
      </div>
    </div>
  );
}
