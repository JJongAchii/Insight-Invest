from datetime import datetime, timedelta

import pandas as pd
from app.routers import actions


def _empty(columns):
    return pd.DataFrame(columns=columns)


def test_action_center_combines_crossing_review_and_data_health(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    today = datetime.now(actions.KST).date()
    monkeypatch.setattr(
        actions.attention,
        "get_attention",
        lambda: {
            "as_of": today.isoformat(),
            "items": [
                {
                    "severity": "medium",
                    "category": "signal",
                    "meta_id": 10,
                    "ticker": "TEST",
                    "name": "테스트",
                    "title": "외인 순매수",
                    "detail": "20일 누적",
                    "link": "/stock/10",
                }
            ],
        },
    )
    monkeypatch.setattr(
        actions.watchlist_api,
        "get_watchlist",
        lambda: {
            "items": [
                {
                    "meta_id": 10,
                    "ticker": "TEST",
                    "name": "테스트",
                    "latest_price": 101.0,
                    "previous_price": 99.0,
                    "chg_pct": 2.02,
                    "price_as_of": today.isoformat(),
                    "alerts_enabled": True,
                    "alert_price_above": 100.0,
                    "alert_price_below": None,
                    "alert_change_pct": None,
                }
            ]
        },
    )
    monkeypatch.setattr(
        actions.watchlist_store,
        "list_items",
        lambda: pd.DataFrame(
            [{"meta_id": 10, "review_date": today + timedelta(days=2)}]
        ),
    )
    monkeypatch.setattr(
        actions.holdings_store, "list_items", lambda: _empty(["meta_id", "review_date"])
    )
    monkeypatch.setattr(
        actions.journal_store,
        "list_entries",
        lambda: _empty(["entry_id", "review_date", "reviewed_at"]),
    )
    monkeypatch.setattr(actions.portfolio, "rebal_signals", lambda: pd.DataFrame())
    monkeypatch.setattr(
        actions.meta,
        "meta_df",
        lambda: pd.DataFrame([{"meta_id": 10, "ticker": "TEST", "name": "테스트"}]),
    )
    monkeypatch.setattr(
        actions.overview,
        "_data_status",
        lambda: [
            {
                "dataset": "us_prices",
                "label": "US prices",
                "level": "warn",
                "as_of": today.isoformat(),
                "built_at": None,
                "detail": "예상보다 1세션 늦음",
            }
        ],
    )

    result = actions.build_actions(horizon_days=30)

    assert {item["kind"] for item in result["items"]} >= {
        "attention",
        "alert",
        "review",
        "data",
    }
    crossing = next(item for item in result["items"] if item["kind"] == "alert")
    assert crossing["data_as_of"] == today.isoformat()
    assert crossing["available_at"] != crossing["data_as_of"]
    assert result["counts"]["scheduled"] == 1

    actions.update_action_state(
        crossing["event_id"], actions.ActionStateRequest(state="dismissed")
    )
    hidden = actions.build_actions(horizon_days=30)
    assert crossing["event_id"] not in {item["event_id"] for item in hidden["items"]}
    visible = actions.build_actions(horizon_days=30, include_dismissed=True)
    dismissed = next(
        item for item in visible["items"] if item["event_id"] == crossing["event_id"]
    )
    assert dismissed["state"] == "dismissed"


def test_price_rule_requires_crossing_not_only_being_above(monkeypatch):
    monkeypatch.setattr(
        actions.watchlist_api,
        "get_watchlist",
        lambda: {
            "items": [
                {
                    "meta_id": 1,
                    "ticker": "AAA",
                    "name": "AAA",
                    "latest_price": 110.0,
                    "previous_price": 105.0,
                    "chg_pct": 4.76,
                    "price_as_of": "2026-08-21",
                    "alerts_enabled": True,
                    "alert_price_above": 100.0,
                    "alert_price_below": None,
                    "alert_change_pct": None,
                }
            ]
        },
    )

    assert actions._watchlist_alert_events(actions.datetime.now(actions.KST)) == []


def test_external_events_include_timing_status_and_source_health(monkeypatch):
    today = datetime.now(actions.KST).date()
    monkeypatch.setattr(
        actions.external_events_store,
        "list_events",
        lambda: pd.DataFrame(
            [
                {
                    "event_key": f"fred:10:{today.isoformat()}",
                    "kind": "event",
                    "category": "macro",
                    "severity": "high",
                    "title": "US CPI",
                    "detail": "공식 발표일",
                    "link": "https://fred.stlouisfed.org/release?rid=10",
                    "meta_id": None,
                    "ticker": None,
                    "name": None,
                    "market": "US",
                    "scope": "market",
                    "occurred_at": today.isoformat(),
                    "available_at": f"{today.isoformat()}T19:00:00+09:00",
                    "data_as_of": today.isoformat(),
                    "scheduled_for": today.isoformat(),
                    "source": "fred",
                    "event_status": "confirmed",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        actions.external_events_store,
        "list_sources",
        lambda: [
            {
                "provider": "fred",
                "label": "FRED Macro",
                "status": "ok",
                "data_as_of": today.isoformat(),
                "available_at": f"{today.isoformat()}T19:00:00+09:00",
                "coverage": "US high-impact releases",
                "message": "향후 1건",
            }
        ],
    )
    monkeypatch.setattr(actions, "_attention_events", lambda now: ([], None))
    monkeypatch.setattr(actions, "_watchlist_alert_events", lambda now: [])
    monkeypatch.setattr(actions, "_review_events", lambda now, horizon: [])
    monkeypatch.setattr(actions, "_rebal_events", lambda now, horizon: [])
    monkeypatch.setattr(actions, "_data_health_events", lambda now: [])
    monkeypatch.setattr(
        actions.action_state,
        "list_states",
        lambda: _empty(actions.action_state.COLUMNS),
    )

    result = actions.build_actions(horizon_days=30)

    event = result["items"][0]
    assert event["kind"] == "event"
    assert event["event_status"] == "confirmed"
    assert event["market"] == "US"
    assert event["available_at"] != event["data_as_of"]
    assert result["counts"]["external"] == 1
    assert result["sources"][0]["status"] == "ok"
