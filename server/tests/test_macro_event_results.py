import json

import httpx
import pandas as pd
import pytest

from app.routers import actions
from module import external_events, macro_event_results

NOW = "2026-09-15T09:00:00+09:00"  # Still September 14 in the US.


def event(day="2026-09-11", release=10):
    return {
        "event_key": f"fred:{release}:{day}",
        "kind": "event",
        "category": "macro",
        "severity": "high",
        "title": "US CPI",
        "detail": "Official calendar",
        "link": "https://fred.stlouisfed.org/release?rid=10",
        "source": "fred",
        "occurred_at": day,
        "available_at": NOW,
        "data_as_of": day,
        "scheduled_for": day,
    }


def enrich(handler, rows=None):
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        frame = macro_event_results.enrich_fred_results(
            pd.DataFrame(rows or [event()]),
            "test-key",
            NOW,
            client=client,
        )
    return frame, [json.loads(value) for value in frame.result_summary]


def test_release_snapshot_survives_parquet_and_api_without_changing_event_identity(
    monkeypatch, tmp_path
):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.params["realtime_end"] == "2026-09-11"
        if request.url.path.endswith("vintagedates"):
            return httpx.Response(200, json={"vintage_dates": ["2026-09-11"]})
        assert request.url.params["units"] in {"pch", "pc1"}
        return httpx.Response(
            200,
            json={
                "observations": [
                    {"date": "2026-08-01", "value": "0"},
                    {"date": "2026-07-01", "value": "-0.2"},
                ]
            },
        )

    frame, summaries = enrich(handler)
    path = tmp_path / "external_events.parquet"
    frame.to_parquet(path, index=False)
    restored = pd.read_parquet(path)
    monkeypatch.setattr(actions.external_events_store, "list_events", lambda: restored)
    output = actions._external_event_events(pd.Timestamp(NOW).to_pydatetime(), 90)[0]
    metric = output["result_summary"]["metrics"][0]
    assert metric["actual"] == 0
    assert metric["previous"] == -0.2
    assert metric["difference"] == pytest.approx(0.2)
    assert metric["difference_unit"] == "%p"
    assert metric["actual_period"] == "2026-08-01"
    assert output["scheduled_for"] == "2026-09-11"
    assert output["result_summary"]["status"] == "released"
    assert metric["estimate"] is None
    restored.drop(columns="result_summary", inplace=True)
    legacy = actions._external_event_events(pd.Timestamp(NOW).to_pydatetime(), 90)[0]
    assert legacy["event_id"] == output["event_id"]
    assert legacy["result_summary"] is None


def test_future_us_date_keeps_latest_value_as_previous_and_reuses_requests():
    called = []

    def handler(request):
        called.append(request)
        assert request.url.path.endswith("observations")
        assert request.url.params["realtime_end"] == "2026-09-14"
        return httpx.Response(200, json={"observations": [{"date": "2026-08-01", "value": "3.1"}]})

    _, summaries = enrich(handler, [event("2026-09-15", 9), event("2026-10-15", 9)])
    assert len(called) == 1
    for summary in summaries:
        assert summary["status"] == "scheduled"
        metric = summary["metrics"][0]
        assert metric["actual"] is None and metric["difference"] is None
        assert metric["previous"] == 3.1


def test_calendar_date_without_vintage_does_not_claim_a_published_result():
    def handler(request):
        if request.url.path.endswith("vintagedates"):
            return httpx.Response(200, json={"vintage_dates": []})
        assert request.url.params["realtime_end"] == "2026-09-10"
        return httpx.Response(200, json={"observations": [{"date": "2026-07-01", "value": "2.9"}]})

    _, summaries = enrich(handler)
    assert summaries[0]["status"] == "pending"
    assert all(m["actual"] is None and m["previous"] == 2.9 for m in summaries[0]["metrics"])


def test_partial_failure_preserves_other_metric_and_schedule():
    def handler(request):
        if request.url.params["series_id"] == "CPIAUCSL":
            return httpx.Response(503)
        if request.url.path.endswith("vintagedates"):
            return httpx.Response(200, json={"vintage_dates": ["2026-09-11"]})
        return httpx.Response(200, json={"observations": [{"date": "2026-08-01", "value": "3.1"}]})

    frame, summaries = enrich(handler)
    assert len(frame) == 1
    assert summaries[0]["status"] == "partial"
    assert summaries[0]["metrics"][0]["actual"] == 3.1
    assert summaries[0]["metrics"][1]["status"] == "unavailable"


@pytest.mark.parametrize("missing", [".", "NaN", "inf"])
def test_missing_latest_value_is_not_replaced_with_older_observation(missing):
    def handler(request):
        if request.url.path.endswith("vintagedates"):
            return httpx.Response(200, json={"vintage_dates": ["2026-09-11"]})
        return httpx.Response(
            200,
            json={
                "observations": [
                    {"date": "2026-08-01", "value": missing},
                    {"date": "2026-07-01", "value": "2.9"},
                ]
            },
        )

    _, summaries = enrich(handler)
    assert summaries[0]["status"] == "pending"
    assert all(m["actual"] is None and m["previous"] == 2.9 for m in summaries[0]["metrics"])


@pytest.mark.parametrize("value", ['{"metrics":null}', '{"status":"released"}', "broken"])
def test_invalid_or_legacy_summary_cannot_break_actions_response(value):
    assert actions._result_summary(pd.Series({"result_summary": value})) is None


def test_earnings_official_eps_and_zero_estimate_do_not_create_false_surprise():
    summary = json.loads(
        external_events.earnings_result_summary(
            {
                "release_date": "2026-09-11",
                "available_at": NOW,
                "period": "2026 Q3",
                "eps_actual": 2.2,
                "eps_estimate": 2.0,
                "eps_actual_source": "sec",
                "revenue_actual": 0,
                "revenue_estimate": 0,
            },
            source="Finnhub · SEC",
        )
    )
    assert summary["status"] == "released"
    eps, revenue = summary["metrics"]
    assert eps["actual"] == 2.2 and eps["difference"] is None
    assert "비교 보류" in eps["note"]
    assert revenue["actual"] == 0 and revenue["estimate"] == 0
    assert revenue["difference"] is None


def test_earnings_future_actuals_are_hidden_but_estimates_are_preserved():
    summary = json.loads(
        external_events.earnings_result_summary(
            {
                "release_date": "2026-09-15",
                "available_at": NOW,
                "eps_actual": 2.2,
                "eps_estimate": -2.0,
            }
        )
    )
    assert summary["status"] == "scheduled"
    assert summary["metrics"][0]["actual"] is None
    assert summary["metrics"][0]["estimate"] == -2.0
