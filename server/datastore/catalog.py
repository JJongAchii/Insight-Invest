"""앱 동작 정의 — 외부 DB 덤프가 아닌 버전 관리되는 코드가 정본이다."""

import pandas as pd

_STRATEGIES = (
    {"strategy_id": 1, "strategy": "eq", "strategy_name": "Equal Weight"},
    {"strategy_id": 2, "strategy": "dual_mmt", "strategy_name": "Dual Momentum"},
)

_MACROS = (
    {"macro_id": 1, "fred": "USRECD", "description": "Recession Indicators"},
    {"macro_id": 2, "fred": "T10Y2Y", "description": "Interest Rate Spread(10Y-2Y)"},
    {"macro_id": 3, "fred": "UNRATE", "description": "Unemployment Rate"},
    {"macro_id": 4, "fred": "PAYEMS", "description": "All Employees(Nonfarm)"},
    {"macro_id": 5, "fred": "FEDFUNDS", "description": "Fed Interest Rate"},
    {"macro_id": 6, "fred": "CPIAUCSL", "description": "Consumer Price Index"},
)


def strategy_df() -> pd.DataFrame:
    return pd.DataFrame(_STRATEGIES).copy()


def macro_df() -> pd.DataFrame:
    return pd.DataFrame(_MACROS).copy()
