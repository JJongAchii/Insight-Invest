"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowUpRight } from "lucide-react";
import { useFetchResearchQuery } from "@/state/api";
import Card from "@/components/ui/Card";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import LoadingState from "@/components/ui/LoadingState";
import styles from "./marketBriefing.module.css";

export default function ResearchPreview() {
  const [lane, setLane] = useState<"core" | "discovery">("core");
  // Previewing the home page must not mark documents read or acknowledge unseen research.
  const {
    currentData: data,
    isFetching,
    error,
    refetch,
  } = useFetchResearchQuery(
    { lane, limit: 3 },
    { pollingInterval: 120_000, skipPollingIfUnfocused: true },
  );

  return (
    <Card
      headingLevel={2}
      title="새로 들어온 리서치"
      action={
        <Link href="/research" className={styles.textLink}>
          서재 전체 <ArrowUpRight size={15} aria-hidden />
        </Link>
      }
    >
      <div
        className="mb-3 flex flex-wrap items-center gap-2"
        aria-label="리서치 분류"
      >
        {(
          [
            ["core", "핵심 연구"],
            ["discovery", "발견함"],
          ] as const
        ).map(([key, label]) => (
          <button
            type="button"
            key={key}
            className="filter-chip"
            aria-pressed={lane === key}
            onClick={() => setLane(key)}
          >
            {label}
          </button>
        ))}
      </div>
      <p className="mb-2 text-xs leading-5 text-ink-muted">
        {lane === "core"
          ? "수집 기준을 통과한 연구 자료입니다. 원문의 방법과 한계를 함께 확인하세요."
          : "방법과 근거를 더 살펴볼 탐색 자료입니다."}
      </p>
      {error ? (
        <ErrorState message="리서치를 불러오지 못했습니다" onRetry={refetch} />
      ) : !data && isFetching ? (
        <LoadingState label="최신 리서치를 불러오는 중…" />
      ) : !data?.items.length ? (
        <EmptyState
          title="이 분류에 등록된 자료가 없습니다"
          hint="다른 분류나 서재 전체에서 읽을거리를 찾아보세요."
        />
      ) : (
        <ul className={styles.researchList}>
          {data.items.map((item) => (
            <li key={item.entry_id}>
              <Link
                href={`/research?lane=${lane}&entry=${encodeURIComponent(item.entry_id)}`}
                className={styles.researchLink}
              >
                <div className={styles.researchMeta}>
                  <span>{item.source_name}</span>
                  <time>
                    {(item.published_at || item.discovered_at).slice(0, 10)}
                  </time>
                </div>
                <h3>
                  {item.title}
                  <ArrowUpRight size={15} aria-hidden />
                </h3>
                <p>
                  {item.summary ||
                    "등록된 요약이 없습니다. 원문에서 연구 내용을 확인하세요."}
                </p>
                {item.relevance_terms.length > 0 && (
                  <span className={styles.researchTopics}>
                    {item.relevance_terms.slice(0, 3).join(" · ")}
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
      <Link
        href="/research?view=saved"
        className="mt-3 inline-flex min-h-10 items-center text-xs text-primary-300 hover:underline"
      >
        보관한 자료 이어 읽기 →
      </Link>
    </Card>
  );
}
