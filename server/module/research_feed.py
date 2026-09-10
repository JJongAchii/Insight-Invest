"""Materialize canonical Research Radar records for the Insight-Invest feed."""

from __future__ import annotations

import io
import hashlib
import json
import os
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from datastore import research as research_store
from module import research_review
from qdata.radar_notifications import is_incremental

DEFAULT_BUCKET = "insight-invest-datalake"
DEFAULT_RECORD_PREFIX = "research-radar/public/records/"
DEFAULT_PENDING_PREFIX = "research-radar/realtime/pending/"
MAX_FETCH_WORKERS = 8
RESEARCH_LANES = frozenset({"core", "discovery", "context"})
EVIDENCE_DIMENSIONS = ("method", "data", "validation", "result")
CONTENT_PROVENANCE = frozenset({"release_detail", "full_body"})
CONFIRMED_RESOLUTIONS = frozenset(
    {"maintainer_published", "maintainer_confirmed", "commit_linked"}
)
RESOLUTION_STATUSES = CONFIRMED_RESOLUTIONS | {"unresolved"}
QUALITY_GATE_FIELDS = frozenset(
    {"transport", "content", "topic", "evidence", "notification"}
)
SHA256 = re.compile(r"^[0-9a-f]{64}$")
PUBLICATION_TYPES = frozenset(
    {"research_article", "research_paper", "preprint", "research_digest"}
)


def _publication_fields(payload: dict, *, key: str) -> dict:
    lane = payload.get("research_lane")
    scope = payload.get("analysis_scope")
    if payload.get("item_type") not in PUBLICATION_TYPES or lane not in RESEARCH_LANES:
        raise ValueError(f"invalid publication type/lane: {key}")
    if scope not in {"full_article", "full_pdf", "pdf_excerpt", "abstract"}:
        raise ValueError(f"invalid publication access scope: {key}")
    for name in (
        "document_identity",
        "source_digest",
        "published_at",
        "summary",
        "parser_version",
    ):
        if not isinstance(payload.get(name), str) or not payload[name].strip():
            raise ValueError(f"missing publication {name}: {key}")
    if not SHA256.fullmatch(payload["source_digest"]):
        raise ValueError(f"invalid publication digest: {key}")
    if not isinstance(payload.get("authors"), list) or not payload["authors"]:
        raise ValueError(f"publication authors missing: {key}")
    if research_store.parse_timestamp(payload["published_at"]) is None:
        raise ValueError(f"invalid publication timestamp: {key}")
    for field in ("url", "pdf_url"):
        value = payload.get(field)
        if value and (
            urlsplit(value).scheme not in {"https", "http"}
            or not urlsplit(value).hostname
        ):
            raise ValueError(f"invalid publication {field}: {key}")
    notifiable = payload.get("notification_eligible")
    terms = payload.get("relevance_terms")
    if not isinstance(notifiable, bool) or not isinstance(terms, list):
        raise ValueError(f"invalid publication eligibility: {key}")
    if lane == "core" and (
        scope == "abstract"
        or payload.get("item_type") == "research_digest"
        or not terms
        or payload.get("source_chars", 0) < 1000
    ):
        raise ValueError(f"publication lacks readable core content: {key}")
    if notifiable and lane != "core":
        raise ValueError(f"non-core publication cannot notify: {key}")
    fields = (
        "quality_profile",
        "research_lane",
        "relevance_reason",
        "relevance_terms",
        "notification_eligible",
        "notification_origin",
        "item_type",
        "content_provenance",
        "source_digest",
        "document_identity",
        "pdf_url",
        "doi",
        "date_precision",
        "source_chars",
        "parser_version",
        "access_status",
        "analysis_scope",
        "analysis_status",
        "summary_kind",
        "validation_status",
        "discovery_sources",
        "discovered_by",
        "identity_aliases",
        "first_discovered_at",
        "updated_at",
        "index_updated_at",
        "publisher",
        "original_access_status",
        "original_access_error",
        "open_access_url",
        "arxiv_version",
        "crossref",
    )
    result = {name: payload.get(name) for name in fields}
    result["record_schema_version"] = 4
    result["editorial_candidate_lane"] = payload.get("editorial_candidate_lane", lane)
    result["notification_candidate"] = payload.get("notification_candidate", notifiable)
    if payload.get("quality_profile") == "academic-discovery-v1":
        # Index metadata/original retrieval qualification does not authorize paid
        # summarization or a core alert. Register the readable source immediately.
        result.update(
            research_lane="discovery",
            editorial_candidate_lane="discovery",
            notification_eligible=False,
            notification_candidate=False,
            analysis_status="not_requested",
        )
    apply_editorial_analysis({**payload, **result}, target=result)
    return result


