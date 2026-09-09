"""Producer -> canonical S3 -> app projection/library; no real provider calls."""

import hashlib
import io
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from botocore.exceptions import ClientError
from datastore import research as store
from module import research_feed, research_analysis
from app.routers.research import _matches_query
from qdata.radar_academic import TopicJob, candidate_record
from qdata.radar_editorial import publication_record
from qdata.radar_realtime import collect_due_sources

NOW = datetime(2026, 9, 8, tzinfo=UTC)
URL = "https://www.robeco.com/en-int/insights/2026/09/portfolio-research"


class S3:
    def __init__(self):
        self.objects = {}
        self.modified = {}
        self.now = NOW

    def list_objects_v2(self, *, Bucket, Prefix, **kwargs):
        return {
            "Contents": [
                {
                    "Key": k,
                    "ETag": hashlib.sha256(v).hexdigest(),
                    "LastModified": self.modified[k],
                }
                for k, v in self.objects.items()
                if k.startswith(Prefix)
            ]
        }

    def get_object(self, *, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[Key])}

    def head_object(self, *, Bucket, Key):
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {}

    def put_object(self, *, Bucket, Key, Body, IfNoneMatch=None, **kwargs):
        if IfNoneMatch == "*" and Key in self.objects:
            raise ClientError(
                {
                    "Error": {"Code": "PreconditionFailed"},
                    "ResponseMetadata": {"HTTPStatusCode": 412},
                },
                "PutObject",
            )
        self.objects[Key] = Body
        self.modified[Key] = self.now
        return {}


def academic_record():
    return candidate_record(
        {
            "title": "Portfolio construction with risk parity",
            "url": URL,
            "doi": "10.1234/portfolio",
            "text": "Portfolio construction with risk parity and empirical risk estimates. "
            * 12,
            "authors": ["Alice"],
            "published_at": "2026-08-01T00:00:00+00:00",
            "publisher": "Portfolio Journal",
            "provider_work_id": "https://openalex.org/W100",
            "item_type": "research_paper",
            "original_access_status": "unverified_open_link",
        },
        TopicJob("openalex", "portfolio"),
        now=NOW,
    )


def collect(s3, record):
    spec = SimpleNamespace(
        source_id="robeco-quant-insights",
        kind="editorial",
        cadence_minutes=60,
        realtime_enabled=True,
    )
    return collect_due_sources(
        [spec],
        s3=s3,
        bucket="b",
        record_prefix="records/",
        runtime_prefix="runtime",
        now=s3.now,
        discoverer=lambda *a, **k: [record],
    )


