"use client";

import Link from "next/link";

import ErrorState from "@/components/ui/ErrorState";
import LoadingState from "@/components/ui/LoadingState";
import {
  DataHealthLevel,
  EvidenceTone,
  OverviewTone,
  useFetchActionsQuery,
  useFetchOverviewQuery,
} from "@/state/api";
import styles from "./DecisionBrief.module.css";

const THESIS: Record<OverviewTone, { lead: string; accent: string }> = {
  risk_on: {
    lead: "시장 환경은 개선되고 있습니다.",
    accent: "내 자산의 예외는 따로 확인하세요.",
  },
  risk_off: {
    lead: "방어가 필요한 구간입니다.",
    accent: "노출과 판단 근거부터 다시 확인하세요.",
  },
  mixed: {
    lead: "단기 흐름은 움직였지만,",
    accent: "시간축별 신호는 아직 엇갈립니다.",
  },
};

const TONE_LABEL: Record<EvidenceTone, string> = {
  positive: "우호",
  negative: "경계",
  neutral: "중립",
};

const TONE_COLOR: Record<EvidenceTone, string> = {
  positive: "var(--gains)",
  negative: "var(--losses)",
  neutral: "var(--text-muted)",
};

const HEALTH_COLOR: Record<DataHealthLevel, string> = {
  ok: "var(--gains)",
  warn: "var(--warning)",
  error: "var(--losses)",
  unknown: "var(--text-muted)",
};

const severityColor = (severity: "high" | "medium" | "low") => {
  if (severity === "high") return "var(--losses)";
  if (severity === "medium") return "var(--primary)";
  return "var(--text-muted)";
};

const compactTimestamp = (value: string) =>
  value.slice(0, 16).replace("T", " ");

const BriefBoundary = ({
  failed = false,
  onRetry,
}: {
  failed?: boolean;
  onRetry?: () => void;
}) => (
  <section className={styles.workspace} aria-labelledby="decision-thesis">
    <header className={styles.hero}>
      <div className={styles.heroCopy}>
        <p className={styles.eyebrow}>Decision brief · {failed ? "interrupted" : "synchronizing"}</p>
        <h1 id="decision-thesis" className={styles.thesis}>
          오늘의 판단 근거를
          <br />
          <span className={styles.accent}>{failed ? "불러오지 못했습니다." : "시간축별로 정리하고 있습니다."}</span>
        </h1>
      </div>
      <div className={styles.heroMeta}>
        <p className={styles.generated}>{failed ? "REQUEST FAILED" : "EVIDENCE SYNC"}</p>
        <p className={styles.method}>가격·수급·경기 근거를 서로 다른 시간축으로 분리합니다.</p>
      </div>
    </header>
    <div className={`${styles.grid} ${styles.boundaryGrid}`}>
      <div className={styles.boundaryState}>
        {failed ? (
          <ErrorState message="판단 브리핑을 불러오지 못했습니다" onRetry={onRetry} />
        ) : (
          <LoadingState label="시간축별 판단 근거를 정리하는 중..." />
        )}
      </div>
    </div>
  </section>
);

