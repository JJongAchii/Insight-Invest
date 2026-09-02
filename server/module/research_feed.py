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
    current_items = {
        item["entry_id"]: item
        for item in current["items"]
        if isinstance(item, dict) and isinstance(item.get("entry_id"), str)
    }
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
    changed = bool(added_items or removed or not current["generated_at"])
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
