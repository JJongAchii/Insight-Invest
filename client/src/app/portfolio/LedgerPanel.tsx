"use client";

import { FormEvent, useMemo, useState } from "react";
import Select, { SingleValue } from "react-select";

import Card from "@/components/ui/Card";
import LoadingState from "@/components/ui/LoadingState";
import { tokenSelectStyles } from "@/components/ui/selectStyles";
import {
  LedgerEventType,
  useAddPortfolioLedgerEventMutation,
  useFetchMetaDataQuery,
  useFetchPortfolioLedgerQuery,
} from "@/state/api";
import { MetaRow } from "@/app/stocksearch/types";
import { formatDate } from "@/lib/market";
import { fmtNative } from "./format";

const EVENT_LABEL: Record<LedgerEventType, string> = {
  BUY: "매수",
  SELL: "매도",
  DEPOSIT: "입금",
  WITHDRAW: "출금",
  DIVIDEND: "배당",
  FEE: "수수료",
  FX: "환전",
};

interface TickerOption {
  value: number;
  label: string;
  currency: "KRW" | "USD";
}

export default function LedgerPanel() {
  const { data, isLoading } = useFetchPortfolioLedgerQuery();
  const { data: rawMeta } = useFetchMetaDataQuery({});
  const [addEvent, { isLoading: saving, error }] =
    useAddPortfolioLedgerEventMutation();
  const [open, setOpen] = useState(false);
  const [type, setType] = useState<LedgerEventType>("BUY");
  const [selected, setSelected] = useState<TickerOption | null>(null);
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [currency, setCurrency] = useState<"KRW" | "USD">("KRW");
  const [shares, setShares] = useState("");
  const [price, setPrice] = useState("");
  const [amount, setAmount] = useState("");
  const [fees, setFees] = useState("0");
  const [counterAmount, setCounterAmount] = useState("");
  const [note, setNote] = useState("");

  const options = useMemo<TickerOption[]>(
    () =>
      ((rawMeta as MetaRow[] | undefined) ?? []).map((row) => ({
        value: row.meta_id,
        label: `${row.ticker} · ${row.name || "이름 없음"}`,
        currency: row.iso_code === "KR" ? "KRW" : "USD",
      })),
    [rawMeta],
  );
  const needsAsset = ["BUY", "SELL", "DIVIDEND"].includes(type);
  const needsTrade = ["BUY", "SELL"].includes(type);
  const needsAmount = ["DEPOSIT", "WITHDRAW", "DIVIDEND", "FEE", "FX"].includes(
    type,
  );

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const payload = {
      idempotency_key: crypto.randomUUID(),
      event_type: type,
      occurred_at: date,
      currency,
      ...(needsAsset && selected ? { meta_id: selected.value } : {}),
      ...(needsTrade ? { shares: Number(shares), price: Number(price) } : {}),
      ...(needsAmount ? { amount: Number(amount) } : {}),
      ...(type === "FX"
        ? {
            counter_currency:
              currency === "KRW" ? ("USD" as const) : ("KRW" as const),
            counter_amount: Number(counterAmount),
          }
        : {}),
      fees: Number(fees) || 0,
      note,
    };
    await addEvent(payload).unwrap();
    setShares("");
    setPrice("");
    setAmount("");
    setCounterAmount("");
    setFees("0");
    setNote("");
    setOpen(false);
  };

  return (
    <Card
      title="거래·현금 원장"
      action={
        <button
          className="btn-secondary"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "입력 닫기" : "이벤트 기록"}
        </button>
      }
    >
      {isLoading || !data ? (
        <LoadingState label="원장을 불러오는 중..." />
      ) : (
        <div className="space-y-5">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-xl bg-raised p-3">
              <p className="metric-label">현금 잔액</p>
              <p className="mt-1 text-sm font-semibold text-ink">
                KRW {fmtNative(data.summary.cash_balances.KRW ?? 0, "KRW")}
              </p>
              <p className="text-sm font-semibold text-ink">
                USD {fmtNative(data.summary.cash_balances.USD ?? 0, "USD")}
              </p>
            </div>
            <div className="rounded-xl bg-raised p-3">
              <p className="metric-label">실현 손익 · 이동평균</p>
              <p className="mt-1 text-sm font-semibold text-ink">
                KRW {fmtNative(data.summary.realized_pnl.KRW ?? 0, "KRW")}
              </p>
              <p className="text-sm font-semibold text-ink">
                USD {fmtNative(data.summary.realized_pnl.USD ?? 0, "USD")}
              </p>
            </div>
            <div className="rounded-xl bg-raised p-3">
              <p className="metric-label">시간가중수익률</p>
              <p className="mt-1 text-sm font-semibold text-ink">
                {data.summary.twr == null
                  ? "계산 보류"
                  : `${(data.summary.twr * 100).toFixed(2)}%`}
              </p>
              <p className="mt-1 text-xs text-ink-muted">
                {data.summary.twr_note}
              </p>
              {data.summary.twr_as_of && (
                <p className="mt-1 text-[11px] text-ink-muted">
                  기준 {formatDate(data.summary.twr_as_of)} · {data.summary.twr_periods.toLocaleString()}개 일별 구간
                </p>
              )}
            </div>
          </div>

          {open && (
            <form
              onSubmit={submit}
              className="rounded-xl border border-edge p-4 space-y-4"
            >
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <label>
                  <span className="input-label">이벤트</span>
                  <select
                    className="input"
                    value={type}
                    onChange={(e) => {
                      setType(e.target.value as LedgerEventType);
                      setSelected(null);
                    }}
                  >
                    {Object.entries(EVENT_LABEL).map(([value, label]) => (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  <span className="input-label">발생일</span>
                  <input
                    required
                    type="date"
                    className="input"
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                  />
                </label>
                <label>
                  <span className="input-label">통화</span>
                  <select
                    className="input"
                    value={currency}
                    onChange={(e) =>
                      setCurrency(e.target.value as "KRW" | "USD")
                    }
                  >
                    <option>KRW</option>
                    <option>USD</option>
                  </select>
                </label>
                <label>
                  <span className="input-label">수수료</span>
                  <input
                    type="number"
                    min={0}
                    step="any"
                    className="input"
                    value={fees}
                    onChange={(e) => setFees(e.target.value)}
                  />
                </label>
              </div>
              {needsAsset && (
                <label className="block">
                  <span className="input-label">종목</span>
                  <Select<TickerOption>
                    options={options}
                    value={selected}
                    onChange={(value: SingleValue<TickerOption>) => {
                      setSelected(value);
                      if (value) setCurrency(value.currency);
                    }}
                    styles={tokenSelectStyles}
                    placeholder="종목 검색"
                  />
                </label>
              )}
              {needsTrade && (
                <div className="grid grid-cols-2 gap-3">
                  <label>
                    <span className="input-label">수량</span>
                    <input
                      required
                      type="number"
                      min={0}
                      step="any"
                      className="input"
                      value={shares}
                      onChange={(e) => setShares(e.target.value)}
                    />
                  </label>
                  <label>
                    <span className="input-label">체결가</span>
                    <input
                      required
                      type="number"
                      min={0}
                      step="any"
                      className="input"
                      value={price}
                      onChange={(e) => setPrice(e.target.value)}
                    />
                  </label>
                </div>
              )}
              {needsAmount && (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <label>
                    <span className="input-label">
                      {type === "FX" ? "지급 금액" : "금액"}
                    </span>
                    <input
                      required
                      type="number"
                      min={0}
                      step="any"
                      className="input"
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                    />
                  </label>
                  {type === "FX" && (
                    <label>
                      <span className="input-label">
                        수취 금액 ({currency === "KRW" ? "USD" : "KRW"})
                      </span>
                      <input
                        required
                        type="number"
                        min={0}
                        step="any"
                        className="input"
                        value={counterAmount}
                        onChange={(e) => setCounterAmount(e.target.value)}
                      />
                    </label>
                  )}
                </div>
              )}
              <label className="block">
                <span className="input-label">메모</span>
                <input
                  className="input"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
              </label>
              {error && (
                <p className="text-sm text-losses">
                  이벤트를 저장하지 못했습니다. 매도 수량과 필수 값을
                  확인하세요.
                </p>
              )}
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs text-ink-muted">
                  처음 기록할 때 현재 보유 종목이 개시 스냅샷으로 고정됩니다.
                  이후 수량은 매수·매도 이벤트에서만 바뀝니다.
                </p>
                <button className="btn-primary" disabled={saving}>
                  {saving ? "기록 중..." : "불변 이벤트 기록"}
                </button>
              </div>
            </form>
          )}

          {data.events.length === 0 ? (
            <p className="text-sm text-ink-muted">
              아직 원장 이벤트가 없습니다.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="table-header">
                    <th className="table-cell text-left">발생일</th>
                    <th className="table-cell text-left">유형</th>
                    <th className="table-cell text-left">종목</th>
                    <th className="table-cell text-right">수량·금액</th>
                    <th className="table-cell text-right">실현 손익</th>
                  </tr>
                </thead>
                <tbody>
                  {data.events.slice(0, 20).map((item) => (
                    <tr key={item.event_id} className="table-row">
                      <td className="table-cell">
                        {formatDate(item.occurred_at)}
                      </td>
                      <td className="table-cell">
                        {EVENT_LABEL[item.event_type]}
                      </td>
                      <td className="table-cell">
                        {item.name ?? item.ticker ?? (item.note || "—")}
                      </td>
                      <td className="table-cell text-right num">
                        {item.shares != null
                          ? `${item.shares.toLocaleString()}주 × ${fmtNative(item.price, item.currency)}`
                          : fmtNative(item.amount, item.currency)}
                      </td>
                      <td className="table-cell text-right num">
                        {fmtNative(item.realized_pnl_native, item.currency)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