def apply_editorial_analysis(item: dict, *, target: dict | None = None) -> None:
    target = item if target is None else target
    if item.get("quality_profile") == "academic-discovery-v1":
        target.update(
            research_lane="discovery",
            editorial_candidate_lane="discovery",
            notification_eligible=False,
            notification_candidate=False,
            analysis_status="not_requested",
            editorial_review_status="pending",
        )
        return
    candidate = item.get("editorial_candidate_lane", item.get("research_lane"))
    if not research_review.enabled() and item.get("analysis_status") != "not_requested":
        # Preserve drafts/receipts and library identity. A key or old ready cache
        # must not turn an unqualified editorial feature into a release.
        target.update(
            editorial_candidate_lane=candidate,
            research_lane="discovery" if candidate == "core" else candidate,
            relevance_reason="editorial_release_pending",
            editorial_review_status="pending",
            notification_eligible=False,
        )
        return
    brief = item.get("analysis", {}).get("brief")
    review_state = research_review.state(item)
    target["editorial_review_status"] = review_state
    if brief:
        kind = brief.get("content_kind")
        relevant = (
            brief.get("quant_relevant") is True and brief.get("substantive") is True
        )
        if kind not in {"research", "practitioner", "market_commentary", "other"}:
            # Old briefs stay readable, but cannot bypass the new classification.
            lane, reason = "discovery", "classification_pending"
        elif review_state != "accepted" or item.get("analysis_status") != "ready":
            lane = "discovery" if candidate == "core" else candidate
            reason = (
                "review_rejected" if review_state == "rejected" else "review_pending"
            )
        elif kind == "market_commentary":
            lane, reason = "context", "market_commentary"
        elif relevant and kind in {"research", "practitioner"}:
            if not brief.get("why_read"):
                lane, reason = "discovery", "reading_value_missing"
            else:
                lane, reason = candidate, "source_checked_reading_brief"
        else:
            lane, reason = "context", "editorial_topic_mismatch"
        target["research_lane"] = lane
        target["relevance_reason"] = reason
        target["notification_eligible"] = bool(
            lane == "core"
            and review_state == "accepted"
            and item.get("notification_candidate")
            and is_incremental(item)
        )
        if target["notification_eligible"] and not item.get("available_at"):
            target["available_at"] = item["analysis"]["review"]["checked_at"]
    elif candidate == "core":
        target["research_lane"] = "discovery"
        target["relevance_reason"] = "analysis_pending"
        target["notification_eligible"] = False


def _topic_concept(term: str) -> str:
    normalized = unicodedata.normalize("NFKC", term).casefold()
    tokens = re.findall(r"\w+", normalized)
    concepts = []
    for token in tokens:
        if (
            token.endswith("ies")
            and token not in {"series", "species"}
            and len(token) > 4
        ):
            token = f"{token[:-3]}y"
        elif (
            token.endswith("s")
            and len(token) > 3
            and not token.endswith(("ss", "us", "is"))
        ):
            token = token[:-1]
        concepts.append(token)
    return "".join(concepts)


def _distinct_topic_count(terms: list[str]) -> int:
    return len({concept for term in terms if (concept := _topic_concept(term))})


def client():
    import boto3

    return boto3.client("s3")


def _prefix(value: str) -> str:
    return value.strip("/") + "/"


def _list_objects(s3: Any, *, bucket: str, prefix: str) -> list[dict]:
    objects: list[dict] = []
    token = ""
    while True:
        kwargs = {"Bucket": bucket, "Prefix": _prefix(prefix)}
        if token:
            kwargs["ContinuationToken"] = token
        response = s3.list_objects_v2(**kwargs)
        objects.extend(
            item
            for item in response.get("Contents", [])
            if item["Key"].endswith(".json")
        )
        if not response.get("IsTruncated"):
            return sorted(objects, key=lambda item: item["Key"])
        token = response["NextContinuationToken"]


def _list_keys(s3: Any, *, bucket: str, prefix: str) -> list[str]:
    return [item["Key"] for item in _list_objects(s3, bucket=bucket, prefix=prefix)]


def _record_id(key: str) -> str:
    return key.rsplit("/", 1)[-1].removesuffix(".json")


