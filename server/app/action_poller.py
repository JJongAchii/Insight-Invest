"""EventBridge 진입점 — 새 Action Center 항목을 Web Push로 전송한다."""

import logging

from app.routers.actions import build_actions
from module.action_push import dispatch

logger = logging.getLogger(__name__)


def handler(event, context):
    try:
        response = build_actions(horizon_days=30)
        return dispatch(response["items"])
    except Exception as exc:
        logger.exception("action notification poll failed")
        return {"enabled": False, "sent": 0, "failed": 1, "error": type(exc).__name__}
