"""Materialize canonical Research Radar records for the Insight-Invest feed."""

from __future__ import annotations

import io
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from datastore import research as research_store

DEFAULT_BUCKET = "insight-invest-datalake"
DEFAULT_RECORD_PREFIX = "research-radar/public/records/"
DEFAULT_PENDING_PREFIX = "research-radar/realtime/pending/"
MAX_FETCH_WORKERS = 8
RESEARCH_LANES = frozenset({"core", "discovery", "context"})


def client():
    import boto3

    return boto3.client("s3")


def _prefix(value: str) -> str:
    return value.strip("/") + "/"


def _list_keys(s3: Any, *, bucket: str, prefix: str) -> list[str]:
    keys: list[str] = []
    token = ""
    while True:
        kwargs = {"Bucket": bucket, "Prefix": _prefix(prefix)}
        if token:
            kwargs["ContinuationToken"] = token
        response = s3.list_objects_v2(**kwargs)
        keys.extend(
            item["Key"] for item in response.get("Contents", []) if item["Key"].endswith(".json")
        )
        if not response.get("IsTruncated"):
            return sorted(keys)
        token = response["NextContinuationToken"]


def _record_id(key: str) -> str:
    return key.rsplit("/", 1)[-1].removesuffix(".json")


def _quality_fields(payload: dict, *, key: str) -> dict:
    schema_version = payload.get("schema_version", 1)
    if schema_version not in {1, 2}:
        raise ValueError(f"지원하지 않는 Radar record schema_version이다: {key}")
    if schema_version == 1:
        return {
            "quality_profile": "archive",
            "research_lane": "context",
            "relevance_reason": "legacy_record",
            "relevance_terms": [],
            "notification_eligible": False,
        }

    quality_profile = payload.get("quality_profile")
    research_lane = payload.get("research_lane")
    relevance_reason = payload.get("relevance_reason")
    relevance_terms = payload.get("relevance_terms")
    notification_eligible = payload.get("notification_eligible")
    if not isinstance(quality_profile, str) or not quality_profile:
        raise ValueError(f"Radar record quality_profile이 유효하지 않다: {key}")
    if research_lane not in RESEARCH_LANES:
        raise ValueError(f"Radar record research_lane이 유효하지 않다: {key}")
    if not isinstance(relevance_reason, str) or not relevance_reason:
        raise ValueError(f"Radar record relevance_reason이 유효하지 않다: {key}")
    if not isinstance(relevance_terms, list) or not all(
        isinstance(term, str) and term for term in relevance_terms
    ):
        raise ValueError(f"Radar record relevance_terms가 유효하지 않다: {key}")
    if not isinstance(notification_eligible, bool):
        raise ValueError(f"Radar record notification_eligible이 유효하지 않다: {key}")
    if notification_eligible and research_lane != "core":
        raise ValueError(f"core가 아닌 Radar record는 알림 대상일 수 없다: {key}")
    return {
        "quality_profile": quality_profile,
        "research_lane": research_lane,
        "relevance_reason": relevance_reason,
        "relevance_terms": relevance_terms,
        "notification_eligible": notification_eligible,
    }


def _normalize_projected_item(item: dict) -> dict:
    normalized = dict(item)
    normalized.setdefault("quality_profile", "archive")
    normalized.setdefault("research_lane", "context")
    normalized.setdefault("relevance_reason", "legacy_record")
    normalized.setdefault("relevance_terms", [])
    normalized.setdefault("notification_eligible", False)
    if not isinstance(normalized["quality_profile"], str) or not normalized["quality_profile"]:
        raise ValueError("research feed item quality_profile이 유효하지 않다")
    if normalized["research_lane"] not in RESEARCH_LANES:
        raise ValueError("research feed item lane이 유효하지 않다")
    if not isinstance(normalized["relevance_reason"], str) or not normalized["relevance_reason"]:
        raise ValueError("research feed item relevance_reason이 유효하지 않다")
    if not isinstance(normalized["relevance_terms"], list) or not all(
        isinstance(term, str) and term for term in normalized["relevance_terms"]
    ):
        raise ValueError("research feed item relevance_terms가 배열이 아니다")
    if not isinstance(normalized["notification_eligible"], bool):
        raise ValueError("research feed item notification_eligible이 bool이 아니다")
    if normalized["notification_eligible"] and normalized["research_lane"] != "core":
        raise ValueError("core가 아닌 research feed item은 알림 대상일 수 없다")
    return normalized


