import pandas as pd
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.routers import research
from datastore import research as research_store
from datastore import storage

client = TestClient(app)


def _feed(first_id, second_id):
    return {
        "schema_version": 1,
        "generated_at": "2026-09-02T00:00:00+00:00",
        "items": [
            {
                "entry_id": first_id,
                "source_id": "alpha",
                "source_name": "Alpha Research",
                "title": "First paper",
                "summary": "Robust portfolio construction",
                "authors": ["Alice Quant"],
            },
            {
                "entry_id": second_id,
                "source_id": "beta",
                "source_name": "Beta Research",
                "title": "Second paper",
                "summary": "Volatility forecasting",
                "authors": ["Bob Risk"],
            },
        ],
    }


def _get(**overrides):
    arguments = {
        "source_id": None,
        "unread_only": False,
        "view": "all",
        "q": None,
        "entry_id": None,
        "offset": 0,
        "limit": 100,
    }
    arguments.update(overrides)
    return research.get_research_feed(**arguments)


def test_feed_filters_and_read_state(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    first_id = "a" * 64
    second_id = "b" * 64
    research_store.save_feed(_feed(first_id, second_id))

    initial = _get()
    assert initial["total"] == 2
    assert initial["unread"] == 2
    assert initial["read"] == 0
    assert initial["saved"] == 0
    assert {source["source_id"] for source in initial["sources"]} == {"alpha", "beta"}

    response = research.set_research_read_state(first_id, research.ResearchReadRequest(read=True))
    assert response == {"entry_id": first_id, "is_read": True}
    assert [item["entry_id"] for item in _get(unread_only=True)["items"]] == [second_id]
    assert [item["entry_id"] for item in _get(source_id="alpha")["items"]] == [first_id]
    assert _get(entry_id=first_id)["items"][0]["is_read"] is True

    saved = research.set_research_saved_state(
        first_id,
        research.ResearchSavedRequest(saved=True),
    )
    assert saved == {"entry_id": first_id, "is_saved": True}
    assert [item["entry_id"] for item in _get(view="saved")["items"]] == [first_id]
    assert _get(entry_id=first_id)["items"][0]["is_saved"] is True

    research.set_research_read_state(first_id, research.ResearchReadRequest(read=False))
    assert _get()["unread"] == 2
    assert _get(entry_id=first_id)["items"][0]["is_saved"] is True

    research.set_research_saved_state(first_id, research.ResearchSavedRequest(saved=False))
    assert _get()["saved"] == 0


def test_search_views_and_entry_deep_link_priority(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    first_id = "a" * 64
    second_id = "b" * 64
    research_store.save_feed(_feed(first_id, second_id))
    research_store.set_read(first_id, read=True)
    research_store.set_saved(second_id, saved=True)

    assert [item["entry_id"] for item in _get(view="read")["items"]] == [first_id]
    assert [item["entry_id"] for item in _get(view="unread")["items"]] == [second_id]
    assert [item["entry_id"] for item in _get(view="saved")["items"]] == [second_id]
    assert [item["entry_id"] for item in _get(q="ROBUST alice")["items"]] == [first_id]
    assert [item["entry_id"] for item in _get(q="beta risk")["items"]] == [second_id]
    assert _get(q="missing")["items"] == []

    selected = _get(
        entry_id=first_id,
        source_id="beta",
        view="saved",
        q="missing",
    )
    assert [item["entry_id"] for item in selected["items"]] == [first_id]


def test_mark_all_read_preserves_saved_state_and_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    first_id = "a" * 64
    second_id = "b" * 64
    research_store.save_feed(_feed(first_id, second_id))
    research_store.set_saved(first_id, saved=True)
    research_store.set_read(first_id, read=True)
    original_read_at = research_store.list_read_state().loc[0, "read_at"]

    assert research.mark_all_research_read() == {"updated": 1, "total": 2, "unread": 0}
    assert research.mark_all_research_read() == {"updated": 0, "total": 2, "unread": 0}
    assert _get()["read"] == 2
    assert _get()["saved"] == 1
    assert _get(entry_id=first_id)["items"][0]["is_saved"] is True
    preserved_read_at = (
        research_store.list_read_state()
        .loc[
            lambda frame: frame["entry_id"] == first_id,
            "read_at",
        ]
        .iloc[0]
    )
    assert preserved_read_at == original_read_at


def test_legacy_read_state_adds_saved_column_without_losing_read_at(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    first_id = "a" * 64
    second_id = "b" * 64
    research_store.save_feed(_feed(first_id, second_id))
    storage.write_parquet(
        pd.DataFrame([{"entry_id": first_id, "read_at": "2026-09-01T00:00:00+00:00"}]),
        research_store.READ_STATE_FILE,
    )

    research_store.set_saved(first_id, saved=True)

    item = _get(entry_id=first_id)["items"][0]
    assert item["is_read"] is True
    assert item["is_saved"] is True
    assert list(research_store.list_read_state().columns) == research_store.READ_STATE_COLUMNS


def test_feed_rejects_invalid_or_unknown_entry(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    known_id = "a" * 64
    research_store.save_feed(_feed(known_id, "b" * 64))

    with pytest.raises(HTTPException) as invalid:
        _get(entry_id="not-a-digest")
    assert invalid.value.status_code == 422

    with pytest.raises(HTTPException) as unknown:
        research.set_research_read_state("c" * 64, research.ResearchReadRequest(read=True))
    assert unknown.value.status_code == 404

    with pytest.raises(HTTPException) as unknown_get:
        _get(entry_id="c" * 64)
    assert unknown_get.value.status_code == 404

    with pytest.raises(HTTPException) as invalid_view:
        _get(view="archive")
    assert invalid_view.value.status_code == 422

    with pytest.raises(HTTPException) as long_query:
        _get(q="x" * 201)
    assert long_query.value.status_code == 422


def test_mark_all_read_static_route_is_not_captured_as_entry_id(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    research_store.save_feed(_feed("a" * 64, "b" * 64))

    response = client.put("/research/read/all")

    assert response.status_code == 200
    assert response.json() == {"updated": 2, "total": 2, "unread": 0}
