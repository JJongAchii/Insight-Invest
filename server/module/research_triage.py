"""Deterministic OpenAI Batch packets and fail-closed Research Radar triage.

The module is deliberately split at the paid boundary: packets and result views are
pure data transformations, while :func:`submit_packet` requires explicit runtime
authorization and an atomic monthly S3 reservation before touching the API.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
from datetime import UTC, datetime
from decimal import ROUND_UP, Decimal, InvalidOperation
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from module import research_jobs

SCHEMA_VERSION = 1
MODEL = "gpt-5.6-luna"
BATCH_ENDPOINT = "/v1/responses"
COMPLETION_WINDOW = "24h"
MAX_OUTPUT_TOKENS = 700
MAX_SUMMARY_CHARS = 12_000
INPUT_OVERHEAD_TOKENS = 2_048
MIN_INPUT_TOKEN_CEILING = 32_000
MAX_BATCH_REQUESTS = 50_000
MAX_BATCH_FILE_BYTES = 200_000_000

# 2026-09-03 OpenAI list prices after the Batch API's 50% discount.  These
# constants are intentionally conservative for cached input, which is costed as
# uncached input here.  Activation requires reviewing them against current prices.
BATCH_INPUT_USD_PER_MILLION = Decimal("0.10")
BATCH_OUTPUT_USD_PER_MILLION = Decimal("0.60")

DEFAULT_TRIAGE_PREFIX = "research-radar/triage/"
TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
}

PRIMARY_FAMILIES = (
    "cross_sectional_momentum",
    "time_series_momentum",
    "value",
    "quality",
    "carry",
    "volatility",
    "statistical_arbitrage",
    "market_microstructure",
    "execution",
    "portfolio_construction",
    "macro_allocation",
    "machine_learning_forecasting",
    "risk_management",
    "other",
)
ASSET_CLASSES = (
    "equities",
    "fixed_income",
    "fx",
    "commodities",
    "crypto",
    "options",
    "futures",
    "multi_asset",
    "unspecified",
)
EVIDENCE_TYPES = (
    "peer_reviewed_empirical",
    "working_paper_empirical",
    "institutional_research",
    "methodology",
    "survey",
    "commentary",
    "unknown",
)
IMPLEMENTATION_COMPLEXITIES = ("low", "medium", "high", "unknown")
RISK_FLAGS = (
    "possible_lookahead",
    "survivorship_bias",
    "unclear_costs",
    "unclear_data_availability",
    "small_sample",
    "weak_reproducibility",
    "marketing_claim",
    "none_identified",
)

SYSTEM_INSTRUCTIONS = """You classify research metadata for a personal quantitative-research inbox.
Use only the supplied metadata; do not claim that you opened the URL. Extract what is stated, keep
uncertainty explicit, and write the two prose fields in concise Korean. This output is descriptive:
never decide whether a source passes review, should be adopted, implemented, or backtested."""

TRIAGE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "relevant_to_quant_research": {"type": "boolean"},
        "primary_family": {"type": "string", "enum": list(PRIMARY_FAMILIES)},
        "asset_classes": {
            "type": "array",
            "items": {"type": "string", "enum": list(ASSET_CLASSES)},
            "maxItems": 4,
        },
        "evidence_type": {"type": "string", "enum": list(EVIDENCE_TYPES)},
        "implementation_complexity": {
            "type": "string",
            "enum": list(IMPLEMENTATION_COMPLEXITIES),
        },
        "data_requirements": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5,
        },
        "mechanism_terms": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 5,
        },
        "summary_ko": {"type": "string"},
        "relevance_reason_ko": {"type": "string"},
        "risk_flags": {
            "type": "array",
            "items": {"type": "string", "enum": list(RISK_FLAGS)},
            "maxItems": 5,
        },
    },
    "required": [
        "relevant_to_quant_research",
        "primary_family",
        "asset_classes",
        "evidence_type",
        "implementation_complexity",
        "data_requirements",
        "mechanism_terms",
        "summary_ko",
        "relevance_reason_ko",
        "risk_flags",
    ],
    "additionalProperties": False,
}


def _canonical_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _money(value: str | Decimal, *, allow_zero: bool = False) -> Decimal:
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("budget values must be finite USD amounts") from exc
    if not amount.is_finite() or amount < 0 or (amount == 0 and not allow_zero):
        raise ValueError("budget values must be positive USD amounts")
    return amount


def _money_string(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.000001"), rounding=ROUND_UP), "f")


def _source_key(url: str) -> str:
    parsed = urlsplit(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("research request URL must be absolute http(s)")
    host = parsed.hostname.lower()
    path = re.sub(r"/{2,}", "/", parsed.path or "/")

    if host in {"arxiv.org", "www.arxiv.org"}:
        match = re.match(r"/(?:abs|pdf|html)/([^/?#]+)", path, re.IGNORECASE)
        if match:
            arxiv_id = re.sub(r"\.pdf$", "", match.group(1), flags=re.IGNORECASE)
            return "arxiv:" + re.sub(r"v\d+$", "", arxiv_id, flags=re.IGNORECASE).lower()
    if host in {"doi.org", "dx.doi.org"} and path.strip("/"):
        return "doi:" + path.strip("/").lower()

    port = parsed.port
    netloc = host
    if port and not (
        (parsed.scheme.lower() == "http" and port == 80)
        or (parsed.scheme.lower() == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"
    query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in TRACKING_QUERY_KEYS:
            continue
        query.append((key, value))
    normalized_path = path.rstrip("/") or "/"
    return urlunsplit(
        (parsed.scheme.lower(), netloc, normalized_path, urlencode(sorted(query)), "")
    )


def _response_body(request: dict) -> dict:
    snapshot = request["input"]
    metadata = {
        "entry_id": snapshot["entry_id"],
        "source_id": snapshot["source_id"][:200],
        "source_name": snapshot["source_name"][:300],
        "title": snapshot["title"][:500],
        "summary": snapshot.get("summary", "")[:MAX_SUMMARY_CHARS],
        "authors": [author[:300] for author in snapshot.get("authors", [])[:20]],
        "url": snapshot["url"][:2_000],
        "published_at": snapshot.get("published_at", "")[:100],
    }
    return {
        "model": MODEL,
        "instructions": SYSTEM_INSTRUCTIONS,
        "input": "Classify this research metadata:\n" + _canonical_bytes(metadata).decode("utf-8"),
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "reasoning": {"effort": "none"},
        "store": False,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "research_triage",
                "strict": True,
                "schema": TRIAGE_OUTPUT_SCHEMA,
            }
        },
    }


def _authorization(request: dict) -> tuple[bool, str | None, str | None]:
    policy = request.get("execution_policy")
    if not isinstance(policy, dict):
        return False, None, "missing_execution_policy"
    budget = policy.get("monthly_budget_usd")
    if request.get("status") != "requested":
        return False, None, "request_not_activated"
    if policy.get("billable_execution_enabled") is not True:
        return False, None, "billable_execution_disabled"
    try:
        normalized_budget = _money_string(_money(str(budget)))
    except ValueError:
        return False, None, "invalid_request_budget"
    return True, normalized_budget, None


def build_triage_packet(requests: Iterable[dict]) -> dict:
    """Build stable Batch JSONL, removing exact input and canonical-URL duplicates."""

    validated: list[dict] = []
    seen_job_ids: dict[str, str] = {}
    for request in requests:
        request = research_jobs.validate_request(request)
        if request.get("workflow") != research_jobs.WORKFLOW:
            raise ValueError("research request has an unsupported workflow")
        job_id = request["job_id"]
        digest = request["input_digest_sha256"]
        if job_id in seen_job_ids and seen_job_ids[job_id] != digest:
            raise ValueError("duplicate research job id has conflicting input")
        seen_job_ids[job_id] = digest
        validated.append(request)
    if not validated:
        raise ValueError("at least one research request is required")

    kept: list[dict] = []
    kept_job_ids: set[str] = set()
    duplicates: list[dict] = []
    digest_owner: dict[str, str] = {}
    source_owner: dict[str, str] = {}
    for request in sorted(validated, key=lambda item: item["job_id"]):
        job_id = request["job_id"]
        digest = request["input_digest_sha256"]
        source_key = _source_key(request["input"]["url"])
        if job_id in kept_job_ids:
            duplicates.append(
                {"job_id": job_id, "kept_job_id": job_id, "reason": "repeated_job_id"}
            )
            continue
        owner = digest_owner.get(digest)
        reason = "input_digest" if owner else None
        if owner is None:
            owner = source_owner.get(source_key)
            reason = "canonical_url" if owner else None
        if owner is not None:
            duplicates.append({"job_id": job_id, "kept_job_id": owner, "reason": reason})
            continue
        digest_owner[digest] = job_id
        source_owner[source_key] = job_id
        kept.append(request)
        kept_job_ids.add(job_id)

    lines = [
        {
            "custom_id": request["job_id"],
            "method": "POST",
            "url": BATCH_ENDPOINT,
            "body": _response_body(request),
        }
        for request in kept
    ]
    jsonl = b"".join(_canonical_bytes(line) + b"\n" for line in lines)
    if len(lines) > MAX_BATCH_REQUESTS or len(jsonl) > MAX_BATCH_FILE_BYTES:
        raise ValueError("triage packet exceeds the OpenAI Batch input limits")
    input_sha256 = hashlib.sha256(jsonl).hexdigest()
    input_token_ceiling = sum(
        max(
            len(_canonical_bytes(line["body"])) + INPUT_OVERHEAD_TOKENS,
            MIN_INPUT_TOKEN_CEILING,
        )
        for line in lines
    )
    output_token_ceiling = len(lines) * MAX_OUTPUT_TOKENS
    maximum_cost = (
        Decimal(input_token_ceiling) * BATCH_INPUT_USD_PER_MILLION
        + Decimal(output_token_ceiling) * BATCH_OUTPUT_USD_PER_MILLION
    ) / Decimal(1_000_000)

    authorizations = [_authorization(request) for request in kept]
    budgets = sorted({budget for allowed, budget, _ in authorizations if allowed and budget})
    blockers = sorted({reason for allowed, _, reason in authorizations if not allowed and reason})
    if len(budgets) > 1:
        blockers.append("mixed_request_budgets")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": "research_radar_batch_triage",
        "batch_id": input_sha256,
        "input_sha256": input_sha256,
        "model": MODEL,
        "endpoint": BATCH_ENDPOINT,
        "completion_window": COMPLETION_WINDOW,
        "request_count": len(lines),
        "source_job_ids": [line["custom_id"] for line in lines],
        "skipped_duplicates": duplicates,
        "input_token_ceiling": input_token_ceiling,
        "output_token_ceiling": output_token_ceiling,
        "estimated_max_cost_usd": _money_string(maximum_cost),
        "source_monthly_budget_usd": budgets[0] if len(budgets) == 1 else None,
        "submission_eligible": not blockers and len(budgets) == 1,
        "submission_blockers": sorted(blockers),
        "human_curation_required": True,
        "human_prereg_required": True,
    }
    return {"manifest": manifest, "input_jsonl": jsonl}


def _runtime_enabled(value: bool | str | None) -> bool:
    if isinstance(value, bool):
        return value
    raw = value if value is not None else os.environ.get("RESEARCH_TRIAGE_API_ENABLED", "false")
    normalized = raw.strip().lower()
    if normalized not in {"true", "false"}:
        raise ValueError("RESEARCH_TRIAGE_API_ENABLED must be true or false")
    return normalized == "true"


def _validate_packet(packet: dict) -> dict:
    manifest = packet.get("manifest", {})
    jsonl = packet.get("input_jsonl")
    if not isinstance(jsonl, bytes) or hashlib.sha256(jsonl).hexdigest() != manifest.get(
        "input_sha256"
    ):
        raise ValueError("triage packet bytes do not match its manifest")
    if manifest.get("batch_id") != manifest.get("input_sha256"):
        raise ValueError("triage packet batch id does not match its input")
    lines = [json.loads(raw) for raw in jsonl.splitlines()]
    custom_ids = [line.get("custom_id") for line in lines]
    if custom_ids != manifest.get("source_job_ids") or len(custom_ids) != manifest.get(
        "request_count"
    ):
        raise ValueError("triage packet request index does not match its manifest")
    return manifest


def authorize_submission(
    packet: dict,
    *,
    enabled: bool | str | None = None,
    monthly_budget_usd: str | None = None,
    api_key: str | None = None,
) -> dict:
    """Validate all non-network controls before a budget reservation or API call."""

    manifest = _validate_packet(packet)
    if not _runtime_enabled(enabled):
        raise PermissionError("Research triage API execution is disabled")
    if not manifest.get("submission_eligible"):
        blockers = ", ".join(manifest.get("submission_blockers", [])) or "unknown"
        raise PermissionError(f"research requests are not activated: {blockers}")
    key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
    if not key or not key.strip():
        raise PermissionError("OPENAI_API_KEY is required for paid execution")
    configured_budget = monthly_budget_usd or os.environ.get("RESEARCH_MONTHLY_BUDGET_USD")
    if configured_budget is None:
        raise PermissionError("RESEARCH_MONTHLY_BUDGET_USD is required for paid execution")
    budget = _money(configured_budget)
    bound_budget = manifest.get("source_monthly_budget_usd")
    if _money_string(budget) != bound_budget:
        raise PermissionError("runtime monthly budget does not match the immutable request budget")
    amount = _money(manifest["estimated_max_cost_usd"])
    if amount > budget:
        raise PermissionError("triage packet maximum cost exceeds the monthly budget")
    return {
        "monthly_budget_usd": _money_string(budget),
        "reservation_usd": _money_string(amount),
    }


def _s3_error_code(exc: Exception) -> str:
    response = getattr(exc, "response", {})
    error = response.get("Error", {}) if isinstance(response, dict) else {}
    return str(error.get("Code", "")) if isinstance(error, dict) else ""


def _s3_json(s3: Any, *, bucket: str, key: str) -> tuple[dict, str | None]:
    response = s3.get_object(Bucket=bucket, Key=key)
    payload = json.load(io.BytesIO(response["Body"].read()))
    return payload, response.get("ETag")


def _optional_s3_json(s3: Any, *, bucket: str, key: str) -> dict | None:
    try:
        return _s3_json(s3, bucket=bucket, key=key)[0]
    except Exception as exc:
        if _s3_error_code(exc) in {"NoSuchKey", "404", "NotFound"}:
            return None
        raise


def reserve_monthly_budget(
    packet: dict,
    *,
    s3: Any,
    bucket: str,
    monthly_budget_usd: str,
    now: datetime | None = None,
    prefix: str = DEFAULT_TRIAGE_PREFIX,
    max_attempts: int = 5,
) -> dict:
    """Atomically reserve the packet's conservative cost in one UTC-month ledger."""

    manifest = packet["manifest"]
    batch_id = manifest["batch_id"]
    amount = _money(manifest["estimated_max_cost_usd"])
    budget = _money(monthly_budget_usd)
    period = (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y-%m")
    key = f"{prefix.strip('/')}/budgets/{period}/state.json"

    for _ in range(max_attempts):
        try:
            current, etag = _s3_json(s3, bucket=bucket, key=key)
        except Exception as exc:
            if _s3_error_code(exc) not in {"NoSuchKey", "404", "NotFound"}:
                raise
            current = {
                "schema_version": SCHEMA_VERSION,
                "period_utc": period,
                "monthly_budget_usd": _money_string(budget),
                "reservations": {},
            }
            etag = None

        if current.get("schema_version") != SCHEMA_VERSION or current.get("period_utc") != period:
            raise ValueError("invalid research triage budget ledger")
        if current.get("monthly_budget_usd") != _money_string(budget):
            raise PermissionError("monthly budget changed after the ledger was created")
        reservations = current.get("reservations")
        if not isinstance(reservations, dict):
            raise ValueError("invalid research triage budget reservations")
        existing = reservations.get(batch_id)
        if existing is not None:
            if _money_string(_money(existing)) != _money_string(amount):
                raise ValueError("existing batch reservation has a different amount")
            total = sum((_money(value) for value in reservations.values()), Decimal(0))
            return {"created": False, "key": key, "reserved_total_usd": _money_string(total)}

        total = sum((_money(value) for value in reservations.values()), Decimal(0))
        if total + amount > budget:
            raise PermissionError("monthly Research triage budget would be exceeded")
        updated = {**current, "reservations": {**reservations, batch_id: _money_string(amount)}}
        kwargs = {
            "Bucket": bucket,
            "Key": key,
            "Body": _canonical_bytes(updated),
            "ContentType": "application/json",
        }
        if etag:
            kwargs["IfMatch"] = etag
        else:
            kwargs["IfNoneMatch"] = "*"
        try:
            s3.put_object(**kwargs)
            return {
                "created": True,
                "key": key,
                "reserved_total_usd": _money_string(total + amount),
            }
        except Exception as exc:
            if _s3_error_code(exc) not in {"PreconditionFailed", "412"}:
                raise
    raise RuntimeError("could not atomically reserve the monthly research budget")


class OpenAIBatchAPI:
    """Small REST adapter; construction alone performs no network request."""

    def __init__(self, api_key: str, *, http_client: Any | None = None):
        if not api_key.strip():
            raise ValueError("OpenAI API key must not be empty")
        if http_client is None:
            import httpx

            http_client = httpx.Client(base_url="https://api.openai.com/v1", timeout=60.0)
        self.http = http_client
        self.headers = {"Authorization": f"Bearer {api_key.strip()}"}

    def upload_batch_file(self, content: bytes) -> str:
        response = self.http.post(
            "/files",
            headers=self.headers,
            data={"purpose": "batch"},
            files={"file": ("research-triage.jsonl", content, "application/jsonl")},
        )
        response.raise_for_status()
        file_id = response.json().get("id")
        if not isinstance(file_id, str) or not file_id:
            raise ValueError("OpenAI file response is missing id")
        return file_id

    def create_batch(self, file_id: str, *, batch_id: str) -> dict:
        response = self.http.post(
            "/batches",
            headers=self.headers,
            json={
                "input_file_id": file_id,
                "endpoint": BATCH_ENDPOINT,
                "completion_window": COMPLETION_WINDOW,
                "metadata": {"kind": "research_radar_triage", "packet_sha256": batch_id},
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload.get("id"), str) or not payload["id"]:
            raise ValueError("OpenAI batch response is missing id")
        return payload

    def retrieve_batch(self, batch_id: str) -> dict:
        response = self.http.get(f"/batches/{batch_id}", headers=self.headers)
        response.raise_for_status()
        payload = response.json()
        if payload.get("id") != batch_id or not isinstance(payload.get("status"), str):
            raise ValueError("OpenAI batch retrieval response is invalid")
        return payload

    def download_file(self, file_id: str) -> bytes:
        response = self.http.get(f"/files/{file_id}/content", headers=self.headers)
        response.raise_for_status()
        return bytes(response.content)


def submit_packet(
    packet: dict,
    *,
    s3: Any,
    bucket: str,
    enabled: bool | str | None = None,
    monthly_budget_usd: str | None = None,
    api_key: str | None = None,
    api: Any | None = None,
    now: datetime | None = None,
    prefix: str = DEFAULT_TRIAGE_PREFIX,
) -> dict:
    """Reserve budget, claim one packet, and submit it at most once locally."""

    authorization = authorize_submission(
        packet,
        enabled=enabled,
        monthly_budget_usd=monthly_budget_usd,
        api_key=api_key,
    )
    resolved_api_key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")
    batch_id = packet["manifest"]["batch_id"]
    base = f"{prefix.strip('/')}/submissions/{batch_id}"
    receipt_key = f"{base}/receipt.json"
    existing_receipt = _optional_s3_json(s3, bucket=bucket, key=receipt_key)
    if existing_receipt is not None:
        return {"created": False, "key": receipt_key, "receipt": existing_receipt}

    reservation = reserve_monthly_budget(
        packet,
        s3=s3,
        bucket=bucket,
        monthly_budget_usd=authorization["monthly_budget_usd"],
        now=now,
        prefix=prefix,
    )
    timestamp = (now or datetime.now(UTC)).astimezone(UTC).isoformat(timespec="seconds")
    claim_key = f"{base}/claim.json"
    claim = {
        "schema_version": SCHEMA_VERSION,
        "batch_id": batch_id,
        "claimed_at": timestamp,
        "reservation_usd": authorization["reservation_usd"],
        "input_sha256": packet["manifest"]["input_sha256"],
    }
    try:
        s3.put_object(
            Bucket=bucket,
            Key=claim_key,
            Body=_canonical_bytes(claim),
            ContentType="application/json",
            IfNoneMatch="*",
        )
    except Exception as exc:
        if _s3_error_code(exc) not in {"PreconditionFailed", "412"}:
            raise
        existing_receipt = _optional_s3_json(s3, bucket=bucket, key=receipt_key)
        if existing_receipt is not None:
            return {"created": False, "key": receipt_key, "receipt": existing_receipt}
        raise RuntimeError("batch is claimed without a receipt; reconcile before retrying") from exc

    api = api or OpenAIBatchAPI(resolved_api_key)
    file_id = api.upload_batch_file(packet["input_jsonl"])
    remote = api.create_batch(file_id, batch_id=batch_id)
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "batch_id": batch_id,
        "submitted_at": timestamp,
        "input_file_id": file_id,
        "openai_batch_id": remote["id"],
        "remote_status": remote.get("status", "unknown"),
        "reservation_usd": authorization["reservation_usd"],
        "budget_ledger_key": reservation["key"],
    }
    s3.put_object(
        Bucket=bucket,
        Key=receipt_key,
        Body=_canonical_bytes(receipt),
        ContentType="application/json",
        IfNoneMatch="*",
    )
    return {"created": True, "key": receipt_key, "receipt": receipt}


def _output_text(body: dict) -> str:
    if isinstance(body.get("output_text"), str):
        return body["output_text"]
    texts = []
    for item in body.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if isinstance(content, dict) and content.get("type") == "output_text":
                texts.append(content.get("text"))
    if len(texts) != 1 or not isinstance(texts[0], str):
        raise ValueError("completed response must contain exactly one output_text")
    return texts[0]


def _validate_classification(value: Any) -> dict:
    if not isinstance(value, dict) or set(value) != set(TRIAGE_OUTPUT_SCHEMA["required"]):
        raise ValueError("triage output does not match the required fields")
    if not isinstance(value["relevant_to_quant_research"], bool):
        raise ValueError("triage relevance must be boolean")
    enum_fields = {
        "primary_family": PRIMARY_FAMILIES,
        "evidence_type": EVIDENCE_TYPES,
        "implementation_complexity": IMPLEMENTATION_COMPLEXITIES,
    }
    for field, choices in enum_fields.items():
        if value[field] not in choices:
            raise ValueError(f"invalid triage {field}")
    list_fields = ("asset_classes", "data_requirements", "mechanism_terms", "risk_flags")
    list_limits = {
        "asset_classes": 4,
        "data_requirements": 5,
        "mechanism_terms": 5,
        "risk_flags": 5,
    }
    if any(not isinstance(value[field], list) for field in list_fields):
        raise ValueError("triage list fields must be arrays")
    if any(len(value[field]) > list_limits[field] for field in list_fields):
        raise ValueError("triage list field exceeds its item limit")
    if any(not isinstance(item, str) for field in list_fields for item in value[field]):
        raise ValueError("triage arrays must contain strings")
    if any(len(value[field]) != len(set(value[field])) for field in list_fields):
        raise ValueError("triage list fields must not contain duplicates")
    if any(item not in ASSET_CLASSES for item in value["asset_classes"]):
        raise ValueError("invalid triage asset class")
    if any(item not in RISK_FLAGS for item in value["risk_flags"]):
        raise ValueError("invalid triage risk flag")
    if (
        not isinstance(value["summary_ko"], str)
        or not value["summary_ko"].strip()
        or not isinstance(value["relevance_reason_ko"], str)
        or not value["relevance_reason_ko"].strip()
    ):
        raise ValueError("triage prose fields must be strings")
    return value


def cluster_results(results: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for result in results:
        classification = result["classification"]
        if classification["relevant_to_quant_research"]:
            assets = sorted(set(classification["asset_classes"])) or ["unspecified"]
            key = "|".join(
                (classification["primary_family"], assets[0], classification["evidence_type"])
            )
        else:
            key = "out_of_scope"
        grouped.setdefault(key, []).append(result)

    clusters = []
    for key, members in sorted(grouped.items()):
        classifications = [member["classification"] for member in members]
        clusters.append(
            {
                "cluster_id": hashlib.sha256(key.encode("utf-8")).hexdigest()[:16],
                "cluster_key": key,
                "entry_ids": sorted(member["entry_id"] for member in members),
                "count": len(members),
                "mechanism_terms": sorted(
                    {term for item in classifications for term in item["mechanism_terms"]}
                ),
                "human_curation_required": True,
            }
        )
    return clusters


def parse_batch_output(packet: dict, output_jsonl: bytes | str) -> dict:
    """Validate a completed Batch output and make a deterministic cluster view."""

    manifest = _validate_packet(packet)
    expected = set(manifest["source_job_ids"])
    source_requests = {
        line["custom_id"]: json.loads(line["body"]["input"].split("\n", 1)[1])
        for line in (json.loads(raw) for raw in packet["input_jsonl"].decode("utf-8").splitlines())
    }
    raw_text = output_jsonl.decode("utf-8") if isinstance(output_jsonl, bytes) else output_jsonl
    received: dict[str, dict] = {}
    received_lines: dict[str, dict] = {}
    input_tokens = 0
    output_tokens = 0
    for raw_line in raw_text.splitlines():
        if not raw_line.strip():
            continue
        line = json.loads(raw_line)
        custom_id = line.get("custom_id")
        if custom_id not in expected:
            raise ValueError("Batch output contains an unknown custom_id")
        if custom_id in received:
            raise ValueError("Batch output contains a duplicate custom_id")
        response = line.get("response")
        if (
            not isinstance(response, dict)
            or response.get("status_code") != 200
            or line.get("error")
        ):
            raise ValueError("Batch output contains a failed request")
        body = response.get("body")
        if not isinstance(body, dict) or body.get("status") != "completed":
            raise ValueError("Batch response is not completed")
        classification = _validate_classification(json.loads(_output_text(body)))
        usage = body.get("usage", {})
        row_input_tokens = usage.get("input_tokens")
        row_output_tokens = usage.get("output_tokens")
        if (
            type(row_input_tokens) is not int
            or row_input_tokens < 0
            or type(row_output_tokens) is not int
            or row_output_tokens < 0
        ):
            raise ValueError("Batch response contains invalid token usage")
        input_tokens += row_input_tokens
        output_tokens += row_output_tokens
        source = source_requests[custom_id]
        received_lines[custom_id] = line
        received[custom_id] = {
            "entry_id": custom_id,
            "source_id": source["source_id"],
            "source_name": source["source_name"],
            "title": source["title"],
            "url": source["url"],
            "classification": classification,
        }
    missing = sorted(expected - set(received))
    if missing:
        raise ValueError(f"Batch output is missing {len(missing)} request(s)")

    actual_cost = (
        Decimal(input_tokens) * BATCH_INPUT_USD_PER_MILLION
        + Decimal(output_tokens) * BATCH_OUTPUT_USD_PER_MILLION
    ) / Decimal(1_000_000)
    results = [received[entry_id] for entry_id in sorted(received)]
    output_digest = hashlib.sha256(
        _canonical_bytes(
            {entry_id: received_lines[entry_id] for entry_id in sorted(received_lines)}
        )
    ).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "batch_id": packet["manifest"]["batch_id"],
        "model": MODEL,
        "output_digest_sha256": output_digest,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_actual_cost_usd": _money_string(actual_cost),
        },
        "results": results,
        "clusters": cluster_results(results),
        "human_curation_required": True,
        "adoption_decision": None,
    }


