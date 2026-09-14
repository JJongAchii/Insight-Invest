"""Producer/consumer span contracts; synthetic fixtures are not semantic acceptance."""

import json

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
