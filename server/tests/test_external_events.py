import io
import zipfile
from datetime import date

import httpx
import pandas as pd
import pytest
from module import external_events

AVAILABLE_AT = "2026-08-25T19:00:00+09:00"


def test_fred_keeps_only_curated_official_release_dates():
    def handler(request: httpx.Request):
        assert request.url.params["include_release_dates_with_no_data"] == "true"
        release_id = int(request.url.params["release_id"])
        releases = {
            10: [{"release_id": 10, "date": "2026-09-11"}],
            50: [{"release_id": 50, "date": "2026-09-04"}],
        }.get(release_id, [])
        return httpx.Response(
            200,
            json={
                "count": len(releases),
                "release_dates": releases,
            },
            request=request,
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = external_events.fetch_fred_events(
            "x" * 32,
            date(2026, 8, 25),
            date(2026, 10, 1),
            AVAILABLE_AT,
            client=client,
        )

    assert set(result.events["title"]) == {"US CPI", "US Employment Situation"}
    assert set(result.events["event_status"]) == {"confirmed"}
    assert set(result.events["available_at"]) == {AVAILABLE_AT}
    assert set(result.events["data_as_of"]) == {"2026-09-04", "2026-09-11"}


def test_fomc_parser_uses_meeting_decision_day_and_marks_it_projected():
    page = """
    <h4><a id="x">2026 FOMC Meetings</a></h4>
    <div class="fomc-meeting__month"><strong>September</strong></div>
    <div class="fomc-meeting__date">15-16*</div>
    <div class="fomc-meeting__month"><strong>October</strong></div>
    <div class="fomc-meeting__date">27-28</div>
    <h4><a id="y">2025 FOMC Meetings</a></h4>
    """

    result = external_events.parse_fomc_calendar(
        page, date(2026, 8, 25), date(2026, 9, 30), AVAILABLE_AT
    )

    assert result.events["scheduled_for"].tolist() == ["2026-09-16"]
    assert result.events["event_status"].tolist() == ["projected"]
    assert "Summary of Economic Projections" in result.events.iloc[0]["detail"]


def test_massive_earnings_entitlement_failure_is_explicit():
    assets = pd.DataFrame(
        [
            {
                "meta_id": 1,
                "ticker": "AAPL",
                "name": "Apple",
                "iso_code": "US",
                "scope": "portfolio",
            }
        ]
    )

    def handler(request: httpx.Request):
        return httpx.Response(403, json={"error": "NOT_AUTHORIZED"}, request=request)

    with (
        httpx.Client(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(external_events.EntitlementRequired),
    ):
        external_events.fetch_massive_earnings(
            "key",
            assets,
            date(2026, 8, 25),
            date(2026, 10, 1),
            AVAILABLE_AT,
            client=client,
        )


def test_dart_filings_are_observed_only_after_receipt():
    corp_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <result><list><corp_code>00126380</corp_code><corp_name>Samsung</corp_name>
    <stock_code>005930</stock_code></list></result>"""
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("CORPCODE.xml", corp_xml)

    def handler(request: httpx.Request):
        if request.url.path.endswith("corpCode.xml"):
            return httpx.Response(
                200, content=archive_bytes.getvalue(), request=request
            )
        return httpx.Response(
            200,
            json={
                "status": "000",
                "list": [
                    {
                        "rcept_no": "20260825000123",
                        "report_nm": "분기보고서 (2026.06)",
                        "rcept_dt": "20260825",
                        "flr_nm": "삼성전자",
                    }
                ],
            },
            request=request,
        )

    assets = pd.DataFrame(
        [
            {
                "meta_id": 10,
                "ticker": "005930",
                "name": "삼성전자",
                "iso_code": "KR",
                "scope": "watchlist",
            }
        ]
    )
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = external_events.fetch_dart_filings(
            "key",
            assets,
            date(2026, 8, 18),
            date(2026, 8, 25),
            AVAILABLE_AT,
            client=client,
        )

    event = result.events.iloc[0]
    assert event["event_status"] == "observed"
    assert event["occurred_at"] == "2026-08-25"
    assert event["available_at"] == AVAILABLE_AT
    assert event["severity"] == "medium"
