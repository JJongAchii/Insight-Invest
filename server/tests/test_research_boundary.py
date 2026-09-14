"""Offline routing/state tests; fixed original API receipts qualify semantics."""

from copy import deepcopy
from datetime import timedelta

import pytest

from datastore import research, storage
from module import research_analysis as analysis, research_boundary as boundary
from module import (
    research_curation,
    research_feed,
    research_review,
    research_selection as selection,
)
from research_review_fixtures import boundary_for, selection_for
from test_research_analysis import NOW, TEXT, source as source


def forbidden(*args, **kwargs):
    pytest.fail("unexpected paid call")


def pending(source, tmp_path):
    (
        tmp_path
        / f"research_analysis/boundaries/{boundary.cache_key(source.record)}.json"
    ).unlink()
    research_feed.reconcile(s3=source, now=NOW)
    item = research.load_feed()["items"][0]
    item["editorial_selection"] = selection_for(item, TEXT, NOW)
    research.save_feed(
        {"items": [item], "generated_at": NOW.isoformat(), "schema_version": 1}
    )
    return item


@pytest.mark.parametrize(
    "verdict,expected",
    [("substantive", "core"), ("context", "held"), ("uncertain", "held")],
)
def test_boundary_is_source_only_reserved_and_disagreement_does_not_retry(
    source, tmp_path, verdict, expected
):
    pending(source, tmp_path)

    def check(text, title, api_key):
        assert text == TEXT
        assert (
            storage.read_json("research_analysis/budget-2026-09.json")[
                "reserved_nanousd"
            ]
            > 185_000
        )
        return {
            "analysis_object": "unclear"
            if verdict == "uncertain"
            else "investment_rule_or_measurement",
            "object_evidence_id": None if verdict == "uncertain" else 0,
            "verdict": verdict,
            "evidence_id": None if verdict == "uncertain" else 0,
            "reason": "Offline boundary fixture",
        }, {"input_tokens": 100, "output_tokens": 80}

    result = analysis.enrich(
        now=NOW,
        text_loader=lambda _: TEXT,
        boundary_call=check,
        selection_call=forbidden,
        model_call=forbidden,
        review_call=forbidden,
        gate_only=True,
    )
    item = research.load_feed()["items"][0]
    assert result["boundary_reviewed"] == 1 and result["reserved_nanousd"] == 185_000
    assert selection.model_state(item) == "core"  # Never rewrite the first judgment.
    assert selection.automatic_state(item) == expected
    assert item["research_lane"] == ("core" if expected == "core" else "discovery")
    assert item["notification_eligible"] is (expected == "core")
    if expected == "core":
        assert item["available_at"] == NOW.isoformat()
    else:
        assert item["relevance_reason"] == "original_selection_disagreement"
    assert "analysis" not in item
    result = analysis.enrich(
        now=NOW,
        text_loader=forbidden,
        boundary_call=forbidden,
        selection_call=forbidden,
        gate_only=True,
    )
    assert result["completed"] == 0


def test_independent_payload_contains_only_original():
    payload = boundary.request_payload(TEXT, "Original title")
    assert set(boundary.json.loads(payload["input"])) == {
        "source_title",
        "source_passages",
    }
    assert payload["store"] is False and "tools" not in payload
    assert "previous_response_id" not in payload
    assert payload["text"]["format"]["strict"] is True


@pytest.mark.parametrize(
    "field", ["source_digest", "title", "parser_version", "analysis_scope", "decision"]
)
def test_receipt_expires_on_changed_source_or_verdict(source, field):
    item = deepcopy(source.record)
    item["editorial_boundary"] = boundary_for(item, TEXT, NOW)
    assert boundary.state(item) == "substantive"
    if field == "decision":
        item["editorial_boundary"][field]["verdict"] = "context"
    else:
        item[field] = "changed"
    assert boundary.state(item) == "pending"


@pytest.mark.parametrize("number", [None, True, -1, 99999, "0"])
def test_invalid_grounding_fails_closed(source, number):
    with pytest.raises(analysis.AnalysisContractError):
        boundary.receipt(
            source.record,
            {
                "analysis_object": "investment_rule_or_measurement",
                "object_evidence_id": 0,
                "verdict": "substantive",
                "evidence_id": number,
                "reason": "Fixture",
            },
            TEXT,
            NOW.isoformat(),
        )


def test_only_clear_empirical_research_skips_boundary(source):
    item = deepcopy(source.record)
    item["editorial_selection"] = selection_for(item, TEXT, NOW)
    assert selection.needs_boundary(item)
    assert selection.automatic_state(item) == "pending"
    value = item["editorial_selection"]["decision"]
    value.update(
        primary_subject="empirical_market_research",
        contribution_type="empirical_finding",
    )
    item["editorial_selection"]["decision_digest"] = research_review.digest(value)
    assert not selection.needs_boundary(item)
    assert selection.automatic_state(item) == "core"
    value["content_kind"] = "practitioner"
    item["editorial_selection"]["decision_digest"] = research_review.digest(value)
    assert selection.needs_boundary(item)


