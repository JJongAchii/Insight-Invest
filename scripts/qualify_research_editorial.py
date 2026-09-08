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
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from datastore import research, storage  # noqa: E402
from module import research_analysis, research_feed  # noqa: E402
from qdata.radar_editorial import CHANNELS, discover_publications  # noqa: E402

QUALIFICATION_ROOT = "s3://insight-invest-datalake/research-radar/qualification/openai"
ENABLED_SOURCES = tuple(
    name for name in CHANNELS if name not in {"man-systematic-insights", "kjfs-current"}
)


def validate_environment() -> tuple[int, list[str]]:
    if not os.environ.get("OPENAI_API_KEY", "").strip():
        raise ValueError("OPENAI_API_KEY is not configured")
    if storage.app_data_root() != QUALIFICATION_ROOT:
        raise ValueError("qualification requires its isolated APP_DATA prefix")
    budget = Decimal(os.environ.get("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "0"))
    if not Decimal("0") < budget <= Decimal("0.10"):
        raise ValueError(
            "qualification monthly budget must be positive and at most $0.10"
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
    return maximum, sources


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

    try:
        maximum, sources = validate_environment()
        report["max_items"] = maximum
        report["monthly_qualification_limit_usd"] = "0.10"

        def collect(name):
            try:
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

        records_by_id = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            for health, records in pool.map(collect, sources):
                report["sources"].append(health)
                for record in records:
                    # This is a backfill qualification, not a live push candidate.
                    record["notification_eligible"] = False
                    records_by_id.setdefault(record["entry_id_sha256"], record)
                print(json.dumps({"stage": "source", **health}), flush=True)
                save_report()
        records = list(records_by_id.values())[:maximum]
        if not records:
            raise ValueError("no readable qualification publications")

        research_feed.reconcile(s3=RecordSnapshot(records), now=now)
        feed = research.load_feed()
        selected_ids = {record["entry_id_sha256"] for record in records}
        feed["items"] = [
            item for item in feed["items"] if item["entry_id"] in selected_ids
        ]
        research.save_feed(feed)  # Dedicated qualification prefix ONLY.

        for _ in range(len(records)):
            result = research_analysis.enrich(max_items=1)
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
            if all(item.get("analysis_status") == "ready" for item in requested):
                break
        requested = [
            item
            for item in report["items"]
            if item.get("analysis_status") != "not_requested"
        ]
        report["requested"] = len(requested)
        report["ready"] = sum(
            item.get("analysis_status") == "ready" for item in requested
        )
        report["core"] = sum(
            item.get("research_lane") == "core" for item in report["items"]
        )
        # This qualifies transport/structure/grounding, not semantic quality or alpha.
        if requested and report["ready"] == len(requested):
            report["status"] = "api_contract_qualified"
        else:
            report["status"] = "needs_diagnosis"
    except Exception as exc:
        report["status"] = "needs_diagnosis"
        report["error_type"] = type(exc).__name__
    finally:
        save_report()
    print(
        json.dumps(
            {
                key: report.get(key)
                for key in ("status", "requested", "ready", "core", "error_type")
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
