import io
import json
from datetime import UTC, datetime

import pytest
from datastore import research as research_store
from module import research_feed

from qdata.radar_public import discover_source, load_watchlist_payload


class FakeS3:
    def __init__(self, objects=None):
        self.objects = objects or {}
        self.reads = []
        self.deleted = []

    def list_objects_v2(self, *, Bucket, Prefix, ContinuationToken=None):  # noqa: N803, ARG002
        return {
            "Contents": [
                {"Key": key} for key in sorted(self.objects) if key.startswith(Prefix)
            ],
            "IsTruncated": False,
        }

    def get_object(self, *, Bucket, Key):  # noqa: N803, ARG002
        self.reads.append(Key)
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, *, Bucket, Key):  # noqa: N803, ARG002
        self.deleted.append(Key)
        self.objects.pop(Key, None)


def _record(
    entry_id, *, source_id="source-a", discovered_at="2026-09-01T00:00:00+00:00"
):
    return {
        "schema_version": 3,
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
        "quality_profile": "strict-evidence-update",
        "research_lane": "core",
        "relevance_reason": "strict_quality_pass",
        "relevance_terms": ["factor", "portfolio"],
        "notification_eligible": True,
        "item_type": "evidence_update",
        "content_provenance": "full_body",
        "evidence_dimensions": ["method", "data", "validation", "result"],
        "evidence_excerpts": {
            "method": ["The method constructs a factor portfolio."],
            "data": ["The data contains CRSP observations."],
            "validation": ["The validation compares both implementations."],
            "result": ["The result confirms the correction."],
        },
        "source_digest": "f" * 64,
        "resolution_status": "maintainer_confirmed",
        "quality_gates": {
            "transport": True,
            "content": True,
            "topic": True,
            "evidence": True,
            "notification": True,
        },
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
    assert all(item["record_schema_version"] == 3 for item in feed["items"])
    assert all(item["evidence_dimensions"][0] == "method" for item in feed["items"])
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


def test_reconcile_rejects_record_whose_digest_does_not_match_key(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    entry_id = "a" * 64
    key, body = _object(entry_id)
    payload = json.loads(body)
    payload["entry_id_sha256"] = "b" * 64

    try:
        research_feed.reconcile(
            s3=FakeS3({key: json.dumps(payload).encode()}), bucket="bucket"
        )
    except ValueError as exc:
        assert "digest" in str(exc)
    else:
        raise AssertionError("digest mismatch must fail closed")


def test_reconcile_maps_legacy_record_to_context_without_deleting_it(
    monkeypatch, tmp_path
):
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
    assert item["record_schema_version"] == 1


def test_reconcile_maps_schema_two_core_fields_to_context(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    entry_id = "f" * 64
    key, body = _object(entry_id)
    payload = json.loads(body)
    payload["schema_version"] = 2
    for field in (
        "item_type",
        "content_provenance",
        "evidence_dimensions",
        "evidence_excerpts",
        "source_digest",
        "resolution_status",
        "quality_gates",
    ):
        payload.pop(field)

    research_feed.reconcile(
        s3=FakeS3({key: json.dumps(payload).encode()}),
        bucket="bucket",
    )
    item = research_store.load_feed()["items"][0]

    assert item["record_schema_version"] == 2
    assert item["research_lane"] == "context"
    assert item["notification_eligible"] is False


def test_projection_migration_does_not_rewrite_read_saved_or_seen_state(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    entry_id = "7" * 64
    key, body = _object(entry_id)
    payload = json.loads(body)
    payload["schema_version"] = 1
    for field in (
        "quality_profile",
        "research_lane",
        "relevance_reason",
        "relevance_terms",
        "notification_eligible",
        "item_type",
        "content_provenance",
        "evidence_dimensions",
        "evidence_excerpts",
        "source_digest",
        "resolution_status",
        "quality_gates",
    ):
        payload.pop(field)
    s3 = FakeS3({key: json.dumps(payload).encode()})
    research_feed.reconcile(s3=s3, bucket="bucket")
    research_store.set_read(entry_id, read=True)
    research_store.set_saved(entry_id, saved=True)
    research_store.save_seen_through(datetime(2026, 9, 1, tzinfo=UTC))
    read_state = (tmp_path / research_store.READ_STATE_FILE).read_bytes()
    seen_state = (tmp_path / research_store.SEEN_STATE_FILE).read_bytes()

    feed = research_store.load_feed()
    feed["items"][0].pop("record_schema_version")
    feed["items"][0]["research_lane"] = "core"
    feed["items"][0]["notification_eligible"] = True
    research_store.save_feed(feed)
    research_feed.reconcile(s3=s3, bucket="bucket")

    assert (tmp_path / research_store.READ_STATE_FILE).read_bytes() == read_state
    assert (tmp_path / research_store.SEEN_STATE_FILE).read_bytes() == seen_state
    assert research_store.entry_states()[entry_id] == {
        "is_read": True,
        "is_saved": True,
    }
    assert research_store.load_feed()["items"][0]["research_lane"] == "context"


def test_reconcile_rejects_notifiable_non_core_record(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    entry_id = "d" * 64
    key, body = _object(entry_id)
    payload = json.loads(body)
    payload["research_lane"] = "discovery"

    with pytest.raises(ValueError, match="discovery"):
        research_feed.reconcile(
            s3=FakeS3({key: json.dumps(payload).encode()}),
            bucket="bucket",
        )


@pytest.mark.parametrize("schema_version", [0, 4])
def test_reconcile_rejects_unsupported_record_schema(
    monkeypatch, tmp_path, schema_version
):
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


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source_digest", "not-hex", "source_digest"),
        ("evidence_dimensions", ["data", "validation"], "evidence gate"),
        ("relevance_terms", ["factor", "factor"], "topic gate"),
        ("relevance_terms", ["factor", "factors"], "topic gate"),
        ("resolution_status", "closed", "resolution_status"),
        ("content_provenance", "title", "content_provenance"),
    ],
)
def test_reconcile_rejects_malformed_schema_three_quality(
    monkeypatch, tmp_path, field, value, message
):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    entry_id = "9" * 64
    key, body = _object(entry_id)
    payload = json.loads(body)
    payload[field] = value
    if field == "evidence_dimensions":
        payload["evidence_excerpts"] = {
            dimension: payload["evidence_excerpts"][dimension] for dimension in value
        }

    with pytest.raises(ValueError, match=message):
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


def test_qdata_schema_three_fixture_survives_projection(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    watchlist = {
        "schema_version": 4,
        "quality_policy": {
            "min_content_chars": 160,
            "min_topic_matches": 2,
            "summary_chars": 1000,
            "excerpt_chars": 400,
            "excerpts_per_dimension": 2,
            "topic_keywords": ["construction", "factor", "portfolio", "return"],
            "exclude_keywords": ["ci configuration"],
            "evidence_keywords": {
                "method": ["algorithm", "construction"],
                "data": ["data", "observations", "sample"],
                "validation": ["validate"],
                "result": ["result"],
            },
        },
        "sources": [
            {
                "id": "jkp-data-changelog",
                "name": "JKP factor data changelog",
                "kind": "markdown_changelog",
                "url": (
                    "https://raw.githubusercontent.com/bkelly-lab/jkp-data/"
                    "main/CHANGELOG_DATA.md"
                ),
                "canonical_url": (
                    "https://github.com/bkelly-lab/jkp-data/blob/main/CHANGELOG_DATA.md"
                ),
                "homepage": "https://jkpfactors.com/",
                "evidence_urls": ["https://github.com/bkelly-lab/jkp-data"],
                "item_type": "evidence_update",
                "content_provenance": "release_detail",
                "lookback_days": 3650,
                "max_entries": 20,
                "cadence_minutes": 60,
            }
        ],
    }
    changelog = b"""# Data Changelog
## 30-07-2026
__Changes__:
- The portfolio construction algorithm now sorts factor observations in the published data sample.
  The validation compares the old return implementation with the corrected result, and the complete
  source detail remains long enough to satisfy the non-title content contract without invented text.
"""
    spec = load_watchlist_payload(watchlist)[0]
    produced = discover_source(
        spec,
        now=datetime(2026, 9, 1, tzinfo=UTC),
        fetcher=lambda _url: changelog,
    )[0]
    key = f"research-radar/public/records/{produced['entry_id_sha256']}.json"

    research_feed.reconcile(
        s3=FakeS3({key: json.dumps(produced).encode()}),
        bucket="bucket",
    )
    projected = research_store.load_feed()["items"][0]

    assert projected["record_schema_version"] == 3
    assert projected["item_type"] == "evidence_update"
    assert projected["content_provenance"] == "release_detail"
    assert projected["evidence_dimensions"] == produced["evidence_dimensions"]
    assert projected["evidence_excerpts"] == produced["evidence_excerpts"]
    assert projected["source_digest"] == produced["source_digest"]
    assert projected["resolution_status"] == "maintainer_published"
