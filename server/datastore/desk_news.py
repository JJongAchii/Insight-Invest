"""뉴스를 마지막으로 본 시각 — 기기 간에 공유하는 단일 사용자 표식."""

import json
import logging
from datetime import datetime

from datastore import storage

SEEN_FILE = ("market_desk", "news_seen.json")
logger = logging.getLogger(__name__)


def load_seen_through() -> datetime | None:
    """A damaged marker counts every article as unseen; the next visit rewrites it."""
    try:
        seen = datetime.fromisoformat(storage.read_json(*SEEN_FILE)["seen_through"])
    except FileNotFoundError:
        return None
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        logger.warning("뉴스 확인 시각 형식 오류 — 다음 방문 때 다시 기록한다")
        return None
    return seen if seen.tzinfo else None


def save_seen_through(through: datetime) -> datetime:
    current = load_seen_through()
    effective = max(current, through) if current else through
    storage.write_json({"version": 1, "seen_through": effective.isoformat()}, *SEEN_FILE)
    return effective
