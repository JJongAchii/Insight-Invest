"""Offline contracts for document admission and source-to-Korean meaning.

These injected decisions are NOT predictions from the revised prompts. Frozen
real-source qualification, including the known E failures, remains required.
"""

from copy import deepcopy
import json

import pytest

from module import research_analysis as analysis, research_review as review
from module import research_selection as selection
from research_review_fixtures import boundary_for, reading_test_value, selection_for
from test_research_analysis import NOW, TEXT, source as source, wire_brief


def refresh(receipt):
    receipt["decision_digest"] = review.digest(receipt["decision"])


@pytest.mark.parametrize(
    "kind", ["research", "practitioner", "market_commentary", "other"]
)
@pytest.mark.parametrize("has_reading_test", [False, True])
def test_document_reading_test_not_genre_or_local_mechanism_selects_core(
    source, kind, has_reading_test
):
    item = deepcopy(source.record)
    receipt = selection_for(item, TEXT, NOW, kind=kind)
    decision = receipt["decision"]
    decision["main_purpose"]["category"] = "mixed_investment_analysis"
    decision["primary_subject"] = "market_outlook"
    if not has_reading_test:
        decision["reading_test"] = None
    refresh(receipt)
    item["editorial_selection"] = receipt
    item["editorial_boundary"] = boundary_for(item, TEXT, NOW)
    # Even an accepted local quote and all the old mixed-outlook flags cannot
    # bypass the whole-document reading decision. Conversely genre isn't a veto.
    assert selection.automatic_state(item) == (
        "core" if has_reading_test else "context"
    )


@pytest.mark.parametrize("reading_test", [{}, {"question": "Why?"}, False])
def test_malformed_document_reading_test_is_not_accepted(source, reading_test):
    item = deepcopy(source.record)
    receipt = selection_for(item, TEXT, NOW)
    receipt["decision"]["reading_test"] = reading_test
    refresh(receipt)
    item["editorial_selection"] = receipt
    assert selection.model_state(item) == "pending"


def test_old_decision_cannot_be_silently_upgraded_to_new_reading_contract(source):
    item = deepcopy(source.record)
    receipt = selection_for(item, TEXT, NOW)
    del receipt["decision"]["reading_test"]
    refresh(receipt)
    item["editorial_selection"] = receipt
    assert selection.model_state(item) == "pending"


def test_reading_test_evidence_is_resolved_from_source_not_generated_quote(source):
    raw = {
        "main_purpose": {
            "category": "investment_analysis",
            "evidence": {"evidence_ids": [0]},
        },
        "reading_test": reading_test_value(),
        "primary_subject": "investment_methodology",
        "content_kind": "practitioner",
        "contribution_type": "investment_mechanism",
        "investment_focus": True,
        "transferable_insight": {"evidence_ids": [0]},
        "reason": "Synthetic contract check.",
        "reading_points": {name: None for name in selection.POINT_NAMES},
    }
    receipt = selection.receipt(source.record, raw, TEXT, NOW.isoformat())
    grounded = receipt["decision"]["reading_test"]
    assert grounded["evidence_excerpts"] == [analysis._source_passages(TEXT)[0]["text"]]
    raw["reading_test"]["evidence"] = {"evidence_ids": [99999]}
    with pytest.raises(analysis.AnalysisContractError, match="bounded span"):
        selection.receipt(source.record, raw, TEXT, NOW.isoformat())


def test_source_claims_survive_grounding_and_reach_independent_reviewer():
    raw = wire_brief()
    grounded = analysis._ground_response(raw, TEXT)
    assert grounded["why_read"]["source_claims"] == raw["why_read"]["source_claims"]
    sent = json.loads(review.request_payload(TEXT, "Original", grounded)["input"])
    assert (
        sent["draft"]["why_read"]["source_claims"] == raw["why_read"]["source_claims"]
    )
    assert "UNTRUSTED draft content" in review.SYSTEM
    assert "subject, direction, condition" in review.SYSTEM


@pytest.mark.parametrize(
    "claims",
    [
        [],
        {},
        [{"subject": "flows"}],
        [{"subject": "flows", "relationship": "reverse", "conditions": ""}],
    ],
)
def test_invalid_claim_extraction_is_not_a_new_brief(claims):
    raw = wire_brief()
    raw["why_read"]["source_claims"] = claims
    with pytest.raises(analysis.AnalysisContractError, match="source claim"):
        analysis._ground_response(raw, TEXT)


def test_new_writer_must_return_claim_extraction_but_legacy_reader_still_works(
    monkeypatch,
):
    raw = wire_brief()
    del raw["why_read"]["source_claims"]
    # Historical persisted briefs remain parseable; new generation cannot omit it.
    assert analysis._ground_response(raw, TEXT)["why_read"]
    usage = {"input_tokens": 11, "output_tokens": 12}
    monkeypatch.setattr(analysis, "_response_call", lambda *_a, **_k: (raw, usage))
    with pytest.raises(
        analysis.AnalysisContractError, match="omitted source claims"
    ) as exc:
        analysis._model_call(TEXT, "Original", "unused")
    assert exc.value.usage == usage


def test_context_is_visible_but_cannot_be_cited_as_selected_evidence(monkeypatch):
    text = (
        "The author discusses a reversal rather than continuing inflows. "
        "A reversal of flows precedes observed defaults in this account. "
        "Loan defaults take time to appear after funding deteriorates."
    )
    passages = analysis._source_passages(text)
    plan = {
        name: [passages[1]["text"]] if name == "why_read" else None
        for name in analysis.FIELDS
    }
    payload = analysis._request_payload(text, "Original", evidence_plan=plan)
    sent = json.loads(payload["input"])
    assert [p["id"] for p in sent["source_passages"]] == [1]
    assert [p["id"] for p in sent["source_context"]] == [0, 2]
    assert all(p["citable"] is False for p in sent["source_context"])
    raw = wire_brief()
    for name in analysis.FIELDS:
        if name != "why_read":
            raw[name] = None
    raw["why_read"]["evidence_ids"] = [0]  # Visible but not admitted citation.
    monkeypatch.setattr(
        analysis,
        "_response_call",
        lambda *_a, **_k: (raw, {"input_tokens": 11, "output_tokens": 12}),
    )
    with pytest.raises(
        analysis.AnalysisContractError, match="outside selected evidence"
    ):
        analysis._model_call(text, "Original", "unused", evidence_plan=plan)


def test_source_claims_do_not_override_rejected_korean_sentence():
    from research_review_fixtures import checks_for

    brief = analysis._ground_response(wire_brief(), TEXT)
    checks = checks_for(brief)
    checks["why_read"].update(status="unsupported", reason_ko="주체와 인과 방향이 다름")
    assert review._decision(checks, brief) == "rejected"
