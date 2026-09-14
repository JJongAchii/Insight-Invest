"""Producer/consumer span contracts; synthetic fixtures are not semantic acceptance."""

import json
import re
from copy import deepcopy

import pytest

from module import (
    research_analysis as analysis,
    research_boundary as boundary,
    research_selection as selection,
)
from research_review_fixtures import boundary_value, selection_for
from test_research_analysis import NOW, TEXT, source as source


def test_contiguous_span_survives_selection_reviewer_writer_and_cache_seed(source):
    from test_research_publication import publisher, report_for

    report = report_for(source.record)
    item = report["items"][0]
    selected = item["editorial_selection"]
    passages = analysis._source_passages(TEXT)
    quotes = selection._evidence_span({"evidence_ids": [0, 1]}, passages)
    selected["decision"]["evidence_excerpts"] = quotes
    selected["decision"]["reading_points"]["method_data"] = quotes
    from module.research_review import digest

    selected["decision_digest"] = digest(selected["decision"])
    item["editorial_boundary"] = boundary.receipt(
        item, boundary_value(), TEXT, NOW.isoformat()
    )
    payload = boundary.request_payload(
        TEXT, "Not sent", proposed=boundary.evidence_plan(item)
    )
    assert json.loads(payload["input"])["proposed_evidence_ids"]["method"] == [0, 1]
    draft = analysis._request_payload(
        TEXT, "Source", evidence_plan=selected["decision"]["reading_points"]
    )
    assert json.loads(draft["input"])["reading_points"]["method_data"] == [0, 1]
    # Gate-only publication tests source receipts, not the old fixture brief.
    report.update(gate_only=True, sample="reading-gate-subject-positive-v1")
    # The mock fixture's hash is not a real frozen source, so inspect before that
    # final expected-original check; all quote reconstruction must succeed first.
    with pytest.raises(ValueError, match="frozen expectations"):
        publisher.plan(report, text_loader=lambda _: TEXT)


@pytest.mark.parametrize(
    "ids", [[0, 2], [1, 0], [0, 0], [0, 1, 2, 3, 4], [True], [-1], []]
)
def test_rejects_gap_reverse_duplicate_oversize_and_invalid_ids(ids):
    with pytest.raises(analysis.AnalysisContractError):
        selection._evidence_span({"evidence_ids": ids}, analysis._source_passages(TEXT))


def test_context_only_or_oversize_span_is_not_citable():
    with pytest.raises(analysis.AnalysisContractError):
        selection._evidence_span(
            {"evidence_ids": [0]}, [{"text": "unfinished", "citable": False}]
        )
    with pytest.raises(analysis.AnalysisContractError, match="too long"):
        selection._evidence_span(
            {"evidence_ids": [0, 1]}, [{"text": "x" * 700, "citable": True}] * 2
        )


def test_repeated_sentence_resolves_the_exact_adjacent_context():
    text = "Repeated source sentence. First distinct explanation. Repeated source sentence. Second distinct explanation."
    quotes = ["Repeated source sentence.", "Second distinct explanation."]
    assert analysis._source_span_ids(text, quotes) == [2, 3]
    with pytest.raises(analysis.AnalysisContractError):
        analysis._source_span_ids(
            text, ["First distinct explanation.", "Second distinct explanation."]
        )


def test_source_sentence_version_cannot_be_reused_as_context_span_selection(
    source, monkeypatch
):
    item = dict(source.record)
    with monkeypatch.context() as prior:
        prior.setattr(
            selection, "PROMPT_VERSION", "reading-selection-v8-disclosed-evidence"
        )
        item["editorial_selection"] = selection_for(item, TEXT, NOW)
    assert selection.model_state(item) == "pending"


def test_provider_can_only_select_prevalidated_bounded_spans():
    # Two individually citable sentences must not form an oversized proposal.
    text = ("A" * 698 + ". ") * 2 + "A short final source explanation."
    payload = selection.request_payload(text, "Fixture")
    schema = payload["text"]["format"]["schema"]
    pattern = schema["$defs"]["source_span"]["properties"]["span_id"]["pattern"]
    choices = selection._span_choices(analysis._source_passages(text))
    assert "0:0" in choices and "1:2" in choices and "0:1" not in choices
    assert not re.fullmatch(pattern, "0:1") and not re.fullmatch(pattern, "0:999")
    passages = analysis._source_passages(text)
    for choice in choices:
        assert re.fullmatch(pattern, choice)
        start, end = map(int, choice.split(":"))
        quotes = selection._evidence_span(
            {"evidence_ids": list(range(start, end + 1))}, passages
        )
        assert quotes and sum(map(len, quotes)) <= analysis.MAX_EVIDENCE_CHARS
    assert json.loads(payload["input"])["source_passages"][0]["span_ends"] == [0]
    assert schema["properties"]["transferable_insight"]["anyOf"][1] == {
        "$ref": "#/$defs/source_span"
    }


