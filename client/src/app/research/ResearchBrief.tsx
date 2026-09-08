import type { ResearchEntry } from "@/state/api";

const POINTS = [
  ["question", "다루는 질문"],
  ["method_data", "방법·데이터"],
  ["finding", "저자가 보고한 결과"],
  ["why_read", "읽어볼 이유"],
  ["limitation", "원문이 밝힌 한계"],
] as const;

export default function ResearchBrief({ item }: { item: ResearchEntry }) {
  const analysis = item.analysis;
  if (!analysis) {
    return (
      <div className="mt-3 space-y-2">
        {item.record_schema_version === 4 && (
          <p className="text-xs text-ink-muted">
            원문 발췌 · {item.analysis_status === "held" ? "요약 확인 필요" : item.analysis_status === "not_requested" ? "요약 대상 아님" : item.analysis_status === "retry_pending" ? "요약 재시도 대기" : "한국어 요약 준비 중"}
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
        AI 읽기 요약 · 원문 {analysis.analyzed_chars.toLocaleString("ko-KR")}자 분석
      </p>
      <dl className="space-y-3">
        {POINTS.map(([field, label]) => {
          const point = analysis.brief[field];
          if (!point) return null;
          return (
            <div key={field} className="grid gap-1 sm:grid-cols-[7.5rem_1fr] sm:gap-3">
              <dt className="text-xs font-medium leading-6 text-ink-muted">{label}</dt>
              <dd className="min-w-0 text-sm leading-6 text-ink-secondary">
                <p>{point.text_ko}</p>
                <details className="mt-1 text-xs text-ink-muted">
                  <summary className="w-fit cursor-pointer rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary-400">
                    근거 문장 보기
                  </summary>
                  <blockquote className="mt-2 border-l-2 border-edge pl-3 leading-5" lang={/[가-힣]/.test(point.evidence) ? "ko" : "en"}>
                    {point.evidence}
                  </blockquote>
                </details>
              </dd>
            </div>
          );
        })}
      </dl>
      <div className="border-t border-edge pt-3 text-xs leading-5 text-ink-muted">
        <p><span className="font-medium text-ink-secondary">리서치 메모 · AI 해석</span> {analysis.brief.reviewer_note}</p>
        <p className="mt-1">원문 일부에 근거한 읽기 도움말입니다. 독립 재현·성과 검증 결과가 아닙니다.</p>
      </div>
    </div>
  );
}
