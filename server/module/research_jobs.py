"""Immutable, idempotent handoff from Research Radar to the research runner."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

DEFAULT_BUCKET = "insight-invest-datalake"
DEFAULT_JOB_PREFIX = "research-radar/jobs/"
ENTRY_ID = re.compile(r"^[0-9a-f]{64}$")
SCHEMA_VERSION = 1
WORKFLOW = "literature-intake"


def client():
    import boto3

    return boto3.client("s3")


def _prefix(value: str) -> str:
    return value.strip("/") + "/"


def request_key(entry_id: str, *, prefix: str = DEFAULT_JOB_PREFIX) -> str:
    if not ENTRY_ID.fullmatch(entry_id):
        raise ValueError("research job entry_id must be a sha256 digest")
    return f"{_prefix(prefix)}{entry_id}/request.json"


def automation_enabled(value: str | None = None) -> bool:
    raw = value if value is not None else os.environ.get("RESEARCH_AUTOMATION_ENABLED", "false")
    normalized = raw.strip().lower()
    if normalized not in {"true", "false"}:
        raise ValueError("RESEARCH_AUTOMATION_ENABLED must be true or false")
    return normalized == "true"


def _normalize_budget(value: str) -> str:
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("research monthly budget must be a positive USD amount") from exc
    if not amount.is_finite() or amount <= 0:
        raise ValueError("research monthly budget must be a positive USD amount")
    return format(amount.normalize(), "f")


def _canonical_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _input_snapshot(record: dict) -> dict:
    required = (
        "entry_id",
        "source_id",
        "source_name",
        "title",
        "url",
        "discovered_at",
    )
    if any(not isinstance(record.get(field), str) or not record[field] for field in required):
        raise ValueError("research job input is missing a required string field")
    if not ENTRY_ID.fullmatch(record["entry_id"]):
        raise ValueError("research job entry_id must be a sha256 digest")
    if record.get("research_lane") != "core" or record.get("notification_eligible") is not True:
        raise ValueError("only notification-eligible core research can create a job")
    authors = record.get("authors", [])
    if not isinstance(authors, list):
        raise ValueError("research job authors must be a list")
    return {
        "entry_id": record["entry_id"],
        "source_id": record["source_id"],
        "source_name": record["source_name"],
        "title": record["title"],
        "summary": str(record.get("summary") or ""),
        "authors": [str(author) for author in authors],
        "url": record["url"],
        "published_at": str(record.get("published_at") or ""),
        "discovered_at": record["discovered_at"],
        "research_lane": "core",
        "notification_eligible": True,
    }


def _request_payload(
    record: dict,
    *,
    now: datetime,
    enabled: bool,
    monthly_budget_usd: str | None,
) -> dict:
    snapshot = _input_snapshot(record)
    input_digest = hashlib.sha256(_canonical_bytes(snapshot)).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "job_id": snapshot["entry_id"],
        "workflow": WORKFLOW,
        "status": "requested" if enabled else "awaiting_activation",
        "created_at": now.astimezone(UTC).isoformat(timespec="seconds"),
        "input_digest_sha256": input_digest,
        "input": snapshot,
        "execution_policy": {
            "billable_execution_enabled": enabled,
            "monthly_budget_usd": monthly_budget_usd,
            "max_concurrency": 1,
            "human_curation_required": True,
            "human_prereg_required": True,
        },
    }


def _error_code(exc: Exception) -> str:
    response = getattr(exc, "response", {})
    if not isinstance(response, dict):
        return ""
    error = response.get("Error", {})
    return str(error.get("Code", "")) if isinstance(error, dict) else ""


def _validate_request(payload: dict, *, expected_entry_id: str | None = None) -> dict:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported research job schema_version")
    entry_id = payload.get("job_id")
    if not isinstance(entry_id, str) or not ENTRY_ID.fullmatch(entry_id):
        raise ValueError("invalid research job id")
    if expected_entry_id is not None and entry_id != expected_entry_id:
        raise ValueError("research job key and payload disagree")
    snapshot = payload.get("input")
    if not isinstance(snapshot, dict) or snapshot.get("entry_id") != entry_id:
        raise ValueError("invalid research job input")
    digest = hashlib.sha256(_canonical_bytes(snapshot)).hexdigest()
    if payload.get("input_digest_sha256") != digest:
        raise ValueError("research job input digest mismatch")
    return payload


def get_request(
    entry_id: str,
    *,
    s3: Any | None = None,
    bucket: str | None = None,
    prefix: str | None = None,
) -> dict:
    s3 = s3 or client()
    bucket = bucket or os.environ.get("RADAR_BUCKET", DEFAULT_BUCKET)
    prefix = prefix or os.environ.get("RADAR_JOB_PREFIX", DEFAULT_JOB_PREFIX)
    key = request_key(entry_id, prefix=prefix)
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    payload = json.load(io.BytesIO(body))
    return _validate_request(payload, expected_entry_id=entry_id)


def ensure_request(
    record: dict,
    *,
    s3: Any | None = None,
    bucket: str | None = None,
    prefix: str | None = None,
    now: datetime | None = None,
    enabled: bool | None = None,
    monthly_budget_usd: str | None = None,
) -> dict:
    """Create one immutable request, or return the identical existing request."""

    s3 = s3 or client()
    bucket = bucket or os.environ.get("RADAR_BUCKET", DEFAULT_BUCKET)
    prefix = prefix or os.environ.get("RADAR_JOB_PREFIX", DEFAULT_JOB_PREFIX)
    is_enabled = automation_enabled() if enabled is None else enabled
    budget = monthly_budget_usd
    if budget is None:
        budget = os.environ.get("RESEARCH_MONTHLY_BUDGET_USD") or None
    if is_enabled and budget is None:
        raise ValueError("enabled research automation requires a monthly budget")
    if is_enabled:
        budget = _normalize_budget(budget)
    payload = _request_payload(
        record,
        now=now or datetime.now(UTC),
        enabled=is_enabled,
        monthly_budget_usd=budget if is_enabled else None,
    )
    entry_id = payload["job_id"]
    key = request_key(entry_id, prefix=prefix)
    try:
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=_canonical_bytes(payload),
            ContentType="application/json",
            IfNoneMatch="*",
            Metadata={"input-sha256": payload["input_digest_sha256"]},
        )
        created = True
        effective = payload
    except Exception as exc:
        if _error_code(exc) not in {"PreconditionFailed", "412"}:
            raise
        created = False
        effective = get_request(entry_id, s3=s3, bucket=bucket, prefix=prefix)
        if effective["input_digest_sha256"] != payload["input_digest_sha256"]:
            raise ValueError("existing research job has a different input digest") from exc
    return {"created": created, "key": key, "job": effective}