def persist_result_projection(
    projection: dict,
    *,
    s3: Any,
    bucket: str,
    prefix: str = DEFAULT_TRIAGE_PREFIX,
) -> dict:
    """Conditionally persist one immutable validated Batch projection."""

    batch_id = projection.get("batch_id")
    if (
        not isinstance(batch_id, str)
        or not research_jobs.ENTRY_ID.fullmatch(batch_id)
        or projection.get("schema_version") != SCHEMA_VERSION
        or not research_jobs.ENTRY_ID.fullmatch(str(projection.get("output_digest_sha256", "")))
        or not isinstance(projection.get("results"), list)
        or not isinstance(projection.get("clusters"), list)
        or projection.get("human_curation_required") is not True
        or projection.get("adoption_decision") is not None
    ):
        raise ValueError("invalid research triage result projection")
    key = f"{prefix.strip('/')}/results/{batch_id}/projection.json"
    body = _canonical_bytes(projection)
    try:
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
            IfNoneMatch="*",
            Metadata={"projection-sha256": hashlib.sha256(body).hexdigest()},
        )
        return {"created": True, "key": key, "projection": projection}
    except Exception as exc:
        if _s3_error_code(exc) not in {"PreconditionFailed", "412"}:
            raise
        existing = _s3_json(s3, bucket=bucket, key=key)[0]
        if _canonical_bytes(existing) != body:
            raise ValueError("existing triage projection has different content") from exc
        return {"created": False, "key": key, "projection": existing}
