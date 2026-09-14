"""Offline contracts only. Actual fixed originals qualify semantic reading value."""

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
from research_review_fixtures import boundary_for, boundary_value, selection_for
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
    [
        ("substantive", "core"),
        ("context", "held"),
        ("uncertain", "held"),
    ],
)
def test_evidence_review_is_reserved_and_disagreement_does_not_retry(
    source, tmp_path, verdict, expected
):
    original = pending(source, tmp_path)

    def check(text, title, api_key, *, proposed):
        assert text == TEXT and proposed == boundary.evidence_plan(original)
        assert (
            storage.read_json("research_analysis/budget-2026-09.json")[
                "reserved_nanousd"
            ]
            > 185_000
        )
        return boundary_value(verdict=verdict), {
            "input_tokens": 100,
            "output_tokens": 80,
        }

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
    assert item["editorial_selection"] == original["editorial_selection"]
    assert selection.model_state(item) == "core"
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


def test_payload_contains_literal_proposal_not_first_reader_labels_or_summary(source):
    plan = boundary.evidence_plan(source.record)
    payload = boundary.request_payload(TEXT, "Original title", proposed=plan)
    data = boundary.json.loads(payload["input"])
    assert set(data) == {
        "source_passages",
        "proposed_evidence_ids",
        "purpose_evidence_ids",
    }
    passages = {p["id"]: p["text"] for p in data["source_passages"]}
    for field, ids in data["proposed_evidence_ids"].items():
        assert [passages[i] for i in ids] == plan[field]
    assert set(passages) == set(data["purpose_evidence_ids"]).union(
        *data["proposed_evidence_ids"].values()
    )
    assert len(data["source_passages"]) < len(analysis._source_passages(TEXT))
    assert "verdict" not in boundary.SCHEMA["properties"]
    assert "explanation" not in boundary.SCHEMA["properties"]
    assert payload["store"] is False and "tools" not in payload
    assert "previous_response_id" not in payload
    assert payload["text"]["format"]["strict"] is True


def test_diagnostic_model_uses_own_reservation_cost_and_cache(
    source, tmp_path, monkeypatch
):
    item = pending(source, tmp_path)
    original_selection = deepcopy(item["editorial_selection"])
    fingerprint = boundary.cache_key(item)
    monkeypatch.setattr(boundary, "MODEL", "gpt-5.4-2026-03-05")
    monkeypatch.setattr(boundary, "INPUT_NANOUSD_PER_TOKEN", 2500)
    monkeypatch.setattr(boundary, "OUTPUT_NANOUSD_PER_TOKEN", 15000)
    reservation = analysis._reserve_payload(
        boundary.request_payload(
            TEXT, item["title"], proposed=boundary.evidence_plan(item)
        ),
        2500,
        15000,
    )

    def check(text, title, api_key, *, proposed):
        assert (
            storage.read_json("research_analysis/budget-2026-09.json")[
                "reserved_nanousd"
            ]
            == reservation
        )
        return boundary_value(), {"input_tokens": 100, "output_tokens": 80}

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
    assert result["reserved_nanousd"] == 1_450_000
    assert item["editorial_selection"] == original_selection
    second = item["editorial_boundary"]
    assert second["cost_nanousd"] == 1_450_000
    assert (
        second["model"] == "gpt-5.4-2026-03-05" and second["fingerprint"] != fingerprint
    )
    monkeypatch.setattr(boundary, "MODEL", "gpt-5-mini")
    assert boundary.state(item) == "pending"


@pytest.mark.parametrize(
    "field",
    [
        "source_digest",
        "title",
        "parser_version",
        "analysis_scope",
        "decision",
        "proposal",
    ],
)
def test_receipt_expires_on_changed_source_verdict_or_proposal(source, field):
    item = deepcopy(source.record)
    item["editorial_boundary"] = boundary_for(item, TEXT, NOW)
    assert boundary.state(item) == "substantive"
    if field == "decision":
        item["editorial_boundary"]["decision"]["verdict"] = "context"
    elif field == "proposal":
        item["editorial_selection"]["decision"]["evidence_excerpts"] = ["Changed"]
    else:
        item[field] = "changed"
    assert boundary.state(item) == "pending"


@pytest.mark.parametrize("number", [None, True, -1, 99999, "0"])
def test_object_requires_bounded_source_evidence(source, number):
    value = boundary_value()
    value["object_evidence_id"] = number
    with pytest.raises(
        analysis.AnalysisContractError, match="analysis-object evidence"
    ):
        boundary.receipt(source.record, value, TEXT, NOW.isoformat())


def test_empirical_label_cannot_bypass_evidence_review(source):
    item = deepcopy(source.record)
    value = item["editorial_selection"]["decision"]
    value.update(
        content_kind="research",
        primary_subject="empirical_market_research",
        contribution_type="empirical_finding",
    )
    item["editorial_selection"]["decision_digest"] = research_review.digest(value)
    assert selection.model_state(item) == "core"
    assert selection.needs_boundary(item)
    assert selection.automatic_state(item) == "pending"


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


