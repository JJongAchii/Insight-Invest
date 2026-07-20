"""벤치마크 지수/NAV 시계열 — qdata 레이크에서 조회.

- "SPY": qdata 수정종가
- "KOSPI"/"KOSDAQ": qdata KRX 지수 종가
- "60_40": SPY 60 / IEF 40 고정비중을 엔진(월간 리밸, 비용 0)으로 돌린 NAV
"""

import logging
from datetime import date

import pandas as pd
from qdata import api as qdata_api

logger = logging.getLogger(__name__)

BENCHMARKS = ("SPY", "KOSPI", "KOSDAQ", "60_40")


def _fmt(d) -> str | None:
    return str(d) if d is not None else None


def benchmark_nav(name: str, start_date=None, end_date=None) -> pd.Series:
    """벤치마크의 일별 가격/NAV 시계열 (datetime 인덱스).

    Raises:
        ValueError: 알 수 없는 벤치마크 이름
    """
    start, end = _fmt(start_date), _fmt(end_date)

    if name == "SPY":
        wide = qdata_api.load_prices(["SPY"], start=start, end=end, fields=("adj_close",))
        s = wide["adj_close"]["SPY"].dropna()
        s.name = name
        return s

    if name in ("KOSPI", "KOSDAQ"):
        df = qdata_api.load_krx_index(start=start, end=end)
        df = df[df["index"] == name]
        s = df.set_index("date")["close"].sort_index().dropna()
        s.index = pd.to_datetime(s.index)
        s.name = name
        return s

    if name == "60_40":
        # Lazy import — datastore는 module 하위 패키지를 기본적으로 참조하지 않는다
        from module.strategy import FixedWeight
        from module.util import calculate_nav

        price = qdata_api.load_prices(
            ["SPY", "IEF"], start=start, end=end, fields=("adj_close",)
        )["adj_close"].dropna()
        weight = FixedWeight({"SPY": 0.6, "IEF": 0.4}).simulate(price=price, freq="M")
        _, nav = calculate_nav(weight=weight, price=price, cost_bps=0.0)
        s = nav["value"]
        s.name = name
        return s

    raise ValueError(f"unknown benchmark: {name} (expected one of {BENCHMARKS})")
