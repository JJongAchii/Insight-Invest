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
from module import research_analysis, research_feed, research_review  # noqa: E402
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
MODEL_PRICES = {"gpt-5-nano": (50, 400), "gpt-5-mini": (250, 2000)}
SAMPLES = ("latest", "reading-value-v1", "v7-regression")
V7_PROMPT = "reading-brief-openai-v7-korean-editorial"


def fixed_cases(sample: str, sources: list[str]) -> dict[str, dict]:
    if sample == "latest":
        return {}
    path = Path(__file__).with_name("fixtures") / "research-reading-samples.json"
    cases = {
        item["source_id"]: item
        for item in json.loads(path.read_text())["items"]
        if sample in item["samples"] and item["source_id"] in sources
    }
    if set(cases) != set(sources):
        raise ValueError("fixed sample does not cover all requested sources")
    return cases


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


def validate_environment() -> tuple[int, list[str], str]:
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise ValueError("OPENAI_API_KEY is not configured")
    if storage.app_data_root() != QUALIFICATION_ROOT:
        raise ValueError("qualification requires its isolated APP_DATA prefix")
    if not research_review.enabled():
        raise ValueError("isolated qualification requires explicit analysis opt-in")
    budget = Decimal(os.environ.get("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "0"))
    if not Decimal("0") < budget <= Decimal("0.50"):
        raise ValueError(
            "qualification monthly budget must be positive and at most $0.50"
        )
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
    fixed_cases(sample, sources)  # Fail before any source/provider I/O.
    if model == "gpt-5-mini" and not 1 <= maximum <= min(3, len(sources)):
        raise ValueError("mini comparison allows at most three distinct sources")
    return maximum, sources, model


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
    try:
        maximum, sources, model = validate_environment()
        sample = os.environ.get("RESEARCH_SAMPLE", "latest")
        cases = fixed_cases(sample, sources)
        texts = {}
        if sample == "v7-regression":
            research_analysis.PROMPT_VERSION = V7_PROMPT
        report["sample"] = sample
        report["prompt_version"] = research_analysis.PROMPT_VERSION
        report["sample_expectations"] = [
            {
                name: case[name]
                for name in (
                    "source_id",
                    "reading_check",
                    "expected_content_kinds",
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
        report["monthly_qualification_limit_usd"] = os.environ[
            "RADAR_ANALYSIS_MONTHLY_BUDGET_USD"
        ]
        report["review_pricing_nanousd_per_token"] = {
            "input": research_review.INPUT_NANOUSD_PER_TOKEN,
            "output": research_review.OUTPUT_NANOUSD_PER_TOKEN,
        }

        def collect(name):
            try:
                if cases:
                    record, text = fixed_publication(cases[name], now)
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
            for health, records in pool.map(collect, sources):
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
        if model == "gpt-5-mini" and len({r["source_id"] for r in records}) != maximum:
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
        for _ in range(3 * len(records)):
            result = research_analysis.enrich(
                max_items=1,
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
            if result.get("failed") or not result.get("completed"):
                break  # Diagnose the first failure before spending on more documents.
            requested = [
                item
                for item in report["items"]
                if item.get("analysis_status") != "not_requested"
            ]
            if all(current_review(item) for item in requested):
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
            current_analysis(item) and item.get("research_lane") == "core"
            for item in report["items"]
        )
        # This qualifies transport/structure/binding, not reviewer correctness or alpha.
        if requested and report["reviewed"] == len(requested):
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
