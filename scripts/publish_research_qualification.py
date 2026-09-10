"""Seed verified reading caches, never feed/library/pending/budget objects.

Explicit release operation after inspecting the actual fixed-source outputs.
The scheduled poller remains the sole feed writer and rechecks all fingerprints.
Default is read-only. Existing cache objects are never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from botocore.exceptions import ClientError
from verify_research_review import verify
from module import (
    research_analysis as analysis,
    research_review as review,
    research_selection as selection,
)

BUCKET = "insight-invest-datalake"
PREFIX = "app/research_analysis/"


def plan(report: dict, *, text_loader=analysis._public_text) -> dict:
    if (
        report.get("production_modified") is not False
        or report.get("status") != "api_contract_qualified"
    ):
        raise ValueError("requires completed isolated qualification")
    if not 1 <= len(report["items"]) <= 12:
        raise ValueError("release requires a bounded inspected sample")
    objects = {}
    for item in report["items"]:
        if selection.state(item) == "pending":
            raise ValueError("selection is not current")
        text = text_loader(item)  # Official re-fetch, exact full source digest checked.
        selected = item["editorial_selection"]
        if selected["input_digest"] != review.digest(text):
            raise ValueError("selection input changed")
        passages = analysis._source_passages(text)
        lookup = {p["text"]: p["id"] for p in reversed(passages)}
        decision = selected["decision"]
        raw = {
            name: decision[name]
            for name in ("content_kind", "investment_focus", "reason")
        }
        raw["transferable_insight"] = (
            {"evidence_ids": [lookup[q] for q in decision["evidence_excerpts"]]}
            if decision["evidence_excerpts"]
            else None
        )
        raw["reading_points"] = {
            name: {"evidence_ids": [lookup[q] for q in quotes]} if quotes else None
            for name, quotes in decision["reading_points"].items()
        }
        checked = selection.receipt(item, raw, text, selected["checked_at"])
        if checked["decision_digest"] != selected["decision_digest"]:
            raise ValueError("selection receipt differs from original evidence")
        objects[PREFIX + f"selections/{selection.cache_key(item)}.json"] = selected
        if selection.state(item) != "core":
            continue  # Never seed an obsolete summary of excluded commentary.
        if (
            item.get("analysis", {}).get("fingerprint") != analysis.cache_key(item)
            or review.state(item) == "pending"
        ):
            raise ValueError("reading brief/review is not current")
        verify({**report, "items": [item]}, text_loader=lambda _: text)
        objects[PREFIX + f"cache/{analysis.cache_key(item)}.json"] = item["analysis"]
        objects[PREFIX + f"reviews/{review.cache_key(item, item['analysis'])}.json"] = (
            item["analysis"]["review"]
        )
    return objects


def seed(objects: dict, client, *, apply: bool = False) -> list[dict]:
    # Validate the entire plan before the first write, not after partially seeding.
    if not objects or any(
        not re.fullmatch(
            re.escape(PREFIX) + r"(?:selections|cache|reviews)/[a-f0-9]{64}\.json", key
        )
        for key in objects
    ):
        raise ValueError("outside reading cache scope")
    receipts = []
    for key, value in objects.items():
        body = json.dumps(value, ensure_ascii=False).encode()
        state = "planned"
        if apply:
            try:
                client.put_object(
                    Bucket=BUCKET,
                    Key=key,
                    Body=body,
                    ContentType="application/json",
                    ServerSideEncryption="AES256",
                    IfNoneMatch="*",
                )
                state = "seeded"
            except ClientError as exc:
                if exc.response["Error"]["Code"] != "PreconditionFailed":
                    raise
                existing = json.loads(
                    client.get_object(Bucket=BUCKET, Key=key)["Body"].read()
                )
                if existing != value:
                    raise ValueError(
                        "existing cache differs; never overwrite it"
                    ) from exc
                state = "already_identical"
        receipts.append(
            {"key": key, "sha256": hashlib.sha256(body).hexdigest(), "state": state}
        )
    return receipts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--report-sha256", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.report.read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.report_sha256:
        raise SystemExit("report digest differs from inspected artifact")
    objects = plan(json.loads(raw))
    import boto3

    result = {
        "report_sha256": args.report_sha256,
        "apply": args.apply,
        "llm_calls": 0,
        "feed_writer": "scheduled_research_poller",
        "library_pending_and_budget_modified": False,
        "objects": seed(
            objects, boto3.client("s3", region_name="ap-northeast-2"), apply=args.apply
        ),
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))
