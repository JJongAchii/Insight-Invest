"""Earnings Hub API — 일정·발표 결과·소스 품질을 한 응답으로 제공한다."""

from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import APIRouter, Query

from datastore import earnings as earnings_store

router = APIRouter(prefix="/earnings", tags=["Earnings Hub"])
KST = ZoneInfo("Asia/Seoul")
US_EASTERN = ZoneInfo("America/New_York")

# Finnhub의 ``date``는 미국 현지 발표일이고 ``hour``는 정확한 시각이 아니라
# 발표 구간이다. 구간이 시작될 때까지 Upcoming에 남기기 위한 보수적 기준점이다.
RELEASE_WINDOW_ET = {
    "bmo": time(9, 30),
    "dmh": time(9, 30),
    "amc": time(16, 0),
    "tbd": time(23, 59),
}
RESULT_UNAVAILABLE_AFTER = timedelta(hours=72)
SOURCE_REFRESH_GRACE_HOUR_KST = 10


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


def _search(frame: pd.DataFrame, query: str) -> pd.DataFrame:
    term = query.strip()
    if frame.empty or not term:
        return frame
    ticker = frame.get("ticker", pd.Series("", index=frame.index)).fillna("").astype(str)
    name = frame.get("name", pd.Series("", index=frame.index)).fillna("").astype(str)
    return frame[
        ticker.str.contains(term, case=False, regex=False)
        | name.str.contains(term, case=False, regex=False)
    ]


def _release_window_at(release_day: date, release_timing: object) -> datetime:
    timing = (
        "tbd" if release_timing is None or pd.isna(release_timing) else str(release_timing).lower()
    )
    anchor = RELEASE_WINDOW_ET.get(timing, RELEASE_WINDOW_ET["tbd"])
    return datetime.combine(release_day, anchor, tzinfo=US_EASTERN).astimezone(KST)


def _display_status(
    lifecycle: object,
    release_window_at: datetime,
    now: datetime,
    has_official_actual: bool = False,
) -> str:
    if str(lifecycle).lower() == "reported" or has_official_actual:
        return "reported"
    if release_window_at > now:
        return "upcoming"
    if now - release_window_at <= RESULT_UNAVAILABLE_AFTER:
        return "awaiting_results"
    return "result_unavailable"


def _surprise(actual: float | None, estimate: float | None) -> float | None:
    if actual is None or estimate is None or estimate == 0:
        return None
    return (actual - estimate) / abs(estimate) * 100


def _close_enough(left: float, right: float, *, relative: float, absolute: float) -> bool:
    return abs(left - right) <= max(absolute, max(abs(left), abs(right)) * relative)


def _resolve_actuals(events: pd.DataFrame) -> pd.DataFrame:
    """Project official fallback values without changing stored Finnhub fields."""
    frame = events.copy()
    for column in (
        "eps_actual",
        "eps_estimate",
        "eps_surprise_pct",
        "revenue_actual",
        "revenue_estimate",
        "revenue_surprise_pct",
        "result_signal",
        "official_eps_gaap_actual",
        "official_eps_adjusted_actual",
        "official_revenue_actual",
    ):
        if column not in frame.columns:
            frame[column] = None
    frame["eps_actual_source"] = None
    frame["eps_actual_basis"] = None
    frame["revenue_actual_source"] = None
    frame["actual_reconciliation_status"] = None

    for index, row in frame.iterrows():
        standard_eps = _finite(row.get("eps_actual"))
        standard_revenue = _finite(row.get("revenue_actual"))
        official_extracted = str(row.get("official_actual_status")) == "extracted"
        official_adjusted_eps = (
            _finite(row.get("official_eps_adjusted_actual")) if official_extracted else None
        )
        official_gaap_eps = (
            _finite(row.get("official_eps_gaap_actual")) if official_extracted else None
        )
        official_revenue = (
            _finite(row.get("official_revenue_actual")) if official_extracted else None
        )
        eps_estimate = _finite(row.get("eps_estimate"))
        revenue_estimate = _finite(row.get("revenue_estimate"))

        if standard_eps is not None:
            frame.at[index, "eps_actual_source"] = "finnhub"
            frame.at[index, "eps_actual_basis"] = "provider_standardized"
            frame.at[index, "eps_surprise_pct"] = _surprise(standard_eps, eps_estimate)
        elif official_adjusted_eps is not None:
            frame.at[index, "eps_actual"] = official_adjusted_eps
            frame.at[index, "eps_actual_source"] = "sec"
            frame.at[index, "eps_actual_basis"] = "non_gaap_diluted"
            frame.at[index, "eps_surprise_pct"] = None
        elif official_gaap_eps is not None:
            frame.at[index, "eps_actual"] = official_gaap_eps
            frame.at[index, "eps_actual_source"] = "sec"
            frame.at[index, "eps_actual_basis"] = "gaap_diluted"
            frame.at[index, "eps_surprise_pct"] = None

        if standard_revenue is not None:
            frame.at[index, "revenue_actual_source"] = "finnhub"
            frame.at[index, "revenue_surprise_pct"] = _surprise(
                standard_revenue, revenue_estimate
            )
        elif official_revenue is not None:
            frame.at[index, "revenue_actual"] = official_revenue
            frame.at[index, "revenue_actual_source"] = "sec"
            frame.at[index, "revenue_surprise_pct"] = _surprise(
                official_revenue, revenue_estimate
            )

        fallback_used = (
            frame.at[index, "eps_actual_source"] == "sec"
            or frame.at[index, "revenue_actual_source"] == "sec"
        )
        comparisons = []
        if standard_eps is not None and official_adjusted_eps is not None:
            comparisons.append(
                _close_enough(standard_eps, official_adjusted_eps, relative=0.005, absolute=0.01)
            )
        if standard_revenue is not None and official_revenue is not None:
            comparisons.append(
                _close_enough(
                    standard_revenue,
                    official_revenue,
                    relative=0.001,
                    absolute=1_000_000,
                )
            )
        if fallback_used:
            frame.at[index, "result_signal"] = None
            frame.at[index, "actual_reconciliation_status"] = "official_only"
        elif comparisons:
            frame.at[index, "actual_reconciliation_status"] = (
                "matched" if all(comparisons) else "differs"
            )
        elif standard_eps is not None or standard_revenue is not None:
            frame.at[index, "actual_reconciliation_status"] = "standardized"

        if _finite(frame.at[index, "eps_actual"]) is not None or _finite(
            frame.at[index, "revenue_actual"]
        ) is not None:
            frame.at[index, "lifecycle"] = "reported"
    return frame


