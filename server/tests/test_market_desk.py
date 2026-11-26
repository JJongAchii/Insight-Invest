from datetime import datetime, timedelta

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from datastore import storage
from module.kr_intraday import KST
from module.market_desk import market_input


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


def test_repeated_home_reads_only_serve_saved_edition(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    monkeypatch.delenv("API_TOKEN", raising=False)
    client = TestClient(app)
    assert client.get("/market-desk").json() == {"state": "awaiting", "board": None}
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
