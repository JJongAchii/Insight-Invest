"""EventBridge handler for Research feed projection and iPhone Web Push."""

from __future__ import annotations

import logging
import os
from typing import Any

from module import action_push, research_analysis, research_feed
from datastore import research as research_store

logger = logging.getLogger(__name__)


def _event(record: dict) -> dict:
    entry_id = record["entry_id"]
    return {
        "event_id": f"research:{entry_id}",
        "severity": "medium",
        "state": "new",
        "title": record["title"],
        "link": f"/research?entry={entry_id}",
    }


def run(*, s3: Any | None = None) -> dict:
    s3 = s3 or research_feed.client()
    bucket = os.environ.get("RADAR_BUCKET", research_feed.DEFAULT_BUCKET)
    pending_prefix = os.environ.get(
        "RADAR_PENDING_PREFIX", research_feed.DEFAULT_PENDING_PREFIX
    )
    projection = research_feed.reconcile(s3=s3, bucket=bucket)
    try:
        analysis = research_analysis.enrich()
    except Exception as exc:
        # Already analyzed items can still settle if the optional analysis
        # queue/budget storage fails. Unanalyzed items stay deferred below.
        logger.warning("research analysis unavailable: %s", type(exc).__name__)
        analysis = {"enabled": False, "reason": type(exc).__name__, "completed": 0}
    projected = {item["entry_id"]: item for item in research_store.load_feed()["items"]}
    pending = research_feed.pending_records(
        s3=s3, bucket=bucket, pending_prefix=pending_prefix
    )
    eligible, suppressed_keys, deferred = [], [], 0
    for key, record in pending:
        item = projected.get(record["entry_id"], record)
        if record.get("record_schema_version") == 4 and record.get(
            "notification_candidate"
        ):
            if item.get("analysis_status") != "ready":
                deferred += 1
                continue
        if item.get("notification_eligible"):
            eligible.append((key, item))
        else:
            suppressed_keys.append(key)
    push = action_push.dispatch(
        [_event(record) for _, record in eligible],
        notification_title="Research Radar",
        digest_url="/research?view=unread",
        tag_prefix="insight-research",
    )
    enabled = bool(push.get("enabled"))
    subscriptions = push.get("subscriptions", 0)
    settled = enabled and push.get("failed", 0) == push.get("disabled", 0)
    delivery_ready = enabled and subscriptions > 0
    deleted_keys = list(suppressed_keys)
    if eligible and settled:
        deleted_keys.extend(key for key, _ in eligible)
    if deleted_keys:
        research_feed.delete_pending(s3=s3, bucket=bucket, keys=deleted_keys)
    return {
        "ok": settled or not eligible,
        "delivery_ready": delivery_ready,
        "projection": projection,
        "analysis": analysis,
        "pending_seen": len(pending),
        "pending_eligible": len(eligible),
        "pending_suppressed": len(suppressed_keys),
        "pending_deferred": deferred,
        "pending_deleted": len(deleted_keys),
        "push": push,
    }


def handler(event, context):  # noqa: ARG001
    try:
        result = run()
        if not result["ok"] or not result["delivery_ready"]:
            logger.warning("research poller did not settle: %s", result)
        return result
    except Exception as exc:
        logger.exception("research poller failed")
        return {"ok": False, "error": type(exc).__name__}
