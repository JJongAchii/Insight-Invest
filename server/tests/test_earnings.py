from datetime import date

import httpx
import pandas as pd

from module import earnings

AVAILABLE_AT = "2026-08-26T10:00:00+09:00"


def _master():
    return pd.DataFrame(
        [
            {
                "meta_id": 1,
                "ticker": "AAPL",
                "name": "Apple",
                "iso_code": "US",
                "security_type": "STOCK",
                "marketcap": 400,
                "as_of": "2026-08-25",
            },
            {
                "meta_id": 2,
                "ticker": "GOOGL",
                "name": "Alphabet A",
                "iso_code": "US",
                "security_type": "STOCK",
                "marketcap": 300,
                "as_of": "2026-08-25",
            },
            {
                "meta_id": 3,
                "ticker": "GOOG",
                "name": "Alphabet C",
                "iso_code": "US",
                "security_type": "STOCK",
                "marketcap": 290,
                "as_of": "2026-08-25",
            },
            {
                "meta_id": 4,
                "ticker": "MSFT",
                "name": "Microsoft",
                "iso_code": "US",
                "security_type": "STOCK",
                "marketcap": 350,
                "as_of": "2026-08-25",
            },
            {
                "meta_id": 5,
                "ticker": "CPSH",
                "name": "CPS",
                "iso_code": "US",
                "security_type": "STOCK",
                "marketcap": 10,
                "as_of": "2026-08-25",
            },
            {
                "meta_id": 6,
                "ticker": "SPY",
                "name": "SPY",
                "iso_code": "US",
                "security_type": "ETF",
                "marketcap": 500,
                "as_of": "2026-08-25",
            },
        ]
    )


def _reference():
    return pd.DataFrame(
        [
            {"ticker": "AAPL", "cik": "320193", "type": "CS"},
            {"ticker": "GOOGL", "cik": "1652044", "type": "CS"},
            {"ticker": "GOOG", "cik": "1652044", "type": "CS"},
            {"ticker": "MSFT", "cik": "789019", "type": "CS"},
            {"ticker": "CPSH", "cik": "814676", "type": "CS"},
            {"ticker": "SPY", "cik": None, "type": "ETF"},
        ]
    )


def test_universe_collapses_share_classes_and_keeps_tracked_outside_top_n():
    tracked = pd.DataFrame(
        [
            {"meta_id": 1, "ticker": "AAPL", "iso_code": "US", "scope": "watchlist"},
            {"meta_id": 5, "ticker": "CPSH", "iso_code": "US", "scope": "portfolio"},
            {"meta_id": 6, "ticker": "SPY", "iso_code": "US", "scope": "portfolio"},
        ]
    )

    universe, coverage = earnings.build_universe(_master(), _reference(), tracked, leader_count=2)

    assert set(universe["ticker"]) == {"AAPL", "MSFT", "CPSH"}
    assert universe.loc[universe["ticker"].eq("AAPL"), "scope"].item() == "watchlist"
    assert universe.loc[universe["ticker"].eq("CPSH"), "scope"].item() == "portfolio"
    assert coverage["market_leaders"] == 2
    assert coverage["requested_tracked_us"] == 3
    assert coverage["matched_tracked_us"] == 2
    assert coverage["ineligible_or_unmatched_tracked_us"] == 1
    assert coverage["cik_coverage_pct"] == 100.0


