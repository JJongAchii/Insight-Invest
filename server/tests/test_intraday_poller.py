"""폴러 오케스트레이션 테스트 — KRX·미러 I/O는 전부 monkeypatch."""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from app import intraday_poller as poller
from datastore import storage
from module import kr_intraday as ki


@pytest.fixture
def app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    return tmp_path


def _snap(chg: float) -> pd.DataFrame:
    df = pd.DataFrame({"시가": [100.0], "고가": [110.0], "저가": [95.0], "종가": [105.0],
                       "거래량": [1000], "거래대금": [5e9], "등락률": [chg],
                       "시가총액": [4e11]}, index=["005930"])
    df.index.name = "티커"
    return df


def _etf_snap(chg: float = -2.03) -> pd.DataFrame:
    df = pd.DataFrame(
        {"시가": [1032], "종가": [1011], "변동폭": [-21], "등락률": [chg],
         "거래량": [688072177], "거래대금": [706209042605]},
        index=["114800"],
    )
    df.index.name = "티커"
    return df


def test_handler_writes_stock_etf_and_timeline_files(app_data, monkeypatch):
    monkeypatch.setattr(poller, "_fetch_krx",
        lambda today: ({"KOSPI": _snap(5.0)}, {"KOSPI": 6300.0}, _etf_snap()))
    monkeypatch.setattr(poller, "_sector_map",
        lambda: pd.DataFrame({"ticker": ["005930"], "sector": ["전기전자"], "name": ["삼성전자"]}))
    monkeypatch.setattr(poller, "_prev_index_closes", lambda trade_date: {"KOSPI": 6000.0})

    out = poller.handler({}, None)
    assert out["status"] == "ok"
    latest = storage.read_parquet("kr_intraday_latest.parquet")
    assert latest.iloc[0]["chg_pct"] == 5.0
    assert latest.iloc[0]["sector"] == "전기전자"
    etfs = storage.read_parquet("kr_intraday_etf_latest.parquet")
    assert etfs.iloc[0]["ticker"] == "114800"
    assert etfs.iloc[0]["close"] == 1011
    assert etfs.iloc[0]["chg_pct"] == pytest.approx(-2.03)
    assert out["etf_status"] == "ok"
    tl = storage.read_parquet("kr_intraday_timeline.parquet")
    assert set(tl["kind"]) == {"index", "breadth", "sector"}

    # 두 번째 폴 → 같은 날 append (지수 행 2개)
    poller.handler({}, None)
    tl2 = storage.read_parquet("kr_intraday_timeline.parquet")
    assert (tl2["kind"] == "index").sum() == 2


def test_handler_holiday_noop(app_data, monkeypatch):
    monkeypatch.setattr(poller, "_fetch_krx", lambda today: ({}, {}, pd.DataFrame()))
    out = poller.handler({}, None)
    assert out["status"] == "holiday-noop"
    assert not storage.exists("kr_intraday_latest.parquet")


def _write_index_mirror(tmp_path, monkeypatch, date_str: str):
    """krx_index_prices.parquet 미러 재현(date: datetime64[ns] — 실레이크 스키마)."""
    lake = tmp_path / "lake"
    (lake / "clean").mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({"date": pd.to_datetime([date_str]), "index_code": ["1001"],
                       "close": [6000.0]})
    df.to_parquet(lake / "clean" / "krx_index_prices.parquet", index=False)
    monkeypatch.setenv("QDATA_LAKE", str(lake))


def test_handler_stale_mirror_omits_index_chg_pct(app_data, tmp_path, monkeypatch):
    """미러 최신 행이 5영업일 낡으면(Finding 2 — 야간 파이프라인 실패 재현)
    핸들러는 성공하되 그 지수의 chg_pct는 NaN으로 빠져야 한다 — 며칠 전 종가
    대비 등락률을 '오늘 것'으로 거짓 서빙하면 안 된다."""
    monkeypatch.setattr(poller, "_fetch_krx",
        lambda today: ({"KOSPI": _snap(5.0)}, {"KOSPI": 6300.0}, _etf_snap()))
    monkeypatch.setattr(poller, "_sector_map",
        lambda: pd.DataFrame({"ticker": ["005930"], "sector": ["전기전자"], "name": ["삼성전자"]}))

    today = datetime.now(ki.KST).strftime("%Y-%m-%d")
    stale_date = str(np.busday_offset(today, -6, roll="backward"))  # 5영업일+ 낡음
    _write_index_mirror(tmp_path, monkeypatch, stale_date)

    out = poller.handler({}, None)
    assert out["status"] == "ok"
    tl = storage.read_parquet("kr_intraday_timeline.parquet")
    idx_row = tl[(tl["kind"] == "index") & (tl["key"] == "KOSPI")].iloc[0]
    assert pd.isna(idx_row["chg_pct"])


def test_handler_fresh_mirror_keeps_index_chg_pct(app_data, tmp_path, monkeypatch):
    """미러 최신 행이 정확히 전영업일 종가면 기존처럼 계산값을 유지해야 한다."""
    monkeypatch.setattr(poller, "_fetch_krx",
        lambda today: ({"KOSPI": _snap(5.0)}, {"KOSPI": 6300.0}, _etf_snap()))
    monkeypatch.setattr(poller, "_sector_map",
        lambda: pd.DataFrame({"ticker": ["005930"], "sector": ["전기전자"], "name": ["삼성전자"]}))

    today = datetime.now(ki.KST).strftime("%Y-%m-%d")
    prev_bday = str(np.busday_offset(today, -1, roll="backward"))
    _write_index_mirror(tmp_path, monkeypatch, prev_bday)

    out = poller.handler({}, None)
    assert out["status"] == "ok"
    tl = storage.read_parquet("kr_intraday_timeline.parquet")
    idx_row = tl[(tl["kind"] == "index") & (tl["key"] == "KOSPI")].iloc[0]
    assert idx_row["chg_pct"] == pytest.approx(5.0)  # (6300/6000-1)*100
