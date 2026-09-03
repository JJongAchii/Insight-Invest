import io
import json
from datetime import UTC, datetime

import pytest

from datastore import research as research_store
from module import research_feed


class FakeS3:
    def __init__(self, objects=None):
        self.objects = objects or {}
        self.reads = []
        self.deleted = []

    def list_objects_v2(self, *, Bucket, Prefix, ContinuationToken=None):  # noqa: N803, ARG002
        return {
            "Contents": [{"Key": key} for key in sorted(self.objects) if key.startswith(Prefix)],
            "IsTruncated": False,
        }

    def get_object(self, *, Bucket, Key):  # noqa: N803, ARG002
        self.reads.append(Key)
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, *, Bucket, Key):  # noqa: N803, ARG002
        self.deleted.append(Key)
        self.objects.pop(Key, None)


def _record(entry_id, *, source_id="source-a", discovered_at="2026-09-01T00:00:00+00:00"):
    return {
        "schema_version": 2,
        "source": "public_watchlist",
        "source_id": source_id,
        "source_name": source_id.title(),
        "entry_id_sha256": entry_id,
        "discovered_at": discovered_at,
        "published_at": discovered_at,
        "title": f"Paper {entry_id[0]}",
        "summary": "Public abstract",
        "authors": ["A. Author"],
        "url": f"https://example.test/{entry_id}",
        "quality_profile": "quant-research",
        "research_lane": "core",
        "relevance_reason": "keyword_match",
        "relevance_terms": ["portfolio"],
        "notification_eligible": True,
    }


def _object(entry_id, **kwargs):
    key = f"research-radar/public/records/{entry_id}.json"
    return key, json.dumps(_record(entry_id, **kwargs)).encode()


def test_reconcile_fetches_only_membership_diff(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    first_id = "1" * 64
    second_id = "2" * 64
    third_id = "3" * 64
    first_key, first = _object(first_id, discovered_at="2026-09-01T00:00:00+00:00")
    second_key, second = _object(second_id, discovered_at="2026-09-02T00:00:00+00:00")
    s3 = FakeS3({first_key: first, second_key: second})

    initial = research_feed.reconcile(
        s3=s3,
        bucket="bucket",
        now=datetime(2026, 9, 2, 1, tzinfo=UTC),
    )
    feed = research_store.load_feed()

    assert initial == {"records": 2, "added": 2, "removed": 0, "updated": True}
    assert [item["entry_id"] for item in feed["items"]] == [second_id, first_id]
    assert all(item["research_lane"] == "core" for item in feed["items"])
    assert all(item["notification_eligible"] is True for item in feed["items"])
    initial_generated_at = feed["generated_at"]

    s3.reads.clear()
    unchanged = research_feed.reconcile(
        s3=s3,
        bucket="bucket",
        now=datetime(2026, 9, 2, 2, tzinfo=UTC),
    )
    assert unchanged == {"records": 2, "added": 0, "removed": 0, "updated": False}
    assert s3.reads == []
    assert research_store.load_feed()["generated_at"] == initial_generated_at

    del s3.objects[first_key]
    third_key, third = _object(third_id, discovered_at="2026-09-03T00:00:00+00:00")
    s3.objects[third_key] = third
    s3.reads.clear()
    changed = research_feed.reconcile(s3=s3, bucket="bucket")

    assert changed == {"records": 2, "added": 1, "removed": 1, "updated": True}
    assert s3.reads == [third_key]
    assert [item["entry_id"] for item in research_store.load_feed()["items"]] == [
        third_id,
        second_id,
    ]


def test_reconcile_rejects_record_whose_digest_does_not_match_key(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    entry_id = "a" * 64
    key, body = _object(entry_id)
    payload = json.loads(body)
    payload["entry_id_sha256"] = "b" * 64

    try:
        research_feed.reconcile(s3=FakeS3({key: json.dumps(payload).encode()}), bucket="bucket")
    except ValueError as exc:
        assert "digest" in str(exc)
    else:
        raise AssertionError("digest mismatch must fail closed")


def test_reconcile_maps_legacy_record_to_context_without_deleting_it(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    entry_id = "c" * 64
    key, body = _object(entry_id)
    payload = json.loads(body)
    payload["schema_version"] = 1
    for field in (
        "quality_profile",
        "research_lane",
        "relevance_reason",
        "relevance_terms",
        "notification_eligible",
    ):
        payload.pop(field)

    research_feed.reconcile(
        s3=FakeS3({key: json.dumps(payload).encode()}),
        bucket="bucket",
    )
    item = research_store.load_feed()["items"][0]

    assert item["research_lane"] == "context"
    assert item["relevance_reason"] == "legacy_record"
    assert item["notification_eligible"] is False


def test_reconcile_rejects_notifiable_non_core_record(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    entry_id = "d" * 64
    key, body = _object(entry_id)
    payload = json.loads(body)
    payload["research_lane"] = "discovery"

    with pytest.raises(ValueError, match="core"):
        research_feed.reconcile(
            s3=FakeS3({key: json.dumps(payload).encode()}),
            bucket="bucket",
        )


@pytest.mark.parametrize("schema_version", [0, 3])
def test_reconcile_rejects_unsupported_record_schema(monkeypatch, tmp_path, schema_version):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    entry_id = "e" * 64
    key, body = _object(entry_id)
    payload = json.loads(body)
    payload["schema_version"] = schema_version

    with pytest.raises(ValueError, match="schema_version"):
        research_feed.reconcile(
            s3=FakeS3({key: json.dumps(payload).encode()}),
            bucket="bucket",
        )


def test_pending_records_are_newest_first():
    older_id = "a" * 64
    newer_id = "b" * 64
    _, older = _object(older_id, discovered_at="2026-09-01T00:00:00+00:00")
    _, newer = _object(newer_id, discovered_at="2026-09-02T00:00:00+00:00")
    prefix = "research-radar/realtime/pending"
    s3 = FakeS3(
        {
            f"{prefix}/{older_id}.json": older,
            f"{prefix}/{newer_id}.json": newer,
        }
    )

    pending = research_feed.pending_records(s3=s3, bucket="bucket")

    assert [record["entry_id"] for _, record in pending] == [newer_id, older_id]
