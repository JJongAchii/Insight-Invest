"""GET /news/briefing 테스트 — 서빙·스테일 강등·500 금지."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from datastore import storage
from module.news_briefing import KST

client = TestClient(app)


@pytest.fixture
def app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    monkeypatch.delenv("API_TOKEN", raising=False)
    return tmp_path


def _payload(as_of=None):
    return {
        "as_of": (as_of or datetime.now(KST)).isoformat(),
        "edition": "morning",
        "curated": True,
        "sections": {
            "general": [{"title": "t", "url": "u", "source": "s",
                         "published_at": None, "cluster_count": 3,
                         "sources": ["s"], "why": "w"}],
            "economy": [],
        },
    }


def test_briefing_active(app_data):
    storage.write_json(_payload(), "news_briefing.json")
    r = client.get("/news/briefing")
    assert r.status_code == 200
    body = r.json()
    assert body["active"] is True
    assert body["edition"] == "morning"
    assert body["sections"]["general"][0]["why"] == "w"


def test_briefing_stale_72h_inactive(app_data):
    storage.write_json(_payload(datetime.now(KST) - timedelta(hours=80)),
                       "news_briefing.json")
    r = client.get("/news/briefing")
    assert r.status_code == 200
    assert r.json() == {"active": False}


def test_briefing_weekend_kept(app_data):
    # 금 19시 발행 → 월 09시(62h)까지 유지되어야 한다 (스펙 §6)
    storage.write_json(_payload(datetime.now(KST) - timedelta(hours=62)),
                       "news_briefing.json")
    assert client.get("/news/briefing").json()["active"] is True


def test_briefing_missing_file_inactive(app_data):
    r = client.get("/news/briefing")
    assert r.status_code == 200
    assert r.json() == {"active": False}


def test_briefing_corrupt_file_no_500(app_data):
    (app_data / "news_briefing.json").write_text("{망가진 json")
    r = client.get("/news/briefing")
    assert r.status_code == 200
    assert r.json() == {"active": False}
