from datetime import datetime, timedelta

import pandas as pd

from app.routers import earnings


def test_earnings_api_filters_scope_and_exposes_coverage(monkeypatch):
    today = datetime.now(earnings.KST).date()
    rows = [
        {
            "event_id": "mine-upcoming",
            "meta_id": 1,
            "ticker": "AAPL",
            "name": "Apple",
            "scope": "portfolio",
            "is_market_leader": True,
            "marketcap_rank": 1,
            "release_date": (today + timedelta(days=2)).isoformat(),
            "lifecycle": "scheduled",
            "data_as_of": today.isoformat(),
            "as_of": today.isoformat(),
        },
        {
            "event_id": "market-result",
            "meta_id": 2,
            "ticker": "MSFT",
            "name": "Microsoft",
            "scope": "market",
            "is_market_leader": True,
            "marketcap_rank": 2,
            "release_date": (today - timedelta(days=2)).isoformat(),
            "lifecycle": "reported",
            "data_as_of": today.isoformat(),
            "as_of": today.isoformat(),
        },
    ]
    monkeypatch.setattr(earnings.earnings_store, "list_events", lambda: pd.DataFrame(rows))
    monkeypatch.setattr(
        earnings.earnings_store,
        "list_universe",
        lambda: pd.DataFrame(
            [
                {"meta_id": 1, "scope": "portfolio", "is_market_leader": True},
                {"meta_id": 2, "scope": "market", "is_market_leader": True},
            ]
        ),
    )
    monkeypatch.setattr(earnings.earnings_store, "list_revisions", lambda: pd.DataFrame())
    monkeypatch.setattr(
        earnings.earnings_store,
        "source_status",
        lambda: {"provider": "finnhub", "status": "ok"},
    )

    result = earnings.get_earnings(scope="mine", days=90, results_days=120)

    assert [item["event_id"] for item in result["upcoming"]] == ["mine-upcoming"]
    assert result["recent_results"] == []
    assert result["summary"]["my_coverage"] == 1
    assert result["coverage"]["universe_total"] == 2
    assert result["coverage"]["filtered_universe"] == 1
    assert result["coverage"]["events_total"] == 2
    assert result["coverage"]["filtered_events"] == 1
    assert result["source"]["status"] == "ok"
