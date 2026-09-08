"""Offline reviewer/budget/publish guards; model accuracy needs real-source review."""

from copy import deepcopy
from datetime import timedelta
import json

import httpx
import pytest

from datastore import research, storage
from module import (
    research_analysis as analysis,
    research_feed,
    research_review as review,
)
from research_review_fixtures import attach_review, checks_for
from test_research_analysis import NOW, TEXT, brief, source as source

USAGE = {"input_tokens": 100, "output_tokens": 80}


def draft(source):
    research_feed.reconcile(s3=source, now=NOW)
    return analysis.enrich(
        now=NOW,
        text_loader=lambda _item: TEXT,
        model_call=lambda *_args: (brief(), USAGE),
    )


def forbidden(*_args):
    pytest.fail("must not regenerate or repeat settled review")


def accepted(_text, _title, value, _key):
    return checks_for(value), USAGE


def test_review_request_is_separate_bounded_untrusted_and_structured(monkeypatch):
    captured = {}

    def post(url, **kwargs):
        captured.update(kwargs["json"])
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "status": "completed",
                "usage": USAGE,
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(checks_for(brief())),
                            }
                        ],
                    }
                ],
            },
        )

    monkeypatch.setattr(analysis.httpx, "post", post)
    checks, usage = review.model_call(TEXT, "Original", brief(), "offline-key")
    assert usage == USAGE and set(checks) == set(review.FIELDS)
    assert captured["model"] == "gpt-5-mini" and captured["store"] is False
    assert captured["instructions"] != analysis.SYSTEM
    assert (
        "UNTRUSTED" in captured["instructions"]
        and "ITS ATTACHED QUOTES" in captured["instructions"]
    )
    assert "previous_response_id" not in captured and "tools" not in captured
    assert captured["text"]["format"]["strict"] is True
    assert json.loads(captured["input"])["draft"] == brief()


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_field",
        "false_null",
        "bool_id",
        "unknown_id",
        "no_evidence",
        "fake_quote",
        "empty_reason",
    ],
)
def test_review_contract_rejects_incomplete_or_unbound_checks(mutation):
    checks = checks_for(brief())
    check = checks["method_data"]
    if mutation == "missing_field":
        del checks["title_ko"]
    elif mutation == "false_null":
        check["status"] = "not_applicable"
    elif mutation == "bool_id":
        check["evidence_ids"] = [True]
    elif mutation == "unknown_id":
        check["evidence_ids"] = [999]
    elif mutation == "no_evidence":
        check["evidence_ids"] = []
    elif mutation == "fake_quote":
        check["evidence"] = "fabricated"
    else:
        check["reason_ko"] = ""
    with pytest.raises(analysis.AnalysisContractError):
        review.validate_checks(checks, TEXT, brief())


def test_semantic_rejection_keeps_original_and_library_without_automatic_retry(
    source, tmp_path
):
    draft(source)
    item = research.load_feed()["items"][0]
    assert (
        item["analysis_status"] == "review_pending"
        and item["research_lane"] == "discovery"
    )
    research.set_read(item["entry_id"], read=True)
    research.set_saved(item["entry_id"], saved=True)
    research.save_seen_through(NOW)
    before = {
        name: (tmp_path / name).read_bytes()
        for name in (research.READ_STATE_FILE, research.SEEN_STATE_FILE)
    }

    def reject(_text, _title, value, _key):
        checks = checks_for(value)
        checks["method_data"].update(
            status="unsupported", reason_ko="오프라인 부정 대조: 개념을 바꾼 요약"
        )
        return checks, USAGE

    result = analysis.enrich(
        now=NOW,
        text_loader=lambda _item: TEXT,
        model_call=forbidden,
        review_call=reject,
    )
    held = research.load_feed()["items"][0]
    assert result["reviewed"] == result["rejected"] == 1 and result["failed"] == 0
    assert (
        held["analysis_status"] == "review_rejected"
        and review.state(held) == "rejected"
    )
    assert held["research_lane"] == "discovery" and not held["notification_eligible"]
    assert held["summary"] == item["summary"] and held["url"] == item["url"]
    assert (
        held["analysis"]["brief"] == item["analysis"]["brief"]
    )  # Never rewrite to get a pass.
    result = analysis.enrich(
        now=NOW + timedelta(hours=1),
        text_loader=forbidden,
        model_call=forbidden,
        review_call=forbidden,
    )
    assert result["completed"] == result["failed"] == 0
    assert before == {name: (tmp_path / name).read_bytes() for name in before}


