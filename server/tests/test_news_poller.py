"""뉴스 알림 폴러 — 편집팀이 긴급으로 분류한 새 뉴스만 기기마다 한 번 알린다."""

from datetime import datetime, timedelta

import pytest

from app import news_poller
from datastore import notifications, storage
from module import action_push
from module.kr_intraday import KST

NOW = datetime(2026, 11, 27, 10, 30, tzinfo=KST)


@pytest.fixture
def sent(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    monkeypatch.setenv("WEB_PUSH_PUBLIC_KEY", "public")
    monkeypatch.setenv("WEB_PUSH_PRIVATE_KEY", "private")
    notifications.upsert_subscription("https://push.example.test/phone", "p" * 32, "a" * 16)
    payloads = []
    monkeypatch.setattr(action_push, "send_to_subscription", lambda _subscription, payload: payloads.append(payload))
    return payloads


def report(identity, minutes_ago, priority, headline):
    published = (NOW - timedelta(minutes=minutes_ago)).isoformat()
    return {"id": identity, "kind": "news", "origin": "reporter", "status": "reported", "headline": headline,
            "fact": "확인된 사실.", "priority": priority, "category": "경제", "significance": "시장에 영향을 준다.",
            "interpretation": "", "watch": "", "observation": "", "published_at": published, "observed_at": None,
            "sources": []}


def publish(*issues, **board):
    storage.write_json({"version": 1, "checked_at": NOW.isoformat(), "market_at": None, "filings_at": None,
                        "issues": list(issues), "briefings": [], **board}, "market_desk", "board.json")


def test_urgent_news_is_sent_once_and_opens_its_article(sent):
    publish(report("source-7/a", 10, "urgent", "긴급 금리 결정"), report("calm", 5, "major", "일반 소식"))
    first = news_poller.run(NOW)
    assert first["urgent"] == 1 and first["push"]["sent"] == 1
    assert sent == [{"title": "긴급 뉴스", "body": "긴급 금리 결정", "url": "/news?item=source-7%2Fa",
                     "tag": f"insight-news-news:source-7/a:{(NOW - timedelta(minutes=10)).isoformat()}",
                     "event_id": f"news:source-7/a:{(NOW - timedelta(minutes=10)).isoformat()}", "badge": 1}]
    assert news_poller.run(NOW + timedelta(minutes=5))["push"]["sent"] == 0
    assert len(sent) == 1


def test_urgent_text_edition_is_recognised(sent):
    text = "*[긴급 · 금융] 은행 지급 중단*\n지급이 중단됐다.\n*왜 중요한가* 예금자 보호 범위를 확인해야 한다."
    issue = {**report("legacy", 2, None, "은행 지급 중단"), "fact": text}
    del issue["priority"], issue["category"], issue["significance"]
    publish(issue)
    assert news_poller.run(NOW)["push"]["sent"] == 1 and sent[0]["body"] == "은행 지급 중단"


def test_urgent_news_in_the_week_list_notifies_even_when_the_home_list_has_only_its_text(sent):
    structured = report("event", 4, "urgent", "긴급 금리 결정")
    as_text = {key: value for key, value in structured.items() if key not in ("priority", "category", "significance")}
    publish({**as_text, "fact": "*[주요 · 경제] 이전 형식 본문*\n사실."}, news=[structured])
    assert news_poller.run(NOW)["push"]["sent"] == 1 and sent[0]["body"] == "긴급 금리 결정"


def test_old_urgent_news_and_ordinary_news_do_not_notify(sent):
    publish(report("old", 181, "urgent", "세 시간 넘게 지난 긴급"), report("calm", 1, "major", "일반 소식"),
            {**report("filing", 1, None, "공시"), "kind": "filing", "origin": "desk"})
    result = news_poller.run(NOW)
    assert result["urgent"] == 0 and sent == []


def test_material_update_to_an_urgent_event_notifies_again(sent):
    publish(report("event", 30, "urgent", "해협 봉쇄"))
    news_poller.run(NOW)
    publish(report("event", 2, "urgent", "해협 봉쇄 해제"))
    news_poller.run(NOW)
    assert [payload["body"] for payload in sent] == ["해협 봉쇄", "해협 봉쇄 해제"]


def test_several_urgent_articles_arrive_as_one_notification(sent):
    publish(report("a", 8, "urgent", "첫 긴급"), report("b", 3, "urgent", "둘째 긴급"))
    news_poller.run(NOW)
    assert [(payload["body"], payload["url"], payload["badge"]) for payload in sent] == [("둘째 긴급 외 1건", "/news", 2)]


def test_absent_board_waits_and_unreadable_board_reports_failure(sent, tmp_path):
    assert news_poller.handler({}, None) == {"ok": True, "state": "awaiting", "urgent": 0}
    (tmp_path / "market_desk").mkdir()
    (tmp_path / "market_desk" / "board.json").write_text("{}")
    assert news_poller.handler({}, None) == {"ok": False, "error": "ValidationError"}
    assert sent == []


def test_malformed_briefing_does_not_silence_urgent_news(sent):
    publish(report("event", 4, "urgent", "긴급 금리 결정"), briefings=[{"id": "am", "kind": "weekly"}])
    assert news_poller.run(NOW)["push"]["sent"] == 1
