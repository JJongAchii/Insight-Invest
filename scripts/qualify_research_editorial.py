"""Bounded real-API acceptance in a dedicated prefix, never the live feed.

Run via deploy.yml's research-qualify mode. The GitHub secret stays on the runner.
Only metadata, short source excerpts, briefs and non-secret diagnostics are retained.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from importlib.metadata import version
from itertools import zip_longest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from datastore import research, storage  # noqa: E402
from module import (
    research_analysis,
    research_boundary,
    research_feed,
    research_review,
    research_selection,
)  # noqa: E402
from qdata.radar_editorial import (  # noqa: E402
    CHANNELS,
    content_digest,
    discover_publications,
    parse_publication,
    publication_record,
)
from qdata.radar_public import _fetch_bytes  # noqa: E402

QUALIFICATION_ROOT = "s3://insight-invest-datalake/research-radar/qualification/openai"
ENABLED_SOURCES = tuple(
    name for name in CHANNELS if name not in {"man-systematic-insights", "kjfs-current"}
)
# This comparison selector exists only in the isolated manual runner. Production
# remains on its configured model; no environment-driven fallback is added.
READING_CONTRAST_MODEL = "gpt-5.4-mini-2026-03-17"
READING_QUALITY_MODEL = "gpt-5.4-2026-03-05"
MODEL_PRICES = {
    "gpt-5-nano": (50, 400),
    "gpt-5-mini": (250, 2000),
    READING_CONTRAST_MODEL: (750, 4500),
    READING_QUALITY_MODEL: (2500, 15000),
}
# Diagnostic only: one fixed model contrast, never a production fallback.
BOUNDARY_MODEL_PRICES = {
    "gpt-5-mini": (250, 2000),
    "gpt-5.4-2026-03-05": (2500, 15000),
}
BOUNDARY_COMPARISON_SAMPLES = frozenset(
    {"reading-gate-products-v1", "reading-gate-boundaries-v1"}
)
GATE_SAMPLES = {
    "reading-gate-products-v1": "reading-products-v1",
    "reading-gate-commercialization-v1": "reading-commercialization-v1",
    "reading-gate-subject-v1": "reading-subject-v1",
    "reading-gate-subject-positive-v1": "reading-subject-positive-v1",
    "reading-gate-boundaries-v1": "reading-contribution-boundaries-v1",
    "reading-gate-methods-v1": "reading-contribution-methods-v1",
    "reading-gate-extension-v1": "reading-contribution-extension-v1",
    "reading-gate-generalization-v1": "reading-evidence-generalization-v1",
}
BRIEF_SAMPLES = {"reading-brief-evidence-v1": "reading-subject-positive-v1"}
BATCH_SAMPLES = frozenset(f"reading-quality-20260915-{part}" for part in "abcde")
SAMPLES = (
    "latest",
    "reading-value-v1",
    "reading-value-v2",
    "reading-diversity-v1",
    "reading-scope-v1",
    "reading-subject-v1",
    "reading-subject-positive-v1",
    "reading-products-v1",
    "reading-commercialization-v1",
    "reading-contribution-boundaries-v1",
    "reading-contribution-methods-v1",
    "v7-regression",
    *GATE_SAMPLES,
    *BRIEF_SAMPLES,
    *BATCH_SAMPLES,
)
SELECTION_SAMPLES = frozenset(
    {
        "reading-scope-v1",
        "reading-subject-v1",
        "reading-subject-positive-v1",
        "reading-products-v1",
        "reading-commercialization-v1",
        "reading-contribution-boundaries-v1",
        "reading-contribution-methods-v1",
    }
)
V7_PROMPT = "reading-brief-openai-v7-korean-editorial"


def fixed_cases(sample: str, sources: list[str]) -> dict[str, dict]:
    if sample == "latest":
        return {}
    if sample in BATCH_SAMPLES:
        filename = (
            "research-reading-holdout-20260915.json"
            if sample == "reading-quality-20260915-e"
            else "research-quality-20260915.json"
        )
        path = Path(__file__).with_name("fixtures") / filename
        cases = {
            item["entry_id"]: item
            for item in json.loads(path.read_text())["items"]
            if item["sample"] == sample
        }
        if not cases or {case["source_id"] for case in cases.values()} != set(sources):
            raise ValueError("frozen reading batch requires its exact sources")
        return cases
    sample = {**GATE_SAMPLES, **BRIEF_SAMPLES}.get(sample, sample)
    path = Path(__file__).with_name("fixtures") / "research-reading-samples.json"
    cases = {
        item["source_id"]: item
        for item in json.loads(path.read_text())["items"]
        if sample in item["samples"] and item["source_id"] in sources
    }
    if set(cases) != set(sources):
        raise ValueError("fixed sample does not cover all requested sources")
    return cases


def case_for(item: dict, cases: dict[str, dict]) -> dict:
    return cases.get(item.get("entry_id"), cases.get(item["source_id"], {}))


def completed_batch_item(item: dict) -> bool:
    lane = research_selection.automatic_state(item)
    return lane in {"context", "held"} or (lane == "core" and current_review(item))


def fixed_publication(case: dict, now: datetime) -> tuple[dict, str]:
    document = parse_publication(
        _fetch_bytes(case["url"]),
        url=case["url"],
        channel=CHANNELS[case["source_id"]],
        seed=case,
    )
    if (
        content_digest(document["text"]) != case["source_digest"]
        or document["title"] != case["title"]
    ):
        raise ValueError("fixed source changed; do not substitute another article")
    record = publication_record(document, source_id=case["source_id"], now=now)
    return record, document["text"][: research_analysis.MAX_INPUT_CHARS]


def selection_check(item: dict, case: dict) -> dict:
    """Check fixed topic/format/lane expectations without borrowing editor overrides."""
    decision = item.get("editorial_selection", {}).get("decision", {})
    lane = research_selection.model_state(item)
    subjects = case.get("expected_subjects", [])
    contributions = case.get("expected_contributions", [])
    return {
        "source_id": item["source_id"],
        "expected": case["expected_content_kinds"],
        "actual": decision.get("content_kind"),
        "expected_subjects": subjects,
        "primary_subject": decision.get("primary_subject"),
        "expected_contributions": contributions,
        "contribution_type": decision.get("contribution_type"),
        "main_purpose": decision.get("main_purpose", {}).get("category"),
        "expected_lane": case.get("expected_lane"),
        "automatic_lane": lane,
        "matches": (
            lane == case.get("expected_lane")
            and decision.get("content_kind") in case["expected_content_kinds"]
            and (not subjects or decision.get("primary_subject") in subjects)
            and (
                not contributions or decision.get("contribution_type") in contributions
            )
        ),
    }


def gate_check(item: dict, case: dict) -> dict:
    """A hold prevents promotion; it does not fix the raw classifier's mistake."""
    allowed = ["core"] if case["expected_lane"] == "core" else ["context", "held"]
    lane = research_selection.automatic_state(item)
    return {
        "source_id": item["source_id"],
        "expected_lanes": allowed,
        "automatic_lane": lane,
        "boundary_required": research_selection.needs_boundary(item),
        "boundary_verdict": research_boundary.state(item),
        "boundary_analysis_object": item.get("editorial_boundary", {})
        .get("decision", {})
        .get("analysis_object"),
        "boundary_derived_verdict": item.get("editorial_boundary", {})
        .get("decision", {})
        .get("verdict"),
        "boundary_evidence_roles": {
            name: (
                item.get("editorial_boundary", {})
                .get("decision", {})
                .get("checks", {})
                .get(name)
                or {}
            ).get("role")
            for name in research_boundary.EVIDENCE_FIELDS
        },
        "raw_selector_matches": selection_check(item, case)["matches"],
        "matches": lane in allowed,
    }


