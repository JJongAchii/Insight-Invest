"use client";

import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  Clock3,
  Database,
  FileCheck2,
  XCircle,
} from "lucide-react";

import PageHeader from "@/components/ui/PageHeader";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import { DataHealthItem, DataHealthLevel, useFetchOverviewQuery } from "@/state/api";
import { formatDate } from "@/lib/market";

const STATUS: Record<
  DataHealthLevel,
  { label: string; color: string; icon: typeof CheckCircle2 }
> = {
  ok: { label: "정상", color: "text-gains", icon: CheckCircle2 },
  warn: { label: "확인 필요", color: "text-warning", icon: AlertTriangle },
  error: { label: "실패", color: "text-losses", icon: XCircle },
  unknown: { label: "미확인", color: "text-ink-muted", icon: CircleHelp },
};

const levelRail = (level: DataHealthLevel) =>
  level === "ok"
    ? "bg-gains"
    : level === "warn"
      ? "bg-warning"
      : level === "error"
        ? "bg-losses"
        : "bg-edge-strong";

const DatasetRow = ({ item }: { item: DataHealthItem }) => {
  const status = STATUS[item.level];
  const Icon = status.icon;
  return (
    <article className="relative grid gap-4 border-b border-edge px-5 py-5 last:border-b-0 md:px-6 xl:grid-cols-[minmax(210px,1.2fr)_130px_190px_110px_minmax(240px,1.4fr)] xl:items-start">
      <span aria-hidden className={`absolute inset-y-3 left-0 w-px ${levelRail(item.level)}`} />
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-sm font-semibold text-ink">{item.label}</p>
          <span className={`inline-flex items-center gap-1 font-mono text-[9px] font-semibold uppercase tracking-[0.1em] ${status.color}`}>
            <Icon size={13} aria-hidden /> {status.label}
          </span>
        </div>
        <p className="mt-1 truncate font-mono text-[10px] text-ink-muted">{item.dataset}</p>
      </div>
      <dl className="contents text-xs">
        <div>
          <dt className="font-mono text-[9px] uppercase tracking-wider text-ink-muted">Observation</dt>
          <dd className="num mt-1 text-ink">{formatDate(item.as_of)}</dd>
          <dd className="mt-1 text-[10px] text-ink-muted">
            {item.market_sessions_old == null ? "경과 미확인" : `${item.market_sessions_old}세션 경과`} · 허용 {item.expected_lag_sessions}
          </dd>
        </div>
        <div>
          <dt className="font-mono text-[9px] uppercase tracking-wider text-ink-muted">Last build</dt>
          <dd className="num mt-1 text-ink">{item.built_at ? new Date(item.built_at).toLocaleString("ko-KR") : "—"}</dd>
          {item.build_version && <dd className="mt-1 text-[10px] text-ink-muted">{item.build_version}</dd>}
        </div>
        <div>
          <dt className="font-mono text-[9px] uppercase tracking-wider text-ink-muted">Rows</dt>
          <dd className="num mt-1 text-ink">{item.row_count?.toLocaleString() ?? "—"}</dd>
        </div>
      </dl>
      <div>
        <p className="text-xs leading-5 text-ink-secondary">{item.detail}</p>
        {item.message && <p className="mt-2 break-words text-[10px] leading-4 text-ink-muted">빌드 메시지 · {item.message}</p>}
      </div>
    </article>
  );
};

