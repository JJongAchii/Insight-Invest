"""Offline presentation and source-bound migration; no semantic API claims."""

from copy import deepcopy

import pytest

from module import research_curation as curation, research_reading as reading
from module import research_review as review, research_selection as selection
from research_review_fixtures import attach_review
from test_research_analysis import NOW, TEXT, brief


@pytest.fixture
def item(monkeypatch):
    monkeypatch.setenv("RADAR_ANALYSIS_ENABLED", "true")
    value = {
        "entry_id": "f" * 64,
        "source_digest": "a" * 64,
        "title": "Original factor article",
        "parser_version": "fixture",
        "analysis_scope": "full_article",
        "editorial_selection_status": "core",
        "analysis": {
            "fingerprint": "b" * 64,
            "source_digest": "a" * 64,
            "analyzed_chars": len(TEXT),
            "brief": brief(),
        },
    }
    attach_review(value, TEXT, NOW)
    return value


def seal(item):
    receipt = item["analysis"]["review"]
    receipt["draft_digest"] = review.digest(item["analysis"]["brief"])
    receipt["fingerprint"] = review.cache_key(item, item["analysis"])
    receipt["verdict"] = review._decision(receipt["checks"], item["analysis"]["brief"])


def test_rejected_point_does_not_hide_other_checked_points_or_rewrite_receipt(item):
    item["analysis"]["review"]["checks"]["question"]["status"] = "unsupported"
    seal(item)
    before = deepcopy(item)
    result = reading.reading_brief(item)
    assert result["status"] == "partial"
    assert result["points"]["question"] is None
    assert result["points"]["method_data"] == item["analysis"]["brief"]["method_data"]
    assert item == before and review.state(item) == "rejected"


def test_regulatory_content_label_does_not_reject_supported_translations(item):
    item["analysis"]["review"]["checks"]["content_kind"]["status"] = "unsupported"
    seal(item)
    result = reading.reading_brief(item)
    assert result["metadata_held"] and result["status"] == "partial"
    assert result["points"]["method_data"]


@pytest.mark.parametrize(
    "field", ["source_digest", "title", "parser_version", "analysis_scope"]
)
def test_changed_source_cannot_borrow_partial_review(item, field):
    item[field] = "changed"
    assert reading.reading_brief(item) is None


def test_no_summary_without_supported_method_or_finding(item):
    item["analysis"]["review"]["checks"]["method_data"]["status"] = "unclear"
    seal(item)
    assert reading.reading_brief(item) is None


def test_source_audit_hold_is_bound_to_exact_draft(item, monkeypatch):
    audit = {
        "draft_digest": review.digest(item["analysis"]["brief"]),
        "field_holds": {"question": "Wrong framing"},
    }
    monkeypatch.setattr(curation, "original_audit", lambda _: audit)
    assert reading.reading_brief(item)["points"]["question"] is None
    item["analysis"]["brief"]["question"] = {
        **item["analysis"]["brief"]["question"],
        "text_ko": "수정된 연구 질문",
    }
    assert reading.reading_brief(item) is None  # needs its OWN review first
    seal(item)
    assert reading.reading_brief(item)["points"]["question"]


@pytest.mark.parametrize(
    "claim,evidence,clean",
    [
        ("1970년 3월부터 2026년 4월까지", "From March 1970 through April 2026.", True),
        ("3월에 3%", "In March.", False),
        ("4월", "In March.", False),
        ("1차 위험", "First-order risks.", True),
        ("1차 위험 1%", "First-order risks.", False),
        ("기후를 고려하는 투자자", "Investors seek value.", False),
        ("기후를 고려하는 투자자", "Climate-aware investors.", True),
        ("연환산 142bp", "Adding 142 bps.", False),
        ("연간 142bp", "Adding 142 bps per year.", True),
        ("중앙값 -0.06", "The median was negative 0.06.", False),
    ],
)
def test_guard_unit_correspondences_do_not_allow_unrelated_numbers(
    claim, evidence, clean
):
    assert (not reading.display_issues(claim, evidence)) is clean


def test_frozen_audit_changes_do_not_apply_to_similar_or_changed_original():
    entry_id, audit = next(iter(curation._audits().items()))
    item = {"entry_id": entry_id, **{name: audit[name] for name in curation.BINDINGS}}
    assert selection.state(item) == audit["lane"]
    for field in (*curation.BINDINGS, "entry_id"):
        changed = {**item, field: "changed"}
        assert curation.original_audit(changed) is None
        assert selection.state(changed) == "pending"


def test_duplicate_requires_both_exact_sources_and_identical_pdf_proof():
    audits = curation._audits()
    alias_id, alias = next(
        (key, value) for key, value in audits.items() if value.get("duplicate_of")
    )
    original_id = alias["duplicate_of"]
    items = [
        {
            **audits[key],
            "entry_id": key,
            "research_lane": "core",
            "notification_eligible": True,
        }
        for key in (original_id, alias_id)
    ]
    curation.mark_duplicates(items)
    assert items[1]["duplicate_of"] == original_id
    assert not items[1]["notification_eligible"]
    assert items[1]["entry_id"] == alias_id
    items[0]["source_digest"] = "changed"
    items[1]["research_lane"] = "core"
    curation.mark_duplicates(items)
    assert "duplicate_of" not in items[1] and items[1]["research_lane"] == "core"
