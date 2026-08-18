"""불변 거래 원장으로부터 보수적으로 시간가중수익률을 계산한다."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TwrResult:
    value: float | None
    as_of: str | None
    periods: int
    note: str


def _fx_value(amount: float, currency: str, usdkrw: float) -> float:
    return amount * usdkrw if currency == "USD" else amount


def calculate_twr(
    events: pd.DataFrame,
    opening_positions: pd.DataFrame,
    prices: pd.DataFrame,
    currency_by_meta: dict[int, str],
    usdkrw: pd.Series,
) -> TwrResult:
    """일별 평가액을 현금흐름 직전/직후로 연결한다.

    입출금은 해당 거래일 시작 시점 발생으로 가정한다. 매매·배당·수수료·환전은
    포트폴리오 내부 흐름이며 수익률 분모에서 제거하지 않는다.
    """
    if events.empty:
        return TwrResult(None, None, 0, "원장 이벤트가 없어 계산하지 않습니다.")
    if prices.empty or len(prices.index) < 2:
        return TwrResult(None, None, 0, "일별 평가 가격이 2개 시점 이상 필요합니다.")

    frame = prices.copy().sort_index()
    frame.index = pd.to_datetime(frame.index).normalize()
    frame = frame[~frame.index.duplicated(keep="last")]
    rates = usdkrw.copy().sort_index()
    rates.index = pd.to_datetime(rates.index).normalize()
    rates = rates.reindex(frame.index).ffill().bfill()

    ordered = events.copy()
    ordered["occurred_at"] = pd.to_datetime(ordered["occurred_at"]).dt.normalize()
    ordered["created_at"] = pd.to_datetime(ordered["created_at"])
    ordered = ordered.sort_values(["occurred_at", "created_at"])
    first_event = ordered["occurred_at"].min()
    base_dates = frame.index[frame.index < first_event]
    if len(base_dates) == 0:
        return TwrResult(None, None, 0, "첫 이벤트 직전의 평가 가격이 없어 시작 가치를 확정할 수 없습니다.")
    base_date = base_dates[-1]

    shares = {
        int(row.meta_id): float(row.shares)
        for row in opening_positions.itertuples(index=False)
        if pd.notna(row.meta_id) and float(row.shares) > 0
    }
    cash = {"KRW": 0.0, "USD": 0.0}

    def portfolio_value(day: pd.Timestamp) -> float | None:
        rate = rates.get(day)
        if pd.isna(rate):
            return None
        total = cash["KRW"] + cash["USD"] * float(rate)
        for meta_id, quantity in shares.items():
            if quantity <= 1e-10:
                continue
            if meta_id not in frame.columns:
                return None
            price = frame.at[day, meta_id]
            if pd.isna(price):
                return None
            total += quantity * _fx_value(
                float(price), currency_by_meta.get(meta_id, "KRW"), float(rate)
            )
        return total

    previous_value = portfolio_value(base_date)
    if previous_value is None or previous_value < 0:
        return TwrResult(None, None, 0, "첫 이벤트 직전 포트폴리오 가치가 음수이거나 불완전합니다.")

    daily_returns: list[float] = []
    last_day = base_date
    event_index = 0
    rows = list(ordered.itertuples(index=False))
    for day in frame.index[frame.index > base_date]:
        external_flow_krw = 0.0
        rate = rates.get(day)
        if pd.isna(rate):
            return TwrResult(None, None, len(daily_returns), "원화 환산 환율이 없어 계산을 중단했습니다.")
        while event_index < len(rows) and rows[event_index].occurred_at <= day:
            event = rows[event_index]
            event_index += 1
            event_type = str(event.event_type)
            currency = str(event.currency)
            fees = 0.0 if pd.isna(event.fees) else float(event.fees)
            if event_type in {"BUY", "SELL"}:
                meta_id = int(event.meta_id)
                quantity = float(event.shares)
                gross = quantity * float(event.price)
                if event_type == "BUY":
                    shares[meta_id] = shares.get(meta_id, 0.0) + quantity
                    cash[currency] = cash.get(currency, 0.0) - gross - fees
                else:
                    shares[meta_id] = shares.get(meta_id, 0.0) - quantity
                    cash[currency] = cash.get(currency, 0.0) + gross - fees
            elif event_type == "DEPOSIT":
                amount = float(event.amount)
                cash[currency] = cash.get(currency, 0.0) + amount
                external_flow_krw += _fx_value(amount, currency, float(rate))
            elif event_type == "WITHDRAW":
                amount = float(event.amount)
                cash[currency] = cash.get(currency, 0.0) - amount
                external_flow_krw -= _fx_value(amount, currency, float(rate))
            elif event_type == "DIVIDEND":
                cash[currency] = cash.get(currency, 0.0) + float(event.amount) - fees
            elif event_type == "FEE":
                cash[currency] = cash.get(currency, 0.0) - float(event.amount)
            elif event_type == "FX":
                cash[currency] = cash.get(currency, 0.0) - float(event.amount)
                counter = str(event.counter_currency)
                cash[counter] = cash.get(counter, 0.0) + float(event.counter_amount)

        value = portfolio_value(day)
        denominator = previous_value + external_flow_krw
        if value is None:
            return TwrResult(
                None,
                last_day.strftime("%Y-%m-%d"),
                len(daily_returns),
                f"{day:%Y-%m-%d} 보유 가격이 불완전해 계산을 중단했습니다.",
            )
        if denominator <= 0:
            return TwrResult(
                None,
                last_day.strftime("%Y-%m-%d"),
                len(daily_returns),
                "외부 현금흐름 반영 후 시작 가치가 양수가 아니어서 계산할 수 없습니다.",
            )
        daily_returns.append(value / denominator - 1.0)
        previous_value = value
        last_day = day

    if event_index < len(rows):
        return TwrResult(None, last_day.strftime("%Y-%m-%d"), len(daily_returns), "가격 기준일 이후 이벤트가 있어 계산하지 않습니다.")
    if not daily_returns:
        return TwrResult(None, base_date.strftime("%Y-%m-%d"), 0, "평가 가능한 수익률 구간이 없습니다.")
    linked = 1.0
    for value in daily_returns:
        linked *= 1.0 + value
    return TwrResult(
        linked - 1.0,
        last_day.strftime("%Y-%m-%d"),
        len(daily_returns),
        "원화 기준 TWR · 입출금은 해당 거래일 시작 시점 발생으로 가정합니다.",
    )
