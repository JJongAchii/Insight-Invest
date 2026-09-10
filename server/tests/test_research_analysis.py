"""Offline GPT-5 mini brief/projection contracts; no real API calls."""

import hashlib
import io
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from datastore import research, storage
from module import research_analysis as analysis, research_feed, research_selection
from qdata.radar_editorial import publication_record
from qdata.radar_notifications import origin
from research_review_fixtures import attach_review, checks_for, selection_for

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)
TEXT = (
    "We examine factor portfolio construction using empirical return data. "
    "We estimate transaction costs and compare portfolio diversification. "
) * 15


class Records:
    def __init__(self, record):
        self.key = f"research-radar/public/records/{record['entry_id_sha256']}.json"
        self.record = record

    def list_objects_v2(self, **_kwargs):
        return {
            "Contents": [
                {
                    "Key": self.key,
                    "ETag": hashlib.sha256(
                        json.dumps(self.record, sort_keys=True).encode()
                    ).hexdigest(),
                }
            ]
        }

    def get_object(self, **_kwargs):
        return {"Body": io.BytesIO(json.dumps(self.record).encode())}


def brief(*, relevant=True, kind="research"):
    point = {
        "text_ko": "저자는 팩터 포트폴리오 구성 방법을 살펴봅니다.",
        "evidence": "We examine factor portfolio construction using empirical return data.",
    }
    return {
        "title_ko": "팩터 포트폴리오 연구",
        "content_kind": kind,
        "question": point,
        "method_data": point,
        "finding": None,
        "why_read": point,
        "limitation": None,
        "reviewer_note": "AI 해석: 원문에서 비용 가정을 확인할 수 있습니다.",
        "quant_relevant": relevant,
        "substantive": relevant,
    }


def wire_brief():
    result = brief()
    for field in analysis.FIELDS:
        if result[field] is not None:
            result[field] = {"text_ko": result[field]["text_ko"], "evidence_ids": [0]}
    return result