/** 오늘의 시장 근거와 사용자 검토 큐를 한 의사결정 표면에 묶는다. */
export default function DecisionBrief() {
  const {
    data,
    isLoading,
    error,
    refetch,
  } = useFetchOverviewQuery();
  const {
    data: actionData,
    isLoading: actionsLoading,
    error: actionsError,
  } = useFetchActionsQuery({ horizonDays: 30 });

  if (error) {
    return <BriefBoundary failed onRetry={refetch} />;
  }

  if (isLoading || !data) {
    return <BriefBoundary />;
  }

  const thesis = THESIS[data.tone];
  const importantActions = (actionData?.items ?? []).filter(
    (item) => item.severity !== "low"
  );
  const reviewItems = (
    importantActions.length > 0 ? importantActions : actionData?.items ?? []
  ).slice(0, 3);
  const reviewCount = actionData?.counts.actionable ?? reviewItems.length;
  const unhealthyCount = data.data_status.filter(
    (item) => item.level !== "ok"
  ).length;

  return (
    <section className={styles.workspace} aria-labelledby="decision-thesis">
      <header className={styles.hero}>
        <div className={styles.heroCopy}>
          <p className={styles.eyebrow}>Decision brief · {data.tone_label}</p>
          <h1 id="decision-thesis" className={styles.thesis}>
            {thesis.lead}
            <br />
            <span className={styles.accent}>{thesis.accent}</span>
          </h1>
        </div>
        <div className={styles.heroMeta}>
          <time className={styles.generated} dateTime={data.generated_at}>
            Updated {compactTimestamp(data.generated_at)}
          </time>
          <p className={styles.method}>{data.method}</p>
        </div>
      </header>

      <div className={styles.grid}>
        <section className={styles.evidence} aria-labelledby="evidence-title">
          <header className={styles.panelHeader}>
            <div>
              <h2 id="evidence-title">시간축별 판단 근거</h2>
              <p>서로 다른 기간의 신호를 한 점수로 합산하지 않습니다.</p>
            </div>
            <Link href="/insight" className={styles.panelLink}>
              시장 전체 보기 →
            </Link>
          </header>

          <div className={styles.spine}>
            {data.horizons.map((horizon) => {
              const primaryEvidence = horizon.evidence[0];
              const additionalCount = Math.max(horizon.evidence.length - 1, 0);

              return (
                <article key={horizon.key} className={styles.evidenceRow}>
                  <div className={styles.horizon}>
                    <strong>{horizon.label}</strong>
                    <span>{horizon.window}</span>
                  </div>
                  <span className={styles.node} aria-hidden />
                  <div className={styles.evidenceCopy}>
                    {primaryEvidence ? (
                      <Link href={primaryEvidence.link} className={styles.evidenceTitle}>
                        {primaryEvidence.title}
                        {primaryEvidence.changed && (
                          <span className={styles.changed}>변화</span>
                        )}
                      </Link>
                    ) : (
                      <span className={styles.evidenceTitle}>{horizon.summary}</span>
                    )}
                    <p>
                      {primaryEvidence?.detail ?? "이 시간축에서 사용할 수 있는 근거가 없습니다."}
                    </p>
                  </div>
                  <div className={styles.evidenceMeta}>
                    <span className={styles.tone}>
                      <span
                        className={styles.toneDot}
                        style={{ backgroundColor: TONE_COLOR[horizon.tone] }}
                        aria-hidden
                      />
                      {TONE_LABEL[horizon.tone]}
                    </span>
                    <small>
                      {horizon.summary}
                      {additionalCount > 0 && <><br />추가 근거 {additionalCount}개</>}
                    </small>
                  </div>
                </article>
              );
            })}
          </div>

          {data.conflicts.length > 0 && (
            <div className={styles.conflict}>
              <strong>엇갈림</strong>
              <p>{data.conflicts[0]}</p>
            </div>
          )}

          <Link href="/data-trust" className={styles.dataHealth}>
            <strong>데이터 신뢰도</strong>
            {data.data_status.length === 0 ? (
              <span>상태표 미발행</span>
            ) : (
              data.data_status.slice(0, 4).map((item) => (
                <span key={item.dataset} className={styles.healthItem}>
                  <span
                    className={styles.healthDot}
                    style={{ backgroundColor: HEALTH_COLOR[item.level] }}
                    aria-hidden
                  />
                  {item.label} {item.as_of?.slice(0, 10) ?? item.level}
                </span>
              ))
            )}
            {unhealthyCount > 0 && <span>{unhealthyCount}개 확인 필요</span>}
          </Link>
        </section>

        <section className={styles.review} aria-labelledby="review-title">
          <header className={styles.panelHeader}>
            <div>
              <h2 id="review-title">지금 검토할 일</h2>
              <p>내 자산과 연결된 중요한 항목부터 표시합니다.</p>
            </div>
            <div className={styles.count} aria-label={`검토할 항목 ${reviewCount}개`}>
              <strong>{reviewCount}</strong>
              <span>건</span>
            </div>
          </header>

          {actionsLoading ? (
            <LoadingState label="검토할 항목을 정리하는 중..." className="py-10" />
          ) : actionsError ? (
            <p className={styles.emptyReview}>검토 큐를 불러오지 못했습니다.</p>
          ) : reviewItems.length === 0 ? (
            <p className={styles.emptyReview}>
              지금 새로 확인할 중요 항목이 없습니다.
            </p>
          ) : (
            <div className={styles.reviewList}>
              {reviewItems.map((item) => (
                <Link key={item.event_id} href={item.link} className={styles.reviewItem}>
                  <div className={styles.reviewMeta}>
                    <span
                      className={styles.severity}
                      style={{ backgroundColor: severityColor(item.severity) }}
                      aria-hidden
                    />
                    <span>{item.category}</span>
                    <span>·</span>
                    <span>{item.ticker ?? item.scope ?? item.event_status ?? "확인"}</span>
                  </div>
                  <h3>{item.title}</h3>
                  <p>{item.detail}</p>
                </Link>
              ))}
            </div>
          )}

          <Link href="/actions" className={styles.primaryAction}>
            검토 시작
          </Link>
        </section>
      </div>
    </section>
  );
}
