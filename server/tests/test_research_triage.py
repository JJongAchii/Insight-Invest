import hashlib
import io
import json
from datetime import UTC, datetime

import pytest

from module import research_jobs, research_triage


class S3Error(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class MemoryS3:
    def __init__(self):
        self.objects = {}
        self.etags = {}
        self.put_calls = []

    def put_object(self, **kwargs):
        target = (kwargs["Bucket"], kwargs["Key"])
        if kwargs.get("IfNoneMatch") == "*" and target in self.objects:
            raise S3Error("PreconditionFailed")
        if "IfMatch" in kwargs and kwargs["IfMatch"] != self.etags.get(target):
            raise S3Error("PreconditionFailed")
        body = bytes(kwargs["Body"])
        self.objects[target] = body
        self.etags[target] = '"' + hashlib.sha256(body).hexdigest() + '"'
        self.put_calls.append(kwargs)
        return {"ETag": self.etags[target]}

    def get_object(self, **kwargs):
        target = (kwargs["Bucket"], kwargs["Key"])
        if target not in self.objects:
            raise S3Error("NoSuchKey")
        return {"Body": io.BytesIO(self.objects[target]), "ETag": self.etags[target]}


class FakeBatchAPI:
    def __init__(self):
        self.calls = []

    def upload_batch_file(self, content):
        self.calls.append(("upload", content))
        return "file_test"

    def create_batch(self, file_id, *, batch_id):
        self.calls.append(("create", file_id, batch_id))
        return {"id": "batch_test", "status": "validating"}


class FakeHTTPResponse:
    def __init__(self, payload, *, content=b""):
        self.payload = payload
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeHTTP:
    def __init__(self):
        self.calls = []

    def post(self, path, **kwargs):
        self.calls.append((path, kwargs))
        if path == "/files":
            return FakeHTTPResponse({"id": "file_http"})
        return FakeHTTPResponse({"id": "batch_http", "status": "validating"})

    def get(self, path, **kwargs):
        self.calls.append((path, kwargs))
        if path == "/batches/batch_http":
            return FakeHTTPResponse(
                {"id": "batch_http", "status": "completed", "output_file_id": "file_output"}
            )
        return FakeHTTPResponse({}, content=b'{"custom_id":"test"}\n')


def _request(
    entry_id,
    *,
    url=None,
    title=None,
    enabled=True,
    budget="75",
):
    record = {
        "entry_id": entry_id,
        "source_id": "alpha",
        "source_name": "Alpha Research",
        "title": title or f"Research {entry_id[:4]}",
        "summary": "A reproducible cross-sectional signal with transaction costs.",
        "authors": ["Alice Quant"],
        "url": url or f"https://example.test/papers/{entry_id[:8]}",
        "published_at": "2026-09-03T00:00:00+00:00",
        "discovered_at": "2026-09-03T00:10:00+00:00",
        "research_lane": "core",
        "notification_eligible": True,
    }
    return research_jobs._request_payload(
        record,
        now=datetime(2026, 9, 3, 1, 0, tzinfo=UTC),
        enabled=enabled,
        monthly_budget_usd=budget if enabled else None,
    )


def _classification(*, relevant=True, family="cross_sectional_momentum", asset="equities"):
    return {
        "relevant_to_quant_research": relevant,
        "primary_family": family,
        "asset_classes": [asset],
        "evidence_type": "working_paper_empirical",
        "implementation_complexity": "medium",
        "data_requirements": ["daily returns"],
        "mechanism_terms": ["underreaction"],
        "summary_ko": "비용을 반영한 횡단면 신호를 다룬다.",
        "relevance_reason_ko": "재현 가능한 전략 가설이 명시되어 있다.",
        "risk_flags": ["unclear_data_availability"],
    }


def _output_line(custom_id, classification, *, input_tokens=500, output_tokens=120):
    return {
        "custom_id": custom_id,
        "response": {
            "status_code": 200,
            "body": {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(classification, ensure_ascii=False),
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
            },
        },
        "error": None,
    }


def test_packet_is_deterministic_and_deduplicates_arxiv_versions():
    first = _request("a" * 64, url="https://arxiv.org/abs/2601.01234v1?utm_source=x")
    duplicate = _request("b" * 64, url="https://arxiv.org/pdf/2601.01234v2.pdf")
    distinct = _request("c" * 64)

    packet = research_triage.build_triage_packet([distinct, duplicate, first])
    replay = research_triage.build_triage_packet([first, distinct, duplicate])

    assert packet == replay
    assert packet["manifest"]["request_count"] == 2
    assert packet["manifest"]["source_job_ids"] == ["a" * 64, "c" * 64]
    assert packet["manifest"]["skipped_duplicates"] == [
        {"job_id": "b" * 64, "kept_job_id": "a" * 64, "reason": "canonical_url"}
    ]
    assert packet["manifest"]["submission_eligible"] is True
    lines = [json.loads(line) for line in packet["input_jsonl"].splitlines()]
    assert all(line["url"] == "/v1/responses" for line in lines)
    assert all(line["body"]["model"] == "gpt-5.6-luna" for line in lines)
    assert all(line["body"]["reasoning"] == {"effort": "none"} for line in lines)
    assert all(line["body"]["store"] is False for line in lines)
    assert all(line["body"]["text"]["format"]["strict"] is True for line in lines)


def test_disabled_requests_can_be_planned_but_not_submitted_without_api_calls():
    packet = research_triage.build_triage_packet([_request("a" * 64, enabled=False)])
    s3 = MemoryS3()
    api = FakeBatchAPI()

    assert packet["manifest"]["submission_eligible"] is False
    assert packet["manifest"]["submission_blockers"] == ["request_not_activated"]
    with pytest.raises(PermissionError, match="not activated"):
        research_triage.submit_packet(
            packet,
            s3=s3,
            bucket="bucket",
            enabled=True,
            monthly_budget_usd="75",
            api_key="test-key",
            api=api,
        )

    assert api.calls == []
    assert s3.objects == {}


def test_one_thousand_metadata_rows_have_a_bounded_batch_cost():
    requests = [_request(hashlib.sha256(str(index).encode()).hexdigest()) for index in range(1_000)]

    packet = research_triage.build_triage_packet(requests)

    assert packet["manifest"]["request_count"] == 1_000
    assert packet["manifest"]["input_token_ceiling"] == 32_000_000
    assert packet["manifest"]["output_token_ceiling"] == 700_000
    assert packet["manifest"]["estimated_max_cost_usd"] == "3.620000"
    assert len(packet["input_jsonl"]) < research_triage.MAX_BATCH_FILE_BYTES


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"enabled": False, "monthly_budget_usd": "75", "api_key": "key"}, "disabled"),
        ({"enabled": True, "monthly_budget_usd": "75", "api_key": ""}, "OPENAI_API_KEY"),
        ({"enabled": True, "monthly_budget_usd": None, "api_key": "key"}, "MONTHLY_BUDGET"),
        ({"enabled": True, "monthly_budget_usd": "25", "api_key": "key"}, "does not match"),
    ],
)
def test_submission_requires_every_explicit_runtime_control(monkeypatch, kwargs, message):
    monkeypatch.delenv("RESEARCH_MONTHLY_BUDGET_USD", raising=False)
    packet = research_triage.build_triage_packet([_request("a" * 64)])

    with pytest.raises(PermissionError, match=message):
        research_triage.authorize_submission(packet, **kwargs)