def _expected_source_day(now: datetime) -> date:
    """09:00 배치 완료 유예 뒤에는 오늘, 그 전에는 직전 평일을 기대한다."""
    expected = now.date()
    if expected.weekday() >= 5 or now.hour < SOURCE_REFRESH_GRACE_HOUR_KST:
        expected -= timedelta(days=1)
    while expected.weekday() >= 5:
        expected -= timedelta(days=1)
    return expected


def _source_with_freshness(source: dict | None, now: datetime) -> dict | None:
    if source is None:
        return None
    out = dict(source)
    expected = _expected_source_day(now)
    parsed = pd.to_datetime(source.get("data_as_of"), errors="coerce")
    observed = None if pd.isna(parsed) else parsed.date()
    age_sessions = None
    if observed is not None:
        age_sessions = max(
            0,
            len(pd.bdate_range(observed + timedelta(days=1), expected)),
        )
    if str(source.get("status")) != "ok":
        freshness = "attention"
    elif observed is None or observed < expected:
        freshness = "stale"
    else:
        freshness = "ready"
    out.update(
        {
            "freshness": freshness,
            "expected_as_of": expected.isoformat(),
            "age_sessions": age_sessions,
        }
    )
    return out


@router.get("")
def get_earnings(
    scope: str = Query("all", pattern="^(all|mine|portfolio|watchlist|leaders)$"),
    days: int = Query(90, ge=7, le=180),
    results_days: int = Query(120, ge=30, le=1098),
    q: str = Query("", max_length=80),
):
    q = q if isinstance(q, str) else ""
    now = datetime.now(KST)
    today = now.date()
    events = earnings_store.list_events()
    universe = earnings_store.list_universe()
    revisions = earnings_store.list_revisions()
    source = _source_with_freshness(earnings_store.source_status(), now)

    if events.empty:
        visible_universe = _search(_scope(universe, scope), q)
        return {
            "generated_at": now.isoformat(),
            "data_as_of": None,
            "scope": scope,
            "query": q.strip(),
            "summary": {
                "this_week": 0,
                "upcoming": 0,
                "awaiting_results": 0,
                "official_results_available": 0,
                "reported_recently": 0,
                "my_coverage": int(
                    universe.get("scope", pd.Series(dtype="object"))
                    .isin(["portfolio", "watchlist"])
                    .sum()
                ),
            },
            "coverage": {
                "universe_total": int(len(universe)),
                "filtered_universe": int(len(visible_universe)),
                "events_total": 0,
                "filtered_events": 0,
                "history_start": None,
            },
            "upcoming": [],
            "pending_results": [],
            "recent_results": [],
            "revisions": [],
            "source": _clean(source),
        }

    frame = _resolve_actuals(events)
    frame["release_day"] = pd.to_datetime(frame["release_date"], errors="coerce").dt.date
    invalid_dates = int(frame["release_day"].isna().sum())
    frame = frame[frame["release_day"].notna()].copy()
    frame["release_window_datetime"] = [
        _release_window_at(release_day, timing)
        for release_day, timing in zip(
            frame["release_day"],
            frame.get("release_timing", pd.Series("tbd", index=frame.index)),
            strict=True,
        )
    ]
    frame["release_window_at"] = frame["release_window_datetime"].map(
        lambda value: value.isoformat()
    )
    official_actual_available = (
        frame.get("official_actual_status", pd.Series("", index=frame.index))
        .fillna("")
        .eq("extracted")
        & frame[
            [
                "official_eps_gaap_actual",
                "official_eps_adjusted_actual",
                "official_revenue_actual",
            ]
        ]
        .notna()
        .any(axis=1)
    )
    frame["display_status"] = [
        _display_status(lifecycle, release_at, now, official_actual)
        for lifecycle, release_at, official_actual in zip(
            frame.get("lifecycle", pd.Series("scheduled", index=frame.index)),
            frame["release_window_datetime"],
            official_actual_available,
            strict=True,
        )
    ]
    filtered = _search(_scope(frame, scope), q)
    horizon = today + timedelta(days=days)
    result_floor = today - timedelta(days=results_days)
    horizon_at = datetime.combine(horizon, time.max, tzinfo=KST)
    week_end_at = now + timedelta(days=7)

    upcoming = filtered[
        filtered["display_status"].eq("upcoming")
        & filtered["release_window_datetime"].le(horizon_at)
    ].sort_values(["release_window_datetime", "marketcap_rank", "ticker"])
    pending = filtered[
        filtered["display_status"].isin(["awaiting_results", "result_unavailable"])
        & filtered["release_day"].ge(result_floor)
    ].sort_values(["release_window_datetime", "marketcap_rank"], ascending=[False, True])
    official_results_available = int(
        pending.get("official_result_status", pd.Series("", index=pending.index))
        .fillna("")
        .eq("filed")
        .sum()
    )
    results = filtered[
        filtered["display_status"].eq("reported")
        & filtered["release_day"].between(result_floor, today, inclusive="both")
    ].sort_values(["release_day", "marketcap_rank"], ascending=[False, True])

    filtered_ids = set(filtered["event_id"].astype(str))
    visible_revisions = revisions
    if not revisions.empty and "event_id" in revisions.columns:
        visible_revisions = revisions[revisions["event_id"].astype(str).isin(filtered_ids)]
        visible_revisions = visible_revisions.sort_values("observed_at", ascending=False).head(20)

    output_columns = list(
        dict.fromkeys(
            [
                column
                for column in frame.columns
                if column
                not in {"as_of", "release_day", "release_window_datetime"}
            ]
            + ["release_window_at", "display_status"]
        )
    )
    data_as_of = None
    if "data_as_of" in frame.columns and not frame.empty:
        valid_as_of = frame["data_as_of"].dropna()
        if not valid_as_of.empty:
            data_as_of = str(valid_as_of.max())
    history_start = min(frame["release_day"]).isoformat() if not frame.empty else None
    my_coverage = int(
        universe.get("scope", pd.Series(dtype="object")).isin(["portfolio", "watchlist"]).sum()
    )
    leader_count = int(
        universe.get("is_market_leader", pd.Series(dtype="bool")).fillna(False).astype(bool).sum()
    )
    visible_universe = _search(_scope(universe, scope), q)
    response = {
        "generated_at": now.isoformat(),
        "data_as_of": data_as_of,
        "scope": scope,
        "query": q.strip(),
        "summary": {
            "this_week": int(upcoming["release_window_datetime"].le(week_end_at).sum()),
            "upcoming": int(len(upcoming)),
            "awaiting_results": int(len(pending)),
            "official_results_available": official_results_available,
            "reported_recently": int(len(results)),
            "my_coverage": my_coverage,
        },
        "coverage": {
            "universe_total": int(len(universe)),
            "market_leaders": leader_count,
            "filtered_universe": int(len(visible_universe)),
            "events_total": int(len(frame)),
            "filtered_events": int(len(filtered)),
            "invalid_release_dates": invalid_dates,
            "history_start": history_start,
            "forward_days": days,
            "results_days": results_days,
        },
        "upcoming": upcoming.reindex(columns=output_columns).to_dict("records"),
        "pending_results": pending.reindex(columns=output_columns).to_dict("records"),
        "recent_results": results.reindex(columns=output_columns).to_dict("records"),
        "revisions": visible_revisions.to_dict("records"),
        "source": source,
    }
    return _clean(response)