def _quality_fields(payload: dict, *, key: str) -> dict:
    schema_version = payload.get("schema_version", 1)
    if schema_version == 4:
        return _publication_fields(payload, key=key)
    if isinstance(schema_version, bool) or schema_version not in {1, 2, 3}:
        raise ValueError(f"지원하지 않는 Radar record schema_version이다: {key}")
    if schema_version in {1, 2}:
        return {
            "record_schema_version": schema_version,
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
    item_type = payload.get("item_type")
    content_provenance = payload.get("content_provenance")
    evidence_dimensions = payload.get("evidence_dimensions")
    evidence_excerpts = payload.get("evidence_excerpts")
    source_digest = payload.get("source_digest")
    resolution_status = payload.get("resolution_status")
    quality_gates = payload.get("quality_gates")
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
    if item_type != "evidence_update":
        raise ValueError(f"Radar record item_type이 유효하지 않다: {key}")
    if content_provenance not in CONTENT_PROVENANCE:
        raise ValueError(f"Radar record content_provenance가 유효하지 않다: {key}")
    if (
        not isinstance(evidence_dimensions, list)
        or not all(
            isinstance(dimension, str) and dimension in EVIDENCE_DIMENSIONS
            for dimension in evidence_dimensions
        )
        or len(evidence_dimensions) != len(set(evidence_dimensions))
    ):
        raise ValueError(f"Radar record evidence_dimensions가 유효하지 않다: {key}")
    if not isinstance(evidence_excerpts, dict) or set(evidence_excerpts) != set(
        evidence_dimensions
    ):
        raise ValueError(f"Radar record evidence_excerpts가 유효하지 않다: {key}")
    for dimension, excerpts in evidence_excerpts.items():
        if (
            not isinstance(excerpts, list)
            or not 1 <= len(excerpts) <= 2
            or not all(
                isinstance(excerpt, str) and excerpt.strip() and len(excerpt) <= 400
                for excerpt in excerpts
            )
        ):
            raise ValueError(
                f"Radar record {dimension} evidence excerpt가 유효하지 않다: {key}"
            )
    if not isinstance(source_digest, str) or not SHA256.fullmatch(source_digest):
        raise ValueError(f"Radar record source_digest가 유효하지 않다: {key}")
    if resolution_status not in RESOLUTION_STATUSES:
        raise ValueError(f"Radar record resolution_status가 유효하지 않다: {key}")
    if (
        not isinstance(quality_gates, dict)
        or set(quality_gates) != QUALITY_GATE_FIELDS
        or not all(isinstance(value, bool) for value in quality_gates.values())
    ):
        raise ValueError(f"Radar record quality_gates가 유효하지 않다: {key}")

    evidence_gate = "method" in evidence_dimensions and any(
        dimension in evidence_dimensions
        for dimension in ("data", "validation", "result")
    )
    if quality_gates["evidence"] is not evidence_gate:
        raise ValueError(
            f"Radar record evidence gate와 excerpt가 일치하지 않는다: {key}"
        )
    if quality_gates["topic"] and _distinct_topic_count(relevance_terms) < 2:
        raise ValueError(f"Radar record topic gate 근거가 부족하다: {key}")
    if quality_gates["notification"] is not notification_eligible:
        raise ValueError(f"Radar record notification gate가 일치하지 않는다: {key}")
    core_gates = all(
        quality_gates[field] for field in ("transport", "content", "topic", "evidence")
    )
    if research_lane == "core" and (
        not core_gates or resolution_status not in CONFIRMED_RESOLUTIONS
    ):
        raise ValueError(
            f"Radar core record의 품질 또는 resolution이 유효하지 않다: {key}"
        )
    if research_lane == "discovery" and (
        not core_gates or resolution_status != "unresolved"
    ):
        raise ValueError(
            f"Radar discovery record의 품질 또는 resolution이 유효하지 않다: {key}"
        )
    if research_lane == "context" and core_gates:
        raise ValueError(f"품질 gate를 통과한 Radar record가 context로 표시됐다: {key}")
    if notification_eligible and (
        research_lane != "core" or resolution_status not in CONFIRMED_RESOLUTIONS
    ):
        raise ValueError(
            f"Radar record notification eligibility가 유효하지 않다: {key}"
        )
    return {
        "record_schema_version": 3,
        "quality_profile": quality_profile,
        "research_lane": "updates",
        "evidence_lane": research_lane,
        "relevance_reason": relevance_reason,
        "relevance_terms": relevance_terms,
        "notification_eligible": False,
        "item_type": item_type,
        "content_provenance": content_provenance,
        "evidence_dimensions": evidence_dimensions,
        "evidence_excerpts": evidence_excerpts,
        "source_digest": source_digest,
        "resolution_status": resolution_status,
        "quality_gates": {**quality_gates, "notification": False},
    }


def _normalize_projected_item(item: dict) -> dict:
    normalized = dict(item)
    schema_version = normalized.get("record_schema_version", 1)
    if isinstance(schema_version, bool):
        raise ValueError("research feed item record_schema_version이 유효하지 않다")
    if schema_version in {1, 2}:
        normalized.update(
            {
                "record_schema_version": schema_version,
                "quality_profile": "archive",
                "research_lane": "context",
                "relevance_reason": "legacy_record",
                "relevance_terms": [],
                "notification_eligible": False,
            }
        )
        for field in (
            "item_type",
            "content_provenance",
            "evidence_dimensions",
            "evidence_excerpts",
            "source_digest",
            "resolution_status",
            "quality_gates",
        ):
            normalized.pop(field, None)
        return normalized
    if schema_version == 4:
        normalized.update(
            _publication_fields(
                {**normalized, "schema_version": 4}, key="projected item"
            )
        )
        return normalized
    if schema_version != 3:
        raise ValueError("research feed item record_schema_version이 유효하지 않다")
    normalized.update(
        _quality_fields(
            {
                **normalized,
                "schema_version": 3,
                "research_lane": normalized.get(
                    "evidence_lane", normalized.get("research_lane")
                ),
            },
            key="projected item",
        )
    )
    return normalized


def _read_record(s3: Any, *, bucket: str, key: str) -> dict:
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    payload = json.load(io.BytesIO(body))
    entry_id = _record_id(key)
    if payload.get("entry_id_sha256") != entry_id:
        raise ValueError(f"Radar record digest가 key와 다르다: {key}")
    if (
        payload.get("schema_version") == 4
        and hashlib.sha256(
            str(payload.get("document_identity", "")).encode()
        ).hexdigest()
        != entry_id
    ):
        raise ValueError(f"publication identity differs from key: {key}")
    required = ("source_id", "source_name", "title", "url", "discovered_at")
    if any(
        not isinstance(payload.get(field), str) or not payload[field]
        for field in required
    ):
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
        return list(
            pool.map(lambda key: _read_record(s3, bucket=bucket, key=key), keys)
        )


def _timestamp(item: dict) -> datetime:
    for field in ("discovered_at", "published_at"):
        value = item.get(field)
        if not value:
            continue
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return (
                parsed.replace(tzinfo=UTC)
                if parsed.tzinfo is None
                else parsed.astimezone(UTC)
            )
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
    record_prefix = record_prefix or os.environ.get(
        "RADAR_RECORD_PREFIX", DEFAULT_RECORD_PREFIX
    )
    captured_at = (now or datetime.now(UTC)).astimezone(UTC)
    objects = _list_objects(s3, bucket=bucket, prefix=record_prefix)
    keys = [item["Key"] for item in objects]
    etags = {item["Key"]: item.get("ETag") for item in objects}
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
    refresh_keys = [
        key
        for key in keys
        if not etags[key]
        or current_items.get(_record_id(key), {}).get("source_etag") != etags[key]
    ]
    refreshed = _read_records(s3, bucket=bucket, keys=refresh_keys)
    added = updated = 0
    for key, item in zip(refresh_keys, refreshed, strict=True):
        prior = current_items.get(item["entry_id"])
        item["source_etag"] = etags[key]
        if prior and prior.get("available_at"):
            # A revised document remains the same library item, including its
            # first core-availability timestamp. Reanalysis must not replay badges.
            item["available_at"] = prior["available_at"]
        if prior and prior.get("source_digest") == item.get("source_digest"):
            for field in (
                "analysis",
                "analysis_status",
                "analysis_updated_at",
                "analysis_retry",
            ):
                if field in prior:
                    item[field] = prior[field]
            if item.get("record_schema_version") == 4:
                apply_editorial_analysis(item)
        if prior is None:
            added += 1
        elif prior != item:
            updated += 1
        current_items[item["entry_id"]] = item

    removed = set(current_items) - canonical_ids
    for entry_id in removed:
        current_items.pop(entry_id, None)
    items = sorted(
        current_items.values(),
        key=lambda item: (_timestamp(item), item["entry_id"]),
        reverse=True,
    )
    changed = bool(
        added or updated or removed or migrated or not current["generated_at"]
    )
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
        "added": added,
        "revised": updated,
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
