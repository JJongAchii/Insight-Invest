"""Verify local before/after production snapshots without credentials or writes to AWS."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import polars as pl


def verify(folder: Path) -> dict:
    files = {}

    def read(name):
        path = folder / name
        files[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        return json.loads(path.read_text())

    before, after = read("feed-before.json"), read("feed-after.json")
    before_ids = {item["entry_id"] for item in before["items"]}
    after_ids = {item["entry_id"] for item in after["items"]}
    if not before_ids <= after_ids:
        raise ValueError("previous feed entries were lost")
    preserved = {}
    for kind in ("read", "deliveries"):
        paths = [folder / f"{kind}-{side}.parquet" for side in ("before", "after")]
        tables = [pl.read_parquet(path) for path in paths]
        if not set(tables[0].columns) <= set(tables[1].columns):
            raise ValueError("previous library/delivery schema was lost")
        old = Counter(tables[0].iter_rows())
        new = Counter(tables[1].select(tables[0].columns).iter_rows())
        if old - new:
            raise ValueError(
                f"previous {kind} records changed; inspect user activity before claiming preservation"
            )
        preserved[kind] = {
            "before": tables[0].height,
            "after": tables[1].height,
            "previous_rows_preserved": True,
        }
        files.update(
            {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        )
    old_seen, new_seen = read("seen-before.json"), read("seen-after.json")
    if datetime.fromisoformat(new_seen["seen_through"]) < datetime.fromisoformat(
        old_seen["seen_through"]
    ):
        raise ValueError("seen cursor moved backwards")
    core = [item for item in after["items"] if item["research_lane"] == "core"]
    if not core or any(
        item.get("editorial_selection_status") != "core" for item in core
    ):
        raise ValueError("core is empty or lacks current source-only selection")
    return {
        "status": "local_release_snapshots_checked",
        "network_calls": 0,
        "llm_calls": 0,
        "files_sha256": files,
        "previous_feed_ids_preserved": True,
        "feed_before": len(before_ids),
        "feed_after": len(after_ids),
        "library": preserved,
        "seen_cursor_not_reset": True,
        "lanes": dict(Counter(item["research_lane"] for item in after["items"])),
        "core": [
            {
                key: item.get(key)
                for key in (
                    "entry_id",
                    "source_id",
                    "title",
                    "url",
                    "analysis_status",
                    "editorial_review_status",
                    "editorial_selection_status",
                    "notification_eligible",
                )
            }
            for item in core
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshots", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = verify(args.snapshots)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))
