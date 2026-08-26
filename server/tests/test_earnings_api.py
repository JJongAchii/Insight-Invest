from datetime import date, datetime, timedelta

import pandas as pd

from app.routers import earnings


def test_release_window_uses_us_market_date_instead_of_kst_midnight():
    release_at = earnings._release_window_at(date(2026, 8, 26), "amc")

    assert release_at.isoformat() == "2026-08-27T05:00:00+09:00"
    assert earnings._display_status(
        "scheduled", release_at, datetime(2026, 8, 27, 0, 30, tzinfo=earnings.KST)
    ) == "upcoming"
    assert earnings._display_status(
        "scheduled", release_at, datetime(2026, 8, 27, 7, 0, tzinfo=earnings.KST)
    ) == "awaiting_results"


def test_missing_post_release_actual_stays_visible_and_is_searchable(monkeypatch):
    today = datetime.now(earnings.KST).date()
    release = (today - timedelta(days=2)).isoformat()
    rows = [
        {
            "event_id": "nvda-awaiting",
            "meta_id": 5327,
            "ticker": "NVDA",
            "name": "Nvidia Corp",
            "scope": "market",
            "is_market_leader": True,
            "marketcap_rank": 1,
            "release_date": release,
            "release_timing": "amc",
            "lifecycle": "scheduled",
            "data_as_of": release,
            "as_of": release,
        },
        {
            "event_id": "aapl-result",
            "meta_id": 1,
            "ticker": "AAPL",
            "name": "Apple",
            "scope": "market",
            "is_market_leader": True,
            "marketcap_rank": 2,
            "release_date": release,
            "release_timing": "amc",
            "lifecycle": "reported",
            "data_as_of": release,
            "as_of": release,
        },
    ]
    monkeypatch.setattr(earnings.earnings_store, "list_events", lambda: pd.DataFrame(rows))
    monkeypatch.setattr(
        earnings.earnings_store,
        "list_universe",
        lambda: pd.DataFrame(
            [
                {
                    "meta_id": 5327,
                    "ticker": "NVDA",
                    "name": "Nvidia Corp",
                    "scope": "market",
                    "is_market_leader": True,
                },
                {
                    "meta_id": 1,
                    "ticker": "AAPL",
                    "name": "Apple",
                    "scope": "market",
                    "is_market_leader": True,
                },
            ]
        ),
    )
    monkeypatch.setattr(earnings.earnings_store, "list_revisions", lambda: pd.DataFrame())
    monkeypatch.setattr(
        earnings.earnings_store,
        "source_status",
        lambda: {"provider": "finnhub", "status": "ok"},
    )

    result = earnings.get_earnings(scope="all", days=90, results_days=120, q="nvidia")

    assert result["query"] == "nvidia"
    assert result["upcoming"] == []
    assert [item["event_id"] for item in result["pending_results"]] == ["nvda-awaiting"]
    assert result["pending_results"][0]["display_status"] in {
        "awaiting_results",
        "result_unavailable",
    }
    assert result["recent_results"] == []
    assert result["summary"]["awaiting_results"] == 1
    assert result["coverage"]["filtered_universe"] == 1
    assert result["coverage"]["filtered_events"] == 1


def test_empty_event_source_still_applies_company_search_to_coverage(monkeypatch):
    monkeypatch.setattr(earnings.earnings_store, "list_events", lambda: pd.DataFrame())
    monkeypatch.setattr(
        earnings.earnings_store,
        "list_universe",
        lambda: pd.DataFrame(
            [
                {
                    "ticker": "NVDA",
                    "name": "Nvidia Corp",
                    "scope": "market",
                    "is_market_leader": True,
                },
                {
                    "ticker": "AAPL",
                    "name": "Apple",
                    "scope": "market",
                    "is_market_leader": True,
                },
            ]
        ),
    )
    monkeypatch.setattr(earnings.earnings_store, "list_revisions", lambda: pd.DataFrame())
    monkeypatch.setattr(
        earnings.earnings_store,
        "source_status",
        lambda: {"provider": "finnhub", "status": "missing"},
    )

    result = earnings.get_earnings(scope="all", days=90, results_days=120, q="nvidia")

    assert result["query"] == "nvidia"
    assert result["coverage"]["filtered_universe"] == 1
    assert result["pending_results"] == []


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
