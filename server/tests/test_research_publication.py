"""Release seeding writes immutable caches only, not user state or the live feed."""

import importlib
import io
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from datastore import research, storage
from module import (
    research_analysis as analysis,
    research_feed,
    research_selection as selection,
)
from research_review_fixtures import attach_review, selection_for
from test_research_analysis import NOW, TEXT, brief, source as source

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
publisher = importlib.import_module("publish_research_qualification")


def report_for(record, *, kind="research"):
    item = {**record, "entry_id": record["entry_id_sha256"], "record_schema_version": 4}
    item["editorial_selection"] = selection_for(item, TEXT, NOW, kind=kind)
    item["analysis"] = {
        "fingerprint": analysis.cache_key(item),
        "brief": brief(),
        "source_digest": item["source_digest"],
    }
    attach_review(item, TEXT, NOW)
    return {
        "production_modified": False,
        "status": "api_contract_qualified",
        "analysis_runs": [{"reserved_nanousd": 100}],
        "items": [item],
    }


class CacheStore:
    def __init__(self):
        self.objects = {}
        self.writes = []

    def put_object(self, **kwargs):
        assert kwargs["Bucket"] == publisher.BUCKET
        assert kwargs["IfNoneMatch"] == "*"
        assert kwargs["ServerSideEncryption"] == "AES256"
        key = kwargs["Key"]
        if key in self.objects:
            raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
        self.writes.append(key)
        self.objects[key] = kwargs["Body"]

    def get_object(self, **kwargs):
        return {"Body": io.BytesIO(self.objects[kwargs["Key"]])}


def test_seeding_is_cache_only_conditional_and_idempotent(source):
    report = report_for(source.record)
    original = deepcopy(report)
    objects = publisher.plan(report, text_loader=lambda _: TEXT)
    assert len(objects) == 3
    client = CacheStore()
    assert all(r["state"] == "planned" for r in publisher.seed(objects, client))
    assert client.writes == []
    assert all(
        r["state"] == "seeded" for r in publisher.seed(objects, client, apply=True)
    )
    assert all(
        r["state"] == "already_identical"
        for r in publisher.seed(objects, client, apply=True)
    )
    assert len(client.writes) == 3 and report == original
    changed = deepcopy(objects)
    changed[next(iter(changed))]["checked_at"] = "different"
    with pytest.raises(ValueError, match="never overwrite"):
        publisher.seed(changed, client, apply=True)
    assert len(client.writes) == 3


@pytest.mark.parametrize(
    "key",
    [
        "app/research_feed.json",
        "app/research_read_state.parquet",
        "app/research_analysis/budget-2026-09.json",
        "research-radar/realtime/pending/a.json",
        "app/research_analysis/../cache/" + "a" * 64 + ".json",
    ],
)
def test_all_keys_are_checked_before_any_write(key):
    client = CacheStore()
    with pytest.raises(ValueError, match="outside reading cache"):
        publisher.seed(
            {publisher.PREFIX + "selections/" + "a" * 64 + ".json": {}, key: {}},
            client,
            apply=True,
        )
    assert client.writes == []


def test_context_seeds_only_selection_and_never_its_obsolete_brief(source):
    report = report_for(source.record, kind="market_commentary")
    report["items"][0]["analysis"] = {"obsolete": "do not publish"}
    objects = publisher.plan(report, text_loader=lambda _: TEXT)
    assert len(objects) == 1 and "/selections/" in next(iter(objects))


@pytest.mark.parametrize("change", ["input", "selection", "draft", "live"])
def test_changed_or_live_report_cannot_seed(source, change):
    report = report_for(source.record)
    if change == "live":
        report["production_modified"] = True
    elif change == "input":
        report["items"][0]["editorial_selection"]["input_digest"] = "changed"
    elif change == "selection":
        report["items"][0]["editorial_selection"]["decision"]["reason"] = "changed"
    else:
        report["items"][0]["analysis"]["brief"]["title_ko"] = "changed"
    with pytest.raises(ValueError):
        publisher.plan(report, text_loader=lambda _: TEXT)


@pytest.mark.parametrize("exhausted", [False, True])
def test_paid_work_limit_does_not_block_later_cache_recovery(source, exhausted):
    research_feed.reconcile(s3=source, now=NOW)
    feed = research.load_feed()
    pending = feed["items"][0]
    # Put an unresolved source first, the verified cache second.
    pending["title"] = "Another unselected original"
    ready = report_for(source.record)["items"][0]
    ready["analysis_status"] = "pending"
    for key, value in publisher.plan(
        {
            "production_modified": False,
            "status": "api_contract_qualified",
            "analysis_runs": [{"reserved_nanousd": 0}],
            "items": [ready],
        },
        text_loader=lambda _: TEXT,
    ).items():
        storage.write_json(value, key.removeprefix("app/"))
    ready.pop("editorial_selection")
    ready.pop("analysis")
    feed["items"].append(ready)
    research.save_feed(feed)
    if exhausted:
        storage.write_json(
            {"reserved_nanousd": 2_000_000_000}, "research_analysis/budget-2026-09.json"
        )

    def forbidden(*_args):
        pytest.fail("cached recovery must make no paid call")

    analysis.enrich(
        now=NOW,
        max_items=1 if exhausted else 0,
        text_loader=lambda _: TEXT,
        model_call=forbidden,
        selection_call=forbidden,
        review_call=forbidden,
    )
    recovered = research.load_feed()["items"][1]
    assert selection.state(recovered) == "core"
    assert recovered["analysis_status"] == "ready"
    assert recovered["research_lane"] == "core"
