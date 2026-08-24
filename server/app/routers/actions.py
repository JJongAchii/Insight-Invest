"""Action Center — 기존 판단 재료를 안정적인 Event 계약으로 연결한다.

이 라우터는 별도 가격 원천을 만들지 않는다. Attention·Watchlist·Holdings·Journal·
Strategy·Data Trust의 기존 API/저장소를 조합하며 각 이벤트에 data_as_of와
available_at을 분리해 반환한다.
"""

import hashlib
import json
import logging
from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from datastore import action_state, meta, portfolio, portfolio_ledger
from datastore import holdings as holdings_store
from datastore import journal as journal_store
from datastore import watchlist as watchlist_store

from . import attention, overview
from . import watchlist as watchlist_api

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/actions", tags=["Action Center"])
KST = ZoneInfo("Asia/Seoul")
SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


class ActionStateRequest(BaseModel):
    state: Literal["new", "read", "snoozed", "dismissed"]
    snoozed_until: datetime | None = None


def _iso(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    return pd.Timestamp(value).isoformat()


def _event_id(source: str, key: str, occurred_at: str | None) -> str:
    raw = json.dumps(
        [source, key, occurred_at or ""], ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _event(
    *,
    source: str,
    key: str,
    kind: str,
    category: str,
    severity: str,
    title: str,
    detail: str,
    link: str,
    occurred_at: str | None,
    available_at: str,
    data_as_of: str | None,
    scheduled_for: str | None = None,
    meta_id: int | None = None,
    ticker: str | None = None,
    name: str | None = None,
    actions: list[str] | None = None,
) -> dict:
    return {
        "event_id": _event_id(source, key, occurred_at),
        "kind": kind,
        "category": category,
        "severity": severity,
        "title": title,
        "detail": detail,
        "link": link,
        "meta_id": meta_id,
        "ticker": ticker,
        "name": name,
        "occurred_at": occurred_at,
        "available_at": available_at,
        "data_as_of": data_as_of,
        "scheduled_for": scheduled_for,
        "source": source,
        "actions": actions or ["open", "journal", "snooze", "dismiss"],
    }


def _parse_day(value) -> date | None:
    try:
        return (
            pd.Timestamp(value).date()
            if value is not None and not pd.isna(value)
            else None
        )
    except (TypeError, ValueError):
        return None


def _review_severity(day: date, today: date) -> str:
    if day < today:
        return "high"
    if day <= today + timedelta(days=3):
        return "medium"
    return "low"


def _review_events(now: datetime, horizon_days: int) -> list[dict]:
    today = now.date()
    last_day = today + timedelta(days=horizon_days)
    master = meta.meta_df()[["meta_id", "ticker", "name"]].drop_duplicates("meta_id")
    master_by_id = {int(row.meta_id): row for row in master.itertuples(index=False)}
    out: list[dict] = []

    holdings = (
        portfolio_ledger.current_positions()
        if portfolio_ledger.has_events()
        else holdings_store.list_items()
    )
    sources = (
        ("watchlist", watchlist_store.list_items(), "/stock/{meta_id}"),
        ("holding", holdings, "/stock/{meta_id}"),
    )
    for source, frame, link_template in sources:
        if frame.empty:
            continue
        for row in frame.itertuples(index=False):
            day = _parse_day(getattr(row, "review_date", None))
            if day is None or day > last_day:
                continue
            meta_id = int(row.meta_id)
            asset = master_by_id.get(meta_id)
            if asset is None:
                out.append(
                    _event(
                        source="data_contract",
                        key=f"missing-master:{source}:{meta_id}",
                        kind="data",
                        category="data",
                        severity="high",
                        title=f"종목 마스터 연결 실패 · meta_id {meta_id}",
                        detail="저장된 판단 대상을 현재 통합 종목 마스터에서 찾지 못했습니다.",
                        link="/data-trust",
                        occurred_at=day.isoformat(),
                        available_at=now.isoformat(),
                        data_as_of=day.isoformat(),
                        scheduled_for=day.isoformat(),
                        actions=["open", "dismiss"],
                    )
                )
                continue
            label = (
                asset.name
                if isinstance(asset.name, str) and asset.name
                else asset.ticker
            )
            out.append(
                _event(
                    source=source,
                    key=f"review:{meta_id}",
                    kind="review",
                    category=source,
                    severity=_review_severity(day, today),
                    title=f"{label} Thesis Review",
                    detail="투자 논거·반증·무효화 조건을 다시 확인할 시점입니다.",
                    link=link_template.format(meta_id=meta_id),
                    occurred_at=day.isoformat(),
                    available_at=now.isoformat(),
                    data_as_of=day.isoformat(),
                    scheduled_for=day.isoformat(),
                    meta_id=meta_id,
                    ticker=str(asset.ticker),
                    name=str(asset.name) if pd.notna(asset.name) else None,
                )
            )

    entries = journal_store.list_entries()
    if not entries.empty:
        for row in entries.itertuples(index=False):
            if pd.notna(getattr(row, "reviewed_at", None)):
                continue
            day = _parse_day(row.review_date)
            if day is None or day > last_day:
                continue
            out.append(
                _event(
                    source="journal",
                    key=f"review:{row.entry_id}",
                    kind="review",
                    category="journal",
                    severity=_review_severity(day, today),
                    title="Decision Review",
                    detail=str(row.decision)[:240],
                    link=f"/journal#entry-{row.entry_id}",
                    occurred_at=day.isoformat(),
                    available_at=now.isoformat(),
                    data_as_of=day.isoformat(),
                    scheduled_for=day.isoformat(),
                    actions=["open", "snooze", "dismiss"],
                )
            )
    return out


def _rebal_events(now: datetime, horizon_days: int) -> list[dict]:
    out: list[dict] = []
    try:
        frame = portfolio.rebal_signals()
    except Exception:
        logger.debug("Action Center rebal signal load failed", exc_info=True)
        return out
    if frame.empty:
        return out
    last_day = now.date() + timedelta(days=horizon_days)
    for port_id, group in frame.groupby("port_id"):
        day = _parse_day(group["next_rebal"].iloc[0])
        if day is None or day < now.date() or day > last_day:
            continue
        n_enter = int((group["action"] == "enter").sum())
        n_exit = int((group["action"] == "exit").sum())
        n_keep = int((group["action"] == "keep").sum())
        port_name = str(group["port_name"].iloc[0])
        out.append(
            _event(
                source="strategy",
                key=f"rebal:{int(port_id)}",
                kind="rebalance",
                category="strategy",
                severity="high" if day <= now.date() + timedelta(days=1) else "medium",
                title=f"{port_name} Rebalance",
                detail=f"진입 {n_enter} · 이탈 {n_exit} · 유지 {n_keep}",
                link=f"/backtest/strategy_list/{int(port_id)}",
                occurred_at=day.isoformat(),
                available_at=now.isoformat(),
                data_as_of=_iso(group.get("as_of", pd.Series([None])).iloc[0]),
                scheduled_for=day.isoformat(),
            )
        )
    return out


def _watchlist_alert_events(now: datetime) -> list[dict]:
    try:
        items = watchlist_api.get_watchlist().get("items", [])
    except Exception:
        logger.debug("Action Center watchlist alert load failed", exc_info=True)
        return []
    out: list[dict] = []
    for item in items:
        if not item.get("alerts_enabled", False):
            continue
        price = item.get("latest_price")
        previous = item.get("previous_price")
        chg = item.get("chg_pct")
        as_of = item.get("price_as_of")
        if price is None:
            continue
        label = item.get("name") or item.get("ticker")
        rules: list[tuple[str, bool, str]] = []
        above = item.get("alert_price_above")
        below = item.get("alert_price_below")
        change = item.get("alert_change_pct")
        rules.append(
            (
                "price_above",
                above is not None
                and previous is not None
                and previous < above <= price,
                f"{label} {price:,.2f} · 상단 기준 {above:,.2f}"
                if above is not None
                else "",
            )
        )
        rules.append(
            (
                "price_below",
                below is not None
                and previous is not None
                and previous > below >= price,
                f"{label} {price:,.2f} · 하단 기준 {below:,.2f}"
                if below is not None
                else "",
            )
        )
        rules.append(
            (
                "daily_move",
                change is not None and chg is not None and abs(chg) >= change,
                f"{label} 일간 {chg:+.1f}% · 기준 ±{change:.1f}%"
                if change is not None
                else "",
            )
        )
        for rule, triggered, detail in rules:
            if not triggered:
                continue
            title = {
                "price_above": "Price Above Alert",
                "price_below": "Price Below Alert",
                "daily_move": "Daily Move Alert",
            }[rule]
            out.append(
                _event(
                    source="watchlist_rule",
                    key=f"{rule}:{item['meta_id']}",
                    kind="alert",
                    category="watchlist",
                    severity="high" if rule == "price_below" else "medium",
                    title=title,
                    detail=detail,
                    link=f"/stock/{item['meta_id']}",
                    occurred_at=as_of,
                    available_at=now.isoformat(),
                    data_as_of=as_of,
                    meta_id=int(item["meta_id"]),
                    ticker=item.get("ticker"),
                    name=item.get("name"),
                )
            )
    return out


def _attention_events(now: datetime) -> tuple[list[dict], str | None]:
    response = attention.get_attention()
    as_of = response.get("as_of")
    out = []
    for index, item in enumerate(response.get("items", [])):
        if item.get("category") == "macro" and item.get("severity") == "low":
            continue
        key = f"{item.get('category')}:{item.get('meta_id') or item.get('ticker') or index}:{item.get('title')}"
        out.append(
            _event(
                source="attention",
                key=key,
                kind="attention",
                category=str(item.get("category", "market")),
                severity=str(item.get("severity", "low")),
                title=str(item.get("title", "확인 필요")),
                detail=str(item.get("detail", "")),
                link=str(item.get("link", "/home")),
                occurred_at=as_of,
                available_at=now.isoformat(),
                data_as_of=as_of,
                meta_id=item.get("meta_id"),
                ticker=item.get("ticker"),
                name=item.get("name"),
            )
        )
    return out, as_of


def _data_health_events(now: datetime) -> list[dict]:
    try:
        # 전체 시장 해석을 다시 계산하지 않고 Data Trust sidecar만 읽는다.
        status = overview._data_status()
    except Exception:
        logger.debug("Action Center data status load failed", exc_info=True)
        return []
    out = []
    for item in status:
        if item.get("level") not in {"warn", "error"}:
            continue
        out.append(
            _event(
                source="data_trust",
                key=f"{item.get('dataset')}:{item.get('level')}:{item.get('as_of')}",
                kind="data",
                category="data",
                severity="high" if item.get("level") == "error" else "medium",
                title=f"{item.get('label', item.get('dataset'))} Data {str(item.get('level')).title()}",
                detail=str(
                    item.get("detail") or item.get("message") or "데이터 상태 확인 필요"
                ),
                link="/data-trust",
                occurred_at=item.get("built_at") or item.get("as_of"),
                available_at=now.isoformat(),
                data_as_of=item.get("as_of"),
                actions=["open", "snooze", "dismiss"],
            )
        )
    return out


def _apply_states(
    items: list[dict], now: datetime, include_dismissed: bool
) -> list[dict]:
    try:
        states = action_state.list_states()
    except Exception:
        logger.warning("Action Center state load failed", exc_info=True)
        states = pd.DataFrame(columns=action_state.COLUMNS)
    by_id = {str(row.event_id): row for row in states.itertuples(index=False)}
    visible = []
    for item in items:
        stored = by_id.get(item["event_id"])
        state = str(stored.state) if stored is not None else "new"
        snoozed_until = _iso(stored.snoozed_until) if stored is not None else None
        if state == "snoozed" and snoozed_until:
            until = pd.Timestamp(snoozed_until)
            if until.tzinfo is None:
                until = until.tz_localize("UTC")
            if until <= pd.Timestamp(now):
                state, snoozed_until = "new", None
        item = {**item, "state": state, "snoozed_until": snoozed_until}
        if not include_dismissed and state in {"dismissed", "snoozed"}:
            continue
        visible.append(item)
    return visible


def build_actions(*, horizon_days: int = 30, include_dismissed: bool = False) -> dict:
    now = datetime.now(KST)
    attention_items, data_as_of = _attention_events(now)
    items = attention_items
    items.extend(_watchlist_alert_events(now))
    items.extend(_review_events(now, horizon_days))
    items.extend(_rebal_events(now, horizon_days))
    items.extend(_data_health_events(now))

    # 여러 소스가 같은 이벤트를 만들면 event_id 기준으로 한 번만 노출한다.
    deduped = {item["event_id"]: item for item in items}
    items = _apply_states(list(deduped.values()), now, include_dismissed)
    items.sort(
        key=lambda item: (
            SEVERITY_RANK.get(item["severity"], 3),
            item.get("scheduled_for") or "9999-12-31",
            item.get("title") or "",
        )
    )
    calendar = sorted(
        [item for item in items if item.get("scheduled_for")],
        key=lambda item: (
            item["scheduled_for"],
            SEVERITY_RANK.get(item["severity"], 3),
        ),
    )
    actionable = [item for item in items if item["severity"] in {"high", "medium"}]
    return {
        "generated_at": now.isoformat(),
        "data_as_of": data_as_of,
        "items": items,
        "calendar": calendar,
        "counts": {
            "total": len(items),
            "actionable": len(actionable),
            "high": sum(item["severity"] == "high" for item in items),
            "new": sum(item["state"] == "new" for item in items),
            "badge": sum(
                item["state"] == "new" and item["severity"] in {"high", "medium"}
                for item in items
            ),
            "scheduled": len(calendar),
        },
    }


@router.get("")
def get_actions(
    horizon_days: int = Query(30, ge=7, le=180),
    include_dismissed: bool = False,
):
    return build_actions(horizon_days=horizon_days, include_dismissed=include_dismissed)


@router.put("/{event_id}/state")
def update_action_state(event_id: str, request: ActionStateRequest):
    if len(event_id) != 24 or any(ch not in "0123456789abcdef" for ch in event_id):
        raise HTTPException(status_code=400, detail="invalid event_id")
    snoozed_until = request.snoozed_until
    if request.state == "snoozed":
        if snoozed_until is None:
            snoozed_until = datetime.combine(
                datetime.now(KST).date() + timedelta(days=1), time(9), KST
            )
        else:
            if snoozed_until.tzinfo is None:
                snoozed_until = snoozed_until.replace(tzinfo=KST)
            if snoozed_until <= datetime.now(snoozed_until.tzinfo):
                raise HTTPException(
                    status_code=422, detail="snoozed_until must be in the future"
                )
    else:
        snoozed_until = None
    action_state.set_state(event_id, request.state, snoozed_until)
    return {
        "event_id": event_id,
        "state": request.state,
        "snoozed_until": _iso(snoozed_until),
    }
