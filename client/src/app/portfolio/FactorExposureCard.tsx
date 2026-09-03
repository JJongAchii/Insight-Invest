"use client";

import React, { useMemo } from "react";
import {
  HoldingPosition,
  useFetchInsightFactorExposureQuery,
} from "@/state/api";
import Card from "@/components/ui/Card";
import InfoTip from "@/components/ui/InfoTip";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import FactorBars from "@/components/charts/FactorBars";

interface FactorExposureCardProps {
  positions: HoldingPosition[];
}

/**
 * Portfolio-level style tilt: percentile of holdings' factor scores vs the
 * universe. Renders only when the portfolio holds ≥1 KR name (server scores
 * KR only and skips US via `note`).
 */
const FactorExposureCard: React.FC<FactorExposureCardProps> = ({
  positions,
}) => {
  // Pass all holdings; server skips US. Sorted for a stable query cache key.
  const metaIds = useMemo(
    () =>
      positions
        .map((p) => p.meta_id)
        .slice()
        .sort((a, b) => a - b),
    [positions]
  );
  const krCount = useMemo(
    () => positions.filter((p) => p.iso_code === "KR").length,
    [positions]
  );

  const { data, isLoading, error, refetch } =
    useFetchInsightFactorExposureQuery(metaIds, { skip: krCount === 0 });

  if (krCount === 0) return null;

  return (
    <Card
      title={
        <span className="inline-flex items-center gap-1.5">
          팩터 노출
          <InfoTip helpKey="factor.exposure" />
        </span>
      }
      action={
        data?.as_of && (
          <span className="text-xs text-ink-muted num">as of {data.as_of}</span>
        )
      }
    >
      {error ? (
        <ErrorState
          message="팩터 노출을 불러오지 못했습니다"
          onRetry={refetch}
        />
      ) : isLoading || !data ? (
        <LoadingState label="팩터 노출을 계산하는 중..." />
      ) : (
        <div className="flex flex-col gap-4">
          {data.tilt && (
            <p className="text-sm text-ink">
              <span className="text-ink-muted">이 포트폴리오: </span>
              <span className="font-semibold">{data.tilt}</span>
            </p>
          )}
          {data.exposures.length > 0 && (
            <div className="max-w-xl">
              <FactorBars exposures={data.exposures} />
            </div>
          )}
          {data.note && (
            <p className="text-xs text-ink-muted">{data.note}</p>
          )}
        </div>
      )}
    </Card>
  );
};

export default FactorExposureCard;
