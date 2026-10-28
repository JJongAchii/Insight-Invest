"use client";

import {
  AlertTriangle,
  CheckCircle2,
  ClipboardList,
  History,
  Info,
  PencilLine,
  Wallet,
} from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import LoadingState from "@/components/ui/LoadingState";
import PageHeader from "@/components/ui/PageHeader";
import { IpoRow, IpoStatus, useFetchIpoQuery } from "@/state/api";
import IpoPositionModal from "./IpoPositionModal";
import IpoSchedule from "./IpoSchedule";
import {
  apiErrorMessage,
  entryOf,
  exitOf,
  fmtDay,
  fmtDayLabel,
  fmtReturn,
  fmtShares,
  fmtTimestamp,
  fmtWon,
  judgement,
  kstToday,
  marketLabel,
  positionMeta,
  returnTone,
} from "./format";
import { EmptyLine, Field, Pill, Section } from "./parts";

const ORDER_NOTE = "공모가 × 1.5 호가 내림 · 당일 유효 지정가 · 동시호가 08:30~09:00 전 주문";
const SELL_NOTE = "종가 동시호가 15:20~15:30";

function EnteredTag({ entered }: { entered: boolean }) {
  return entered ? (
    <Pill className="bg-secondary-400/15 text-secondary-400">입력</Pill>
  ) : null;
}

function RowTitle({ row }: { row: IpoRow }) {
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2">
      <h3 className="truncate text-[15px] font-semibold text-ink">{row.corp_name ?? row.event_id}</h3>
      <span className="badge-neutral">{marketLabel(row.market)}</span>
      {row.ticker && <span className="num text-[11px] text-ink-muted">{row.ticker}</span>}
    </div>
  );
}

function EditButton({ row, onEdit }: { row: IpoRow; onEdit: (row: IpoRow) => void }) {
  return (
    <button
      type="button"
      className="btn-secondary inline-flex items-center gap-1.5 whitespace-nowrap px-3 py-1.5 text-xs"
      onClick={() => onEdit(row)}
      aria-label={`${row.corp_name ?? row.event_id} 체결 입력`}
    >
      <PencilLine size={14} aria-hidden /> 체결 입력
    </button>
  );
}

function SignalCard({ row }: { row: IpoRow }) {
  return (
    <article className="rounded-xl border border-edge bg-raised/40 p-4">
      <RowTitle row={row} />
      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
        <Field label="상장일">{fmtDayLabel(row.listing_date)}</Field>
        <Field label="공모가">
          <span className="num">{fmtWon(row.offer_price)}</span>
        </Field>
        <Field label="주문 가격">
          <span className="num text-base font-semibold">{fmtWon(row.limit_price)}</span>
        </Field>
        <Field label="매도 예정">
          {row.sell_on ? `${fmtDayLabel(row.sell_on)} 종가` : row.sell_plan ?? "—"}
        </Field>
      </dl>
      <p className="mt-3 text-[11px] leading-5 text-ink-muted">{ORDER_NOTE}</p>
    </article>
  );
}

function HoldingCard({ row, onEdit }: { row: IpoRow; onEdit: (row: IpoRow) => void }) {
  const entry = entryOf(row);
  const rolls = Math.round(row.rolls ?? 0);
  return (
    <article className="rounded-xl border border-edge bg-raised/40 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <RowTitle row={row} />
        <EditButton row={row} onEdit={onEdit} />
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
        <Field label="상장일">{fmtDayLabel(row.listing_date)}</Field>
        <Field label="체결가">
          <span className="inline-flex flex-wrap items-center gap-1.5">
            <span className="num">{fmtWon(entry.price)}</span>
            {entry.entered ? (
              <EnteredTag entered />
            ) : (
              entry.price != null && <span className="text-[11px] text-ink-muted">추정</span>
            )}
          </span>
        </Field>
        <Field label="수량">
          <span className="num">{fmtShares(row.user?.quantity)}</span>
        </Field>
        <Field label="매도일">
          <span className="inline-flex flex-wrap items-center gap-1.5">
            {row.sell_on ? `${fmtDayLabel(row.sell_on)} 종가` : "—"}
            {rolls > 0 && <Pill className="bg-losses/15 text-losses">하한가 이월 {rolls}회</Pill>}
          </span>
        </Field>
      </dl>
      <p className="mt-3 text-[11px] leading-5 text-ink-muted">{SELL_NOTE}</p>
      {row.user?.note && (
        <p className="mt-2 text-xs leading-5 text-ink-secondary">메모 · {row.user.note}</p>
      )}
    </article>
  );
}

