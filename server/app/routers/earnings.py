"""Earnings Hub API — 일정·발표 결과·소스 품질을 한 응답으로 제공한다."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import APIRouter, Query

from datastore import earnings as earnings_store

router = APIRouter(prefix="/earnings", tags=["Earnings Hub"])
KST = ZoneInfo("Asia/Seoul")


def _finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _clean(value):
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    number = _finite(value)
    return number if number is not None else None


def _scope(frame: pd.DataFrame, scope: str) -> pd.DataFrame:
    if frame.empty or scope == "all":
        return frame
    if scope == "mine":
        return frame[frame["scope"].isin(["portfolio", "watchlist"])]
    if scope == "leaders":
        return frame[frame["is_market_leader"].fillna(False).astype(bool)]
    return frame[frame["scope"].eq(scope)]


@router.get("")
def get_earnings(
    scope: str = Query("all", pattern="^(all|mine|portfolio|watchlist|leaders)$"),
    days: int = Query(90, ge=7, le=180),
    results_days: int = Query(120, ge=30, le=1098),
):
    now = datetime.now(KST)
    today = now.date()
    events = earnings_store.list_events()
    universe = earnings_store.list_universe()
    revisions = earnings_store.list_revisions()
    source = earnings_store.source_status()

    if events.empty:
        return {
            "generated_at": now.isoformat(),
            "data_as_of": None,
            "scope": scope,
            "summary": {
                "this_week": 0,
                "upcoming": 0,
                "reported_recently": 0,
                "my_coverage": int(
                    universe.get("scope", pd.Series(dtype="object"))
                    .isin(["portfolio", "watchlist"])
                    .sum()
                ),
            },
            "coverage": {
                "universe_total": int(len(universe)),
                "filtered_universe": int(len(_scope(universe, scope))),
                "events_total": 0,
                "filtered_events": 0,
                "history_start": None,
            },
            "upcoming": [],
            "recent_results": [],
            "revisions": [],
            "source": _clean(source),
        }

    frame = events.copy()
    frame["release_day"] = pd.to_datetime(frame["release_date"], errors="coerce").dt.date
    invalid_dates = int(frame["release_day"].isna().sum())
    frame = frame[frame["release_day"].notna()].copy()
    filtered = _scope(frame, scope)
    horizon = today + timedelta(days=days)
    result_floor = today - timedelta(days=results_days)
    week_end = today + timedelta(days=6)

    upcoming = filtered[
        filtered["lifecycle"].eq("scheduled")
        & filtered["release_day"].between(today, horizon, inclusive="both")
    ].sort_values(["release_day", "marketcap_rank", "ticker"])
    results = filtered[
        filtered["lifecycle"].eq("reported")
        & filtered["release_day"].between(result_floor, today, inclusive="both")
    ].sort_values(["release_day", "marketcap_rank"], ascending=[False, True])

    filtered_ids = set(filtered["event_id"].astype(str))
    visible_revisions = revisions
    if not revisions.empty and "event_id" in revisions.columns:
        visible_revisions = revisions[revisions["event_id"].astype(str).isin(filtered_ids)]
        visible_revisions = visible_revisions.sort_values("observed_at", ascending=False).head(20)

    output_columns = [column for column in events.columns if column != "as_of"]
    data_as_of = None
    if "data_as_of" in frame.columns and not frame.empty:
        data_as_of = str(frame["data_as_of"].dropna().max())
    history_start = min(frame["release_day"]).isoformat() if not frame.empty else None
    my_coverage = int(
        universe.get("scope", pd.Series(dtype="object")).isin(["portfolio", "watchlist"]).sum()
    )
    leader_count = int(
        universe.get("is_market_leader", pd.Series(dtype="bool")).fillna(False).astype(bool).sum()
    )
    response = {
        "generated_at": now.isoformat(),
        "data_as_of": data_as_of,
        "scope": scope,
        "summary": {
            "this_week": int(upcoming["release_day"].le(week_end).sum()),
            "upcoming": int(len(upcoming)),
            "reported_recently": int(len(results)),
            "my_coverage": my_coverage,
        },
        "coverage": {
            "universe_total": int(len(universe)),
            "market_leaders": leader_count,
            "filtered_universe": int(len(_scope(universe, scope))),
            "events_total": int(len(frame)),
            "filtered_events": int(len(filtered)),
            "invalid_release_dates": invalid_dates,
            "history_start": history_start,
            "forward_days": days,
            "results_days": results_days,
        },
        "upcoming": upcoming.reindex(columns=output_columns).to_dict("records"),
        "recent_results": results.reindex(columns=output_columns).to_dict("records"),
        "revisions": visible_revisions.to_dict("records"),
        "source": source,
    }
    return _clean(response)
