"""storage JSON 헬퍼 + 뉴스 KR 리전 설정 테스트."""

import pytest

from datastore import storage
from module.news.config import DOMAIN_TO_SOURCE, NewsRegion
from module.news.service import NewsService


@pytest.fixture
def app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    return tmp_path


def test_json_roundtrip(app_data):
    obj = {"as_of": "2026-08-14T09:00:00+09:00", "sections": {"general": [{"제목": "한글"}]}}
    target = storage.write_json(obj, "news_briefing.json")
    assert (app_data / "news_briefing.json").exists()
    assert "한글" in (app_data / "news_briefing.json").read_text()  # ensure_ascii=False
    assert storage.read_json("news_briefing.json") == obj
    assert target.endswith("news_briefing.json")


def test_kr_region_config():
    assert NewsRegion.KR.value == "kr"
    assert NewsService.REGION_CONFIG[NewsRegion.KR] == ("ko", "KR")
    assert DOMAIN_TO_SOURCE["yna.co.kr"] == "연합뉴스"
    assert DOMAIN_TO_SOURCE["hankyung.com"] == "한국경제"


def test_kr_region_schema():
    from app import schemas

    assert schemas.NewsRegion("kr") is schemas.NewsRegion.KR