def test_submit_reserves_budget_writes_receipt_and_replays_without_second_charge():
    packet = research_triage.build_triage_packet([_request("a" * 64)])
    s3 = MemoryS3()
    api = FakeBatchAPI()
    now = datetime(2026, 9, 3, 2, 0, tzinfo=UTC)

    created = research_triage.submit_packet(
        packet,
        s3=s3,
        bucket="bucket",
        enabled=True,
        monthly_budget_usd="75",
        api_key="test-key",
        api=api,
        now=now,
    )
    replay = research_triage.submit_packet(
        packet,
        s3=s3,
        bucket="bucket",
        enabled=True,
        monthly_budget_usd="75",
        api_key="test-key",
        api=api,
        now=now,
    )

    assert created["created"] is True
    assert created["receipt"]["openai_batch_id"] == "batch_test"
    assert replay == {**created, "created": False}
    assert [call[0] for call in api.calls] == ["upload", "create"]
    budget_key = ("bucket", "research-radar/triage/budgets/2026-09/state.json")
    budget = json.loads(s3.objects[budget_key])
    assert budget["reservations"] == {
        packet["manifest"]["batch_id"]: packet["manifest"]["estimated_max_cost_usd"]
    }


def test_monthly_budget_ledger_blocks_before_api_call():
    packet = research_triage.build_triage_packet([_request("a" * 64)])
    s3 = MemoryS3()
    api = FakeBatchAPI()
    ledger = {
        "schema_version": 1,
        "period_utc": "2026-09",
        "monthly_budget_usd": "75.000000",
        "reservations": {"older": "75.000000"},
    }
    s3.put_object(
        Bucket="bucket",
        Key="research-radar/triage/budgets/2026-09/state.json",
        Body=json.dumps(ledger).encode(),
    )

    with pytest.raises(PermissionError, match="would be exceeded"):
        research_triage.submit_packet(
            packet,
            s3=s3,
            bucket="bucket",
            enabled=True,
            monthly_budget_usd="75",
            api_key="test-key",
            api=api,
            now=datetime(2026, 9, 3, tzinfo=UTC),
        )

    assert api.calls == []


