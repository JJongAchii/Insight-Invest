"use client";

import { AlertTriangle, CircleCheck } from "lucide-react";

import Card from "@/components/ui/Card";
import LoadingState from "@/components/ui/LoadingState";
import {
  HoldingPosition,
  HoldingsSummary,
  useFetchHoldingsRiskQuery,
} from "@/state/api";

interface PortfolioXRayProps {
  positions: HoldingPosition[];
  summary: HoldingsSummary;
}

const pct = (value: number | null | undefined, digits = 1) =>
  value == null ? "—" : `${(value * 100).toFixed(digits)}%`;

const Metric = ({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) => (
  <div className="rounded-xl border border-edge bg-raised/40 p-3">
    <p className="metric-label">{label}</p>
    <p className="num mt-1 text-xl font-semibold text-ink">{value}</p>
    <p className="mt-1 text-xs leading-5 text-ink-muted">{detail}</p>
  </div>
);

const PortfolioXRay = ({ positions, summary }: PortfolioXRayProps) => {
  const { data: risk, isLoading: riskLoading } = useFetchHoldingsRiskQuery();
  const priced = positions
    .filter((position) => position.weight != null)
    .sort((a, b) => (b.weight ?? 0) - (a.weight ?? 0));
  const largest = priced[0];
  const largestMarket = [...summary.market_alloc].sort(
    (a, b) => b.weight - a.weight,
  )[0];
  const contributions = risk?.risk_contributions ?? [];
  const largestRisk = contributions[0];

  const checkpoints: string[] = [];
  if ((summary.top_weight ?? 0) >= 0.25 && largest) {
    checkpoints.push(
      `${largest.name ?? largest.ticker} 비중이 ${pct(summary.top_weight)}로 단일 종목 변동의 영향이 큽니다.`,
    );
  }
  if ((summary.top3_weight ?? 0) >= 0.6) {
    checkpoints.push(
      `상위 3개 종목이 ${pct(summary.top3_weight)}를 차지합니다. 개별 투자 논거가 서로 다른 위험인지 확인하세요.`,
    );
  }
  if (largestMarket && largestMarket.weight >= 0.8) {
    checkpoints.push(
      `${largestMarket.label} 시장 노출이 ${pct(largestMarket.weight)}입니다. 국가·통화 충격이 함께 작동할 수 있습니다.`,
    );
  }
  if (
    largestRisk &&
    largestRisk.risk_share - largestRisk.weight >= 0.1
  ) {
    checkpoints.push(
      `${largestRisk.name}은 비중 ${pct(largestRisk.weight)}보다 위험 기여 ${pct(largestRisk.risk_share)}가 큽니다.`,
    );
  }
  if (summary.unpriced_positions > 0) {
    checkpoints.push(
      `가격 미확인 ${summary.unpriced_positions}개 종목은 비중과 위험 계산에서 제외되어 있습니다.`,
    );
  }
  if ((risk?.coverage?.weight ?? 1) < 0.999) {
    checkpoints.push(
      `위험 분석 커버리지는 평가 가능한 포트폴리오의 ${pct(risk?.coverage?.weight)}입니다.`,
    );
  }
  if (risk?.empty) {
    checkpoints.push(
      `위험 분석을 계산하지 못했습니다${risk.reason ? `: ${risk.reason}` : "."}`,
    );
  } else if (risk?.insufficient) {
    checkpoints.push(
      `공통 가격 이력이 ${risk.overlap_days ?? 0}거래일로 60일 기준에 미달합니다.`,
    );
  }

  return (
    <Card title="포트폴리오 진단">
      <p className="-mt-2 mb-4 text-sm leading-6 text-ink-secondary">
        수익률보다 먼저 포트폴리오의 쏠림과 실제 변동성 기여를 확인합니다. 아래 수치는 매수·매도 신호가 아니라 점검 우선순위입니다.
      </p>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric
          label="상위 3개 비중"
          value={pct(summary.top3_weight)}
          detail="평가 가능한 종목 중 상위 3개 비중"
        />
        <Metric
          label="유효 분산 종목 수"
          value={summary.effective_positions?.toFixed(1) ?? "—"}
          detail="현재 HHI와 같은 집중도를 갖는 동일비중 종목 수"
        />
        <Metric
          label="분산 효과"
          value={risk?.diversification_ratio?.toFixed(2) ?? "—"}
          detail="1보다 클수록 종목 간 분산효과가 존재"
        />
        <Metric
          label="위험 분석 범위"
          value={risk?.coverage ? pct(risk.coverage.weight) : "—"}
          detail={
            risk?.coverage
              ? `${risk.coverage.n_assets}/${risk.coverage.total_assets}개 평가 종목의 가격 이력`
              : "위험 계산에 포함된 평가 비중"
          }
        />
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2">
        <section>
          <h4 className="metric-label mb-3">종목별 위험 기여</h4>
          {riskLoading ? (
            <LoadingState label="위험 기여도를 계산하는 중..." />
          ) : contributions.length === 0 ? (
            <p className="text-sm leading-6 text-ink-muted">
              공통 가격 이력이 60거래일 미만이거나 비교 가능한 가격이 없어 위험 기여도를 표시하지 않습니다.
            </p>
          ) : (
            <div className="space-y-3">
              {contributions.slice(0, 5).map((row) => {
                const riskWidth = Math.max(0, Math.min(100, row.risk_share * 100));
                return (
                  <div key={row.ticker}>
                    <div className="mb-1.5 flex items-center justify-between gap-3 text-sm">
                      <span className="min-w-0 truncate font-medium text-ink">
                        {row.name} <span className="num text-xs text-ink-muted">{row.ticker}</span>
                      </span>
                      <span className="num shrink-0 text-ink-secondary">
                        위험 {pct(row.risk_share)} · 비중 {pct(row.weight)}
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-raised">
                      <div
                        className="h-full rounded-full bg-primary-400"
                        style={{ width: `${riskWidth}%` }}
                      />
                    </div>
                  </div>
                );
              })}
              <p className="text-xs leading-5 text-ink-muted">
                현재 비중을 고정하고 KRW 환산 split-adjusted 일수익률의 공분산으로 계산합니다. 현금분배는 제외하며 음의 위험 기여는 분산효과를 뜻할 수 있습니다.
              </p>
            </div>
          )}
        </section>

        <section>
          <h4 className="metric-label mb-3">우선 점검 항목</h4>
          {checkpoints.length > 0 ? (
            <ul className="space-y-2">
              {checkpoints.map((item) => (
                <li
                  key={item}
                  className="flex gap-2 rounded-xl border border-warning/30 bg-warning/5 p-3 text-sm leading-6 text-ink-secondary"
                >
                  <AlertTriangle className="mt-1 shrink-0 text-warning" size={15} aria-hidden />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="flex gap-2 rounded-xl border border-edge bg-raised/40 p-3 text-sm leading-6 text-ink-secondary">
              <CircleCheck className="mt-1 shrink-0 text-gains" size={15} aria-hidden />
              <p>
                설정한 휴리스틱 기준에서 큰 구조적 쏠림은 감지되지 않았습니다. 이는 손실 가능성이 낮다는 뜻은 아닙니다.
              </p>
            </div>
          )}
        </section>
      </div>
    </Card>
  );
};

export default PortfolioXRay;
