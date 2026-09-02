import pytest
from fastapi import HTTPException

from app.routers import research
from datastore import research as research_store


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
            },
            {
                "entry_id": second_id,
                "source_id": "beta",
                "source_name": "Beta Research",
                "title": "Second paper",
            },
        ],
    }


def _get(**overrides):
    arguments = {
        "source_id": None,
        "unread_only": False,
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
    assert {source["source_id"] for source in initial["sources"]} == {"alpha", "beta"}

    response = research.set_research_read_state(first_id, research.ResearchReadRequest(read=True))
    assert response == {"entry_id": first_id, "is_read": True}
    assert [item["entry_id"] for item in _get(unread_only=True)["items"]] == [second_id]
    assert [item["entry_id"] for item in _get(source_id="alpha")["items"]] == [first_id]
    assert _get(entry_id=first_id)["items"][0]["is_read"] is True

    research.set_research_read_state(first_id, research.ResearchReadRequest(read=False))
    assert _get()["unread"] == 2


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
