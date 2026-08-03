"""리밸 전일 신호 — active 전략의 다음 리밸일 목표 비중 (순수 로직).

엔진 동일성이 생명이다: 리밸일 = 주기 첫 거래일, 비중은 전일까지 가격으로
산출 (Momentum.simulate의 price[:rebal_date-1일]과 동치). 같은 함수를 호출해
같은 식으로 계산한다 — 산출과 백테스트가 다른 코드를 재면 신호가 거짓이 된다.
"""

import pandas as pd

from module.strategy import absolute_momentum

_FREQ_PERIOD = {"M": "M", "Q": "Q", "Y": "Y"}


def next_business_day(d: pd.Timestamp) -> pd.Timestamp:
    """월~금 달력 근사 — KRX 휴일은 모른다. 주기 말 휴장이면 신호가 1~2 저녁
    일찍 뜨고 다음 배치가 최신 데이터로 재산출한다 (멱등)."""
    nxt = d + pd.Timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += pd.Timedelta(days=1)
    return nxt


def is_new_period(as_of: pd.Timestamp, nxt: pd.Timestamp, freq: str) -> bool:
    p = _FREQ_PERIOD[freq]
    return bool(pd.Period(nxt, p) != pd.Period(as_of, p))


def next_period_weights(price: pd.DataFrame, algorithm: str, params: dict | None = None) -> dict:
    """다음 리밸일에 엔진이 쓸 목표 비중 — strategy.simulate와 동일 산출식.

    price는 신호 산출 기준일(as_of)까지의 일별 가격 — simulate가 리밸일 r에서
    쓰는 price[:r-1일]과 동치다. dual_mmt는 Backtest.rebalance와 동일하게
    params를 무시하고 top_n=4·lookback 12를 쓴다.
    """
    params = params or {}
    if algorithm == "eq":
        w = 1.0 / len(price.columns)
        return {str(t): w for t in price.columns}
    if algorithm in ("momentum", "dual_mmt"):
        if algorithm == "dual_mmt":
            top_n, lookback = 4, 12
        else:
            top_n = int(params.get("top_n", 4))
            lookback = int(params.get("lookback_months", 12))
        score = absolute_momentum(price=price, lookback_months=lookback)
        if score is None:
            return {}
        top = score.nlargest(top_n)
        s = float(top.sum())
        return {str(t): (float(v) / s if s > 0 else 0.0) for t, v in top.items()}
    if algorithm == "custom":
        return {str(k): float(v) for k, v in (params.get("weights") or {}).items()}
    raise ValueError(f"unknown algorithm: {algorithm}")


def classify_actions(prev: dict, target: dict) -> list:
    """진입/이탈/유지 분류 — exit은 target 0 행으로 유지한다 (조용한 소실 금지)."""
    rows = []
    ordered = sorted(target.items(), key=lambda kv: -kv[1])
    for rank, (t, w) in enumerate(ordered, start=1):
        rows.append(
            {
                "ticker": t,
                "target_weight": float(w),
                "prev_weight": float(prev.get(t, 0.0)),
                "action": "keep" if t in prev else "enter",
                "rank": rank,
            }
        )
    for t, w in sorted(prev.items(), key=lambda kv: -kv[1]):
        if t not in target:
            rows.append(
                {
                    "ticker": t,
                    "target_weight": 0.0,
                    "prev_weight": float(w),
                    "action": "exit",
                    "rank": None,
                }
            )
    return rows