@pytest.fixture
def source(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-never-used-over-network")
    monkeypatch.setenv("RADAR_ANALYSIS_ENABLED", "true")
    monkeypatch.setenv("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "2")
    record = publication_record(
        {
            "title": "Factor portfolio research",
            "url": "https://www.robeco.com/en-int/insights/2026/09/factor-research",
            "pdf_url": "",
            "authors": ["Alice"],
            "published_at": NOW.isoformat(),
            "date_precision": "day",
            "text": TEXT,
            "analysis_scope": "full_article",
            "access_status": "open_full",
            "doi": "",
        },
        source_id="robeco-quant-insights",
        now=NOW,
    )
    record["notification_origin"] = origin(
        record, baseline=NOW - timedelta(days=1), now=NOW
    )
    storage.write_json(
        selection_for(record, TEXT, NOW),
        f"research_analysis/selections/{research_selection.cache_key(record)}.json",
    )
    return Records(record)


def apply_test_brief(*, now=NOW, relevant=True):
    """Synthetic fixture, not a provider or end-to-end API acceptance claim."""
    feed = research.load_feed()
    for item in feed["items"]:
        item["editorial_selection"] = selection_for(item, TEXT, now, relevant=relevant)
        item["analysis"] = {
            "model": "offline-test-fixture",
            "analyzed_at": now.isoformat(),
            "source_digest": item["source_digest"],
            "brief": analysis.validate_brief(brief(relevant=relevant), TEXT),
        }
        item["analysis_status"] = "ready"
        attach_review(item, TEXT, now)
        research_feed.apply_editorial_analysis(item)
    research.save_feed(feed)


def test_default_off_does_not_read_storage_or_call_provider(monkeypatch):
    monkeypatch.delenv("RADAR_ANALYSIS_ENABLED", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "configured-but-not-release-approval")

    def forbidden(*args, **kwargs):
        raise AssertionError("release hold must stop before any I/O")

    monkeypatch.setattr(storage, "exists", forbidden)
    monkeypatch.setattr(research, "load_feed", forbidden)
    assert analysis.enrich(
        now=NOW, text_loader=forbidden, model_call=forbidden, review_call=forbidden
    ) == {"enabled": False, "reason": "editorial_release_pending", "completed": 0}


def test_release_hold_hides_cached_brief_without_mutating_library(
    source, tmp_path, monkeypatch
):
    from app.routers import research as api

    research_feed.reconcile(s3=source, now=NOW)
    apply_test_brief()
    entry_id = source.record["entry_id_sha256"]
    research.set_read(entry_id, read=True)
    research.set_saved(entry_id, saved=True)
    before = {path: path.read_bytes() for path in tmp_path.iterdir() if path.is_file()}
    monkeypatch.delenv("RADAR_ANALYSIS_ENABLED", raising=False)
    response = api.get_research_feed(
        source_id=None,
        unread_only=False,
        view="all",
        lane="all",
        q=None,
        entry_id=None,
        offset=0,
        limit=100,
    )
    item = response["items"][0]
    assert item["entry_id"] == entry_id and item["is_read"] and item["is_saved"]
    assert item["research_lane"] == "core"
    assert item["editorial_candidate_lane"] == "core"
    assert item["editorial_review_status"] == "pending"
    assert item["relevance_reason"] == "source_selected_original"
    assert item["notification_eligible"]
    assert api.get_research_status()["unseen"] == 0
    assert item["analysis"] == research.load_feed()["items"][0]["analysis"]
    assert before == {path: path.read_bytes() for path in before}


def test_grounding_rejects_fabricated_quotes_and_wrong_types():
    assert analysis.validate_brief(brief(), TEXT)["quant_relevant"]
    value = brief()
    value["finding"] = {
        "text_ko": "검증 완료",
        "evidence": "Invented independently verified performance.",
    }
    with pytest.raises(ValueError, match="not in the analyzed source"):
        analysis.validate_brief(value, TEXT)
    value = brief()
    value["substantive"] = "true"
    with pytest.raises(ValueError, match="invalid brief"):
        analysis.validate_brief(value, TEXT)
    value = brief()
    value["question"] = {"text_ko": "원문 분석", "evidence": " " * 15}
    with pytest.raises(ValueError, match="invalid excerpt"):
        analysis.validate_brief(value, TEXT)


def test_projection_waits_for_a_brief_and_retains_it_on_unchanged_source(source):
    research_feed.reconcile(s3=source, now=NOW)
    item = research.load_feed()["items"][0]
    assert item["research_lane"] == "discovery" and not item["notification_eligible"]
    apply_test_brief()
    item = research.load_feed()["items"][0]
    assert item["research_lane"] == "core" and item["notification_eligible"]
    assert item["available_at"] == NOW.isoformat()
    assert item["relevance_reason"] == "source_selected_original"
    research_feed.reconcile(s3=source, now=NOW + timedelta(hours=1))
    assert research.load_feed()["items"][0]["analysis"] == item["analysis"]


def test_body_revision_preserves_user_library_and_first_core_availability(
    source, tmp_path
):
    research_feed.reconcile(s3=source, now=NOW)
    apply_test_brief()
    entry_id = source.record["entry_id_sha256"]
    research.set_read(entry_id, read=True)
    research.set_saved(entry_id, saved=True)
    research.save_seen_through(NOW + timedelta(minutes=5))
    state_before = {
        name: (tmp_path / name).read_bytes()
        for name in (research.READ_STATE_FILE, research.SEEN_STATE_FILE)
    }
    source.record["source_digest"] = "a" * 64
    source.record["summary"] = "The source corrected its text."
    result = research_feed.reconcile(s3=source, now=NOW + timedelta(hours=1))
    assert result["revised"] == 1 and result["records"] == 1
    assert research.load_feed()["items"][0]["analysis_status"] == "pending"
    apply_test_brief(now=NOW + timedelta(hours=1))
    item = research.load_feed()["items"][0]
    assert item["available_at"] == NOW.isoformat()
    assert research.unseen_entry_count([item], research.load_seen_through()) == 0
    assert research.entry_states()[entry_id] == {"is_read": True, "is_saved": True}
    assert state_before == {
        name: (tmp_path / name).read_bytes() for name in state_before
    }


@pytest.mark.parametrize(
    "bootstrap,relevant,expected_lane",
    [
        (True, True, "core"),
        (False, False, "context"),
    ],
)
def test_backfill_and_topic_mismatch_never_notify(
    source, bootstrap, relevant, expected_lane
):
    if bootstrap:
        source.record["notification_eligible"] = False
    research_feed.reconcile(s3=source, now=NOW)
    apply_test_brief(relevant=relevant)
    item = research.load_feed()["items"][0]
    assert item["research_lane"] == expected_lane
    assert not item["notification_eligible"]


def test_model_request_uses_gpt5_mini_strict_schema_without_storage(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": json.dumps(wire_brief())}
                        ],
                    }
                ],
                "usage": {"input_tokens": 100, "output_tokens": 80},
            }

    def post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Response()

    monkeypatch.setattr(analysis.httpx, "post", post)
    result, usage = analysis._model_call(TEXT, "Test", "test-key")
    payload = captured["json"]
    assert result["quant_relevant"] and usage == {
        "input_tokens": 100,
        "output_tokens": 80,
    }
    assert payload["model"] == "gpt-5-mini" and payload["store"] is False
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["strict"] is True
    assert payload["max_output_tokens"] == analysis.MAX_OUTPUT_TOKENS
    assert payload["reasoning"] == {"effort": "medium"}
    source = json.loads(payload["input"])
    assert source["source_passages"][0]["text"] in TEXT
    assert "source_text" not in source
    assert "tools" not in payload
    assert captured["headers"]["Authorization"] == "Bearer test-key"


