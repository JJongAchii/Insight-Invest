"""Read-only source/draft/receipt verification for isolated qualification artifacts.

No OpenAI call, S3 write, or semantic-accuracy verdict. Original bodies are read
transiently; only hashes, counts and review diagnostics enter the output receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from module import research_analysis as analysis, research_review as review  # noqa: E402


def verify(
    report: dict, baseline: dict | None = None, *, text_loader=analysis._public_text
) -> dict:
    if report.get("production_modified") is not False:
        raise ValueError("only isolated qualification artifacts are accepted")
    old = {item["entry_id"]: item for item in baseline["items"]} if baseline else None
    checked = []
    for item in report["items"]:
        draft = item["analysis"]
        if old is not None:
            prior = old[item["entry_id"]]
            if (
                draft["fingerprint"] != prior["analysis"]["fingerprint"]
                or draft["brief"] != prior["analysis"]["brief"]
                or item["source_digest"] != prior["source_digest"]
            ):
                raise ValueError("source or draft changed from the preserved baseline")
        text = text_loader(item)
        analysis.validate_brief(draft["brief"], text)
        quotes = [
            quote
            for field in analysis.FIELDS
            if (point := draft["brief"][field])
            for quote in point.get("evidence_excerpts", [point["evidence"]])
        ]
        receipt = draft.get("review") or {}
        current = receipt.get("prompt_version") == review.PROMPT_VERSION
        check_quotes = []
        if current:
            if review.state(item) == "pending" or receipt[
                "input_digest"
            ] != review.digest(text):
                raise ValueError(
                    "review receipt is not bound to the exact source/draft/settings"
                )
            passages = analysis._source_passages(text)
            lookup = {passage["text"]: passage["id"] for passage in reversed(passages)}
            raw = {}
            for field, check in receipt["checks"].items():
                check_quotes.extend(check["evidence_excerpts"])
                raw[field] = {
                    "status": check["status"],
                    "reason_ko": check["reason_ko"],
                    "evidence_ids": [
                        lookup[quote] for quote in check["evidence_excerpts"]
                    ],
                }
            recomputed = review.validate_checks(raw, text, draft["brief"])
            for field in review.FIELDS:
                if (
                    recomputed[field]["guard_issues"]
                    != receipt["checks"][field]["guard_issues"]
                ):
                    raise ValueError(
                        "code guard receipt differs from original evidence"
                    )
            if review._decision(recomputed, draft["brief"]) != receipt["verdict"]:
                raise ValueError("stored review verdict differs from computed decision")
        checked.append(
            {
                "entry_id": item["entry_id"],
                "source_id": item["source_id"],
                "url": item["url"],
                "source_digest": item["source_digest"],
                "source_chars_checked": len(text),
                "draft_digest": review.digest(draft["brief"]),
                "draft_unchanged": True if old is not None else None,
                "draft_quotes_checked": len(quotes),
                "review_quotes_checked": len(check_quotes),
                "current_review": current,
                "review_state": review.state(item),
                "model_held_fields": [
                    name
                    for name, check in receipt.get("checks", {}).items()
                    if current and check["status"] in {"unsupported", "unclear"}
                ],
                "code_guard_issues": {
                    name: check["guard_issues"]
                    for name, check in receipt.get("checks", {}).items()
                    if current and check.get("guard_issues")
                },
                "review_cost_nanousd": receipt.get("cost_nanousd") if current else None,
            }
        )
    return {
        "checked_at": datetime.now(UTC).isoformat(),
        "production_modified": False,
        "status": "source_and_receipts_checked",
        "semantic_acceptance": "requires_human_review",
        "items": checked,
        "review_cost_nanousd": sum(
            item["review_cost_nanousd"] or 0 for item in checked
        ),
        "qualification_reserved_nanousd": report["analysis_runs"][-1][
            "reserved_nanousd"
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = verify(
        json.loads(args.report.read_text()),
        json.loads(args.baseline.read_text()) if args.baseline else None,
    )
    result.update(
        {
            name + "_sha256": hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in (("report", args.report), ("baseline", args.baseline))
            if path is not None
        }
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))
