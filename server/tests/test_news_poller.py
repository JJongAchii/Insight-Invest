"""뉴스 폴러 Lambda 핸들러 테스트 — 발행·no-candidates·env 키 전달."""

from datetime import datetime, timezone

import pytest

from app import news_poller
from datastore import storage
from module import news_publish


@pytest.fixture
def app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return tmp_path


def _items():
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for i, t in enumerate(["대통령 회담 개최", "정부 정책 발표", "국제 갈등 고조",
                           "선거 판세 분석", "재난 대응 점검", "외교 순방 일정"]):
        rows.append({"title": t, "url": f"g{i}", "source": "한겨레", "published_at": now,
                     "cluster_count": 3, "sources": ["한겨레"], "cluster_urls": [],
                     "feed": "general"})
    for i, t in enumerate(["코스피 급등 마감", "환율 하락 전환", "기업 실적 호조",
                           "부동산 거래 증가", "물가 상승 둔화", "금리 인하 기대"]):
        rows.append({"title": t, "url": f"e{i}", "source": "한국경제", "published_at": now,
                     "cluster_count": 3, "sources": ["한국경제"], "cluster_urls": [],
                     "feed": "economy"})
    return rows


def test_handler_publishes_fallback_without_key(app_data, monkeypatch):
    monkeypatch.setattr(news_publish, "fetch_feeds", _items)
    out = news_poller.handler({}, None)
    assert out["status"] == "ok"
    assert out["curated"] is False
    assert out["items"] == 10
    data = storage.read_json("news_briefing.json")
    assert len(data["sections"]["general"]) == 5


def test_handler_no_candidates(app_data, monkeypatch):
    monkeypatch.setattr(news_publish, "fetch_feeds", lambda: [])
    out = news_poller.handler({}, None)
    assert out == {"status": "no-candidates"}
    assert not (app_data / "news_briefing.json").exists()


def test_handler_forwards_env_key(app_data, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")
    monkeypatch.setattr(news_publish, "fetch_feeds", _items)
    seen = {}

    def _fake_curate(candidates, api_key=None, _client=None):
        seen["api_key"] = api_key
        from module import news_briefing as nb
        return nb.fallback_selection(candidates), False

    monkeypatch.setattr(news_publish, "curate", _fake_curate)
    out = news_poller.handler({}, None)
    assert out["status"] == "ok"
    assert seen["api_key"] == "test-key-123"
