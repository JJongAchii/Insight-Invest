from datetime import datetime, timedelta

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.routers.market_desk import _current_lead
from datastore import storage
from module.kr_intraday import KST
from module.market_desk import market_input


def test_representative_article_uses_current_session_and_only_completed_closes():
    close = datetime(2026, 11, 26, 15, 30, tzinfo=KST)
    now = close + timedelta(minutes=45)
    stamp = (now - timedelta(minutes=10)).isoformat()
    source = {"title": "시황 원문", "publisher": "통신사", "url": "https://example.org/market", "published_at": stamp}
    passage = {"text": "현재 장세를 비교 시점의 근거와 함께 읽습니다.", "sources": [source]}
    item = {"phase": "close", "trade_date": now.date().isoformat(), "close_at": close.isoformat(),
            "as_of": stamp, "cutoff": stamp, "published_at": now.isoformat(), "headline": "코스피 장세 해석",
            "reading": passage, "qualification": passage, "watch": "다음 거래일 수급을 봅니다."}
    assert _current_lead(item, now).phase == "close"
    assert _current_lead(item, now + timedelta(days=1)) is None
    assert _current_lead({**item, "as_of": (close-timedelta(minutes=5)).isoformat()}, now) is None
    assert _current_lead({**item, "published_at": (now+timedelta(minutes=5)).isoformat()}, now) is None
    future = {**passage, "sources": [{**source, "published_at": now.isoformat()}]}
    assert _current_lead({**item, "reading": future}, now) is None
    early = close.replace(hour=11)
    early_source = {**passage, "sources": [{**source, "published_at": early.isoformat()}]}
    live = {**item, "phase": "intraday", "as_of": early.isoformat(), "cutoff": early.isoformat(),
            "published_at": early.isoformat(), "reading": early_source, "qualification": early_source}
    assert _current_lead(live, early + timedelta(minutes=60))
    assert _current_lead(live, early + timedelta(minutes=91)) is None
    assert _current_lead(live, close) is None


def test_compare_adjacent_observations_even_without_yesterdays_close():
    now = datetime(2026, 11, 26, 10, 15, tzinfo=KST)
    rows = []
    for hour, level, change in [("09:35", 100, 0), ("10:05", 102, 0.1), ("10:15", 101, -1.0)]:
        base = {"trade_date": "2026-11-26", "as_of": f"2026-11-26 {hour}"}
        rows.extend([{**base, "kind": "index", "key": "KOSPI", "level": level, "chg_pct": None},
                     {**base, "kind": "sector", "key": "전자", "chg_pct": change, "n": 10}])
    stocks = pd.DataFrame([{"sector": "전자", "name": "테스트기업", "value": 1000, "cap": 2000}])
    packet = market_input(pd.DataFrame(rows + rows[-1:]), stocks, now)
    assert [(m["subject"], m["change"], m["unit"]) for m in packet["moves"]] == [
        ("KOSPI", -0.98, "%"), ("전자", -1.1, "%p")]
    assert packet["moves"][1]["companies"] == ["테스트기업"]
    assert packet["observed_at"] == now.isoformat()
    assert packet["session"] is None  # KOSDAQ was not collected


def test_session_explains_intraday_reversal_and_sector_concentration_from_aligned_samples():
    now = datetime(2026, 11, 26, 11, 5, tzinfo=KST)
    levels = [("09:05", 102, 105), ("10:05", 101, 103), ("11:05", 100.5, 101), ("11:15", 200, 200)]
    rows = pd.DataFrame([
        {"trade_date": "2026-11-26", "as_of": f"2026-11-26 {time}", "kind": "index", "key": key,
         "level": level, "chg_pct": level - 100, "n": None}
        for time, kospi, kosdaq in levels for key, level in [("KOSPI", kospi), ("KOSDAQ", kosdaq)]
    ])
    stocks = pd.DataFrame([
        {"as_of": f"2026-11-26 {time}", "sector": sector, "chg_pct": chg, "cap": cap, "name": name, "value": 5}
        for sector, name, cap, chg, time in [
            ("증권", "대형증권", 80, 5, "11:05"), *[("증권", "기타증권", 5, 1, "11:05")] * 4,
            *[("운송", "운송기업", 2, -1, "11:05")] * 5, ("소수업종", "단일기업", 5, 99, "11:05"),
            *[("기타", "미분류", 5, 99, "11:05")] * 5, ("증권", "다음수집", 9999, 70, "11:15"),
        ]
    ])
    session = market_input(rows, stocks, now)["session"]
    assert session["observed_at"] == now.isoformat()
    assert session["headline"] == "코스닥, 오전 상승분의 80% 반납"
    assert "09:05 수집 때 +5.00%" in session["market"] and "11:05에는 +1.00%" in session["market"]
    assert "10:05~11:05" in session["market"] and "코스닥 -1.94%" in session["market"]
    assert "증권(+4.20%)" in session["sectors"] and "운송(-1.00%)" in session["sectors"]
    assert "95%가 대형증권" in session["sectors"]
    assert "대형증권 외 종목" in session["watch"]
    rows.loc[rows["key"].eq("KOSDAQ"), "chg_pct"] = None
    no_baseline = market_input(rows, stocks.iloc[0:0], now)["session"]
    assert "전일 종가 미확인" in no_baseline["market"] and no_baseline["sectors"] == ""