export default function DataTrustPage() {
  const { data, isLoading, error, refetch } = useFetchOverviewQuery();
  const statusCounts = (data?.data_status ?? []).reduce(
    (counts, item) => ({ ...counts, [item.level]: counts[item.level] + 1 }),
    { ok: 0, warn: 0, error: 0, unknown: 0 } as Record<DataHealthLevel, number>
  );
  const overallLevel: DataHealthLevel = statusCounts.error
    ? "error"
    : statusCounts.warn
      ? "warn"
      : statusCounts.unknown
        ? "unknown"
        : "ok";
  const overall = STATUS[overallLevel];
  const OverallIcon = overall.icon;

  return (
    <div className="flex flex-col gap-6 pb-16">
      <PageHeader
        eyebrow="Data provenance"
        title="데이터 상태"
        description="숫자를 믿기 전에 관측일, 허용 지연, 마지막 빌드, 계산 계약을 한 경로에서 검산합니다."
        meta={
          <>
            <span>{data?.data_status.length ?? 0} sources</span>
            <span>·</span>
            <span>{data ? `evaluated ${new Date(data.generated_at).toLocaleString("ko-KR")}` : "evaluation pending"}</span>
          </>
        }
      />

      {error ? (
        <div className="card"><ErrorState message="데이터 상태를 불러오지 못했습니다" onRetry={refetch} /></div>
      ) : isLoading || !data ? (
        <div className="card"><LoadingState label="데이터 상태를 확인하는 중..." /></div>
      ) : (
        <>
          <section className="relative overflow-hidden rounded-2xl border border-edge bg-surface" aria-labelledby="health-summary-title">
            <span aria-hidden className={`absolute inset-y-0 left-0 w-px ${levelRail(overallLevel)}`} />
            <div className="grid gap-6 p-5 md:grid-cols-[minmax(0,1fr)_auto] md:items-end md:p-6">
              <div>
                <p className={`inline-flex items-center gap-1.5 font-mono text-[10px] font-semibold uppercase tracking-[0.16em] ${overall.color}`}>
                  <OverallIcon size={14} aria-hidden /> Pipeline {overall.label}
                </p>
                <h2 id="health-summary-title" className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-ink">
                  {overallLevel === "ok"
                    ? "현재 확인된 데이터 지연 없음"
                    : overallLevel === "warn"
                      ? "판단 전 지연 항목 확인 필요"
                      : overallLevel === "error"
                        ? "실패한 데이터 경로가 있습니다"
                        : "확인되지 않은 데이터 경로가 있습니다"}
                </h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-muted">상태는 투자 판단의 승인 표시가 아니라, 이번 화면이 어떤 관측치로 계산됐는지 확인하는 출발점입니다.</p>
              </div>
              <dl className="grid grid-cols-4 overflow-hidden rounded-xl border border-edge bg-raised/45">
                {(["ok", "warn", "error", "unknown"] as DataHealthLevel[]).map((level) => (
                  <div key={level} className="min-w-[62px] border-r border-edge px-3 py-3 text-center last:border-r-0">
                    <dt className={`font-mono text-[9px] uppercase tracking-wider ${STATUS[level].color}`}>{STATUS[level].label}</dt>
                    <dd className="num mt-1 text-lg font-semibold text-ink">{statusCounts[level]}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </section>

          <div className="grid gap-6 xl:grid-cols-[minmax(280px,0.75fr)_minmax(0,1.6fr)]">
            <section className="card" aria-labelledby="evaluation-rules-title">
              <div className="flex items-start gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-primary-400/25 bg-primary-500/10 text-primary-300">
                  <Clock3 size={16} aria-hidden />
                </span>
                <div>
                  <p className="font-mono text-[9px] font-semibold uppercase tracking-[0.16em] text-primary-300">Evaluation protocol</p>
                  <h2 id="evaluation-rules-title" className="mt-1 font-semibold text-ink">신선도 판정 규칙</h2>
                </div>
              </div>
              <p className="mt-5 text-sm leading-6 text-ink-secondary">달력 일수가 아니라 평일 시장 세션 경과를 봅니다. 미국 가격은 1세션, 한국 인사이트는 2세션을 기본 허용 지연으로 두며 거래소 휴일은 배치 완결 검증을 따릅니다.</p>
              <p className="mt-4 border-t border-edge pt-4 font-mono text-[10px] leading-5 text-ink-muted">REQUEST EVALUATED<br />{new Date(data.generated_at).toLocaleString("ko-KR")}</p>
            </section>

            <section className="overflow-hidden rounded-2xl border border-edge bg-surface" aria-labelledby="contracts-title">
              <header className="flex items-start gap-3 border-b border-edge px-5 py-5 md:px-6">
                <FileCheck2 size={18} className="mt-0.5 text-primary-300" aria-hidden />
                <div>
                  <p className="font-mono text-[9px] font-semibold uppercase tracking-[0.16em] text-primary-300">Calculation registry</p>
                  <h2 id="contracts-title" className="mt-1 font-semibold text-ink">계산 계약</h2>
                  <p className="mt-1 text-xs text-ink-muted">가격·수익률·밸류에이션 숫자가 포함하는 범위와 실행 시점</p>
                </div>
              </header>
              <div>
                {(data.calculation_contracts ?? []).map((item) => (
                  <article key={item.key} className="grid gap-3 border-b border-edge px-5 py-4 last:border-b-0 md:grid-cols-[minmax(150px,0.65fr)_minmax(0,1.6fr)] md:px-6">
                    <div>
                      <p className="text-sm font-semibold text-ink">{item.label}</p>
                      <p className="mt-1 font-mono text-[9px] uppercase tracking-wider text-ink-muted">{item.version}</p>
                    </div>
                    <div>
                      <dl className="grid gap-2 text-xs sm:grid-cols-2">
                        <div><dt className="font-mono text-[9px] uppercase tracking-wider text-ink-muted">Basis</dt><dd className="mt-1 text-ink">{item.basis}</dd></div>
                        <div><dt className="font-mono text-[9px] uppercase tracking-wider text-ink-muted">Coverage</dt><dd className="mt-1 text-ink">{item.coverage}</dd></div>
                        {item.execution && <div className="sm:col-span-2"><dt className="font-mono text-[9px] uppercase tracking-wider text-ink-muted">Execution</dt><dd className="mt-1 text-ink">{item.execution}</dd></div>}
                      </dl>
                      <p className="mt-3 text-xs leading-5 text-ink-secondary">{item.detail}</p>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          </div>

          {data.data_status.length === 0 ? (
            <div className="card text-sm text-ink-muted">배치 상태표가 아직 발행되지 않았습니다.</div>
          ) : (
            <section className="overflow-hidden rounded-2xl border border-edge bg-surface" aria-labelledby="source-ledger-title">
              <header className="flex flex-col gap-2 border-b border-edge px-5 py-5 md:flex-row md:items-end md:justify-between md:px-6">
                <div>
                  <p className="flex items-center gap-1.5 font-mono text-[9px] font-semibold uppercase tracking-[0.16em] text-primary-300"><Database size={13} aria-hidden /> Source ledger</p>
                  <h2 id="source-ledger-title" className="mt-1 text-lg font-semibold text-ink">데이터 경로별 신선도</h2>
                </div>
                <p className="flex items-center gap-1.5 text-xs text-ink-muted"><Activity size={13} aria-hidden /> 관측일 → 빌드 → 행 수 → 상세 메시지</p>
              </header>
              <div className="hidden grid-cols-[minmax(210px,1.2fr)_130px_190px_110px_minmax(240px,1.4fr)] gap-4 border-b border-edge bg-raised/50 px-6 py-3 font-mono text-[9px] font-semibold uppercase tracking-[0.12em] text-ink-muted xl:grid">
                <span>Dataset</span><span>Observation</span><span>Last build</span><span>Volume</span><span>Evaluation detail</span>
              </div>
              {data.data_status.map((item) => <DatasetRow key={item.dataset} item={item} />)}
            </section>
          )}
        </>
      )}
    </div>
  );
}