def test_budget_is_reserved_before_call_and_cache_avoids_second_call(source):
    research_feed.reconcile(s3=source, now=NOW)
    calls = []

    def model(*_args):
        budget = storage.read_json("research_analysis/budget-2026-09.json")
        assert budget["reserved_nanousd"] > 44_000
        calls.append(True)
        return brief(), {"input_tokens": 100, "output_tokens": 80}

    result = analysis.enrich(now=NOW, text_loader=lambda _item: TEXT, model_call=model)
    assert result["completed"] == 1
    assert result["reserved_nanousd"] == 185_000
    assert research.load_feed()["items"][0]["research_lane"] == "core"
    reviewed = analysis.enrich(
        now=NOW,
        text_loader=lambda _item: TEXT,
        review_call=lambda _text, _title, value, _key: (
            checks_for(value),
            {"input_tokens": 100, "output_tokens": 80},
        ),
    )
    assert reviewed["reviewed"] == 1 and reviewed["reserved_nanousd"] == 370_000
    assert research.load_feed()["items"][0]["research_lane"] == "core"
    assert (
        analysis.enrich(now=NOW, text_loader=lambda _item: TEXT, model_call=model)[
            "completed"
        ]
        == 0
    )
    assert len(calls) == 1


def test_monthly_cap_stops_before_network(source, monkeypatch):
    research_feed.reconcile(s3=source, now=NOW)
    monkeypatch.setenv("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "0.00001")

    def forbidden(*_args):
        pytest.fail("model must not be called above the monthly request cap")

    result = analysis.enrich(
        now=NOW, text_loader=lambda _item: TEXT, model_call=forbidden
    )
    assert result["reason"] == "monthly_budget_reached"
    assert not research.load_feed()["items"][0]["notification_eligible"]


def test_missing_openai_key_leaves_original_readable(source, monkeypatch):
    research_feed.reconcile(s3=source, now=NOW)
    monkeypatch.delenv("OPENAI_API_KEY")
    before = research.load_feed()

    def forbidden(*_args, **_kwargs):
        pytest.fail("missing key must return before any storage or network I/O")

    with monkeypatch.context() as guard:
        guard.setattr(analysis.httpx, "post", forbidden)
        guard.setattr(storage, "exists", forbidden)
        guard.setattr(storage, "read_json", forbidden)
        guard.setattr(storage, "write_json", forbidden)
        assert analysis.enrich() == {
            "enabled": False,
            "reason": "missing_api_key",
            "completed": 0,
        }
    assert research.load_feed() == before and before["items"][0]["summary"]


@pytest.mark.parametrize(
    "case", ["incomplete", "refusal", "missing_usage", "negative_usage"]
)
def test_invalid_api_responses_are_not_published(monkeypatch, case):
    payload = {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": json.dumps(brief())}],
            }
        ],
        "usage": {"input_tokens": 100, "output_tokens": 80},
    }
    if case == "incomplete":
        payload["status"] = "incomplete"
    elif case == "refusal":
        payload["output"][0]["content"] = [{"type": "refusal", "refusal": "Declined"}]
    elif case == "missing_usage":
        payload.pop("usage")
    else:
        payload["usage"]["input_tokens"] = -100
    monkeypatch.setattr(
        analysis.httpx,
        "post",
        lambda *_args, **_kwargs: httpx.Response(
            200,
            json=payload,
            request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
        ),
    )
    with pytest.raises(ValueError):
        analysis._model_call(TEXT, "Test", "test-key")