def test_real_provider_adapter_resolves_spans_before_receipt(source, monkeypatch):
    value = {
        "main_purpose": {
            "category": "investment_analysis",
            "evidence": {"span_id": "0:1"},
        },
        "primary_subject": "investment_methodology",
        "content_kind": "research",
        "contribution_type": "rule_or_measurement",
        "investment_focus": True,
        "reason": "Synthetic transport fixture, not semantic acceptance.",
        "transferable_insight": {"span_id": "0:1"},
        "reading_points": {name: {"span_id": "0:1"} for name in selection.POINT_NAMES},
    }
    usage = {"input_tokens": 10, "output_tokens": 10}
    monkeypatch.setattr(analysis, "_response_call", lambda *a, **k: (value, usage))
    resolved, measured = selection.model_call(TEXT, "Fixture", "unused")
    assert measured == usage
    checked = selection.receipt(source.record, resolved, TEXT, NOW.isoformat())
    assert len(checked["decision"]["evidence_excerpts"]) == 2
    # An out-of-contract response is not clipped, repaired or silently accepted.
    value["transferable_insight"] = {"span_id": "0:999"}
    with pytest.raises(analysis.AnalysisContractError) as error:
        selection.model_call(TEXT, "Fixture", "unused")
    assert error.value.usage == usage


def test_many_choices_preserve_complete_source_coverage_without_enum_limit():
    payload = selection.request_payload(
        "One sufficiently long source sentence. " * 300, ""
    )
    schema = payload["text"]["format"]["schema"]
    pattern = schema["$defs"]["source_span"]["properties"]["span_id"]["pattern"]
    assert re.fullmatch(pattern, "0:3")
    assert re.fullmatch(pattern, "296:299")
    assert re.fullmatch(pattern, "299:299")
    assert not re.fullmatch(pattern, "299:300")


def test_publication_reconstructs_object_citation_from_visible_duplicate(source):
    from test_research_publication import publisher, report_for
    from module.research_review import digest

    text = (
        "Repeated investment statement. First separate explanation. "
        "Repeated investment statement. Second contextual explanation."
    )
    passages = analysis._source_passages(text)
    report = report_for(source.record)
    item = report["items"][0]
    selected = item["editorial_selection"]
    decision = selected["decision"]
    decision["evidence_excerpts"] = [p["text"] for p in passages[2:4]]
    decision["main_purpose"]["evidence_excerpts"] = [passages[3]["text"]]
    decision["reading_points"] = {
        name: decision["evidence_excerpts"] for name in selection.POINT_NAMES
    }
    selected["input_digest"] = digest(text)
    selected["decision_digest"] = digest(decision)
    value = boundary_value()
    value["object_evidence_id"] = 2
    item["editorial_boundary"] = boundary.receipt(item, value, text, NOW.isoformat())
    report.update(gate_only=True, sample="reading-gate-subject-positive-v1")
    with pytest.raises(ValueError, match="frozen expectations"):
        publisher.plan(report, text_loader=lambda _: text)


def test_brief_uses_accepted_insight_and_not_rejected_method(source):
    from module.research_review import digest

    item = dict(source.record)
    item["editorial_selection"] = selection_for(item, TEXT, NOW)
    decision = item["editorial_selection"]["decision"]
    passages = analysis._source_passages(TEXT)
    # The old plan would lose the admitted contribution in a different why-read.
    decision["reading_points"]["why_read"] = [passages[1]["text"]]
    item["editorial_selection"]["decision_digest"] = digest(decision)
    original = deepcopy(item["editorial_selection"])
    previous_key = analysis.cache_key(item)
    value = boundary_value()
    value["checks"]["method"]["role"] = "objective_or_profile"
    item["editorial_boundary"] = boundary.receipt(item, value, TEXT, NOW.isoformat())
    plan = analysis.reading_evidence_plan(item)
    assert plan["method_data"] is None
    assert plan["why_read"] == decision["evidence_excerpts"]
    assert analysis.cache_key(item) != previous_key
    assert item["editorial_selection"] == original
    request = analysis._request_payload(TEXT, "Fixture", evidence_plan=plan)
    assert request["text"]["format"]["schema"]["properties"]["method_data"] == {
        "type": "null"
    }