def _read_record(s3: Any, *, bucket: str, key: str) -> dict:
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    payload = json.load(io.BytesIO(body))
    entry_id = _record_id(key)
    if payload.get("entry_id_sha256") != entry_id:
        raise ValueError(f"Radar record digest가 key와 다르다: {key}")
    required = ("source_id", "source_name", "title", "url", "discovered_at")
    if any(not isinstance(payload.get(field), str) or not payload[field] for field in required):
        raise ValueError(f"Radar record 필수 필드가 유효하지 않다: {key}")
    authors = payload.get("authors", [])
    if not isinstance(authors, list):
        raise ValueError(f"Radar record authors가 배열이 아니다: {key}")
    return {
        "entry_id": entry_id,
        "source_id": payload["source_id"],
        "source_name": payload["source_name"],
        "title": payload["title"],
        "summary": str(payload.get("summary") or ""),
        "authors": [str(author) for author in authors],
        "url": payload["url"],
        "published_at": str(payload.get("published_at") or ""),
        "discovered_at": payload["discovered_at"],
        **_quality_fields(payload, key=key),
    }


def _read_records(s3: Any, *, bucket: str, keys: list[str]) -> list[dict]:
    if not keys:
        return []
    with ThreadPoolExecutor(max_workers=min(MAX_FETCH_WORKERS, len(keys))) as pool:
        return list(pool.map(lambda key: _read_record(s3, bucket=bucket, key=key), keys))


def _timestamp(item: dict) -> datetime:
    for field in ("discovered_at", "published_at"):
        value = item.get(field)
        if not value:
            continue
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
        except ValueError:
            continue
    return datetime.min.replace(tzinfo=UTC)


def reconcile(
    *,
    s3: Any | None = None,
    bucket: str | None = None,
    record_prefix: str | None = None,
    now: datetime | None = None,
) -> dict:
    s3 = s3 or client()
    bucket = bucket or os.environ.get("RADAR_BUCKET", DEFAULT_BUCKET)
    record_prefix = record_prefix or os.environ.get("RADAR_RECORD_PREFIX", DEFAULT_RECORD_PREFIX)
    captured_at = (now or datetime.now(UTC)).astimezone(UTC)
    keys = _list_keys(s3, bucket=bucket, prefix=record_prefix)
    canonical_ids = {_record_id(key) for key in keys}

    current = research_store.load_feed()
    current_items = {}
    migrated = False
    for item in current["items"]:
        if not isinstance(item, dict) or not isinstance(item.get("entry_id"), str):
            continue
        normalized = _normalize_projected_item(item)
        migrated = migrated or normalized != item
        current_items[normalized["entry_id"]] = normalized
    missing_keys = [key for key in keys if _record_id(key) not in current_items]
    added_items = _read_records(s3, bucket=bucket, keys=missing_keys)
    for item in added_items:
        current_items[item["entry_id"]] = item

    removed = set(current_items) - canonical_ids
    for entry_id in removed:
        current_items.pop(entry_id, None)
    items = sorted(
        current_items.values(),
        key=lambda item: (_timestamp(item), item["entry_id"]),
        reverse=True,
    )
    changed = bool(added_items or removed or migrated or not current["generated_at"])
    if changed:
        research_store.save_feed(
            {
                "schema_version": 1,
                "generated_at": captured_at.isoformat(timespec="seconds"),
                "items": items,
            }
        )
    return {
        "records": len(items),
        "added": len(added_items),
        "removed": len(removed),
        "updated": changed,
    }


def pending_records(
    *,
    s3: Any,
    bucket: str,
    pending_prefix: str = DEFAULT_PENDING_PREFIX,
) -> list[tuple[str, dict]]:
    keys = _list_keys(s3, bucket=bucket, prefix=pending_prefix)
    records = _read_records(s3, bucket=bucket, keys=keys)
    pairs = list(zip(keys, records, strict=True))
    return sorted(
        pairs,
        key=lambda pair: (_timestamp(pair[1]), pair[1]["entry_id"]),
        reverse=True,
    )


def delete_pending(*, s3: Any, bucket: str, keys: list[str]) -> None:
    for key in keys:
        s3.delete_object(Bucket=bucket, Key=key)
