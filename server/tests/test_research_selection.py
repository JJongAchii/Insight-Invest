"""Synthetic state/budget tests. Real classification is separately qualified."""

from copy import deepcopy

import pytest

from datastore import research, storage
from module import (
    research_analysis as analysis,
    research_feed,
    research_selection as selection,
)
from module.research_review import literal_issues
from research_review_fixtures import selection_for
from test_research_analysis import NOW, TEXT, source as source


def forbidden(*_args):
    pytest.fail("must not call another paid stage")


def remove_selection_cache(source, tmp_path):
    (
        tmp_path
        / f"research_analysis/selections/{selection.cache_key(source.record)}.json"
    ).unlink()
    research_feed.reconcile(s3=source, now=NOW)


@pytest.mark.parametrize(
    "kind,insight,expected",
    [
        ("research", True, "core"),
        ("practitioner", True, "core"),
        ("market_commentary", True, "context"),
        ("other", True, "context"),
        ("research", False, "context"),
    ],
)
def test_source_only_selection_is_first_budgeted_stage(
    source, tmp_path, kind, insight, expected
):
    remove_selection_cache(source, tmp_path)

    def choose(text, title, key):
        assert (
            storage.read_json("research_analysis/budget-2026-09.json")[
                "reserved_nanousd"
            ]
            > 0
        )
        assert text == TEXT
        return {
            "content_kind": kind,
            "investment_focus": True,
            "transferable_insight": {"evidence_ids": [0]} if insight else None,
            "reason": "Offline purpose fixture.",
            "reading_points": {
                name: {"evidence_ids": [0]} if insight else None
                for name in selection.POINT_NAMES
            },
        }, {"input_tokens": 100, "output_tokens": 80}

    result = analysis.enrich(
        now=NOW,
        text_loader=lambda _: TEXT,
        selection_call=choose,
        model_call=forbidden,
        review_call=forbidden,
    )
    item = research.load_feed()["items"][0]
    assert result["selected"] == 1 and result["drafted"] == result["reviewed"] == 0
    assert result["reserved_nanousd"] == 185_000
    assert item["research_lane"] == expected and "analysis" not in item
    if expected == "context":
        assert (
            analysis.enrich(
                now=NOW,
                text_loader=forbidden,
                selection_call=forbidden,
                model_call=forbidden,
                review_call=forbidden,
            )["completed"]
            == 0
        )


def test_selected_original_survives_summary_off_budget_and_bad_draft(
    source, monkeypatch
):
    research_feed.reconcile(s3=source, now=NOW)
    item = research.load_feed()["items"][0]
    item["editorial_selection"] = selection_for(item, TEXT, NOW)
    item["analysis_status"] = "review_rejected"
    monkeypatch.setenv("RADAR_ANALYSIS_ENABLED", "false")
    research_feed.apply_editorial_analysis(item)
    assert item["research_lane"] == "core" and item["notification_eligible"]
    assert item["editorial_review_status"] == "pending"
    item.pop("notification_origin")
    research_feed.apply_editorial_analysis(item)
    assert item["research_lane"] == "core" and not item["notification_eligible"]


@pytest.mark.parametrize(
    "change", ["source_digest", "title", "parser_version", "analysis_scope", "decision"]
)
def test_selection_is_bound_to_exact_original(source, change):
    item = deepcopy(source.record)
    item["editorial_selection"] = selection_for(item, TEXT, NOW)
    assert selection.state(item) == "core"
    if change == "decision":
        item["editorial_selection"]["decision"]["reason"] = "Changed decision"
    else:
        item[change] = "changed"
    assert selection.state(item) == "pending"


def test_selection_never_sees_draft_or_provider_key():
    payload = selection.request_payload(TEXT, "Original")
    assert "draft" not in selection.json.loads(payload["input"])
    assert payload["store"] is False and "tools" not in payload
    assert payload["text"]["format"]["strict"] is True
    assert "PRIMARY PURPOSE" in payload["instructions"]


def test_broken_pdf_numbers_are_context_only_not_reconstructed():
    text = "The measured alpha was +1 .76% in the study. Another alpha was 1. 49%. A normal number is 1.76%."
    passages = analysis._source_passages(text)
    assert len(passages) == 3
    assert [p["citable"] for p in passages] == [False, False, True]
    assert passages[0]["text"].startswith("The measured alpha was +1 .76%")


@pytest.mark.parametrize(
    "claim,evidence,issue",
    [
        ("연 1.76%", "The alpha was 1.7%.", "numbers_absent"),
        ("리스(リース)", "The lease.", "unexpected_japanese"),
        ("재무화된 배출", "Financed emissions.", "unqualified_financial"),
        ("지수 확장", "An equity extension portfolio.", "equity_extension"),
    ],
)
def test_literal_guard_preserves_known_bad_output_as_held(claim, evidence, issue):
    assert any(value.startswith(issue) for value in literal_issues(claim, evidence))


def test_literal_guard_allows_same_decimal_and_grouped_number():
    assert literal_issues("1,000개와 1.76%", "1000 stocks and 1.76%.") == []
    assert (
        literal_issues("2025년, 3개, 1년", "Until 2025. Three buckets and a year.")
        == []
    )


def test_writer_sees_only_preselected_field_evidence():
    assert literal_issues("2/3", "around two -thirds") == []
    text = "We define a transparent portfolio weighting rule. Unselected outlook predicts a market crash."
    first = analysis._source_passages(text)[0]["text"]
    plan = {
        name: [first] if name == "method_data" else None
        for name in selection.POINT_NAMES
    }
    payload = analysis._request_payload(text, "Original", evidence_plan=plan)
    sent = selection.json.loads(payload["input"])
    assert "market crash" not in payload["input"]
    assert sent["reading_points"]["method_data"] == [0]
    assert payload["text"]["format"]["schema"]["properties"]["finding"] == {
        "type": "null"
    }
    assert payload["text"]["format"]["schema"]["properties"]["method_data"]["anyOf"][1][
        "properties"
    ]["evidence_ids"]["items"]["enum"] == [0]


def test_generation_cannot_add_an_unquoted_editorial_note():
    from module import research_review as review
    from research_review_fixtures import checks_for
    from test_research_analysis import brief

    assert analysis.BRIEF_SCHEMA["properties"]["reviewer_note"] == {
        "type": "string",
        "enum": [""],
    }
    value = brief()
    value["reviewer_note"] = ""
    analysis.validate_brief(value, TEXT)
    checks = checks_for(value)
    checks["reviewer_note"] = {
        "status": "not_applicable",
        "reason_ko": "",
        "evidence_ids": [],
    }
    assert review._decision(checks, value) == "accepted"
    assert literal_issues("활성 탄소 노출", "active carbon exposure") == [
        "active_exposure_is_not_activation"
    ]
