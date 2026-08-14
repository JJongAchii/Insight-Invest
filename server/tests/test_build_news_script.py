"""build_news.py 스크립트 테스트 — 폴백 발행·fake LLM 큐레이션·재시도."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from datastore import storage

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_news.py"
spec = importlib.util.spec_from_file_location("build_news", SCRIPT)
bn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bn)


@pytest.fixture
def app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # 로컬 ~/Quant/quant-data/.env에 실키가 있어도 절대 읽지 않도록
    # 존재하지 않는 경로로 고정 — 없으면 no-key 폴백 경로가 결정적으로 탄다.
    monkeypatch.setenv("BRIEFING_ENV_FILE", str(tmp_path / "no-such.env"))
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


class FakeClient:
    def __init__(self, texts):
        self.calls = 0
        outer = self

        class _Messages:
            def create(self, **kwargs):
                outer.calls += 1
                text = texts[min(outer.calls - 1, len(texts) - 1)]
                return SimpleNamespace(content=[SimpleNamespace(text=text)])

        self.messages = _Messages()


def test_no_key_falls_back(app_data, monkeypatch):
    monkeypatch.setattr(bn, "_fetch_feeds", lambda: _items())
    assert bn.main() == 0
    data = storage.read_json("news_briefing.json")
    assert data["curated"] is False
    assert len(data["sections"]["general"]) == 5
    assert len(data["sections"]["economy"]) == 5
    assert all("why" not in r for r in data["sections"]["general"])


def test_fake_llm_curates(app_data):
    items = _items()
    from datetime import datetime, timezone
    from module import news_briefing as nb
    cand = nb.rank_candidates(nb.merge_stories(items), datetime.now(timezone.utc))
    gen = [c["id"] for c in cand if c["feed"] == "general"][:5]
    eco = [c["id"] for c in cand if c["feed"] == "economy"][:5]
    good = json.dumps({
        "general": [{"id": i, "why": f"이유 {i}"} for i in gen],
        "economy": [{"id": i, "why": f"이유 {i}"} for i in eco],
    })
    sel, curated = bn._curate(cand, _client=FakeClient([good]))
    assert curated is True
    assert len(sel["general"]) == 5


def test_bad_then_good_retries_once(app_data):
    items = _items()
    from datetime import datetime, timezone
    from module import news_briefing as nb
    cand = nb.rank_candidates(nb.merge_stories(items), datetime.now(timezone.utc))
    gen = [c["id"] for c in cand if c["feed"] == "general"][:5]
    eco = [c["id"] for c in cand if c["feed"] == "economy"][:5]
    bad = json.dumps({"general": [{"id": 9999, "why": "x"}], "economy": []})
    good = json.dumps({
        "general": [{"id": i, "why": "이유"} for i in gen],
        "economy": [{"id": i, "why": "이유"} for i in eco],
    })
    fake = FakeClient([bad, good])
    sel, curated = bn._curate(cand, _client=fake)
    assert curated is True and fake.calls == 2


def test_bad_twice_falls_back(app_data):
    items = _items()
    from datetime import datetime, timezone
    from module import news_briefing as nb
    cand = nb.rank_candidates(nb.merge_stories(items), datetime.now(timezone.utc))
    bad = json.dumps({"general": [{"id": 9999, "why": "x"}], "economy": []})
    fake = FakeClient([bad, bad])
    sel, curated = bn._curate(cand, _client=fake)
    assert curated is False and fake.calls == 2


def test_empty_feeds_skip_publish(app_data, monkeypatch):
    monkeypatch.setattr(bn, "_fetch_feeds", lambda: [])
    assert bn.main() == 0
    assert not (app_data / "news_briefing.json").exists()
