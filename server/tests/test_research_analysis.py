"""Offline GPT-5 nano brief/projection contracts; no real API calls."""

import hashlib
import io
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from datastore import research, storage
from module import research_analysis as analysis, research_feed
from qdata.radar_editorial import publication_record

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


def brief(*, relevant=True):
    point = {
        "text_ko": "저자는 팩터 포트폴리오 구성 방법을 살펴봅니다.",
        "evidence": "We examine factor portfolio construction using empirical return data.",
    }
    return {
        "title_ko": "팩터 포트폴리오 연구",
        "question": point,
        "method_data": point,
        "finding": None,
        "why_read": None,
        "limitation": None,
        "reviewer_note": "AI 해석: 원문에서 비용 가정을 확인할 수 있습니다.",
        "quant_relevant": relevant,
        "substantive": relevant,
    }


def wire_brief():
    result = brief()
    for field in analysis.FIELDS:
        if result[field] is not None:
            result[field] = {"text_ko": result[field]["text_ko"], "evidence_id": 0}
    return result


@pytest.fixture
def source(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-never-used-over-network")
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
    return Records(record)


def apply_test_brief(*, now=NOW, relevant=True):
    """Synthetic fixture, not a provider or end-to-end API acceptance claim."""
    feed = research.load_feed()
    for item in feed["items"]:
        item["analysis"] = {
            "model": "offline-test-fixture",
            "analyzed_at": now.isoformat(),
            "source_digest": item["source_digest"],
            "brief": analysis.validate_brief(brief(relevant=relevant), TEXT),
        }
        item["analysis_status"] = "ready"
        research_feed.apply_editorial_analysis(item)
    research.save_feed(feed)


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
    assert item["relevance_reason"] == "grounded_reading_brief"
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


def test_model_request_uses_gpt5_nano_strict_schema_without_storage(monkeypatch):
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
    assert payload["model"] == "gpt-5-nano" and payload["store"] is False
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["strict"] is True
    assert payload["max_output_tokens"] == analysis.MAX_OUTPUT_TOKENS
    assert payload["reasoning"] == {"effort": "minimal"}
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
    assert result["reserved_nanousd"] == 37_000
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
    assert item["analysis_status"] == "held" and not item["notification_eligible"]
    assert result["reserved_nanousd"] == 3 * analysis._request_reservation(
        TEXT, item["title"]
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
    assert not research.load_feed()["items"][0]["notification_eligible"]


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
        ] == analysis._request_reservation(text, title)
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
    assert not research.load_feed()["items"][0]["notification_eligible"]


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
    assert 'RADAR_ANALYSIS_MONTHLY_BUDGET_USD: "1.90"' in poller


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
    bad["method_data"]["evidence_id"] = 999999
    with pytest.raises(analysis.AnalysisContractError, match="unknown source passage"):
        analysis._ground_response(bad, TEXT)


def test_passages_are_bounded_verbatim_even_with_unicode_and_a_short_tail():
    text = ("한국어 원문 근거를 그대로 연결합니다. " * 40) + "끝"
    for passage in analysis._source_passages(text):
        assert 15 <= len(passage["text"]) <= 180
        assert passage["text"] in analysis._normalize(text)
