"""Source verification must not turn matching quotes into semantic acceptance."""

from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

from datastore import research
from module import research_analysis as analysis, research_feed
from research_review_fixtures import attach_review
from test_research_analysis import NOW, TEXT, brief, source as source

spec = importlib.util.spec_from_file_location(
    "verify_research_review",
    Path(__file__).resolve().parents[2] / "scripts/verify_research_review.py",
)
verification = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verification)


def reports(source):
    research_feed.reconcile(s3=source, now=NOW)
    analysis.enrich(
        now=NOW,
        text_loader=lambda _item: TEXT,
        model_call=lambda *_args: (brief(), {"input_tokens": 100, "output_tokens": 80}),
    )
    baseline = deepcopy(research.load_feed())
    item = research.load_feed()["items"][0]
    attach_review(item, TEXT, NOW)
    return {
        "production_modified": False,
        "items": [item],
        "analysis_runs": [{"reserved_nanousd": 123}],
    }, baseline


def test_source_check_keeps_semantic_acceptance_separate(source):
    report, baseline = reports(source)
    result = verification.verify(report, baseline, text_loader=lambda _item: TEXT)
    assert result["status"] == "source_and_receipts_checked"
    assert result["semantic_acceptance"] == "requires_human_review"
    assert result["items"][0]["draft_unchanged"]
    assert result["items"][0]["review_state"] == "accepted"


@pytest.mark.parametrize("change", ["draft", "input", "production", "guard"])
def test_verification_rejects_changed_or_unbound_receipts(source, change):
    report, baseline = reports(source)
    text = TEXT
    if change == "draft":
        report["items"][0]["analysis"]["brief"]["title_ko"] = "Changed"
    elif change == "input":
        text += " Different source content."
    elif change == "production":
        report["production_modified"] = True
    else:
        report["items"][0]["analysis"]["review"]["checks"]["method_data"][
            "guard_issues"
        ] = ["forged"]
    with pytest.raises(ValueError):
        verification.verify(report, baseline, text_loader=lambda _item: text)