def test_late_doi_keeps_saved_read_seen_bytes_and_one_card(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    s3 = S3()
    original = publication_record(
        {
            "title": "Portfolio construction research",
            "url": URL,
            "pdf_url": "",
            "doi": "",
            "authors": ["Alice"],
            "published_at": "2026-08-01T00:00:00+00:00",
            "text": "We examine portfolio construction and risk diversification using monthly return data. "
            * 20,
            "analysis_scope": "full_article",
            "access_status": "open_full",
            "date_precision": "day",
        },
        source_id="robeco-quant-insights",
        now=NOW,
    )
    collect(s3, original)
    research_feed.reconcile(s3=s3, bucket="b", record_prefix="records/", now=NOW)
    entry_id = original["entry_id_sha256"]
    store.set_read(entry_id, read=True)
    store.set_saved(entry_id, saved=True)
    store.save_seen_through(NOW)
    paths = [tmp_path / store.READ_STATE_FILE, tmp_path / store.SEEN_STATE_FILE]
    before = [path.read_bytes() for path in paths]
    s3.now += timedelta(days=1)
    collect(s3, academic_record())
    result = research_feed.reconcile(
        s3=s3, bucket="b", record_prefix="records/", now=s3.now
    )
    assert result["added"] == result["removed"] == 0
    items = store.load_feed()["items"]
    assert len(items) == 1 and items[0]["entry_id"] == entry_id
    assert items[0]["doi"] == "10.1234/portfolio"
    assert _matches_query(items[0], "OpenAlex portfolio")
    assert store.entry_states()[entry_id] == {"is_read": True, "is_saved": True}
    assert [path.read_bytes() for path in paths] == before
    assert not any("/pending/" in key for key in s3.objects)


def test_academic_original_visible_without_llm_and_never_core(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    s3 = S3()
    collect(s3, academic_record())
    research_feed.reconcile(s3=s3, bucket="b", record_prefix="records/", now=NOW)
    item = store.load_feed()["items"][0]
    assert item["publisher"] == "Portfolio Journal"
    assert item["research_lane"] == "discovery"
    assert item["analysis_status"] == "not_requested"
    assert not item["notification_eligible"] and "analysis" not in item
    assert _matches_query(item, "Portfolio Journal")
    assert _matches_query(item, "10.1234/portfolio")
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-only")
    monkeypatch.setenv("RADAR_ANALYSIS_ENABLED", "true")

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "academic intake must not invoke a summary or fetch source again"
        )

    outcome = research_analysis.enrich(
        now=NOW, text_loader=forbidden, model_call=forbidden, review_call=forbidden
    )
    assert outcome["completed"] == 0
    item.update(
        analysis_status="ready", research_lane="core", notification_eligible=True
    )
    research_feed.apply_editorial_analysis(item)
    assert item["research_lane"] == "discovery" and not item["notification_eligible"]


def test_legacy_original_upgrade_preserves_user_state_and_one_card(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    url = "https://verdadcap.com/archive/factor-research"
    entry_id = hashlib.sha256(f"verdad-archive\0{url}".encode()).hexdigest()
    legacy = {
        "schema_version": 2,
        "source": "public_watchlist",
        "source_id": "verdad-archive",
        "source_name": "Verdad Research",
        "entry_id_sha256": entry_id,
        "url": url,
        "title": "Factor research",
        "summary": "Historical original",
        "authors": ["Alice"],
        "discovered_at": (NOW - timedelta(days=10)).isoformat(),
    }
    s3 = S3()
    key = f"records/{entry_id}.json"
    s3.put_object(Bucket="b", Key=key, Body=json.dumps(legacy).encode())
    research_feed.reconcile(s3=s3, bucket="b", record_prefix="records/", now=NOW)
    store.set_read(entry_id, read=True)
    store.set_saved(entry_id, saved=True)
    store.save_seen_through(NOW)
    paths = [tmp_path / store.READ_STATE_FILE, tmp_path / store.SEEN_STATE_FILE]
    before = [path.read_bytes() for path in paths]
    incoming = publication_record(
        {
            "title": "Factor research",
            "url": url,
            "pdf_url": "",
            "doi": "",
            "authors": ["Alice"],
            "published_at": "2026-08-01T00:00:00+00:00",
            "text": "We examine factor portfolios and the effect of trading costs. "
            * 25,
            "analysis_scope": "full_article",
            "access_status": "open_full",
            "date_precision": "day",
        },
        source_id="verdad-research",
        now=NOW,
    )
    collect_due_sources(
        [
            SimpleNamespace(
                source_id="verdad-research",
                kind="editorial",
                cadence_minutes=60,
                realtime_enabled=True,
            )
        ],
        s3=s3,
        bucket="b",
        record_prefix="records/",
        runtime_prefix="runtime",
        now=NOW,
        discoverer=lambda *a, **k: [incoming],
    )
    result = research_feed.reconcile(
        s3=s3, bucket="b", record_prefix="records/", now=NOW
    )
    assert result["added"] == result["removed"] == 0
    items = store.load_feed()["items"]
    assert len(items) == 1 and items[0]["entry_id"] == entry_id
    assert items[0]["record_schema_version"] == 4
    assert items[0]["discovered_at"] == legacy["discovered_at"]
    assert items[0]["source_id"] == "verdad-research"
    assert not items[0]["notification_candidate"]
    assert store.entry_states()[entry_id] == {"is_read": True, "is_saved": True}
    assert [path.read_bytes() for path in paths] == before
    assert not any("/pending/" in key for key in s3.objects)
