"use client";

import { AlertTriangle, CheckCircle2, CircleHelp, Database, XCircle } from "lucide-react";

import PageHeader from "@/components/ui/PageHeader";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import { DataHealthItem, DataHealthLevel, useFetchOverviewQuery } from "@/state/api";
import { formatDate } from "@/lib/market";

const STATUS: Record<DataHealthLevel, { label: string; color: string; icon: typeof CheckCircle2 }> = {
  ok: { label: "정상", color: "text-gains", icon: CheckCircle2 },
  warn: { label: "확인 필요", color: "text-warning", icon: AlertTriangle },
  error: { label: "실패", color: "text-losses", icon: XCircle },
  unknown: { label: "미확인", color: "text-ink-muted", icon: CircleHelp },
};

const DatasetCard = ({ item }: { item: DataHealthItem }) => {
  const status = STATUS[item.level];
  const Icon = status.icon;
  return (
    <article className="rounded-2xl border border-edge bg-surface p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">{item.label}</p>
          <p className="text-xs text-ink-muted num">{item.dataset}</p>
        </div>
        <span className={`inline-flex items-center gap-1 text-xs font-semibold ${status.color}`}>
          <Icon size={15} aria-hidden /> {status.label}
        </span>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
        <div><dt className="text-xs text-ink-muted">데이터 기준일</dt><dd className="mt-0.5 text-ink num">{formatDate(item.as_of)}</dd></div>
        <div><dt className="text-xs text-ink-muted">시장일 경과</dt><dd className="mt-0.5 text-ink num">{item.market_sessions_old == null ? "—" : `${item.market_sessions_old}세션`}</dd></div>
        <div><dt className="text-xs text-ink-muted">마지막 빌드</dt><dd className="mt-0.5 text-ink num">{item.built_at ? new Date(item.built_at).toLocaleString("ko-KR") : "—"}</dd></div>
        <div><dt className="text-xs text-ink-muted">행 수</dt><dd className="mt-0.5 text-ink num">{item.row_count?.toLocaleString() ?? "—"}</dd></div>
      </dl>
      <p className="mt-4 rounded-lg bg-raised p-2 text-xs text-ink-secondary">{item.detail}</p>
      {item.message && <p className="mt-2 text-xs text-ink-muted break-words">빌드 메시지: {item.message}</p>}
      {item.build_version && <p className="mt-1 text-xs text-ink-muted">빌드 버전 {item.build_version}</p>}
    </article>
  );
};

export default function DataTrustPage() {
  const { data, isLoading, error, refetch } = useFetchOverviewQuery();
  return (
    <div className="flex flex-col gap-6 pb-16">
      <PageHeader
        title="데이터 신뢰센터"
        description="판단에 사용한 데이터의 기준일·마지막 빌드·부분 결측을 확인합니다"
      />
      {error ? <div className="card"><ErrorState message="데이터 상태를 불러오지 못했습니다" onRetry={refetch} /></div> : isLoading || !data ? <div className="card"><LoadingState label="데이터 상태를 확인하는 중..." /></div> : (
        <>
          <section className="card">
            <div className="flex items-start gap-3">
              <Database className="mt-0.5 text-primary-400" size={20} aria-hidden />
              <div>
                <h2 className="font-semibold text-ink">판정 원칙</h2>
                <p className="mt-1 text-sm text-ink-secondary">달력 일수가 아니라 평일 세션 경과를 기준으로 보며, 미국 가격 1세션·한국 인사이트 2세션을 기본 허용 지연으로 둡니다. 거래소 휴일은 배치의 완결 세션 검증이 최종 기준입니다.</p>
                <p className="mt-2 text-xs text-ink-muted">요청 계산 시각 {new Date(data.generated_at).toLocaleString("ko-KR")}</p>
              </div>
            </div>
          </section>
          {data.data_status.length === 0 ? (
            <div className="card text-sm text-ink-muted">배치 상태표가 아직 발행되지 않았습니다.</div>
          ) : (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
              {data.data_status.map((item) => <DatasetCard key={item.dataset} item={item} />)}
            </div>
          )}
        </>
      )}
    </div>
  );
}