def test_http_adapter_uses_batch_file_and_responses_endpoint_contract():
    http = FakeHTTP()
    api = research_triage.OpenAIBatchAPI("secret-not-logged", http_client=http)

    file_id = api.upload_batch_file(b'{"test":true}\n')
    batch = api.create_batch(file_id, batch_id="packet")
    completed = api.retrieve_batch(batch["id"])
    output = api.download_file(completed["output_file_id"])

    assert file_id == "file_http"
    assert batch["id"] == "batch_http"
    assert output == b'{"custom_id":"test"}\n'
    assert [call[0] for call in http.calls] == [
        "/files",
        "/batches",
        "/batches/batch_http",
        "/files/file_output/content",
    ]
    assert http.calls[0][1]["data"] == {"purpose": "batch"}
    assert http.calls[1][1]["json"] == {
        "input_file_id": "file_http",
        "endpoint": "/v1/responses",
        "completion_window": "24h",
        "metadata": {"kind": "research_radar_triage", "packet_sha256": "packet"},
    }
    assert all("secret-not-logged" in call[1]["headers"]["Authorization"] for call in http.calls)


def test_completed_output_is_validated_costed_and_clustered_deterministically():
    packet = research_triage.build_triage_packet(
        [_request("a" * 64), _request("b" * 64), _request("c" * 64)]
    )
    lines = [
        _output_line("c" * 64, _classification(relevant=False, family="other")),
        _output_line("a" * 64, _classification()),
        _output_line("b" * 64, _classification()),
    ]
    output = "\n".join(json.dumps(line, ensure_ascii=False) for line in lines)

    result = research_triage.parse_batch_output(packet, output)
    replay = research_triage.parse_batch_output(packet, "\n".join(reversed(output.splitlines())))

    assert result == replay
    assert result["usage"] == {
        "input_tokens": 1500,
        "output_tokens": 360,
        "estimated_actual_cost_usd": "0.000366",
    }
    assert [cluster["count"] for cluster in result["clusters"]] == [2, 1]
    assert result["human_curation_required"] is True
    assert result["adoption_decision"] is None

    s3 = MemoryS3()
    stored = research_triage.persist_result_projection(result, s3=s3, bucket="bucket")
    replayed = research_triage.persist_result_projection(replay, s3=s3, bucket="bucket")
    assert stored["created"] is True
    assert replayed == {**stored, "created": False}
    assert stored["key"].endswith(f"/{packet['manifest']['batch_id']}/projection.json")


def test_output_rejects_missing_or_duplicate_custom_ids():
    packet = research_triage.build_triage_packet([_request("a" * 64), _request("b" * 64)])
    first = json.dumps(_output_line("a" * 64, _classification()))

    with pytest.raises(ValueError, match="missing 1"):
        research_triage.parse_batch_output(packet, first)
    with pytest.raises(ValueError, match="duplicate custom_id"):
        research_triage.parse_batch_output(packet, first + "\n" + first)