@pytest.mark.parametrize(
    "change", ["source", "title", "draft", "review_version", "decision"]
)
def test_passing_receipt_cannot_be_reused_after_changes(source, monkeypatch, change):
    draft(source)
    item = research.load_feed()["items"][0]
    attach_review(item, TEXT, NOW)
    item["analysis_status"] = "ready"
    assert review.state(item) == "accepted"
    if change == "source":
        item["source_digest"] = "b" * 64
    elif change == "title":
        item["title"] += " Revised"
    elif change == "draft":
        item["analysis"]["brief"]["method_data"]["text_ko"] = "근거 없는 다른 개념"
    elif change == "review_version":
        monkeypatch.setattr(review, "PROMPT_VERSION", "changed-review")
    else:
        item["analysis"]["review"]["checks"]["method_data"]["status"] = "unsupported"
    assert review.state(item) == "pending"
    research_feed.apply_editorial_analysis(item)
    assert item["research_lane"] == "discovery" and not item["notification_eligible"]


def test_new_budget_preserves_old_reservations_and_resumes_cached_draft(
    source, monkeypatch
):
    draft(source)
    path = "research_analysis/budget-2026-09.json"
    storage.write_json({"reserved_nanousd": 82_040_450}, path)
    monkeypatch.setenv("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "0.08205")
    result = analysis.enrich(
        now=NOW,
        text_loader=lambda _item: TEXT,
        model_call=forbidden,
        review_call=forbidden,
    )
    assert result["reason"] == "monthly_budget_reached"
    assert result["reserved_nanousd"] == 82_040_450
    monkeypatch.setenv("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "0.50")

    def reserved_call(*args):
        assert storage.read_json(path)["reserved_nanousd"] > 82_040_450
        return accepted(*args)

    result = analysis.enrich(
        now=NOW + timedelta(minutes=10),
        text_loader=lambda _item: TEXT,
        model_call=forbidden,
        review_call=reserved_call,
    )
    assert (
        result["reserved_nanousd"] == 82_225_450
        and result["limit_nanousd"] == 500_000_000
    )
    item = research.load_feed()["items"][0]
    assert item["analysis_status"] == "ready" and item["notification_eligible"]
    assert item["available_at"] == (NOW + timedelta(minutes=10)).isoformat()


def test_review_cache_recovers_lost_projection_without_api_or_source_fetch(source):
    draft(source)
    before = deepcopy(research.load_feed())
    result = analysis.enrich(
        now=NOW,
        text_loader=lambda _item: TEXT,
        model_call=forbidden,
        review_call=accepted,
    )
    research.save_feed(before)
    recovered = analysis.enrich(
        now=NOW, text_loader=forbidden, model_call=forbidden, review_call=forbidden
    )
    assert (
        recovered["completed"] == 1
        and recovered["reserved_nanousd"] == result["reserved_nanousd"]
    )
    assert research.load_feed()["items"][0]["notification_eligible"]


def test_review_transport_failure_keeps_reservation_and_draft_then_retries_only_review(
    source,
):
    draft(source)
    prior = deepcopy(research.load_feed()["items"][0]["analysis"])

    def fail(*_args):
        raise analysis.AnalysisContractError("review output unusable")

    result = analysis.enrich(
        now=NOW, text_loader=lambda _item: TEXT, model_call=forbidden, review_call=fail
    )
    item = research.load_feed()["items"][0]
    assert result["failed"] == 1 and result["reserved_nanousd"] > 185_000
    assert item["analysis"] == prior and item["analysis_retry"]["stage"] == "review"
    assert not item["notification_eligible"]
    analysis.enrich(
        now=NOW + timedelta(hours=1),
        text_loader=lambda _item: TEXT,
        model_call=forbidden,
        review_call=accepted,
    )
    assert research.load_feed()["items"][0]["analysis"]["brief"] == prior["brief"]


def test_unchanged_etag_migration_demotes_unreviewed_ready_without_key(
    source, monkeypatch
):
    draft(source)
    feed = research.load_feed()
    feed["items"][0].update(
        analysis_status="ready", research_lane="core", notification_eligible=True
    )
    research.save_feed(feed)
    monkeypatch.delenv("OPENAI_API_KEY")
    research_feed.reconcile(s3=source, now=NOW)
    item = research.load_feed()["items"][0]
    assert item["research_lane"] == "discovery" and not item["notification_eligible"]
    assert item["analysis"]["brief"] == feed["items"][0]["analysis"]["brief"]