def test_budget_hold_cannot_promote_or_pay_for_writer(source, tmp_path, monkeypatch):
    pending(source, tmp_path)
    monkeypatch.setenv("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "0.000001")
    result = analysis.enrich(
        now=NOW,
        text_loader=lambda _: TEXT,
        boundary_call=forbidden,
        model_call=forbidden,
    )
    item = research.load_feed()["items"][0]
    assert result["reason"] == "monthly_budget_reached"
    assert item["research_lane"] == "discovery" and not item["notification_eligible"]
    assert item["relevance_reason"] == "original_boundary_pending"


def test_boundary_cache_recovers_with_no_paid_budget_and_survives_reconcile(
    source, monkeypatch
):
    research_feed.reconcile(s3=source, now=NOW)
    monkeypatch.setenv("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "0.000001")
    result = analysis.enrich(
        now=NOW, text_loader=forbidden, boundary_call=forbidden, gate_only=True
    )
    assert result["cache_hits"] == 2 and not result["boundary_reviewed"]
    before = research.load_feed()["items"][0]
    assert selection.state(before) == "core"
    research_feed.reconcile(s3=source, now=NOW + timedelta(minutes=10))
    after = research.load_feed()["items"][0]
    assert after["editorial_boundary"] == before["editorial_boundary"]
    assert after["available_at"] == before["available_at"]


def test_gate_qualification_cannot_borrow_editor_audit(source, tmp_path, monkeypatch):
    item = pending(source, tmp_path)
    monkeypatch.setattr(
        research_curation,
        "original_audit",
        lambda _: {"lane": "core", "checked_at": NOW.isoformat()},
    )
    assert selection.state(item) == "core"
    assert selection.automatic_state(item) == "pending"
    research_feed.apply_editorial_analysis(item, use_editor_audit=False)
    assert item["research_lane"] == "discovery" and not item["notification_eligible"]
    monkeypatch.setenv("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "0.000001")
    result = analysis.enrich(
        now=NOW, text_loader=lambda _: TEXT, boundary_call=forbidden, gate_only=True
    )
    assert result["reason"] == "monthly_budget_reached"


def test_failed_boundary_keeps_reservation_and_durable_retry(source, tmp_path):
    pending(source, tmp_path)

    def invalid(*args):
        return {
            "analysis_object": "investment_rule_or_measurement",
            "object_evidence_id": 0,
            "verdict": "substantive",
            "evidence_id": 99999,
            "reason": "Invalid",
        }, {
            "input_tokens": 100,
            "output_tokens": 80,
        }

    result = analysis.enrich(now=NOW, text_loader=lambda _: TEXT, boundary_call=invalid)
    item = research.load_feed()["items"][0]
    assert result["failed"] == 1 and result["reserved_nanousd"] > 185_000
    assert item["analysis_retry"]["stage"] == "boundary"
    assert storage.exists(f"research_analysis/retries/{boundary.cache_key(item)}.json")
    assert selection.automatic_state(item) == "pending"
    assert not item["notification_eligible"]


@pytest.mark.parametrize("analysis_object", boundary.ANALYSIS_OBJECTS)
def test_primary_object_cannot_be_overridden_by_substantive_verdict(
    source, analysis_object
):
    research_feed.reconcile(s3=source, now=NOW)
    item = research.load_feed()["items"][0]
    item["editorial_selection"] = selection_for(item, TEXT, NOW)
    item["editorial_boundary"] = boundary.receipt(
        item,
        {
            "analysis_object": analysis_object,
            "object_evidence_id": None if analysis_object == "unclear" else 0,
            "verdict": "substantive",
            "evidence_id": 0,
            "reason": "Contradictory model fixture",
        },
        TEXT,
        NOW.isoformat(),
    )
    expected = "core" if analysis_object in boundary.INVESTMENT_OBJECTS else "held"
    assert selection.automatic_state(item) == expected
    assert item["editorial_boundary"]["decision"]["verdict"] == "substantive"
    research_feed.apply_editorial_analysis(item, use_editor_audit=False)
    assert item["notification_eligible"] is (expected == "core")


@pytest.mark.parametrize("analysis_object", [None, "unknown", ""])
def test_missing_or_unknown_object_is_pending(source, analysis_object):
    item = deepcopy(source.record)
    item["editorial_boundary"] = boundary_for(item, TEXT, NOW)
    value = item["editorial_boundary"]["decision"]
    value["analysis_object"] = analysis_object
    item["editorial_boundary"]["decision_digest"] = research_review.digest(value)
    assert boundary.state(item) == "pending"


@pytest.mark.parametrize("number", [None, True, -1, 99999, "0"])
def test_object_itself_requires_grounded_passage(source, number):
    with pytest.raises(
        analysis.AnalysisContractError, match="analysis-object evidence"
    ):
        boundary.receipt(
            source.record,
            {
                "analysis_object": "business_product_or_policy",
                "object_evidence_id": number,
                "verdict": "context",
                "evidence_id": 0,
                "reason": "Object evidence fixture",
            },
            TEXT,
            NOW.isoformat(),
        )


def test_v1_receipt_is_not_a_current_object_review(source, monkeypatch):
    item = deepcopy(source.record)
    with monkeypatch.context() as prior:
        prior.setattr(boundary, "PROMPT_VERSION", "reading-boundary-v1-source-only")
        value = boundary_for(item, TEXT, NOW)
    item["editorial_boundary"] = value
    assert boundary.state(item) == "pending"
    assert next(iter(boundary.SCHEMA["properties"])) == "analysis_object"
