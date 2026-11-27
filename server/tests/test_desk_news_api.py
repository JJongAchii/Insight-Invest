"""뉴스 목록·미확인 수 API — 저장된 발행본만 읽고, 마지막으로 본 시각을 기기 간에 공유한다."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from datastore import storage
from module.kr_intraday import KST


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    monkeypatch.delenv("API_TOKEN", raising=False)
    return TestClient(app)


def issue(identity, minutes_ago, *, kind="news", origin="reporter", now=None):
    published = ((now or datetime.now(KST)) - timedelta(minutes=minutes_ago)).isoformat()
    return {"id": identity, "kind": kind, "origin": origin, "status": "reported", "headline": f"제목 {identity}",
            "fact": f"본문 {identity}", "interpretation": "", "watch": "", "observation": "",
            "published_at": published, "observed_at": published if kind == "move" else None, "sources": []}


def publish(issues, checked_minutes_ago=0):
    checked = (datetime.now(KST) - timedelta(minutes=checked_minutes_ago)).isoformat()
    storage.write_json({"version": 1, "checked_at": checked, "market_at": None, "filings_at": None,
                        "issues": issues, "briefings": []}, "market_desk", "board.json")
    return checked


def test_news_lists_published_articles_newest_first_without_market_moves(client):
    checked = publish([issue("old", 90), issue("move", 5, kind="move", origin="desk"),
                       issue("filing", 30, kind="filing", origin="desk"), issue("new", 10)])
    saved = client.get("/market-desk/news").json()
    assert [item["id"] for item in saved["items"]] == ["new", "filing", "old"]
    assert saved["state"] == "ready" and saved["checked_at"] == checked
    assert saved["items"][1]["kind"] == "filing" and saved["items"][0]["body"] == "본문 new"


def test_news_reports_a_late_board_and_an_absent_one_without_failing(client):
    assert client.get("/market-desk/news").json() == {
        "state": "awaiting", "checked_at": None, "items": [], "seen_through": None, "unseen": 0}
    publish([issue("only", 60 * 80)], checked_minutes_ago=60 * 72)
    late = client.get("/market-desk/news").json()
    assert late["state"] == "stale" and [item["id"] for item in late["items"]] == ["only"]


def test_unreadable_board_is_an_error_for_the_news_page_but_not_for_the_badge(client, tmp_path):
    (tmp_path / "market_desk").mkdir()
    (tmp_path / "market_desk" / "board.json").write_text("{}")
    assert client.get("/market-desk/news").status_code == 503
    assert client.get("/market-desk/news/status").json() == {"unseen": 0, "latest_at": None, "seen_through": None}


def test_unseen_counts_news_published_after_the_last_visit(client):
    issues = [issue("a", 120), issue("b", 60), issue("c", 5), issue("move", 1, kind="move", origin="desk")]
    publish(issues)
    first = client.get("/market-desk/news/status").json()
    assert first == {"unseen": 3, "latest_at": issues[2]["published_at"], "seen_through": None}
    seen = client.put("/market-desk/news/seen", json={"through": issues[1]["published_at"]}).json()
    assert seen == {"unseen": 1, "latest_at": issues[2]["published_at"], "seen_through": issues[1]["published_at"]}
    listed = client.get("/market-desk/news").json()
    assert (listed["unseen"], listed["seen_through"]) == (1, issues[1]["published_at"])


def test_last_visit_never_moves_back_or_ahead_of_now(client):
    issues = [issue("a", 60), issue("b", 5)]
    publish(issues)
    client.put("/market-desk/news/seen", json={"through": issues[1]["published_at"]})
    earlier = client.put("/market-desk/news/seen", json={"through": issues[0]["published_at"]}).json()
    assert earlier["seen_through"] == issues[1]["published_at"]
    ahead = (datetime.now(KST) + timedelta(days=2)).isoformat()
    clamped = datetime.fromisoformat(client.put("/market-desk/news/seen", json={"through": ahead}).json()["seen_through"])
    assert clamped <= datetime.now(KST) + timedelta(seconds=5)
    assert client.put("/market-desk/news/seen", json={"through": "2026-11-27T10:00:00"}).status_code == 422


def test_damaged_last_visit_counts_everything_until_the_next_visit(client, tmp_path):
    issues = [issue("a", 60), issue("b", 5)]
    publish(issues)
    (tmp_path / "market_desk" / "news_seen.json").write_text("{broken")
    assert client.get("/market-desk/news/status").json()["unseen"] == 2
    repaired = client.put("/market-desk/news/seen", json={"through": issues[1]["published_at"]}).json()
    assert repaired["unseen"] == 0 and repaired["seen_through"] == issues[1]["published_at"]


def test_week_list_of_the_board_is_the_news_page_and_stays_out_of_the_home_response(client):
    recent = [issue("move", 3, kind="move", origin="desk"), issue("today", 10)]
    week = [{**issue("today", 10), "fact": "핵심 사실.", "category": "경제", "priority": "urgent",
             "significance": "왜 중요한지."}] + [issue(f"day{i}", 60 * 24 * i) for i in range(1, 7)]
    checked = datetime.now(KST).isoformat()
    storage.write_json({"version": 1, "checked_at": checked, "market_at": None, "filings_at": None,
                        "issues": recent, "news": week, "briefings": []}, "market_desk", "board.json")
    listed = client.get("/market-desk/news").json()["items"]
    assert [item["id"] for item in listed] == ["today", "day1", "day2", "day3", "day4", "day5", "day6"]
    assert (listed[0]["summary"], listed[0]["priority"], listed[0]["significance"]) == ("핵심 사실.", "urgent", "왜 중요한지.")
    assert client.get("/market-desk/news/status").json()["unseen"] == 7
    home = client.get("/market-desk").json()["board"]
    assert [item["id"] for item in home["issues"]] == ["move", "today"] and "news" not in home


def test_malformed_article_is_left_out_of_the_news_without_taking_down_the_home_or_the_rest(client):
    good, broken = issue("good", 10), issue("broken", 5)
    del broken["observed_at"]
    storage.write_json({"version": 1, "checked_at": datetime.now(KST).isoformat(), "market_at": None,
                        "filings_at": None, "issues": [good], "news": [broken, good, "not an article"],
                        "briefings": []}, "market_desk", "board.json")
    assert [item["id"] for item in client.get("/market-desk/news").json()["items"]] == ["good"]
    assert client.get("/market-desk/news/status").json()["unseen"] == 1
    home = client.get("/market-desk").json()
    assert home["state"] == "ready" and [item["id"] for item in home["board"]["issues"]] == ["good"]


def test_news_is_still_served_when_another_part_of_the_board_is_malformed(client):
    storage.write_json({"version": 1, "checked_at": datetime.now(KST).isoformat(), "market_at": None,
                        "filings_at": None, "issues": [issue("report", 10)],
                        "briefings": [{"id": "am", "kind": "weekly"}]}, "market_desk", "board.json")
    assert client.get("/market-desk").status_code == 503
    assert [item["id"] for item in client.get("/market-desk/news").json()["items"]] == ["report"]


def test_visit_reaches_the_newest_article_even_when_its_time_is_ahead_of_this_clock(client):
    ahead = issue("ahead", -3)
    publish([issue("past", 30), ahead])
    seen = client.put("/market-desk/news/seen", json={"through": ahead["published_at"]}).json()
    assert seen == {"unseen": 0, "latest_at": ahead["published_at"], "seen_through": ahead["published_at"]}
