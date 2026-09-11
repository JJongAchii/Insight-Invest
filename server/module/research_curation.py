"""Source-bound editorial corrections from the production reading audit.

These are explicit editor decisions, NOT manufactured model receipts or research
validity judgments. Changed originals automatically leave the frozen audit scope.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

BINDINGS = (
    "source_id",
    "source_digest",
    "title",
    "url",
    "parser_version",
    "analysis_scope",
)


@lru_cache(maxsize=1)
def _audits() -> dict:
    path = Path(__file__).with_name("research_editorial_audit.json")
    return json.loads(path.read_text())["items"]


def original_audit(item: dict) -> dict | None:
    entry_id = item.get("entry_id", item.get("entry_id_sha256"))
    audit = _audits().get(entry_id)
    if audit and all(item.get(key) == audit.get(key) for key in BINDINGS):
        return audit
    return None


def mark_duplicates(items: list[dict]) -> None:
    """Keep both IDs and library records; only suppress a verified second card.

    A title match alone is never enough. The fixed pair was checked against the
    exact same PDF bytes on both official hosts. A changed/missing peer unlinks it.
    """
    by_id = {item["entry_id"]: item for item in items}
    for item in items:
        item.pop("duplicate_of", None)
        audit = original_audit(item) or {}
        peer = by_id.get(audit.get("duplicate_of"))
        peer_audit = original_audit(peer) if peer else None
        if (
            peer_audit
            and audit.get("document_sha256")
            and audit["document_sha256"] == peer_audit.get("document_sha256")
            and peer.get("research_lane") == "core"
        ):
            item["duplicate_of"] = peer["entry_id"]
            item["research_lane"] = "context"
            item["relevance_reason"] = "same_official_document"
            item["notification_eligible"] = False
