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
    # 실제 pykrx처럼 시가/고가/저가/종가/거래량/거래대금/시가총액은 int64,
    # 등락률만 float64 — 이 pandas 버전(2.3.3)의 to_dict("records")는 numpy
    # 스칼라를 native로 박싱해주지만, 그 경계에 기대지 않고 _stock_rows/
    # _my_rows에서 명시 캐스팅한다(향후 pandas 버전·object dtype 경로에서
    # 깨지지 않도록 — holdings.py `_r()` 관례와 동일).
    now = _now_kst()
    as_of = as_of or now.strftime("%Y-%m-%d %H:%M")
    trade_date = trade_date or now.strftime("%Y-%m-%d")
    latest = pd.DataFrame({
        "ticker": ["005930", "035720"], "market": ["KOSPI", "KOSDAQ"],
        "open": [100, 50], "high": [110, 55], "low": [95, 50],
        "close": [105, 50], "volume": [1000, 100], "value": [int(value), int(1e9)],
        "chg_pct": [chg, -1.0], "cap": [int(cap), int(5e10)],
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
    # 숫자 필드가 native 타입으로 캐스팅됐는지 — 안 되면 응답 인코딩 단계에서
    # 예외를 던져 위의 .json() 호출 자체가 실패한다
    assert body["top_value"][0]["close"] == 105
    assert body["top_value"][0]["value"] == pytest.approx(5e9)
    # 급등락 필터: 035720은 cap 미달로 down에 없어야 한다
    assert all(m["ticker"] != "035720" for m in body["top_movers"]["down"])


def test_missing_chg_pct_serializes_as_null_not_nan(app_data):
    """등락률 결측(신규상장 등으로 pykrx가 NaN을 주는 경우)이 top_value에
    흘러가면, stdlib json은 NaN을 리터럴 그대로 찍어(RFC 8259 위반) 브라우저
    JSON.parse가 깨진다 — None으로 강등해야 한다."""
    _write_snapshot()
    latest = storage.read_parquet("kr_intraday_latest.parquet")
    latest.loc[latest["ticker"] == "005930", "chg_pct"] = float("nan")
    storage.write_parquet(latest, "kr_intraday_latest.parquet")

    r = client.get("/intraday/market")
    assert r.status_code == 200
    assert "NaN" not in r.text
    row = next(x for x in r.json()["top_value"] if x["ticker"] == "005930")
    assert row["chg_pct"] is None


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


def test_my_join_failure_degrades_only_my_section(app_data, monkeypatch):
    """watchlist/holdings/meta 조인이 깨져도 나머지(지수·업종·랭킹)는 살아있어야
    한다 — 스펙 D3 섹션 강등. 전체 active:false로 뭉개면 안 된다."""
    _write_snapshot()
    import app.routers.intraday as intraday_mod

    def _boom():
        raise RuntimeError("watchlist read failed")

    monkeypatch.setattr(intraday_mod.watchlist_store, "list_items", _boom)

    body = client.get("/intraday/market").json()
    assert body["active"] is True
    assert body["my"] == {"watchlist": [], "holdings": []}
    # 나머지 섹션은 정상 조립돼야 한다
    assert body["top_value"][0]["ticker"] == "005930"
    assert body["breadth"]["advancers"] == 1