function JudgementCell({ row }: { row: IpoRow }) {
  const j = judgement(row);
  return (
    <div className="min-w-0">
      <Pill className={j.style}>{j.label}</Pill>
      {j.reason && <p className="mt-1 text-[11px] leading-4 text-ink-muted">{j.reason}</p>}
    </div>
  );
}

function ResultCell({ row }: { row: IpoRow }) {
  const meta = positionMeta(row.position);
  const userFilled = row.user?.filled;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {meta ? <Pill className={meta.style}>{meta.label}</Pill> : <span className="text-ink-muted">—</span>}
      {userFilled != null && (
        <span className="text-[11px] text-ink-muted">입력: {userFilled ? "체결" : "미체결"}</span>
      )}
    </div>
  );
}

function EntryCell({ row }: { row: IpoRow }) {
  const entry = entryOf(row);
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="num">{fmtWon(entry.price)}</span>
      <EnteredTag entered={entry.entered} />
    </span>
  );
}

function ExitCell({ row }: { row: IpoRow }) {
  const exit = exitOf(row);
  if (exit.price == null) return <span className="text-ink-muted">—</span>;
  return (
    <span className="inline-flex flex-col items-end gap-0.5">
      <span className="inline-flex items-center gap-1.5">
        <span className="num">{fmtWon(exit.price)}</span>
        <EnteredTag entered={exit.entered} />
      </span>
      <span className="num text-[11px] text-ink-muted">{fmtDay(exit.date)}</span>
    </span>
  );
}

