"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowUpRight, ChevronDown } from "lucide-react";
import {
  EvidenceTone,
  OverviewEvidence,
  OverviewHorizon,
  useFetchOverviewQuery,
} from "@/state/api";
import ErrorState from "@/components/ui/ErrorState";
import LoadingState from "@/components/ui/LoadingState";
import styles from "./marketBriefing.module.css";

const tones: Record<EvidenceTone, { label: string; color: string }> = {
  positive: { label: "우호", color: "var(--gains)" },
  negative: { label: "경계", color: "var(--losses)" },
  neutral: { label: "중립", color: "var(--text-muted)" },
};

function Evidence({ item }: { item: OverviewEvidence }) {
  return (
    <li className={styles.evidence}>
      <Link
        href={
          item.link === "/regime"
            ? "/regime?section=phase"
            : item.key === "flow"
              ? "/insight?tab=settled&section=flows"
              : item.key === "breadth"
                ? "/insight?tab=settled&section=overview"
                : item.link
        }
        className={styles.evidenceLink}
      >
        <span>{item.title}</span>
        <ArrowUpRight size={14} aria-hidden />
      </Link>
      <p>{item.detail}</p>
      <div className={styles.evidenceMeta}>
        <span>기준 {item.as_of || "미확인"}</span>
        {item.changed && <span className={styles.changed}>변화 감지</span>}
      </div>
    </li>
  );
}

function Horizon({ horizon }: { horizon: OverviewHorizon }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <article className={styles.horizon}>
      <header className={styles.horizonHeader}>
        <div>
          <h3>{horizon.label}</h3>
          <span>{horizon.window}</span>
        </div>
        <span
          className={styles.tone}
          style={{ color: tones[horizon.tone].color }}
        >
          {tones[horizon.tone].label}
        </span>
      </header>
      <p className={styles.horizonSummary}>{horizon.summary}</p>
      <button
        type="button"
        className={styles.mobileEvidenceToggle}
        aria-expanded={expanded}
        aria-controls={`horizon-${horizon.key}`}
        onClick={() => setExpanded((value) => !value)}
      >
        관측 근거 {horizon.evidence.length}개{" "}
        <ChevronDown size={14} aria-hidden />
      </button>
      <div
        id={`horizon-${horizon.key}`}
        className={styles.horizonEvidence}
        data-expanded={expanded}
      >
        <ul>
          {horizon.evidence.slice(0, 2).map((item) => (
            <Evidence item={item} key={item.key} />
          ))}
        </ul>
        {horizon.evidence.length === 0 && (
          <p className={styles.empty}>사용할 수 있는 근거가 없습니다.</p>
        )}
        {horizon.evidence.length > 2 && (
          <details className={styles.moreEvidence}>
            <summary>
              근거 {horizon.evidence.length - 2}개 더 보기{" "}
              <ChevronDown size={14} aria-hidden />
            </summary>
            <ul>
              {horizon.evidence.slice(2).map((item) => (
                <Evidence item={item} key={item.key} />
              ))}
            </ul>
          </details>
        )}
      </div>
    </article>
  );
}

export default function MarketOverview() {
  const { data, isLoading, error, refetch } = useFetchOverviewQuery();
  const unhealthy =
    data?.data_status.filter((item) => item.level !== "ok") ?? [];

  return (
    <section
      className={styles.overview}
      aria-labelledby="market-overview-title"
    >
      <header className={styles.sectionHeader}>
        <div>
          <h2 id="market-overview-title">시간축별 시장 흐름</h2>
          <p>장중 움직임, 최근 수급, 경기 흐름을 함께 읽습니다.</p>
        </div>
        <Link href="/insight" className={styles.textLink}>
          시장 분석 <ArrowUpRight size={15} aria-hidden />
        </Link>
      </header>
      {error ? (
        <ErrorState
          message="시장 요약을 불러오지 못했습니다"
          onRetry={refetch}
        />
      ) : isLoading || !data ? (
        <LoadingState label="시장 근거를 불러오는 중…" />
      ) : (
        <>
          {data.horizons.length === 0 ? (
            <p className={styles.empty}>
              시간축별 요약이 아직 없습니다. 시장 분석에서 개별 지표를
              확인하세요.
            </p>
          ) : (
            <div className={styles.horizons}>
              {data.horizons.map((horizon) => (
                <Horizon key={horizon.key} horizon={horizon} />
              ))}
            </div>
          )}
          {data.conflicts.length > 0 && (
            <div className={styles.conflicts}>
              <strong>함께 봐야 할 엇갈림</strong>
              <ul>
                {data.conflicts.map((conflict) => (
                  <li key={conflict}>{conflict}</li>
                ))}
              </ul>
            </div>
          )}
          <footer className={styles.overviewFooter}>
            <Link href="/data-trust" className={styles.textLink}>
              데이터 상태 ·{" "}
              {data.data_status.length === 0
                ? "미확인"
                : unhealthy.length
                  ? `${unhealthy.length}개 확인 필요`
                  : `${data.data_status.length}개 정상`}
              <ArrowUpRight size={13} aria-hidden />
            </Link>
            <details className={styles.method}>
              <summary>요약 기준</summary>
              <p>{data.method}</p>
              <p>
                요약 생성 {data.generated_at.slice(0, 16).replace("T", " ")} ·
                관측 기준일은 각 근거에 표시합니다.
              </p>
            </details>
          </footer>
        </>
      )}
    </section>
  );
}
