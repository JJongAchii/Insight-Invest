"""EventBridge 진입점 — 긴급 뉴스와 시장 급변을 Web Push로 알린다.

긴급 뉴스: 편집팀이 긴급으로 분류한 새 뉴스(`market_desk/board.json`). 나머지 뉴스는 알림 없이 뉴스 화면의 미확인
표시로 남는다. 같은 글은 delivery receipt로 기기마다 한 번만 보내고, 긴급 사건의 후속 발행은 발행 시각이 달라 다시 알린다.

시장 급변(스펙 2026-11-27 §7): 당일 사이드카·서킷브레이커 보도(보드 `alerts`)와 코스피 ±2%·코스닥 ±3% 첫 돌파
(`market_desk/input.json`의 `events`, Insight KRX 지도). 하루 3회까지, 사건마다 기기별 한 번.
"""

import logging
from datetime import datetime, timedelta
from urllib.parse import quote

from app.routers.market_desk import saved_news
from datastore import notifications, storage
from module import action_push
from module.kr_intraday import KST

logger = logging.getLogger(__name__)

# 구독을 늦게 켰거나 폴러가 쉬었던 동안의 지난 긴급 뉴스를 뒤늦게 울리지 않는다.
RECENT = timedelta(hours=3)
MARKET_PER_DAY = 3
INDEX_NAMES = {"KOSPI": "코스피", "KOSDAQ": "코스닥"}


def _listed(name: str, key: str) -> list:
    try:
        listed = storage.read_json("market_desk", name).get(key)
    except FileNotFoundError:
        return []
    return listed if isinstance(listed, list) else []


def _action(alert: dict) -> tuple[datetime, str, str]:
    return datetime.fromisoformat(alert["published_at"]), alert["id"], alert["title"]


def _crossing(event: dict) -> tuple[datetime, str, str]:
    sign = {"up": "+", "down": "-"}[event["direction"]]
    title = f"{INDEX_NAMES[event['index']]} {sign}{event['threshold']:g}% 돌파 ({event['chg_pct']:+.2f}%)"
    return datetime.strptime(event["observed_at"], "%Y-%m-%d %H:%M").replace(tzinfo=KST), event["id"], title


def _market_events(now: datetime) -> list[dict]:
    """오늘의 시장 급변을 일어난 순서로: 사이드카·서킷브레이커 보도와 지수 첫 돌파. 형식이 어긋난 한 건은 그 건만 뺀다."""
    found = []
    for name, key, read in (("board.json", "alerts", _action), ("input.json", "events", _crossing)):
        for raw in _listed(name, key):
            try:
                at, identity, title = read(raw)
                recent = at.astimezone(KST).date() == now.date() and timedelta(0) <= now - at <= RECENT
            except (KeyError, TypeError, ValueError, AttributeError):
                logger.warning("시장 급변 형식 오류 — 한 건 제외: %s/%s", name, raw.get("id") if isinstance(raw, dict) else None)
                continue
            if recent:
                found.append((at, {"event_id": f"market:{identity}", "severity": "high", "state": "new",
                                   "title": title, "link": "/home"}))
    return [event for _, event in sorted(found, key=lambda pair: pair[0])]


def _allowed(now: datetime) -> list[dict]:
    """하루 세 사건까지. 이미 알린 사건은 다른 기기에도 계속 대상이고(기기별 중복은 영수증이 막는다), 새 사건은 남은 몫만큼 먼저 일어난 것부터."""
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    sent = notifications.delivered_events("market:", start)
    room = MARKET_PER_DAY - len(sent)
    allowed = []
    for event in _market_events(now):
        if event["event_id"] in sent:
            allowed.append(event)
        elif room > 0:
            allowed.append(event)
            room -= 1
    return allowed


def _event(item: dict) -> dict:
    return {
        "event_id": f"news:{item['id']}:{item['published_at']}",
        "severity": "high",
        "state": "new",
        "title": item["headline"],
        "link": f"/news?item={quote(item['id'], safe='')}",
    }


def _urgent_news(now: datetime) -> dict:
    items, state, _ = saved_news(now)
    urgent = [
        item
        for item in items
        if item["priority"] == "urgent"
        and timedelta(0) <= now - datetime.fromisoformat(item["published_at"]) <= RECENT
    ]
    result = {"state": state, "urgent": len(urgent)}
    if urgent:
        result["push"] = action_push.dispatch(
            [_event(item) for item in urgent],
            notification_title="긴급 뉴스",
            digest_url="/news",
            tag_prefix="insight-news",
        )
    return result


def _market_alerts(now: datetime) -> dict:
    events = _allowed(now)
    result = {"market": len(events)}
    if events:
        result["market_push"] = action_push.dispatch(
            events, notification_title="시장 급변", digest_url="/home", tag_prefix="insight-market"
        )
    return result


def run(now: datetime | None = None) -> dict:
    """긴급 뉴스와 시장 급변은 입력이 다르다 — 한쪽을 읽지 못해도 다른 쪽 알림은 나간다."""
    now = now or datetime.now(KST)
    result = {"ok": True}
    for name, part in (("news", _urgent_news), ("market", _market_alerts)):
        try:
            result.update(part(now))
        except Exception as exc:
            logger.exception("%s 알림 확인 실패", name)
            result.update({"ok": False, f"{name}_error": type(exc).__name__})
    return result


def handler(event, context):  # noqa: ARG001
    try:
        return run()
    except Exception as exc:
        logger.exception("news notification poll failed")
        return {"ok": False, "error": type(exc).__name__}