def test_calendar_splits_a_capped_window_and_filters_to_universe():
    universe, _ = earnings.build_universe(_master(), _reference(), pd.DataFrame(), leader_count=2)
    requests = []

    def handler(request: httpx.Request):
        start = request.url.params["from"]
        end = request.url.params["to"]
        requests.append((start, end))
        if start != end:
            rows = [
                {"symbol": "AAPL", "date": "2026-08-26", "year": 2026, "quarter": 3},
                {"symbol": "MSFT", "date": "2026-08-27", "year": 2026, "quarter": 3},
            ]
        elif start == "2026-08-26":
            rows = [{"symbol": "AAPL", "date": start, "year": 2026, "quarter": 3}]
        else:
            rows = [{"symbol": "MSFT", "date": start, "year": 2026, "quarter": 3}]
        return httpx.Response(200, json={"earningsCalendar": rows}, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        events, coverage = earnings.fetch_finnhub_calendar(
            "key",
            universe,
            date(2026, 8, 26),
            date(2026, 8, 27),
            AVAILABLE_AT,
            client=client,
            chunk_days=2,
            response_cap=2,
        )

    assert requests == [
        ("2026-08-26", "2026-08-27"),
        ("2026-08-26", "2026-08-26"),
        ("2026-08-27", "2026-08-27"),
    ]
    assert set(events["ticker"]) == {"AAPL", "MSFT"}
    assert coverage["calendar_calls"] == 3


def test_history_preserves_reported_values_and_records_date_revision():
    universe, _ = earnings.build_universe(_master(), _reference(), pd.DataFrame(), leader_count=1)
    previous = earnings.normalize_calendar(
        [
            {
                "symbol": "AAPL",
                "date": "2026-08-25",
                "year": 2026,
                "quarter": 3,
                "epsActual": 2.2,
                "epsEstimate": 2.0,
            }
        ],
        universe,
        AVAILABLE_AT,
    )
    previous.loc[:, "official_result_status"] = "filed"
    previous.loc[:, "official_result_url"] = "https://www.sec.gov/example"
    current = earnings.normalize_calendar(
        [
            {
                "symbol": "AAPL",
                "date": "2026-08-27",
                "year": 2026,
                "quarter": 3,
                "epsActual": None,
                "epsEstimate": 2.1,
            }
        ],
        universe,
        "2026-08-27T10:00:00+09:00",
    )

    merged, revisions = earnings.merge_history(
        previous,
        current,
        earnings.empty_revisions(),
        available_at="2026-08-27T10:00:00+09:00",
    )

    assert len(merged) == 1
    assert merged.iloc[0]["release_date"] == "2026-08-27"
    assert merged.iloc[0]["eps_actual"] == 2.2
    assert merged.iloc[0]["eps_estimate"] == 2.1
    assert merged.iloc[0]["lifecycle"] == "reported"
    assert merged.iloc[0]["result_signal"] == "beat"
    assert merged.iloc[0]["official_result_status"] == "filed"
    assert merged.iloc[0]["official_result_url"] == "https://www.sec.gov/example"
    assert revisions.iloc[0]["previous_release_date"] == "2026-08-25"
    assert revisions.iloc[0]["release_date"] == "2026-08-27"


def test_result_signal_distinguishes_beat_miss_and_mixed():
    universe, _ = earnings.build_universe(_master(), _reference(), pd.DataFrame(), leader_count=1)
    events = earnings.normalize_calendar(
        [
            {
                "symbol": "AAPL",
                "date": "2026-08-25",
                "year": 2026,
                "quarter": 3,
                "epsActual": 2.2,
                "epsEstimate": 2.0,
                "revenueActual": 99,
                "revenueEstimate": 100,
            }
        ],
        universe,
        AVAILABLE_AT,
    )

    assert events.iloc[0]["result_signal"] == "mixed"
    assert round(events.iloc[0]["eps_surprise_pct"], 1) == 10.0
    assert round(events.iloc[0]["revenue_surprise_pct"], 1) == -1.0


def test_sec_result_filing_enriches_exact_202_item_without_filling_actuals():
    universe, _ = earnings.build_universe(_master(), _reference(), pd.DataFrame(), leader_count=2)
    events = earnings.normalize_calendar(
        [
            {
                "symbol": "AAPL",
                "date": "2026-08-25",
                "year": 2026,
                "quarter": 3,
                "epsActual": None,
                "epsEstimate": 2.0,
            },
            {
                "symbol": "MSFT",
                "date": "2026-08-25",
                "year": 2026,
                "quarter": 3,
                "epsActual": None,
                "epsEstimate": 3.0,
            },
        ],
        universe,
        AVAILABLE_AT,
    )

    def handler(request: httpx.Request):
        cik = request.url.path.rsplit("CIK", 1)[-1].removesuffix(".json")
        is_apple = cik == "0000320193"
        return httpx.Response(
            200,
            json={
                "filings": {
                    "recent": {
                        "accessionNumber": [
                            "0000320193-26-000100" if is_apple else "0000789019-26-000100"
                        ],
                        "filingDate": ["2026-08-25"],
                        "acceptanceDateTime": ["2026-08-25T16:21:19.000Z"],
                        "reportDate": ["2026-08-25"],
                        "form": ["8-K"],
                        "items": ["2.02,9.01" if is_apple else "5.02,9.01"],
                        "primaryDocument": ["filing.htm"],
                    }
                }
            },
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        enriched, coverage = earnings.enrich_sec_result_filings(
            events,
            "research@example.com",
            date(2026, 8, 20),
            date(2026, 8, 26),
            AVAILABLE_AT,
            client=client,
            request_interval_seconds=0,
        )

    apple = enriched.loc[enriched["ticker"].eq("AAPL")].iloc[0]
    microsoft = enriched.loc[enriched["ticker"].eq("MSFT")].iloc[0]
    assert apple["official_result_status"] == "filed"
    assert apple["official_result_form"] == "8-K"
    assert apple["official_result_url"] == (
        "https://www.sec.gov/Archives/edgar/data/320193/"
        "000032019326000100/0000320193-26-000100-index.html"
    )
    assert pd.isna(apple["eps_actual"])
    assert apple["lifecycle"] == "scheduled"
    assert pd.isna(microsoft["official_result_status"])
    assert coverage["companies_queried"] == 2
    assert coverage["events_enriched"] == 1


def test_sec_periodic_report_is_an_official_result_fallback():
    assert earnings._sec_result_filing("10-Q", "") is True
    assert earnings._sec_result_filing("8-K", "2.02,9.01") is True
    assert earnings._sec_result_filing("8-K", "5.02,9.01") is False
