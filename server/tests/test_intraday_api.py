"""GET /intraday/market 테스트 — 조립·강등·필터."""

from datetime import datetime, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from datastore import storage
from module import kr_intraday as ki

client = TestClient(app)


@pytest.fixture
def app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    monkeypatch.delenv("API_TOKEN", raising=False)
    return tmp_path


def _now_kst():
    return datetime.now(ki.KST)


def _write_snapshot(chg=4.0, cap=4e11, value=5e9, as_of=None, trade_date=None):
    now = _now_kst()
    as_of = as_of or now.strftime("%Y-%m-%d %H:%M")
    trade_date = trade_date or now.strftime("%Y-%m-%d")
    latest = pd.DataFrame({
        "ticker": ["005930", "035720"], "market": ["KOSPI", "KOSDAQ"],
        "open": [100.0, 50.0], "high": [110.0, 55.0], "low": [95.0, 50.0],
        "close": [105.0, 50.0], "volume": [1000, 100], "value": [value, 1e9],
        "chg_pct": [chg, -1.0], "cap": [cap, 5e10],
        "as_of": as_of, "trade_date": trade_date,
        "sector": ["전기전자", "게임"], "name": ["삼성전자", "카카오게임즈"],
    })
    storage.write_parquet(latest, "kr_intraday_latest.parquet")
    tl = pd.concat([
        ki.index_rows({"KOSPI": 6300.0, "KOSDAQ": 850.0},
                      {"KOSPI": 6000.0, "KOSDAQ": 860.0}, as_of, trade_date),
        ki.breadth_row(latest, as_of, trade_date),
        ki.sector_rows(latest, as_of, trade_date),
    ], ignore_index=True)
    storage.write_parquet(tl, "kr_intraday_timeline.parquet")


def test_missing_files_inactive(app_data):
    r = client.get("/intraday/market")
    assert r.status_code == 200
    assert r.json() == {"active": False}


def test_assembled_response(app_data):
    _write_snapshot()
    body = client.get("/intraday/market").json()
    assert body["active"] is True
    kospi = next(i for i in body["indices"] if i["key"] == "KOSPI")
    assert kospi["chg_pct"] == pytest.approx(5.0)
    assert len(kospi["sparkline"]) == 1
    assert body["breadth"]["advancers"] == 1
    names = [s["name"] for s in body["sectors"]]
    assert "전기전자" in names and body["sectors"][0]["flow"]
    assert body["top_value"][0]["ticker"] == "005930"
    # 급등락 필터: 035720은 cap 미달로 down에 없어야 한다
    assert all(m["ticker"] != "035720" for m in body["top_movers"]["down"])


def test_stale_snapshot_inactive(app_data):
    old = _now_kst() - timedelta(days=7)
    _write_snapshot(as_of=old.strftime("%Y-%m-%d %H:%M"),
                    trade_date=old.strftime("%Y-%m-%d"))
    assert client.get("/intraday/market").json() == {"active": False}


def test_corrupt_file_returns_inactive_not_500(app_data, tmp_path):
    (tmp_path / "kr_intraday_latest.parquet").write_text("not parquet")
    (tmp_path / "kr_intraday_timeline.parquet").write_text("not parquet")
    r = client.get("/intraday/market")
    assert r.status_code == 200
    assert r.json() == {"active": False}
