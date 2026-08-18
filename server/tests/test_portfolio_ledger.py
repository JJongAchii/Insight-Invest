from datetime import date

import pandas as pd

from datastore import holdings
from datastore import portfolio_ledger as ledger
from module.portfolio_performance import calculate_twr


def _base():
    row = {column: None for column in holdings._EMPTY}
    row.update({
        "meta_id": 1,
        "shares": 10.0,
        "avg_cost": 100.0,
        "currency": "USD",
        "note": "opening",
        "thesis": "growth",
    })
    return pd.DataFrame([row], columns=holdings._EMPTY)


def _event(key, event_type, shares, price, fees=0):
    return {
        "idempotency_key": key,
        "event_type": event_type,
        "occurred_at": date(2026, 8, 18),
        "meta_id": 1,
        "shares": shares,
        "price": price,
        "currency": "USD",
        "amount": None,
        "fees": fees,
        "counter_currency": None,
        "counter_amount": None,
        "note": "",
        "thesis": "",
        "invalidation": "",
        "review_date": None,
    }


def test_ledger_is_idempotent_and_derives_average_cost(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    first_id, created = ledger.record(_event("buy-0001", "BUY", 2, 120), _base())
    duplicate_id, duplicate_created = ledger.record(_event("buy-0001", "BUY", 2, 120), _base())

    assert created is True
    assert duplicate_created is False
    assert first_id == duplicate_id

    position = ledger.current_positions().iloc[0]
    assert position["shares"] == 12
    assert round(position["avg_cost"], 4) == 103.3333

    ledger.record(_event("sell-001", "SELL", 5, 130, fees=1), _base())
    position = ledger.current_positions().iloc[0]
    assert position["shares"] == 7
    assert round(ledger.realized_pnl()["USD"], 2) == 132.33
    assert round(ledger.cash_balances()["USD"], 2) == 409.0


def test_ledger_rejects_oversell(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    try:
        ledger.record(_event("sell-too-many", "SELL", 11, 130), _base())
    except ValueError as exc:
        assert "초과" in str(exc)
    else:
        raise AssertionError("oversell must fail")


def test_position_notes_can_change_without_mutating_economic_events(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    ledger.record(_event("buy-notes", "BUY", 2, 120), _base())
    before = ledger.list_events().copy()

    ledger.upsert_position_metadata(
        1,
        {
            "target_weight": 0.6,
            "note": "",
            "thesis": "revised thesis",
            "invalidation": "revised invalidation",
            "review_date": date(2026, 9, 1),
        },
    )

    position = ledger.current_positions().iloc[0]
    assert position["shares"] == 12
    assert position["thesis"] == "revised thesis"
    pd.testing.assert_frame_equal(before, ledger.list_events())


def test_twr_links_returns_around_external_deposit():
    opening = _base()
    opening.loc[0, "shares"] = 1.0
    events = pd.DataFrame(
        [
            {
                **_event("deposit-1", "DEPOSIT", None, None),
                "occurred_at": date(2026, 1, 2),
                "created_at": pd.Timestamp("2026-01-02T00:00:00Z"),
                "amount": 100.0,
            }
        ]
    )
    prices = pd.DataFrame(
        {1: [100.0, 110.0, 121.0]},
        index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
    )
    rates = pd.Series(1.0, index=prices.index)

    result = calculate_twr(events, opening, prices, {1: "KRW"}, rates)

    # 1/2: (110 + 100) / (100 + 100) - 1 = 5%
    # 1/3: (121 + 100) / 210 - 1 ≈ 5.238%; linked = 10.5%
    assert round(result.value, 6) == 0.105
    assert result.periods == 2


def test_twr_can_start_from_first_deposit_and_buy():
    opening = pd.DataFrame(columns=holdings._EMPTY)
    deposit = {
        **_event("deposit-start", "DEPOSIT", None, None),
        "occurred_at": date(2026, 1, 2),
        "created_at": pd.Timestamp("2026-01-02T00:00:00Z"),
        "currency": "KRW",
        "amount": 100.0,
    }
    buy = {
        **_event("buy-start", "BUY", 1, 100),
        "occurred_at": date(2026, 1, 2),
        "created_at": pd.Timestamp("2026-01-02T00:01:00Z"),
        "currency": "KRW",
    }
    prices = pd.DataFrame(
        {1: [100.0, 110.0, 121.0]},
        index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
    )

    result = calculate_twr(
        pd.DataFrame([deposit, buy]),
        opening,
        prices,
        {1: "KRW"},
        pd.Series(1.0, index=prices.index),
    )

    assert round(result.value, 6) == 0.21
