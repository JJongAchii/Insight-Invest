"""US 화면 가격은 raw close, 일간 변화는 기업행동 보정 수익률을 사용한다."""

import pandas as pd

from app.routers import holdings, watchlist


def _split_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "meta_id": [1, 1],
            "trade_date": pd.to_datetime(["2026-08-20", "2026-08-21"]),
            "ticker": ["TEST", "TEST"],
            # 2:1 분할로 raw 가격은 절반이지만 경제적 일간 수익률은 0%다.
            "close": [100.0, 50.0],
            "adj_close": [50.0, 50.0],
            "gross_return": [float("nan"), 0.0],
        }
    )


def test_watchlist_uses_raw_close_for_crossing_and_adjusted_daily_return(monkeypatch):
    monkeypatch.setattr(watchlist, "read_price_data", lambda *_args, **_kwargs: _split_fixture())

    latest, previous, change_pct, as_of = watchlist._us_latest_prices([1])[1]

    assert latest == 50.0
    assert previous == 100.0
    assert change_pct == 0.0
    assert as_of == "2026-08-21"


def test_holdings_values_at_raw_close_without_false_split_loss(monkeypatch):
    monkeypatch.setattr(holdings, "read_price_data", lambda *_args, **_kwargs: _split_fixture())

    latest, change_pct = holdings._us_latest([1])[1]

    assert latest == 50.0
    assert change_pct == 0.0