function HistoryTable({ rows, onEdit }: { rows: IpoRow[]; onEdit: (row: IpoRow) => void }) {
  return (
    <>
      <div className="hidden overflow-x-auto lg:block">
        <table className="w-full text-sm">
          <thead className="border-y border-edge bg-raised/35 text-[11px] text-ink-secondary">
            <tr>
              <th className="whitespace-nowrap px-3 py-2.5 text-left font-medium">상장일</th>
              <th className="px-3 py-2.5 text-left font-medium">종목</th>
              <th className="px-3 py-2.5 text-left font-medium">판단</th>
              <th className="whitespace-nowrap px-3 py-2.5 text-right font-medium">주문 가격</th>
              <th className="px-3 py-2.5 text-left font-medium">결과</th>
              <th className="whitespace-nowrap px-3 py-2.5 text-right font-medium">체결가</th>
              <th className="whitespace-nowrap px-3 py-2.5 text-right font-medium">매도가 · 매도일</th>
              <th className="whitespace-nowrap px-3 py-2.5 text-right font-medium">
                수익
                <span className="block text-[10px] font-normal text-ink-muted">비용 차감 추정</span>
              </th>
              <th className="px-3 py-2.5">
                <span className="sr-only">입력</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-edge">
            {rows.map((row) => (
              <tr key={row.event_id} className="align-top hover:bg-raised/35">
                <td className="num whitespace-nowrap px-3 py-3 text-ink-secondary">{fmtDay(row.listing_date)}</td>
                <td className="px-3 py-3">
                  <p className="font-medium text-ink">{row.corp_name ?? row.event_id}</p>
                  <p className="text-[11px] text-ink-muted">{marketLabel(row.market)}</p>
                </td>
                <td className="max-w-[240px] px-3 py-3">
                  <JudgementCell row={row} />
                </td>
                <td className="num whitespace-nowrap px-3 py-3 text-right">
                  {row.buy ? fmtWon(row.limit_price) : "—"}
                </td>
                <td className="px-3 py-3">
                  <ResultCell row={row} />
                </td>
                <td className="whitespace-nowrap px-3 py-3 text-right">
                  {row.buy ? <EntryCell row={row} /> : <span className="text-ink-muted">—</span>}
                </td>
                <td className="whitespace-nowrap px-3 py-3 text-right">
                  {row.buy ? <ExitCell row={row} /> : <span className="text-ink-muted">—</span>}
                </td>
                <td className={`num whitespace-nowrap px-3 py-3 text-right ${returnTone(row.net_base)}`}>
                  {fmtReturn(row.net_base)}
                </td>
                <td className="px-3 py-3 text-right">{row.buy && <EditButton row={row} onEdit={onEdit} />}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="divide-y divide-edge border-y border-edge lg:hidden">
        {rows.map((row) => {
          const exit = exitOf(row);
          return (
            <article key={row.event_id} className="py-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="num text-[11px] text-ink-muted">
                    {fmtDay(row.listing_date)} · {marketLabel(row.market)}
                  </p>
                  <p className="mt-0.5 truncate font-medium text-ink">{row.corp_name ?? row.event_id}</p>
                </div>
                {row.buy && <EditButton row={row} onEdit={onEdit} />}
              </div>
              <div className="mt-2">
                <JudgementCell row={row} />
              </div>
              {row.buy && (
                <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-3">
                  <Field label="주문 가격">
                    <span className="num">{fmtWon(row.limit_price)}</span>
                  </Field>
                  <Field label="결과">
                    <ResultCell row={row} />
                  </Field>
                  <Field label="체결가">
                    <EntryCell row={row} />
                  </Field>
                  <Field label="매도가 · 매도일">
                    {exit.price == null ? (
                      "—"
                    ) : (
                      <span className="inline-flex flex-wrap items-center gap-1.5">
                        <span className="num">{fmtWon(exit.price)}</span>
                        <EnteredTag entered={exit.entered} />
                        <span className="num text-[11px] text-ink-muted">{fmtDay(exit.date)}</span>
                      </span>
                    )}
                  </Field>
                  <Field label="수익 (비용 차감 추정)">
                    <span className={`num ${returnTone(row.net_base)}`}>{fmtReturn(row.net_base)}</span>
                  </Field>
                </dl>
              )}
            </article>
          );
        })}
      </div>
    </>
  );
}

export default function IpoPage() {
  const { data, isLoading, error, refetch, isFetching } = useFetchIpoQuery(undefined, {
    refetchOnFocus: true,
    refetchOnReconnect: true,
  });
  const [editing, setEditing] = useState<IpoRow | null>(null);
  const closeModal = useCallback(() => setEditing(null), []);

  const status: IpoStatus = data?.status ?? {};
  const problems = (status.problems ?? []).filter((p): p is string => typeof p === "string" && p.length > 0);
  const rule = status.rule ?? null;

  const { signals, holdings } = useMemo(() => {
    const open = data?.open ?? [];
    return {
      signals: open.filter((row) => row.position === "signal"),
      holdings: open.filter((row) => row.position === "holding"),
    };
  }, [data]);

  // 달력의 '오늘'은 한국 시간 기준. 데이터가 클라이언트에서만 그려지므로 하이드레이션 차이가 없다.
  const [today] = useState(kstToday);
  const calendar = status.calendar ?? [];
  const calendarEvents = status.calendar_events ?? [];
  const history = data?.history ?? [];

  return (
    <div className="flex flex-col gap-6 pb-20">
      <PageHeader
        eyebrow="IPO signals"
        title="공모주 신호"
        description="t01 매수 + 2번째 거래일 종가 매도 · 연구 규칙(op-day1-v2)"
        meta={
          <>
            <span>기준일 {status.as_of ? fmtDay(status.as_of) : "확인 중"}</span>
            <span>·</span>
            <span>생성 {fmtTimestamp(status.generated_at)}</span>
            <span>·</span>
            <span>다음 거래일 {status.next_session ? fmtDay(status.next_session) : "—"}</span>
          </>
        }
      />

      {error ? (
        <div className="card text-center" role="alert">
          <p className="text-sm text-ink-secondary">
            {apiErrorMessage(error, "공모주 신호를 불러오지 못했습니다.")}
          </p>
          <button type="button" className="btn-secondary mt-3" onClick={() => refetch()} disabled={isFetching}>
            다시 시도
          </button>
        </div>
      ) : isLoading || !data ? (
        <div className="card">
          <LoadingState label="공모주 신호를 불러오는 중..." />
        </div>
      ) : (
        <>
          {problems.length > 0 ? (
            <section
              role="alert"
              aria-label="데이터 상태"
              className="rounded-2xl border border-warning/40 bg-warning/10 p-4 sm:p-5"
            >
              <h2 className="flex items-center gap-2 font-semibold text-warning">
                <AlertTriangle size={18} aria-hidden /> 데이터 상태 · 확인 필요
              </h2>
              <ul className="mt-3 list-disc space-y-1 pl-5 text-sm leading-6 text-ink">
                {problems.map((problem, index) => (
                  <li key={`${index}-${problem}`}>{problem}</li>
                ))}
              </ul>
              <p className="mt-2 text-xs leading-5 text-ink-secondary">
                해결되기 전까지 아래 신호와 보유 현황이 비어 있거나 늦을 수 있습니다.
              </p>
            </section>
          ) : (
            <div
              aria-label="데이터 상태"
              className="flex items-center gap-2 self-start rounded-xl border border-edge bg-surface px-4 py-2.5 text-sm text-ink-secondary"
            >
              <CheckCircle2 size={16} className="text-gains" aria-hidden />
              데이터 상태
              <Pill className="bg-gains/15 text-gains">정상</Pill>
            </div>
          )}

          <Section
            icon={ClipboardList}
            title="다음 거래일 주문"
            meta={status.next_session ? `${fmtDayLabel(status.next_session)} 시가 동시호가` : undefined}
          >
            {signals.length === 0 ? (
              <EmptyLine>다음 거래일 매수 신호 없음</EmptyLine>
            ) : (
              <div className="grid gap-3 xl:grid-cols-2">
                {signals.map((row) => (
                  <SignalCard key={row.event_id} row={row} />
                ))}
              </div>
            )}
          </Section>

          <IpoSchedule calendar={calendar} events={calendarEvents} today={today} />

          <Section icon={Wallet} title="보유 · 매도 예정" meta={SELL_NOTE}>
            {holdings.length === 0 ? (
              <EmptyLine>보유 중인 공모주 없음</EmptyLine>
            ) : (
              <div className="grid gap-3 xl:grid-cols-2">
                {holdings.map((row) => (
                  <HoldingCard key={row.event_id} row={row} onEdit={setEditing} />
                ))}
              </div>
            )}
          </Section>

          <Section icon={History} title="기록" meta={`결정 ${history.length}건 · 최신 상장일 먼저`}>
            {history.length === 0 ? (
              <EmptyLine>아직 결정 기록이 없습니다</EmptyLine>
            ) : (
              <>
                <HistoryTable rows={history} onEdit={setEditing} />
                <p className="mt-3 text-[11px] leading-5 text-ink-muted">
                  수익은 수수료·슬리피지·매도세를 뺀 추정치이며 실제 계좌 손익과 다를 수 있습니다. 체결 여부와
                  체결가는 입력이 없으면 배치가 시세로 추정한 값입니다.
                </p>
              </>
            )}
          </Section>

          <section
            aria-label="규칙 안내"
            className="rounded-2xl border border-edge bg-surface/60 p-4 text-xs leading-5 text-ink-muted"
          >
            <h2 className="flex items-center gap-1.5 font-medium text-ink-secondary">
              <Info size={14} aria-hidden /> 규칙 안내
            </h2>
            <ul className="mt-2 space-y-0.5">
              {rule?.entry && <li>매수 · {rule.entry}</li>}
              {rule?.exit && <li>매도 · {rule.exit}</li>}
              {rule?.sizing && <li>비중 · {rule.sizing}</li>}
              <li>손절 없음</li>
              {rule?.spec && <li className="num">규칙 {rule.spec}</li>}
            </ul>
            <p className="mt-2">
              개발 구간 검증 결과이며 실제 성과를 보장하지 않습니다. 이 화면은 신호만 보여 주며 주문을 내지
              않습니다.
            </p>
          </section>
        </>
      )}

      <IpoPositionModal row={editing} onClose={closeModal} />
    </div>
  );
}
