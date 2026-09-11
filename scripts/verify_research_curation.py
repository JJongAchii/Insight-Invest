"""Replay the real feed through editorial projection without network or state writes.

Outputs local evidence only; the normal poller remains the sole production writer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
from module import research_curation, research_feed  # noqa: E402


def run(before: dict) -> tuple[dict, dict]:
    after = deepcopy(before)
    for item in after["items"]:
        if item.get("record_schema_version") == 4:
            research_feed.apply_editorial_analysis(item)
    research_curation.mark_duplicates(after["items"])
    old = {item["entry_id"]: item for item in before["items"]}
    assert set(old) == {item["entry_id"] for item in after["items"]}
    for item in after["items"]:
        prior = old[item["entry_id"]]
        for field in (
            "analysis",
            "editorial_selection",
            "available_at",
            "notification_origin",
        ):
            assert prior.get(field) == item.get(field), (item["title"], field)
        # This historical audit cannot create a new notification entitlement.
        assert not item.get("notification_eligible") or prior.get(
            "notification_eligible"
        )
    core = [item for item in after["items"] if item["research_lane"] == "core"]
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "status": "curation_projection_checked",
        "production_modified": False,
        "llm_calls": 0,
        "network_calls": 0,
        "entries_preserved": len(old),
        "lanes": dict(Counter(item["research_lane"] for item in after["items"])),
        "core_reading": dict(
            Counter(
                (item.get("reading_brief") or {}).get("status", "held") for item in core
            )
        ),
        "items": [
            {
                "entry_id": item["entry_id"],
                "title": item["title"],
                "url": item["url"],
                "source_id": item["source_id"],
                "lane": item["research_lane"],
                "duplicate_of": item.get("duplicate_of"),
                "reading_status": (item.get("reading_brief") or {}).get("status"),
                "held_fields": (item.get("reading_brief") or {}).get("held_fields", {}),
            }
            for item in after["items"]
            if old[item["entry_id"]].get("research_lane") == "core"
        ],
    }
    return after, report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    os.environ["RADAR_ANALYSIS_ENABLED"] = "true"
    snapshot, report = run(json.loads(args.before.read_text()))
    report["before_sha256"] = hashlib.sha256(args.before.read_bytes()).hexdigest()
    args.output.mkdir(parents=True, exist_ok=True)
    for name, value in (
        ("projected-feed.json", snapshot),
        ("curation-report.json", report),
    ):
        (args.output / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        )
    # Small actual-output UI fixture; no synthetic promotion of rejected content.
    sample_ids = ("f7aa0071", "abd06c08", "937631bb")
    sample = [item for item in snapshot["items"] if item["entry_id"][:8] in sample_ids]
    (args.output / "ui-sample.json").write_text(
        json.dumps({**report, "items": sample}, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "status",
                    "entries_preserved",
                    "lanes",
                    "core_reading",
                    "llm_calls",
                )
            },
            ensure_ascii=False,
        )
    )
