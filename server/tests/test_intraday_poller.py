"""폴러 오케스트레이션 테스트 — KRX·미러 I/O는 전부 monkeypatch."""

import pandas as pd
import pytest

from app import intraday_poller as poller
from datastore import storage


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


def test_handler_writes_both_files(app_data, monkeypatch):
    monkeypatch.setattr(poller, "_fetch_krx",
        lambda today: ({"KOSPI": _snap(5.0)}, {"KOSPI": 6300.0}))
    monkeypatch.setattr(poller, "_sector_map",
        lambda: pd.DataFrame({"ticker": ["005930"], "sector": ["전기전자"], "name": ["삼성전자"]}))
    monkeypatch.setattr(poller, "_prev_index_closes", lambda: {"KOSPI": 6000.0})

    out = poller.handler({}, None)
    assert out["status"] == "ok"
    latest = storage.read_parquet("kr_intraday_latest.parquet")
    assert latest.iloc[0]["chg_pct"] == 5.0
    assert latest.iloc[0]["sector"] == "전기전자"
    tl = storage.read_parquet("kr_intraday_timeline.parquet")
    assert set(tl["kind"]) == {"index", "breadth", "sector"}

    # 두 번째 폴 → 같은 날 append (지수 행 2개)
    poller.handler({}, None)
    tl2 = storage.read_parquet("kr_intraday_timeline.parquet")
    assert (tl2["kind"] == "index").sum() == 2


def test_handler_holiday_noop(app_data, monkeypatch):
    monkeypatch.setattr(poller, "_fetch_krx", lambda today: ({}, {}))
    out = poller.handler({}, None)
    assert out["status"] == "holiday-noop"
    assert not storage.exists("kr_intraday_latest.parquet")
