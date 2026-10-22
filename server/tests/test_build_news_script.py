"""build_news 스크립트 + news_publish 공용 로직 테스트 — 규칙 랭킹 발행, API 미호출."""

import importlib.util
from pathlib import Path

import pytest

from datastore import storage
from module import news_publish

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_news.py"
spec = importlib.util.spec_from_file_location("build_news", SCRIPT)
bn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bn)


@pytest.fixture
def app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return tmp_path


def _items(n_general=6, n_economy=6):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    out = []
    gen_titles = [
        "대통령 경제회의 개최",
        "정부 예산안 국회 통과",
        "국제 정상회담 개최",
        "국내 실업률 발표",
        "기업 실적 발표 시즌",
        "금리 결정 공개",
    ]
    econ_titles = [
        "주식시장 신고가 경신",
        "원화 환율 변동",
        "기업 이익 증가",
        "부동산 시장 분석",
        "소비자 물가지수 발표",
        "금융감독 정책 변경",
    ]
    for i in range(n_general):
        out.append({"title": gen_titles[i % len(gen_titles)], "url": f"g{i}", "source": "한겨레",
                    "published_at": now, "cluster_count": 5 - (i % 5),
                    "sources": ["한겨레"], "cluster_urls": [], "feed": "general"})
    for i in range(n_economy):
        out.append({"title": econ_titles[i % len(econ_titles)], "url": f"e{i}", "source": "한국경제",
                    "published_at": now, "cluster_count": 5 - (i % 5),
                    "sources": ["한국경제"], "cluster_urls": [], "feed": "economy"})
    return out


def test_publishes_rule_ranking(app_data, monkeypatch):
    monkeypatch.setattr(news_publish, "fetch_feeds", lambda: _items())
    assert bn.main() == 0
    data = storage.read_json("news_briefing.json")
    assert data["curated"] is False
    assert len(data["sections"]["general"]) == 5
    assert len(data["sections"]["economy"]) == 5
    assert all("why" not in r for r in data["sections"]["general"])


def test_empty_feeds_skip_publish(app_data, monkeypatch):
    monkeypatch.setattr(news_publish, "fetch_feeds", lambda: [])
    assert bn.main() == 0
    assert not (app_data / "news_briefing.json").exists()


def test_never_calls_the_anthropic_api_even_with_a_key(app_data, monkeypatch):
    """AI 큐레이션은 껐다(2026-10-23) — 키가 남아 있어도 클라이언트를 만들지 않는다."""
    import sys
    from types import ModuleType

    made = []
    fake = ModuleType("anthropic")
    fake.Anthropic = lambda **kw: made.append(kw)
    monkeypatch.setitem(sys.modules, "anthropic", fake)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(news_publish, "fetch_feeds", lambda: _items())
    assert bn.main() == 0
    data = storage.read_json("news_briefing.json")
    assert made == [] and data["curated"] is False
    assert len(data["sections"]["general"]) + len(data["sections"]["economy"]) == 10
