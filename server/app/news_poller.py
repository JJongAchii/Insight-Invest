"""EventBridge 진입점 — 편집팀이 긴급으로 분류한 새 뉴스를 Web Push로 알린다.

저장된 발행본(`market_desk/board.json`)만 읽는다. 나머지 뉴스는 알림 없이 뉴스 화면의 미확인
표시로 남는다. 같은 글은 delivery receipt로 기기마다 한 번만 보내고, 긴급 사건의 후속 발행은
발행 시각이 달라 다시 알린다.
"""

import logging
from datetime import datetime, timedelta
from urllib.parse import quote

from app.routers.market_desk import saved_news
from module import action_push
from module.kr_intraday import KST

logger = logging.getLogger(__name__)

# 구독을 늦게 켰거나 폴러가 쉬었던 동안의 지난 긴급 뉴스를 뒤늦게 울리지 않는다.
RECENT = timedelta(hours=3)


def _event(item: dict) -> dict:
    return {
        "event_id": f"news:{item['id']}:{item['published_at']}",
        "severity": "high",
        "state": "new",
        "title": item["headline"],
        "link": f"/news?item={quote(item['id'], safe='')}",
    }


def run(now: datetime | None = None) -> dict:
    now = now or datetime.now(KST)
    items, state, _ = saved_news(now)
    urgent = [
        item
        for item in items
        if item["priority"] == "urgent"
        and timedelta(0) <= now - datetime.fromisoformat(item["published_at"]) <= RECENT
    ]
    result = {"ok": True, "state": state, "urgent": len(urgent)}
    if urgent:
        result["push"] = action_push.dispatch(
            [_event(item) for item in urgent],
            notification_title="긴급 뉴스",
            digest_url="/news",
            tag_prefix="insight-news",
        )
    return result


def handler(event, context):  # noqa: ARG001
    try:
        return run()
    except Exception as exc:
        logger.exception("news notification poll failed")
        return {"ok": False, "error": type(exc).__name__}
