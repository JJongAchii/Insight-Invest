from datetime import date, datetime, timedelta

import pandas as pd

from app.routers import earnings


def test_release_window_uses_us_market_date_instead_of_kst_midnight():
    release_at = earnings._release_window_at(date(2026, 8, 26), "amc")

    assert release_at.isoformat() == "2026-08-27T05:00:00+09:00"
    assert (
        earnings._display_status(
            "scheduled", release_at, datetime(2026, 8, 27, 0, 30, tzinfo=earnings.KST)
        )
        == "upcoming"
    )
    assert (
        earnings._display_status(
            "scheduled", release_at, datetime(2026, 8, 27, 7, 0, tzinfo=earnings.KST)
        )
        == "awaiting_results"
    )


def test_source_freshness_is_stale_after_the_morning_refresh_window():
    source = {
        "provider": "finnhub",
        "status": "ok",
        "data_as_of": "2026-08-27",
        "available_at": "2026-08-27T10:04:15+09:00",
    }

    result = earnings._source_with_freshness(
        source,
        datetime(2026, 9, 1, 15, 0, tzinfo=earnings.KST),
    )

    assert result["status"] == "ok"
    assert result["freshness"] == "stale"
    assert result["expected_as_of"] == "2026-09-01"
    assert result["age_sessions"] == 3


def test_source_freshness_uses_previous_weekday_before_morning_grace():
    source = {
        "provider": "finnhub",
        "status": "ok",
        "data_as_of": "2026-09-04",
        "available_at": "2026-09-04T19:10:00+09:00",
    }

    result = earnings._source_with_freshness(
        source,
        datetime(2026, 9, 7, 9, 30, tzinfo=earnings.KST),
    )

    assert result["freshness"] == "ready"
    assert result["expected_as_of"] == "2026-09-04"
    assert result["age_sessions"] == 0


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
            "official_result_status": "filed",
            "official_result_url": "https://www.sec.gov/example",
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
    assert result["summary"]["official_results_available"] == 1
    assert result["pending_results"][0]["official_result_url"] == ("https://www.sec.gov/example")
    assert result["coverage"]["filtered_universe"] == 1
    assert result["coverage"]["filtered_events"] == 1


def test_official_actuals_are_reported_without_unsafe_eps_surprise(monkeypatch):
    today = datetime.now(earnings.KST).date()
    release = (today - timedelta(days=2)).isoformat()
    rows = [
        {
            "event_id": "dell-official",
            "meta_id": 5431,
            "ticker": "DELL",
            "name": "Dell Technologies Inc.",
            "scope": "market",
            "is_market_leader": True,
            "marketcap_rank": 45,
            "release_date": release,
            "release_timing": "amc",
            "lifecycle": "scheduled",
            "eps_actual": None,
            "eps_estimate": 5.012,
            "revenue_actual": None,
            "revenue_estimate": 45_852_452_985,
            "official_result_status": "filed",
            "official_actual_status": "extracted",
            "official_eps_gaap_actual": 6.34,
            "official_eps_adjusted_actual": 7.04,
            "official_revenue_actual": 46_971_000_000,
            "official_actual_url": "https://www.sec.gov/dell-release",
            "data_as_of": today.isoformat(),
            "as_of": today.isoformat(),
        }
    ]
    monkeypatch.setattr(earnings.earnings_store, "list_events", lambda: pd.DataFrame(rows))
    monkeypatch.setattr(
        earnings.earnings_store,
        "list_universe",
        lambda: pd.DataFrame(
            [
                {
                    "meta_id": 5431,
                    "ticker": "DELL",
                    "name": "Dell Technologies Inc.",
                    "scope": "market",
                    "is_market_leader": True,
                }
            ]
        ),
    )
    monkeypatch.setattr(earnings.earnings_store, "list_revisions", lambda: pd.DataFrame())
    monkeypatch.setattr(
        earnings.earnings_store,
        "source_status",
        lambda: {"provider": "finnhub", "status": "ok", "data_as_of": today.isoformat()},
    )

    result = earnings.get_earnings(scope="all", days=90, results_days=120, q="DELL")

    assert result["pending_results"] == []
    assert len(result["recent_results"]) == 1
    dell = result["recent_results"][0]
    assert dell["display_status"] == "reported"
    assert dell["eps_actual"] == 7.04
    assert dell["eps_actual_source"] == "sec"
    assert dell["eps_actual_basis"] == "non_gaap_diluted"
    assert dell["eps_surprise_pct"] is None
    assert dell["revenue_actual"] == 46_971_000_000
    assert dell["revenue_actual_source"] == "sec"
    assert round(dell["revenue_surprise_pct"], 2) == 2.44
    assert dell["result_signal"] is None
    assert dell["actual_reconciliation_status"] == "official_only"


def test_finnhub_actuals_reconcile_against_preserved_official_values():
    frame = pd.DataFrame(
        [
            {
                "eps_actual": 7.04,
                "eps_estimate": 5.012,
                "eps_surprise_pct": 40.46,
                "revenue_actual": 46_970_000_000,
                "revenue_estimate": 45_852_452_985,
                "revenue_surprise_pct": 2.44,
                "result_signal": "beat",
                "official_actual_status": "extracted",
                "official_eps_adjusted_actual": 7.04,
                "official_eps_gaap_actual": 6.34,
                "official_revenue_actual": 46_971_000_000,
            },
            {
                "eps_actual": 6.34,
                "eps_estimate": 5.012,
                "revenue_actual": 44_000_000_000,
                "revenue_estimate": 45_852_452_985,
                "official_actual_status": "extracted",
                "official_eps_adjusted_actual": 7.04,
                "official_eps_gaap_actual": 6.34,
                "official_revenue_actual": 46_971_000_000,
            },
        ]
    )

    resolved = earnings._resolve_actuals(frame)

    assert resolved.iloc[0]["actual_reconciliation_status"] == "matched"
    assert resolved.iloc[0]["eps_actual_source"] == "finnhub"
    assert resolved.iloc[1]["actual_reconciliation_status"] == "differs"


def test_non_extracted_official_values_never_become_display_actuals():
    frame = pd.DataFrame(
        [
            {
                "lifecycle": "scheduled",
                "eps_actual": None,
                "revenue_actual": None,
                "official_actual_status": "ambiguous",
                "official_eps_adjusted_actual": 99.0,
                "official_revenue_actual": 999_000_000_000,
            }
        ]
    )

    resolved = earnings._resolve_actuals(frame).iloc[0]

    assert pd.isna(resolved["eps_actual"])
    assert pd.isna(resolved["revenue_actual"])
    assert resolved["lifecycle"] == "scheduled"
    assert resolved["actual_reconciliation_status"] is None


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