def preserved_input(record: dict, case: dict) -> dict:
    """Replay historical input metadata only after its body/scope is revalidated.

    The current parser is reported separately, not mislabelled as the old parser.
    This isolated regression tests the preserved draft, never a replacement draft.
    """
    if (
        record["source_digest"] != case["source_digest"]
        or record["analysis_scope"] != case["baseline_analysis_scope"]
    ):
        raise ValueError("preserved source body or analysis scope differs")
    return {**record, "parser_version": case["baseline_parser_version"]}


def validate_environment(*, now: datetime | None = None) -> tuple[int, list[str], str]:
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise ValueError("OPENAI_API_KEY is not configured")
    if storage.app_data_root() != QUALIFICATION_ROOT:
        raise ValueError("qualification requires its isolated APP_DATA prefix")
    if not research_review.enabled():
        raise ValueError("isolated qualification requires explicit analysis opt-in")
    research_analysis.budget_limit_nanousd(now or datetime.now(UTC))
    budget = Decimal(os.environ.get("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "0"))
    if not Decimal("0") < budget <= Decimal("1.10"):
        raise ValueError(
            "qualification monthly budget must be positive and at most $1.10"
        )
    month = os.environ.get("RADAR_ANALYSIS_BUDGET_OVERRIDE_MONTH", "").strip()
    if month and (
        month != "2026-09"
        or Decimal(os.environ["RADAR_ANALYSIS_BUDGET_OVERRIDE_USD"]) > Decimal("4")
    ):
        raise ValueError("qualification override is approved only for 2026-09 up to $4")
    maximum = int(os.environ.get("RESEARCH_MAX_ITEMS", "1"))
    if not 1 <= maximum <= 30:
        raise ValueError("qualification requires 1 to 30 items")
    selected = os.environ.get("RESEARCH_SOURCES", "").strip()
    sources = (
        list(dict.fromkeys(s.strip() for s in selected.split(",")))
        if selected
        else list(ENABLED_SOURCES)
    )
    if any(name not in ENABLED_SOURCES for name in sources):
        raise ValueError("source is outside the approved enabled editorial bundle")
    model = os.environ.get("RESEARCH_QUALIFICATION_MODEL", research_analysis.MODEL)
    if model not in MODEL_PRICES:
        raise ValueError("qualification model is not approved")
    sample = os.environ.get("RESEARCH_SAMPLE", "latest")
    if sample not in SAMPLES or (sample == "v7-regression" and model != "gpt-5-mini"):
        raise ValueError("qualification sample is not approved")
    reading_contrast = model == READING_CONTRAST_MODEL
    reading_quality = model == READING_QUALITY_MODEL
    if reading_quality and sample not in {*BATCH_SAMPLES, "latest"}:
        raise ValueError("reading quality model requires a bounded reading batch")
    if reading_contrast and sample != "reading-quality-20260915-a":
        raise ValueError("reading model contrast requires its frozen seven originals")
    if (
        sample in {*GATE_SAMPLES, *BRIEF_SAMPLES, *BATCH_SAMPLES}
        and model != "gpt-5-mini"
        and not reading_contrast
        and not reading_quality
    ):
        raise ValueError("source-only gate qualification keeps GPT-5 mini")
    boundary_model(sample, model)  # Validate the contrast before source/provider I/O.
    cases = fixed_cases(sample, sources)  # Fail before any source/provider I/O.
    if sample in BATCH_SAMPLES:
        if maximum != len(cases) or maximum > 12:
            raise ValueError("frozen reading batch requires its exact bounded size")
    elif model in {"gpt-5-mini", READING_QUALITY_MODEL} and not 1 <= maximum <= min(
        3, len(sources)
    ):
        raise ValueError("mini comparison allows at most three distinct sources")
    return maximum, sources, model


def boundary_model(sample: str, model: str) -> str:
    name = os.environ.get("RESEARCH_BOUNDARY_MODEL", "gpt-5-mini")
    if name not in BOUNDARY_MODEL_PRICES:
        raise ValueError("boundary comparison model is not approved")
    if name != "gpt-5-mini" and (
        model != "gpt-5-mini"
        or sample not in BOUNDARY_COMPARISON_SAMPLES
        or research_selection.PROMPT_VERSION
        != "reading-selection-v7-evidence-first-purpose"
    ):
        raise ValueError("boundary comparison requires its fixed gate samples")
    return name


def preserved_selections(records: list[dict], texts: dict[str, str]) -> list[dict]:
    """A model-only contrast must not pay to regenerate its first-stage baseline."""
    receipts = []
    for record in records:
        fingerprint = research_selection.cache_key(record)
        path = f"research_analysis/selections/{fingerprint}.json"
        if not storage.exists(path):
            raise ValueError("boundary comparison requires preserved v7 selections")
        selected = storage.read_json(path)
        if research_selection.model_state(
            {**record, "editorial_selection": selected}
        ) == "pending" or selected.get("input_digest") != research_review.digest(
            texts[record["entry_id_sha256"]]
        ):
            raise ValueError("boundary comparison selection/input changed")
        receipts.append(
            {
                "entry_id": record["entry_id_sha256"],
                "fingerprint": fingerprint,
                "decision_digest": selected["decision_digest"],
                "input_digest": selected["input_digest"],
            }
        )
    return receipts


def select_records(groups: list[list[dict]], maximum: int) -> list[dict]:
    """One recent readable item per source first, then fill remaining slots."""
    selected = {}
    for row in zip_longest(*groups):
        for record in row:
            if record is None:
                continue
            selected.setdefault(
                record["entry_id_sha256"], {**record, "notification_eligible": False}
            )
            if len(selected) == maximum:
                return list(selected.values())
    return list(selected.values())


def analysis_candidates(records: list[dict]) -> list[dict]:
    """Do not count deterministic prefilter skips as model comparison slots."""
    return [
        record for record in records if record.get("analysis_status") != "not_requested"
    ]


def current_analysis(item: dict) -> bool:
    return (
        item.get("analysis_status") == "ready"
        and current_review(item)
        and research_review.state(item) == "accepted"
    )


def current_review(item: dict) -> bool:
    # A completed draft is not a reviewed brief. A semantic rejection is a valid
    # review outcome, but not a ready/core publication or human quality acceptance.
    return research_review.state(item) in {"accepted", "rejected"} and item.get(
        "analysis", {}
    ).get("fingerprint") == research_analysis.cache_key(item)


def current_automatic_review(item: dict) -> bool:
    return research_selection.automatic_state(item) == "core" and current_review(item)


class RecordSnapshot:
    """Feed the real producer records through the real consumer projection."""

    def __init__(self, records):
        self.records = {
            f"research-radar/public/records/{record['entry_id_sha256']}.json": record
            for record in records
        }

    def list_objects_v2(self, **_kwargs):
        return {
            "Contents": [
                {
                    "Key": key,
                    "ETag": hashlib.sha256(
                        json.dumps(value, sort_keys=True).encode()
                    ).hexdigest(),
                }
                for key, value in self.records.items()
            ]
        }

    def get_object(self, *, Key, **_kwargs):
        return {"Body": io.BytesIO(json.dumps(self.records[Key]).encode())}


def run(output: Path) -> int:
    now = datetime.now(UTC)
    report = {
        "checked_at": now.isoformat(),
        "status": "incomplete",
        "production_modified": False,
        "quality_review": "pending_human_comparison",
        "execution_host": "github-actions",
        "insight_commit": os.environ.get("GITHUB_SHA"),
        "qdata_commit": os.environ.get("QDATA_REF"),
        "workflow_run": os.environ.get("GITHUB_RUN_ID"),
        "model": research_analysis.MODEL,
        "prompt_version": research_analysis.PROMPT_VERSION,
        "review_model": research_review.MODEL,
        "review_prompt_version": research_review.PROMPT_VERSION,
        "selection_prompt_version": research_selection.PROMPT_VERSION,
        "selection_model": research_selection.MODEL,
        "selection_pricing_nanousd_per_token": {
            "input": research_selection.INPUT_NANOUSD_PER_TOKEN,
            "output": research_selection.OUTPUT_NANOUSD_PER_TOKEN,
        },
        "dependencies": {
            name: version(name) for name in ("beautifulsoup4", "pypdf", "httpx")
        },
        "sources": [],
        "items": [],
        "analysis_runs": [],
    }

    def save_report():
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    original_settings = (
        research_analysis.MODEL,
        research_analysis.INPUT_NANOUSD_PER_TOKEN,
        research_analysis.OUTPUT_NANOUSD_PER_TOKEN,
    )
    original_prompt = research_analysis.PROMPT_VERSION
    original_boundary = (
        research_boundary.MODEL,
        research_boundary.INPUT_NANOUSD_PER_TOKEN,
        research_boundary.OUTPUT_NANOUSD_PER_TOKEN,
    )
    original_review = (
        research_review.MODEL,
        research_review.INPUT_NANOUSD_PER_TOKEN,
        research_review.OUTPUT_NANOUSD_PER_TOKEN,
    )
    try:
        maximum, sources, model = validate_environment(now=now)
        sample = os.environ.get("RESEARCH_SAMPLE", "latest")
        cases = fixed_cases(sample, sources)
        name = boundary_model(sample, model)
        (
            research_boundary.MODEL,
            research_boundary.INPUT_NANOUSD_PER_TOKEN,
            research_boundary.OUTPUT_NANOUSD_PER_TOKEN,
        ) = (name, *BOUNDARY_MODEL_PRICES[name])
        report["diagnostic_only"] = (
            name != "gpt-5-mini" or model == READING_CONTRAST_MODEL
        )
        if model == READING_CONTRAST_MODEL:
            (
                research_review.MODEL,
                research_review.INPUT_NANOUSD_PER_TOKEN,
                research_review.OUTPUT_NANOUSD_PER_TOKEN,
            ) = (model, *MODEL_PRICES[model])
            report["review_model"] = model
            report["contrast_scope"] = (
                "writer_and_reviewer_only; identical prompts and preserved source selection"
            )
        report["boundary_model"] = name
        report["boundary_request_config"] = {
            "system_digest": research_review.digest(research_boundary.SYSTEM),
            "schema_digest": research_review.digest(research_boundary.SCHEMA),
            "reasoning_effort": research_boundary.REASONING_EFFORT,
            "max_output_tokens": research_boundary.MAX_OUTPUT_TOKENS,
            "max_input_chars": research_analysis.MAX_INPUT_CHARS,
            "input_nanousd_per_token": BOUNDARY_MODEL_PRICES[name][0],
            "output_nanousd_per_token": BOUNDARY_MODEL_PRICES[name][1],
        }
        texts = {}
        if sample == "v7-regression":
            research_analysis.PROMPT_VERSION = V7_PROMPT
        report["sample"] = sample
        if sample in GATE_SAMPLES:
            report["boundary_prompt_version"] = research_boundary.PROMPT_VERSION
            report["gate_policy"] = (
                "positive=core; negative=context|held; no editorial overrides"
            )
        report["prompt_version"] = research_analysis.PROMPT_VERSION
        report["sample_expectations"] = [
            {
                name: case[name]
                for name in (
                    "source_id",
                    "reading_check",
                    "expected_content_kinds",
                    "expected_subjects",
                    "expected_lane",
                    "known_bad_v7_fields",
                )
                if name in case
            }
            for case in cases.values()
        ]
        (
            research_analysis.MODEL,
            research_analysis.INPUT_NANOUSD_PER_TOKEN,
            research_analysis.OUTPUT_NANOUSD_PER_TOKEN,
        ) = (model, *MODEL_PRICES[model])
        report["model"] = model
        report["pricing_nanousd_per_token"] = {
            "input": MODEL_PRICES[model][0],
            "output": MODEL_PRICES[model][1],
        }
        report["max_items"] = maximum
        report["monthly_qualification_base_usd"] = os.environ[
            "RADAR_ANALYSIS_MONTHLY_BUDGET_USD"
        ]
        report["monthly_qualification_limit_usd"] = str(
            Decimal(research_analysis.budget_limit_nanousd(now)) / 1_000_000_000
        )
        report["budget_override_month_kst"] = os.environ.get(
            "RADAR_ANALYSIS_BUDGET_OVERRIDE_MONTH", ""
        )
        report["review_pricing_nanousd_per_token"] = {
            "input": research_review.INPUT_NANOUSD_PER_TOKEN,
            "output": research_review.OUTPUT_NANOUSD_PER_TOKEN,
        }

        def collect(key):
            name = cases[key]["source_id"] if cases else key
            try:
                if cases:
                    record, text = fixed_publication(cases[key], now)
                    if sample in BATCH_SAMPLES and record["entry_id_sha256"] != key:
                        raise ValueError("frozen reading entry identity changed")
                    texts[record["entry_id_sha256"]] = text
                    return {
                        "source_id": name,
                        "health": {
                            "readable_items": 1,
                            "fixed_source_digest_verified": True,
                        },
                    }, [record]
                records = discover_publications(
                    SimpleNamespace(
                        source_id=name,
                        max_entries=3,
                        lookback_days=3650,
                    ),
                    now=now,
                )
                return {"source_id": name, "health": records.health}, list(records)
            except Exception as exc:
                return {"source_id": name, "error_type": type(exc).__name__}, []

        groups = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            for health, records in pool.map(collect, list(cases) if cases else sources):
                report["sources"].append(health)
                if model == "gpt-5-mini":
                    report.setdefault("prefilter_skipped", []).extend(
                        {
                            key: record[key]
                            for key in ("source_id", "title", "url", "relevance_reason")
                        }
                        for record in records
                        if record.get("analysis_status") == "not_requested"
                    )
                    records = analysis_candidates(records)
                # Listings can pin an old abstract first. A one-card connection
                # check should prefer a recent accessible body from that source.
                groups.append(
                    sorted(
                        records,
                        key=lambda record: (
                            record["analysis_scope"] != "abstract",
                            record["published_at"],
                        ),
                        reverse=True,
                    )
                )
                print(json.dumps({"stage": "source", **health}), flush=True)
                save_report()
        records = select_records(groups, maximum)
        if not records:
            raise ValueError("no readable qualification publications")
        if sample in BATCH_SAMPLES and len(records) != maximum:
            raise ValueError("frozen reading batch is incomplete; no paid calls")
        if (
            model == "gpt-5-mini"
            and sample not in BATCH_SAMPLES
            and len({r["source_id"] for r in records}) != maximum
        ):
            raise ValueError("mini comparison requires one readable item per source")
        report["selected_entries"] = [
            {
                key: record[key]
                for key in (
                    "entry_id_sha256",
                    "source_id",
                    "title",
                    "url",
                    "source_digest",
                )
            }
            for record in records
        ]
        save_report()  # Record the sample before the first paid call.
        if report["diagnostic_only"]:
            report["preserved_selection_receipts"] = preserved_selections(
                records, texts
            )
            save_report()
        if sample == "v7-regression":
            report["preserved_input_replay"] = [
                {
                    "source_id": record["source_id"],
                    "reparse_version": record["parser_version"],
                    "baseline_parser_version": cases[record["source_id"]][
                        "baseline_parser_version"
                    ],
                    "source_digest": record["source_digest"],
                    "analysis_scope": record["analysis_scope"],
                }
                for record in records
            ]
            records = [
                preserved_input(record, cases[record["source_id"]])
                for record in records
            ]
            for record in records:
                fingerprint = research_analysis.cache_key(record)
                if fingerprint != cases[record["source_id"]]["baseline_fingerprint"]:
                    raise ValueError("preserved v7 draft fingerprint differs")
                path = f"research_analysis/cache/{fingerprint}.json"
                if (
                    not storage.exists(path)
                    or storage.read_json(path).get("fingerprint") != fingerprint
                ):
                    raise ValueError(
                        "preserved v7 draft missing; regeneration is forbidden"
                    )
                if (
                    research_review.digest(storage.read_json(path)["brief"])
                    != cases[record["source_id"]]["baseline_brief_digest"]
                ):
                    raise ValueError(
                        "preserved v7 draft changed from the recorded baseline"
                    )
        if texts:
            report["input_snapshots"] = [
                {
                    "entry_id": key,
                    "input_digest": research_review.digest(text),
                    "analyzed_chars": len(text),
                }
                for key, text in sorted(texts.items())
            ]
            save_report()

        research_analysis.preserve_retries(research.load_feed()["items"])
        research_feed.reconcile(s3=RecordSnapshot(records), now=now)
        feed = research.load_feed()
        selected_ids = {record["entry_id_sha256"] for record in records}
        feed["items"] = [
            item for item in feed["items"] if item["entry_id"] in selected_ids
        ]
        research.save_feed(feed)  # Dedicated qualification prefix ONLY.

        # At most one paid stage per enrich call; an old cache recovery can also
        # occupy a step. Review-only migration does not regenerate the v7 drafts.
        for _ in range(4 * len(records)):
            result = research_analysis.enrich(
                max_items=1,
                selection_only=sample in SELECTION_SAMPLES,
                gate_only=sample in GATE_SAMPLES,
                **({"selection_call": None} if sample == "v7-regression" else {}),
                **(
                    {"text_loader": lambda item: texts[item["entry_id"]]}
                    if texts
                    else {}
                ),
            )
            report["analysis_runs"].append(result)
            report["items"] = research.load_feed()["items"]
            save_report()
            print(json.dumps({"stage": "analysis", **result}), flush=True)
            if result.get("failed") or not (
                result.get("completed") or result.get("cache_hits")
            ):
                break  # Diagnose the first failure before spending on more documents.
            requested = [
                item
                for item in report["items"]
                if item.get("analysis_status") != "not_requested"
            ]
            if all(
                completed_batch_item(item)
                if sample in BATCH_SAMPLES
                else research_selection.model_state(item) != "pending"
                if sample in SELECTION_SAMPLES
                else research_selection.automatic_state(item) != "pending"
                if sample in GATE_SAMPLES
                else current_automatic_review(item)
                if sample in BRIEF_SAMPLES
                else current_review(item) or research_selection.state(item) == "context"
                for item in requested
            ):
                break
        requested = [
            item
            for item in report["items"]
            if item.get("analysis_status") != "not_requested"
        ]
        report["requested"] = len(requested)
        report["ready"] = sum(current_analysis(item) for item in requested)
        report["reviewed"] = sum(current_review(item) for item in requested)
        report["review_rejected"] = sum(
            current_review(item) and research_review.state(item) == "rejected"
            for item in requested
        )
        report["core"] = sum(
            item.get("research_lane") == "core" for item in report["items"]
        )
        report["selection_context"] = sum(
            research_selection.state(item) == "context" for item in requested
        )
        report["selection_checks"] = [
            selection_check(item, case_for(item, cases))
            for item in requested
            if case_for(item, cases) and sample != "v7-regression"
        ]
        if sample in GATE_SAMPLES or sample in BRIEF_SAMPLES or sample in BATCH_SAMPLES:
            # Isolated report/UI uses automatic outcomes too, not migration audits.
            for item in report["items"]:
                research_feed.apply_editorial_analysis(item, use_editor_audit=False)
            report["core"] = sum(
                item["research_lane"] == "core" for item in report["items"]
            )
            report["selection_context"] = sum(
                item["research_lane"] == "context" for item in report["items"]
            )
            report["selection_held"] = sum(
                item.get("editorial_selection_status") == "held"
                for item in report["items"]
            )
        # This qualifies transport/structure/binding, not reviewer correctness or alpha.
        if sample in BATCH_SAMPLES:
            report["editorial_audits_used_for_qualification"] = False
            report["gate_checks"] = [
                {
                    "entry_id": item["entry_id"],
                    **gate_check(item, case_for(item, cases)),
                }
                for item in requested
            ]
            report["status"] = (
                "api_contract_qualified"
                if len(requested) == maximum
                and all(check["matches"] for check in report["gate_checks"])
                and all(completed_batch_item(item) for item in requested)
                else "needs_diagnosis"
            )
        elif sample in GATE_SAMPLES:
            report["gate_only"] = True
            report["editorial_audits_used_for_qualification"] = False
            report["gate_checks"] = [
                gate_check(item, cases[item["source_id"]]) for item in requested
            ]
            report["status"] = (
                "api_contract_qualified"
                if len(requested) == maximum
                and all(check["matches"] for check in report["gate_checks"])
                else "needs_diagnosis"
            )
        elif sample in SELECTION_SAMPLES:
            report["selection_only"] = True
            report["editorial_audits_used_for_qualification"] = False
            report["status"] = (
                "api_contract_qualified"
                if len(requested) == maximum
                and len(report["selection_checks"]) == maximum
                and all(check["matches"] for check in report["selection_checks"])
                else "needs_diagnosis"
            )
        elif sample in BRIEF_SAMPLES:
            report["editorial_audits_used_for_qualification"] = False
            report["gate_checks"] = [
                gate_check(item, cases[item["source_id"]]) for item in requested
            ]
            report["status"] = (
                "api_contract_qualified"
                if len(requested) == maximum
                and all(check["matches"] for check in report["gate_checks"])
                and all(current_automatic_review(item) for item in requested)
                else "needs_diagnosis"
            )
        elif requested and report["reviewed"] + report["selection_context"] == len(
            requested
        ):
            report["status"] = "api_contract_qualified"
        else:
            report["status"] = "needs_diagnosis"
    except Exception as exc:
        report["status"] = "needs_diagnosis"
        report["error_type"] = type(exc).__name__
    finally:
        save_report()
        (
            research_analysis.MODEL,
            research_analysis.INPUT_NANOUSD_PER_TOKEN,
            research_analysis.OUTPUT_NANOUSD_PER_TOKEN,
        ) = original_settings
        research_analysis.PROMPT_VERSION = original_prompt
        (
            research_boundary.MODEL,
            research_boundary.INPUT_NANOUSD_PER_TOKEN,
            research_boundary.OUTPUT_NANOUSD_PER_TOKEN,
        ) = original_boundary
        (
            research_review.MODEL,
            research_review.INPUT_NANOUSD_PER_TOKEN,
            research_review.OUTPUT_NANOUSD_PER_TOKEN,
        ) = original_review
    print(
        json.dumps(
            {
                key: report.get(key)
                for key in (
                    "status",
                    "requested",
                    "ready",
                    "reviewed",
                    "review_rejected",
                    "core",
                    "error_type",
                )
            }
        ),
        flush=True,
    )
    return 0 if report["status"] == "api_contract_qualified" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.output))
