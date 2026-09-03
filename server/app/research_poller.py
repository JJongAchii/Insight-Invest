"""EventBridge handler for Research feed projection and iPhone Web Push."""

from __future__ import annotations

import logging
import os
from typing import Any

from module import action_push, research_feed, research_jobs

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
    pending_prefix = os.environ.get("RADAR_PENDING_PREFIX", research_feed.DEFAULT_PENDING_PREFIX)
    projection = research_feed.reconcile(s3=s3, bucket=bucket)
    pending = research_feed.pending_records(s3=s3, bucket=bucket, pending_prefix=pending_prefix)
    eligible = [(key, record) for key, record in pending if record["notification_eligible"]]
    suppressed_keys = [key for key, record in pending if not record["notification_eligible"]]
    jobs = [research_jobs.ensure_request(record, s3=s3, bucket=bucket) for _, record in eligible]
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
        "pending_seen": len(pending),
        "pending_eligible": len(eligible),
        "pending_suppressed": len(suppressed_keys),
        "pending_deleted": len(deleted_keys),
        "jobs": {
            "requested": len(jobs),
            "created": sum(job["created"] for job in jobs),
            "replayed": sum(not job["created"] for job in jobs),
            "billable_execution_enabled": research_jobs.automation_enabled(),
        },
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