def test_failed_requests_keep_reservation_and_stop_after_three_attempts(source):
    research_feed.reconcile(s3=source, now=NOW)
    calls = []

    def failed(*_args):
        calls.append(True)
        raise ValueError("unusable model output")

    for hours in (0, 1, 2, 3, 4):
        result = analysis.enrich(
            now=NOW + timedelta(hours=hours),
            text_loader=lambda _item: TEXT,
            model_call=failed,
        )
    assert len(calls) == 3
    item = research.load_feed()["items"][0]
    assert item["analysis_status"] == "held" and item["notification_eligible"]
    assert result["reserved_nanousd"] == 3 * analysis._request_reservation(
        TEXT,
        item["title"],
        evidence_plan=item["editorial_selection"]["decision"]["reading_points"],
    )


def test_provider_auth_error_pauses_requests_without_fallback(source):
    research_feed.reconcile(s3=source, now=NOW)
    calls = []

    def failed(*_args):
        calls.append(True)
        httpx.Response(
            401, request=httpx.Request("POST", "https://api.openai.com/v1/responses")
        ).raise_for_status()

    for minutes in (0, 10, 30):
        result = analysis.enrich(
            now=NOW + timedelta(minutes=minutes),
            text_loader=lambda _item: TEXT,
            model_call=failed,
        )
        assert result["reason"] == "provider_paused"
    assert len(calls) == 1
    assert research.load_feed()["items"][0]["notification_eligible"]


def test_persisted_cache_recovers_projection_without_another_request(source):
    research_feed.reconcile(s3=source, now=NOW)
    before = research.load_feed()
    result = analysis.enrich(
        now=NOW,
        text_loader=lambda _item: TEXT,
        model_call=lambda *_args: (brief(), {"input_tokens": 100, "output_tokens": 80}),
    )
    research.save_feed(
        before
    )  # Simulate a lost projection write after the cache write.

    def forbidden(*_args):
        pytest.fail("persisted analysis must not be billed twice")

    recovered = analysis.enrich(now=NOW, text_loader=forbidden, model_call=forbidden)
    assert recovered["completed"] == 1
    assert recovered["reserved_nanousd"] == result["reserved_nanousd"]
    assert research.load_feed()["items"][0]["research_lane"] == "core"


def test_source_input_is_bounded_before_reserving_and_sending(source):
    research_feed.reconcile(s3=source, now=NOW)
    long_text = TEXT * 100

    def model(text, title, _key):
        assert text == long_text[: analysis.MAX_INPUT_CHARS]
        assert storage.read_json("research_analysis/budget-2026-09.json")[
            "reserved_nanousd"
        ] == analysis._request_reservation(
            text,
            title,
            evidence_plan=selection_for(source.record, TEXT, NOW)["decision"][
                "reading_points"
            ],
        )
        return brief(), {"input_tokens": 100, "output_tokens": 80}

    assert (
        analysis.enrich(now=NOW, text_loader=lambda _item: long_text, model_call=model)[
            "completed"
        ]
        == 1
    )


