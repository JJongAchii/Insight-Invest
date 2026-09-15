"""Fetch every current core original for a local editorial audit, without LLM calls.

The supplied feed is a frozen read-only snapshot. Full extracted bodies stay in the
explicit local output directory, not published research or Git. This collects facts;
it does not declare a document useful, correct, or suitable for core publication.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from qdata.radar_editorial import CHANNELS, content_digest, parse_publication  # noqa: E402
from qdata.radar_public import _fetch_bytes  # noqa: E402


def run(feed_path: Path, output: Path, entry_ids: list[str] | None = None) -> dict:
    feed = json.loads(feed_path.read_text())
    selected = [
        item
        for item in feed["items"]
        if (
            item["entry_id"] in entry_ids
            if entry_ids
            else item["research_lane"] == "core"
        )
    ]
    if entry_ids and {item["entry_id"] for item in selected} != set(entry_ids):
        raise ValueError("requested original missing from frozen feed")
    output.mkdir(parents=True, exist_ok=True)

    def collect(item):
        entry = item["entry_id"]
        # Digest-based filenames only; the webpage cannot choose an output path.
        if len(entry) != 64 or any(c not in "0123456789abcdef" for c in entry):
            raise ValueError("invalid entry digest")
        result = {
            name: item.get(name)
            for name in (
                "entry_id",
                "title",
                "source_id",
                "url",
                "pdf_url",
                "source_digest",
                "source_chars",
                "analysis_scope",
                "published_at",
                "authors",
            )
        }
        try:
            document = parse_publication(
                _fetch_bytes(item["url"]),
                url=item["url"],
                channel=CHANNELS[item["source_id"]],
                seed=item,
            )
            text = document["text"]
            digest = content_digest(text)
            result.update(
                fetched_digest=digest,
                fetched_chars=len(text),
                digest_matches=digest == item["source_digest"],
                fetched_scope=document["analysis_scope"],
            )
            # Save exactly what was read, even on drift. Never pretend it matched.
            (output / f"{entry}.txt").write_text(text)
        except Exception as exc:
            result["error_type"] = type(exc).__name__
        print(
            json.dumps(
                {
                    k: v
                    for k, v in result.items()
                    if k
                    in {
                        "entry_id",
                        "title",
                        "digest_matches",
                        "fetched_chars",
                        "error_type",
                    }
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        return result

    with ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(collect, selected))
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "feed_generated_at": feed.get("generated_at"),
        "selection": "explicit_entries" if entry_ids else "current_core",
        "selected_count": len(selected),
        "core_count": sum(item["research_lane"] == "core" for item in selected),
        "llm_calls": 0,
        "production_writes": 0,
        "semantic_acceptance": "pending_editorial_reading",
        "items": records,
    }
    (output / "manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--entry-id",
        action="append",
        help="Exact frozen-feed ID; repeat for additional originals",
    )
    args = parser.parse_args()
    report = run(args.feed, args.output, args.entry_id)
    print(json.dumps({key: value for key, value in report.items() if key != "items"}))
