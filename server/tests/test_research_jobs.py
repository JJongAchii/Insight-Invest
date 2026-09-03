import io
from datetime import UTC, datetime

import pytest

from module import research_jobs


class S3Error(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class MemoryS3:
    def __init__(self):
        self.objects = {}
        self.put_calls = []

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)
        target = (kwargs["Bucket"], kwargs["Key"])
        if kwargs.get("IfNoneMatch") == "*" and target in self.objects:
            raise S3Error("PreconditionFailed")
        self.objects[target] = bytes(kwargs["Body"])
        return {"ETag": '"test"'}

    def get_object(self, **kwargs):
        target = (kwargs["Bucket"], kwargs["Key"])
        if target not in self.objects:
            raise S3Error("NoSuchKey")
        return {"Body": io.BytesIO(self.objects[target])}


def _record(entry_id="a" * 64):
    return {
        "entry_id": entry_id,
        "source_id": "alpha",
        "source_name": "Alpha Research",
        "title": "Causal signal paper",
        "summary": "A reproducible signal",
        "authors": ["Alice Quant"],
        "url": "https://example.test/paper",
        "published_at": "2026-09-03T00:00:00+00:00",
        "discovered_at": "2026-09-03T00:10:00+00:00",
        "research_lane": "core",
        "notification_eligible": True,
    }


def test_disabled_handoff_creates_one_immutable_request_and_replays_it():
    s3 = MemoryS3()
    first = research_jobs.ensure_request(
        _record(),
        s3=s3,
        bucket="bucket",
        now=datetime(2026, 9, 3, 1, 0, tzinfo=UTC),
        enabled=False,
    )
    replay = research_jobs.ensure_request(
        _record(),
        s3=s3,
        bucket="bucket",
        now=datetime(2026, 9, 3, 2, 0, tzinfo=UTC),
        enabled=False,
    )

    assert first["created"] is True
    assert replay["created"] is False
    assert replay["job"] == first["job"]
    assert first["job"]["status"] == "awaiting_activation"
    assert first["job"]["execution_policy"] == {
        "billable_execution_enabled": False,
        "monthly_budget_usd": None,
        "max_concurrency": 1,
        "human_curation_required": True,
        "human_prereg_required": True,
    }
    assert first["key"] == f"research-radar/jobs/{'a' * 64}/request.json"
    assert all(call["IfNoneMatch"] == "*" for call in s3.put_calls)
    assert len(s3.objects) == 1


def test_enabled_request_requires_and_records_an_explicit_budget():
    s3 = MemoryS3()

    with pytest.raises(ValueError, match="requires a monthly budget"):
        research_jobs.ensure_request(
            _record("b" * 64),
            s3=s3,
            bucket="bucket",
            enabled=True,
        )

    result = research_jobs.ensure_request(
        _record("b" * 64),
        s3=s3,
        bucket="bucket",
        now=datetime(2026, 9, 3, 1, 0, tzinfo=UTC),
        enabled=True,
        monthly_budget_usd="25",
    )

    assert result["job"]["status"] == "requested"
    assert result["job"]["execution_policy"]["billable_execution_enabled"] is True
    assert result["job"]["execution_policy"]["monthly_budget_usd"] == "25"

    with pytest.raises(ValueError, match="positive USD amount"):
        research_jobs.ensure_request(
            _record("c" * 64),
            s3=s3,
            bucket="bucket",
            enabled=True,
            monthly_budget_usd="0",
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"research_lane": "discovery", "notification_eligible": False},
        {"research_lane": "context", "notification_eligible": False},
        {"research_lane": "core", "notification_eligible": False},
    ],
)
def test_non_eligible_or_non_core_records_are_rejected(changes):
    record = {**_record(), **changes}

    with pytest.raises(ValueError, match="only notification-eligible core"):
        research_jobs.ensure_request(record, s3=MemoryS3(), bucket="bucket", enabled=False)


def test_automation_flag_defaults_off_and_rejects_ambiguous_values(monkeypatch):
    monkeypatch.delenv("RESEARCH_AUTOMATION_ENABLED", raising=False)
    assert research_jobs.automation_enabled() is False

    with pytest.raises(ValueError, match="must be true or false"):
        research_jobs.automation_enabled("yes")


def test_existing_request_with_different_input_fails_closed():
    s3 = MemoryS3()
    research_jobs.ensure_request(_record(), s3=s3, bucket="bucket", enabled=False)
    changed = {**_record(), "title": "Changed after job creation"}

    with pytest.raises(ValueError, match="different input digest"):
        research_jobs.ensure_request(changed, s3=s3, bucket="bucket", enabled=False)