def test_budget_write_failure_prevents_model_request(source, monkeypatch):
    research_feed.reconcile(s3=source, now=NOW)
    write_json = storage.write_json

    def fail_budget_write(value, path):
        if path.startswith("research_analysis/budget-"):
            raise OSError("budget storage unavailable")
        return write_json(value, path)

    def forbidden(*_args):
        pytest.fail("no paid request without a durable reservation")

    monkeypatch.setattr(storage, "write_json", fail_budget_write)
    result = analysis.enrich(
        now=NOW, text_loader=lambda _item: TEXT, model_call=forbidden
    )
    assert result["failed"] == 1
    assert research.load_feed()["items"][0]["notification_eligible"]


def test_research_deployment_uses_separate_openai_key_not_news_key():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    template = (root / "infra/template.yaml").read_text()
    poller = template.split("  ResearchPollerFunction:", 1)[1].split(
        "  ResearchPollerSchedule:", 1
    )[0]
    assert "ANTHROPIC_API_KEY" not in poller
    assert "AnthropicApiKey" not in poller
    assert "OPENAI_API_KEY: !Ref OpenAIApiKey" in poller
    assert 'RADAR_ANALYSIS_MONTHLY_BUDGET_USD: "1.50"' in poller


def test_contract_failure_records_only_a_safe_diagnosis(source):
    research_feed.reconcile(s3=source, now=NOW)

    def failed(*_args):
        raise analysis.AnalysisContractError(
            "analysis response was incomplete: max_output_tokens"
        )

    analysis.enrich(now=NOW, text_loader=lambda _item: TEXT, model_call=failed)
    retry = research.load_feed()["items"][0]["analysis_retry"]
    assert (
        retry["error_reason"] == "analysis response was incomplete: max_output_tokens"
    )
    assert "api_key" not in retry and "response" not in retry


def test_request_limits_are_part_of_the_cache_identity(source, monkeypatch):
    research_feed.reconcile(s3=source, now=NOW)
    item = research.load_feed()["items"][0]
    before = analysis.cache_key(item)
    monkeypatch.setattr(analysis, "MAX_OUTPUT_TOKENS", 3600)
    assert analysis.cache_key(item) != before


def test_practitioner_article_needs_substance_not_a_formal_research_question():
    value = brief()
    value["question"] = None
    assert analysis.validate_brief(value, TEXT)["substantive"]
    value["method_data"] = None
    with pytest.raises(
        analysis.AnalysisContractError, match="lacks grounded method/finding"
    ):
        analysis.validate_brief(value, TEXT)


def test_quotes_are_attached_by_code_not_rewritten_by_the_model():
    value = analysis._ground_response(wire_brief(), TEXT)
    assert (
        value["method_data"]["evidence"] == analysis._source_passages(TEXT)[0]["text"]
    )
    assert value["method_data"]["evidence"] in TEXT
    bad = wire_brief()
    bad["method_data"]["evidence_ids"] = [999999]
    with pytest.raises(analysis.AnalysisContractError, match="unknown source passage"):
        analysis._ground_response(bad, TEXT)


def test_passages_are_bounded_verbatim_even_with_unicode_and_a_short_tail():
    text = ("한국어 원문 근거를 그대로 연결합니다. " * 40) + "끝"
    passages = analysis._source_passages(text)
    for passage in passages:
        assert passage["text"] in analysis._normalize(text)
        if passage["citable"]:
            assert 15 <= len(passage["text"]) <= analysis.MAX_EVIDENCE_CHARS
            assert passage["text"].endswith(".")
    assert passages[-1] == {"id": 40, "text": "끝", "citable": False}


