"""Small, dated FRED result summaries for the existing release-calendar batch."""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pandas as pd

from module.external_events import ProviderUnavailable, _request_json

# release id -> (series, display label, FRED transformation, displayed unit)
RELEASE_METRICS = {
    9: [("RSAFS", "소매판매 · 전월비", "pch", "%")],
    10: [
        ("CPIAUCNS", "소비자물가 · 전년비", "pc1", "%"),
        ("CPIAUCSL", "소비자물가 · 전월비·계절조정", "pch", "%"),
    ],
    13: [("INDPRO", "산업생산 · 전월비·계절조정", "pch", "%")],
    46: [("PPIFIS", "생산자물가 · 전월비·계절조정", "pch", "%")],
    50: [
        ("PAYEMS", "비농업 고용 · 전월 증감", "chg", "천 명"),
        ("UNRATE", "실업률", "lin", "%"),
    ],
    53: [("A191RL1Q225SBEA", "실질 GDP · 전분기비 연율", "lin", "%")],
    54: [
        ("PCEPI", "PCE 물가 · 전년비", "pc1", "%"),
        ("PCEPILFE", "근원 PCE 물가 · 전년비", "pc1", "%"),
    ],
    192: [("JTSJOL", "JOLTS 구인 건수", "lin", "천 건")],
}


def _finite(value):
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    return result if math.isfinite(result) else None


def enrich_fred_results(events: pd.DataFrame, api_key: str, available_at: str, *, client=None):
    """Do not infer a release from its calendar date or a later revised observation."""
    if events.empty:
        return events.copy()
    out = events.copy()
    out["result_summary"] = None
    now = datetime.fromisoformat(available_at).astimezone(ZoneInfo("America/New_York"))
    today = now.date().isoformat()
    owns_client = client is None
    client = client or httpx.Client(timeout=15, follow_redirects=True)
    cache: dict = {}

    def request(endpoint, **params):
        key = (endpoint, tuple(sorted(params.items())))
        if key not in cache:
            try:
                cache[key] = _request_json(
                    client,
                    f"https://api.stlouisfed.org/fred/{endpoint}",
                    params={"api_key": api_key, "file_type": "json", **params},
                )
            except ProviderUnavailable as exc:
                cache[key] = exc
        if isinstance(cache[key], Exception):
            raise cache[key]
        return cache[key]

    def observations(series, units, vintage):
        payload = request(
            "series/observations",
            series_id=series,
            units=units,
            realtime_start=vintage,
            realtime_end=vintage,
            observation_end=vintage,
            sort_order="desc",
            limit=3,
        )
        values = payload.get("observations")
        if not isinstance(values, list):
            raise ProviderUnavailable("FRED observations 응답 확인 필요")
        # Preserve missing periods. Skipping a missing first value would label
        # an older result as the new release.
        return sorted(values, key=lambda value: value["date"], reverse=True)

    try:
        for index, row in out.iterrows():
            release_id = int(str(row["event_key"]).split(":")[1])
            specs = RELEASE_METRICS.get(release_id, [])
            scheduled = str(row["scheduled_for"])[:10]
            future = scheduled > today
            metrics = []
            for series, label, units, unit in specs:
                metric = {
                    "label": label,
                    "unit": unit,
                    "actual": None,
                    "estimate": None,
                    "previous": None,
                    "actual_period": None,
                    "previous_period": None,
                    "frequency": "quarterly" if release_id == 53 else "monthly",
                    "comparison": "previous",
                    "difference": None,
                    "difference_unit": "%p" if unit == "%" else unit,
                    "source_url": f"https://fred.stlouisfed.org/series/{series}",
                    "status": "scheduled" if future else "pending",
                }
                try:
                    released = False
                    if not future:
                        vintages = request(
                            "series/vintagedates",
                            series_id=series,
                            realtime_start=scheduled,
                            realtime_end=scheduled,
                        )
                        dates = vintages.get("vintage_dates")
                        if not isinstance(dates, list):
                            raise ProviderUnavailable("FRED vintage 응답 확인 필요")
                        released = scheduled in dates
                    # A pending event uses only observations known before its
                    # scheduled date; later releases must never become its result.
                    vintage = (
                        today
                        if future
                        else scheduled
                        if released
                        else (
                            datetime.fromisoformat(scheduled).date() - timedelta(days=1)
                        ).isoformat()
                    )
                    points = observations(series, units, vintage)
                    current = points[0] if points else {}
                    previous = (
                        points[1]
                        if released and len(points) > 1
                        else current
                        if not released
                        else {}
                    )
                    metric["previous"] = _finite(previous.get("value"))
                    metric["previous_period"] = previous.get("date")
                    if released:
                        metric["actual"] = _finite(current.get("value"))
                        metric["actual_period"] = current.get("date")
                        if metric["actual"] is not None:
                            metric["status"] = "released"
                        if metric["actual"] is not None and metric["previous"] is not None:
                            metric["difference"] = metric["actual"] - metric["previous"]
                except (ProviderUnavailable, KeyError, TypeError, ValueError):
                    metric["status"] = "unavailable"
                metrics.append(metric)
            statuses = {metric["status"] for metric in metrics}
            status = (
                "released"
                if statuses == {"released"}
                else (
                    "partial"
                    if "released" in statuses
                    else "unavailable"
                    if statuses == {"unavailable"}
                    else "scheduled"
                    if future
                    else "pending"
                )
            )
            out.at[index, "result_summary"] = json.dumps(
                {
                    "status": status,
                    "source": "FRED",
                    "available_at": available_at,
                    "note": "예상치 미제공 · 발표 전 최근값은 현재 확인된 최신 관측값입니다."
                    if future
                    else "예상치 미제공 · 발표일 당시 FRED 자료. 이전값은 같은 시점의 개정값을 포함합니다.",
                    "metrics": metrics,
                },
                ensure_ascii=False,
                allow_nan=False,
            )
    finally:
        if owns_client:
            client.close()
    return out