def test_paid_cache_recovers_without_new_budget_and_survives_reconcile(
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


def test_qualification_cannot_borrow_manual_audit(source, tmp_path, monkeypatch):
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


def test_failed_review_keeps_reservation_and_durable_retry(source, tmp_path):
    pending(source, tmp_path)

    def invalid(*args, **kwargs):
        value = boundary_value()
        value["checks"]["insight"]["role"] = "invented"
        return value, {"input_tokens": 100, "output_tokens": 80}

    result = analysis.enrich(now=NOW, text_loader=lambda _: TEXT, boundary_call=invalid)
    item = research.load_feed()["items"][0]
    assert result["failed"] == 1 and result["reserved_nanousd"] > 185_000
    assert item["analysis_retry"]["stage"] == "boundary"
    assert storage.exists(f"research_analysis/retries/{boundary.cache_key(item)}.json")
    assert (
        selection.automatic_state(item) == "pending"
        and not item["notification_eligible"]
    )


@pytest.mark.parametrize("analysis_object", boundary.ANALYSIS_OBJECTS)
def test_business_topic_cannot_be_overridden_by_incidental_method(
    source, analysis_object
):
    item = deepcopy(source.record)
    value = boundary_value()
    value.update(
        analysis_object=analysis_object,
        object_evidence_id=None if analysis_object == "unclear" else 0,
    )
    item["editorial_boundary"] = boundary.receipt(item, value, TEXT, NOW.isoformat())
    expected = "core" if analysis_object in boundary.INVESTMENT_OBJECTS else "held"
    assert selection.automatic_state(item) == expected


@pytest.mark.parametrize("role", boundary.ROLES)
def test_code_derives_route_from_roles_not_model_overall_verdict(source, role):
    item = deepcopy(source.record)
    value = boundary_value()
    for check in value["checks"].values():
        check["role"] = role
    item["editorial_boundary"] = boundary.receipt(item, value, TEXT, NOW.isoformat())
    assert selection.automatic_state(item) == (
        "core" if role in boundary.SUBSTANTIVE_ROLES else "held"
    )
    value["verdict"] = "substantive"
    with pytest.raises(analysis.AnalysisContractError):
        boundary.receipt(item, value, TEXT, NOW.isoformat())


@pytest.mark.parametrize("role", sorted(boundary.SUBSTANTIVE_ROLES))
def test_one_specific_insight_is_enough_no_all_criteria_and_gate(source, role):
    item = deepcopy(source.record)
    value = boundary_value(verdict="context")
    value["checks"]["insight"]["role"] = role
    item["editorial_boundary"] = boundary.receipt(item, value, TEXT, NOW.isoformat())
    assert selection.automatic_state(item) == "core"


@pytest.mark.parametrize(
    "version",
    [
        "reading-boundary-v1-source-only",
        "reading-boundary-v2-analysis-object",
        "reading-boundary-v3-explanation-card",
        "reading-boundary-v4-evidence-roles",
    ],
)
def test_previous_receipts_cannot_borrow_new_policy(source, monkeypatch, version):
    item = deepcopy(source.record)
    with monkeypatch.context() as old:
        old.setattr(boundary, "PROMPT_VERSION", version)
        value = boundary_for(item, TEXT, NOW)
    item["editorial_boundary"] = value
    assert boundary.state(item) == "pending"


@pytest.mark.parametrize(
    "proposed",
    [
        {},
        {"insight": [], "method": []},
        {"insight": ["invented"], "method": []},
        {"insight": "not a list", "method": []},
    ],
)
def test_invalid_proposal_stops_before_provider(proposed):
    with pytest.raises(analysis.AnalysisContractError):
        boundary.request_payload(TEXT, "Original", proposed=proposed)


def test_missing_check_or_altered_attached_evidence_is_pending(source):
    item = deepcopy(source.record)
    for change in ("missing", "quote"):
        item["editorial_boundary"] = boundary_for(item, TEXT, NOW)
        decision = item["editorial_boundary"]["decision"]
        if change == "missing":
            decision["checks"]["insight"] = None
        else:
            decision["checks"]["insight"]["evidence_excerpts"] = [
                "Another real sentence cannot repair this quote"
            ]
        item["editorial_boundary"]["decision_digest"] = research_review.digest(decision)
        assert boundary.state(item) == "pending"


def test_absent_method_must_be_null_and_does_not_block_specific_insight(source):
    item = deepcopy(source.record)
    item["editorial_selection"]["decision"]["reading_points"]["method_data"] = None
    item["editorial_selection"]["decision_digest"] = research_review.digest(
        item["editorial_selection"]["decision"]
    )
    value = boundary_value()
    with pytest.raises(analysis.AnalysisContractError, match="absent evidence"):
        boundary.receipt(item, value, TEXT, NOW.isoformat())
    value["checks"]["method"] = None
    item["editorial_boundary"] = boundary.receipt(item, value, TEXT, NOW.isoformat())
    assert selection.automatic_state(item) == "core"


def test_cannot_cite_a_valid_but_unseen_body_passage(source):
    value = boundary_value()
    value["object_evidence_id"] = 1
    assert analysis._source_passages(TEXT)[1]["citable"]
    with pytest.raises(
        analysis.AnalysisContractError, match="analysis-object evidence"
    ):
        boundary.receipt(source.record, value, TEXT, NOW.isoformat())


def test_receipt_records_actual_read_scope_not_whole_source_length(source):
    receipt = boundary_for(source.record, TEXT, NOW)
    assert receipt["source_input_chars"] == len(TEXT)
    assert receipt["analyzed_chars"] == len(analysis._source_passages(TEXT)[0]["text"])
    assert receipt["scope"] == "isolated_proposed_source_passages"
    payload = boundary.request_payload(
        TEXT, source.record["title"], proposed=boundary.evidence_plan(source.record)
    )
    assert receipt["request_input_digest"] == research_review.digest(payload["input"])