def test_evidence_keeps_complete_sentences_across_a_method_explanation():
    sentences = [
        "The ranking engine orders issuers using valuation and momentum signals.",
        "The construction engine then builds a portfolio subject to liquidity and risk constraints.",
        "Analysts review exceptional events that the quantitative model may miss.",
    ]
    text = " ".join(sentences)
    passages = analysis._source_passages(text)
    assert [p["text"] for p in passages] == sentences
    value = wire_brief()
    value["method_data"]["evidence_ids"] = [0, 1]
    grounded = analysis._ground_response(value, text)
    assert grounded["method_data"]["evidence"] == " ".join(sentences[:2])


@pytest.mark.parametrize("ids", [[], [True], [-1], [999999], [0, 1, 2, 3, 4]])
def test_invalid_evidence_selection_cannot_publish(ids):
    value = wire_brief()
    value["method_data"]["evidence_ids"] = ids
    with pytest.raises(analysis.AnalysisContractError):
        analysis._ground_response(value, TEXT)


def test_nonadjacent_evidence_stays_separate_verbatim_with_explicit_gaps():
    sentences = [
        "The method ranks bonds using a systematic model.",
        "An unrelated discussion appears between the two source statements.",
        "Analysts review events that the model does not capture.",
    ]
    text = " ".join(sentences)
    value = wire_brief()
    value["method_data"]["evidence_ids"] = [2, 0, 2]
    result = analysis._ground_response(value, text)
    grounded = result["method_data"]
    assert grounded["evidence_excerpts"] == [sentences[0], sentences[2]]
    assert grounded["evidence"] == sentences[0] + " […] " + sentences[2]
    assert sentences[1] not in grounded["evidence"]
    assert analysis.validate_brief(result, text)
    grounded["evidence_excerpts"][1] = (
        "Invented implementation assumption absent from the source."
    )
    with pytest.raises(
        analysis.AnalysisContractError, match="not in the analyzed source"
    ):
        analysis.validate_brief(result, text)


def test_sentence_boundaries_preserve_decimals_abbreviations_and_numbered_lists():
    sentences = [
        "Dr. Lee evaluates U.S. bonds with a 2.5 percent yield, e.g. liquid credit.",
        "Three effects are considered: 1. portfolio weights and valuation.",
        "2. Company emissions enter a separate component.4",
        "3. Interaction terms are reported separately.",
        "The sample finishes in 2026.",
        "The adjusted score is 2.5.",
    ]
    assert [
        p["text"] for p in analysis._source_passages(" ".join(sentences))
    ] == sentences


@pytest.mark.parametrize(
    "tail", ["The unfinished claim continues", "Long clause " * 110 + "."]
)
def test_incomplete_or_oversized_passages_are_context_only(tail):
    text = "A complete sentence explains the investment method. " + tail
    value = wire_brief()
    value["method_data"]["evidence_ids"] = [1]
    assert not analysis._source_passages(text)[1]["citable"]
    with pytest.raises(analysis.AnalysisContractError, match="context only"):
        analysis._ground_response(value, text)


def test_combined_evidence_cannot_exceed_the_excerpt_limit():
    text = ("A long sentence " + "with bounded words " * 35 + ". ") * 2
    value = wire_brief()
    value["method_data"]["evidence_ids"] = [0, 1]
    with pytest.raises(analysis.AnalysisContractError, match="invalid excerpt length"):
        analysis._ground_response(value, text)


def test_unusable_sentence_extraction_stops_before_reservation_or_request(source):
    research_feed.reconcile(s3=source, now=NOW)

    def forbidden(*_args):
        pytest.fail("unusable evidence must not incur an API request")

    result = analysis.enrich(
        now=NOW,
        text_loader=lambda _item: "An unfinished source fragment",
        model_call=forbidden,
    )
    assert result["failed"] == 1 and result["reserved_nanousd"] == 0
    assert not storage.exists("research_analysis/budget-2026-09.json")


