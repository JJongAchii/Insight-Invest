"""Offline replay of public-source probe receipts through producer and consumer.

Uses the existing in-memory S3 test double and a temporary, synthetic user library.
No network, LLM, production write, or semantic-quality acceptance is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "server/tests")]

from datastore import research as store  # noqa: E402
from module import research_feed  # noqa: E402
from qdata.radar_realtime import collect_due_sources  # noqa: E402
from test_research_academic import S3  # noqa: E402


def run(probes: list[Path], legacy_path: Path) -> dict:
    groups, inputs = {}, {}
    for path in [*probes, legacy_path]:
        inputs[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    for path in probes:
        for group in json.loads(path.read_text())["sources"]:
            if group.get("error"):
                raise ValueError("resolve source transport errors before replay")
            groups[group["source_id"]] = group["records"]
    legacy = json.loads(legacy_path.read_text())
    if not any(
        record["url"] == legacy["url"] for rows in groups.values() for record in rows
    ):
        raise ValueError("the actual legacy original must appear in the source probes")
    specs = [
        SimpleNamespace(
            source_id=name, kind="editorial", cadence_minutes=60, realtime_enabled=True
        )
        for name in groups
    ]
    s3 = S3()
    s3.now = datetime.now(UTC)
    key = f"records/{legacy['entry_id_sha256']}.json"
    s3.put_object(Bucket="b", Key=key, Body=json.dumps(legacy).encode())
    with (
        TemporaryDirectory(prefix="research-originals-") as root,
        patch.dict(os.environ, {"APP_DATA": root, "RADAR_ANALYSIS_ENABLED": "false"}),
    ):
        research_feed.reconcile(s3=s3, bucket="b", record_prefix="records/", now=s3.now)
        entry_id = legacy["entry_id_sha256"]
        store.set_read(entry_id, read=True)
        store.set_saved(entry_id, saved=True)
        store.save_seen_through(s3.now)
        paths = [
            Path(root) / name for name in (store.READ_STATE_FILE, store.SEEN_STATE_FILE)
        ]
        before = [path.read_bytes() for path in paths]
        collections, projections = [], []
        for _ in range(3):
            collections.append(
                collect_due_sources(
                    specs,
                    s3=s3,
                    bucket="b",
                    record_prefix="records/",
                    runtime_prefix="runtime",
                    now=s3.now,
                    discoverer=lambda spec, **kwargs: groups[spec.source_id],
                )
            )
            projections.append(
                research_feed.reconcile(
                    s3=s3,
                    bucket="b",
                    record_prefix="records/",
                    now=s3.now,
                )
            )
            assert collections[-1]["sources_failed"] == 0
            assert not any("/pending/" in key for key in s3.objects)
            s3.now += timedelta(days=1)
        items = store.load_feed()["items"]
        assert all(
            item["research_lane"] != "core" and not item["notification_eligible"]
            for item in items
        )
        assert all(
            item["url"] and item["authors"] and item["published_at"] and item["summary"]
            for item in items
        )
        assert len({item["url"] for item in items}) == len(items)
        assert projections[-1]["added"] == projections[-1]["removed"] == 0
        assert collections[-1]["records_revised"] == 0
        match = [item for item in items if item["url"] == legacy["url"]]
        assert len(match) == 1 and match[0]["entry_id"] == entry_id
        assert match[0]["record_schema_version"] == 4
        assert match[0]["discovered_at"] == legacy["discovered_at"]
        assert not match[0]["notification_candidate"]
        assert store.entry_states()[entry_id] == {"is_read": True, "is_saved": True}
        assert [path.read_bytes() for path in paths] == before
        sample = [
            next(
                item
                for item in items
                if item["source_id"] == "aqr-research"
                and item["analysis_scope"] == "full_pdf"
            ),
            next(item for item in items if item["source_id"] == "rafi-publications"),
            next(item for item in items if item["source_id"] == "arxiv-q-fin-tr"),
        ]
        return {
            "checked_at": datetime.now(UTC).isoformat(),
            "status": "original_feed_checked",
            "production_modified": False,
            "llm_calls": 0,
            "network_calls": 0,
            "semantic_quality": "not_evaluated",
            "input_sha256": inputs,
            "source_count": len(groups),
            "records": len(items),
            "collections": collections,
            "projections": projections,
            "legacy_id_preserved": True,
            "synthetic_library_bytes_preserved": True,
            "core": 0,
            "notification_candidates": 0,
            "items": sample,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--probe",
        type=Path,
        action="append",
        required=True,
        help="Local receipt; later files replace earlier source groups",
    )
    parser.add_argument("--legacy-record", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.probe, args.legacy_record)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "items"}))