def test_repeated_home_reads_only_serve_saved_edition(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    monkeypatch.delenv("API_TOKEN", raising=False)
    client = TestClient(app)
    empty = client.get("/market-desk").json()
    assert empty["state"] == empty["session_state"] == "awaiting" and empty["board"] is empty["session"] is None
    stamp = (datetime.now(KST) - timedelta(days=3)).isoformat()
    board = {"version": 1, "checked_at": stamp, "market_at": None, "filings_at": None, "issues": [],
             "briefings": [{"id": "sent", "kind": "am", "body": "이미 발송된 브리핑", "published_at": stamp, "as_of": stamp}]}
    storage.write_json(board, "market_desk", "board.json")
    path = tmp_path / "market_desk" / "board.json"
    before = path.stat().st_mtime_ns
    for _ in range(3):
        saved = client.get("/market-desk").json()
        assert saved["state"] == "stale" and saved["board"]["briefings"][0]["body"] == "이미 발송된 브리핑"
    assert path.stat().st_mtime_ns == before
    assert client.post("/market-desk").status_code == 405
    path.write_text("{}")
    assert client.get("/market-desk").status_code == 503


def test_session_can_publish_first_and_policy_news_is_time_bounded(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    monkeypatch.delenv("API_TOKEN", raising=False)
    client = TestClient(app)
    at = (datetime.now(KST) - timedelta(days=1)).replace(hour=14, minute=0)
    stamp = at.isoformat()
    session = {"observed_at": stamp, "headline": "두 지수 엇갈림", "market": "지수 흐름", "sectors": "", "watch": ""}
    packet = {"version": 1, "trade_date": at.date().isoformat(), "session": session}
    storage.write_json(packet, "market_desk", "input.json")
    saved = client.get("/market-desk").json()
    assert saved["session"]["headline"] == session["headline"] and saved["state"] == "awaiting"
    assert saved["session_state"] == "previous"
    def issue(headline, kind, minutes):
        published = (at - timedelta(minutes=minutes)).isoformat()
        return {"id": headline, "kind": kind, "status": "reported", "headline": headline, "fact": headline,
                "interpretation": "", "watch": "", "published_at": published, "observed_at": None, "observation": "",
                "sources": [{"publisher": "시험 통신사", "title": headline, "published_at": published, "url": "https://example.org/news"}]}
    eligible = issue("한은, 기준금리 인상", "news", 45)
    board = {"version": 1, "checked_at": stamp, "market_at": stamp, "filings_at": None, "briefings": [], "issues": [
        eligible, issue("한은 기준금리 인하 전망", "news", -5), issue("한은 성장률 전망 상향", "news", 15),
        issue("한은 성장률 전망 하향", "news", 24 * 60), issue("기업 단일판매계약 공시", "filing", 50),
    ]}
    storage.write_json(board, "market_desk", "board.json")
    saved = client.get("/market-desk").json()
    assert [x["headline"] for x in saved["policy_coverage"]] == [eligible["headline"]]
    storage.write_json({}, "market_desk", "board.json")
    assert client.get("/market-desk").json()["session"]["headline"] == session["headline"]
    storage.write_json(board, "market_desk", "board.json")
    storage.write_json({**packet, "trade_date": "2000-01-01"}, "market_desk", "input.json")
    degraded = client.get("/market-desk").json()
    assert degraded["session_state"] == "unavailable" and degraded["board"]["issues"]
