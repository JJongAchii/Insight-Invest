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


def test_no_summary_without_supported_reading_content(item):
    item["analysis"]["review"]["checks"]["method_data"]["status"] = "unclear"
    item["analysis"]["review"]["checks"]["why_read"]["status"] = "unclear"
    seal(item)
    assert reading.reading_brief(item) is None


def test_one_reviewed_insight_does_not_require_filler_method_or_finding(item):
    item["analysis"]["brief"]["method_data"] = None
    attach_review(item, TEXT, NOW)
    shown = reading.reading_brief(item)
    assert shown["points"]["why_read"]
    assert shown["points"]["method_data"] is None
    assert shown["points"]["finding"] is None
    assert shown["status"] == "ready"


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


@pytest.mark.parametrize(
    "claim,evidence,issue",
    [
        (
            "중간급 딥은 0.38로 감소한다.",
            "Moderate dips shrink to 0.38.",
            "unnamed_numeric_metric",
        ),
        ("샤프비율은 0.38이다.", "The value is 0.38.", "unnamed_numeric_metric"),
        ("상관계수는 0.95이다.", "The correlation is 0.95.", None),
        ("샤프비율은 0.38이다.", "The Sharpe ratio is 0.38.", None),
        ("비용은 1.5%다.", "Costs are 1.5%.", None),
        ("기간은 1.5년이다.", "The horizon is 1.5 years.", None),
        ("p값은 0.05이다.", "The p-value is 0.05.", None),
        (
            "실무에서는 3.2배 차이가 난다.",
            "Simplified example: in this case, 3.2x larger.",
            "numeric_example_scope_missing",
        ),
        (
            "이 예시에서는 3.2배다.",
            "Simplified example: in this case, 3.2x larger.",
            None,
        ),
        ("포지션이 더 커진다.", "In this example, 3.2x larger.", None),
    ],
)
def test_numeric_scope_holds_are_generic_and_preserve_typed_comparisons(
    claim, evidence, issue
):
    assert reading.numeric_scope_issues(claim, evidence) == ([issue] if issue else [])


def test_numeric_scope_hold_preserves_other_points_and_original_model_verdict(item):
    item["analysis"]["brief"]["why_read"] = {
        "text_ko": "중간급 딥은 0.38로 감소한다.",
        "evidence": "Moderate dips shrink to 0.38.",
    }
    seal(item)
    before = deepcopy(item)
    assert review.state(item) == "accepted"
    shown = reading.reading_brief(item)
    assert shown["policy_version"] == "reading-display-v3-standalone-insight"
    assert shown["status"] == "partial" and shown["points"]["why_read"] is None
    assert shown["points"]["method_data"] == before["analysis"]["brief"]["method_data"]
    assert item == before and review.state(item) == "accepted"


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


def test_product_editor_correction_is_not_automatic_classifier_success(monkeypatch):
    entry_id = "4a2f1514e7a59cedd5002866e299eb974a359760ee1ebbf3185e389fa0326026"
    audit = curation._audits()[entry_id]
    item = {"entry_id": entry_id, **{name: audit[name] for name in curation.BINDINGS}}
    before = deepcopy(item)
    # Simulate the separately preserved production mismatch, not an API receipt.
    monkeypatch.setattr(selection, "model_state", lambda _: "core")
    assert selection.model_state(item) == "core"
    assert selection.state(item) == "context"
    assert item == before
    assert curation.original_audit({**item, "source_digest": "changed"}) is None