@pytest.mark.parametrize(
    "kind,expected_lane,notifiable",
    [
        ("research", "core", True),
        ("practitioner", "core", True),
        ("market_commentary", "context", False),
        ("other", "context", False),
        (None, "discovery", False),
    ],
)
def test_document_kind_controls_core_without_deleting_or_rewriting_library(
    source, tmp_path, kind, expected_lane, notifiable
):
    research_feed.reconcile(s3=source, now=NOW)
    entry_id = source.record["entry_id_sha256"]
    research.set_read(entry_id, read=True)
    research.set_saved(entry_id, saved=True)
    research.save_seen_through(NOW)
    before = {
        name: (tmp_path / name).read_bytes()
        for name in (research.READ_STATE_FILE, research.SEEN_STATE_FILE)
    }
    feed = research.load_feed()
    value = brief(kind=kind)
    if kind is None:
        del value["content_kind"]  # A v4 cache must remain readable, not count as v5.
    feed["items"][0].update(
        analysis_status="ready",
        analysis={
            "brief": value,
            "source_digest": feed["items"][0]["source_digest"],
            "analyzed_at": NOW.isoformat(),
        },
    )
    if kind is not None:
        feed["items"][0]["editorial_selection"] = selection_for(
            feed["items"][0], TEXT, NOW, kind=kind
        )
        attach_review(feed["items"][0], TEXT, NOW)
    research_feed.apply_editorial_analysis(feed["items"][0])
    research.save_feed(feed)
    item = research.load_feed()["items"][0]
    assert item["entry_id"] == entry_id
    assert item["analysis"]["brief"] == value
    assert item["research_lane"] == expected_lane
    assert item["notification_eligible"] is notifiable
    assert len(research.load_feed()["items"]) == 1
    assert before == {name: (tmp_path / name).read_bytes() for name in before}


def test_unknown_or_missing_content_kind_is_not_a_new_valid_brief():
    for kind in (None, "research_paper", ["research"]):
        with pytest.raises(analysis.AnalysisContractError, match="content_kind"):
            analysis.validate_brief(brief(kind=kind), TEXT)
    old = brief()
    del old["content_kind"]
    with pytest.raises(analysis.AnalysisContractError, match="fields differ"):
        analysis.validate_brief(old, TEXT)


def test_prompt_requires_finance_terms_attribution_and_conditions():
    # Real linguistic/semantic quality is checked separately against real sources.
    assert "금융배출량" in analysis.SYSTEM
    assert "매출 for revenue" in analysis.SYSTEM
    assert "independently reproduced" in analysis.SYSTEM
    assert "Do not reconstruct broken PDF numbers" in analysis.SYSTEM
    assert "current outlook/sector preference/positioning" in analysis.SYSTEM
    assert list(analysis.POINT_SCHEMA["anyOf"][1]["properties"]) == [
        "evidence_ids",
        "text_ko",
    ]


def test_accepted_topic_without_concrete_reading_value_stays_in_discovery(source):
    research_feed.reconcile(s3=source, now=NOW)
    item = research.load_feed()["items"][0]
    value = brief()
    value["why_read"] = None
    item.update(
        analysis_status="ready",
        analysis={"source_digest": item["source_digest"], "brief": value},
    )
    attach_review(item, TEXT, NOW)
    research_feed.apply_editorial_analysis(item)
    assert item["research_lane"] == "discovery"
    assert item["relevance_reason"] == "original_selection_pending"
    assert not item["notification_eligible"]


def test_accepted_historical_brief_can_be_read_in_core_but_never_badged(source):
    research_feed.reconcile(s3=source, now=NOW)
    apply_test_brief()
    item = research.load_feed()["items"][0]
    item.pop("notification_origin")
    research_feed.apply_editorial_analysis(item)
    assert item["research_lane"] == "core"
    assert not item["notification_eligible"]


def test_reasoning_change_does_not_reuse_old_analysis_cache(monkeypatch):
    item = {"source_digest": "a" * 64, "title": "Same source"}
    original = analysis.cache_key(item)
    monkeypatch.setattr(analysis, "REASONING_EFFORT", "minimal")
    assert analysis.cache_key(item) != original
