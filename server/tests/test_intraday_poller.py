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


def _daily(*rows) -> pd.DataFrame:
    """pykrx 지수 일자별 시세 모양: 날짜 인덱스와 종가."""
    return pd.DataFrame({"종가": [close for _, close in rows]}, index=pd.to_datetime([day for day, _ in rows]))


def test_previous_close_is_the_last_krx_session_even_after_a_weekday_holiday(monkeypatch):
    """추석 연휴(9/24~9/28) 다음 날: 평일 달력의 '전영업일'(9/28)이 아니라 KRX의 직전 거래일(9/23) 종가다."""
    asked = []

    def daily(start, end, code):
        asked.append((start, end, code))
        return _daily(("2026-09-22", 3900.0), ("2026-09-23", 3950.0), ("2026-09-29", 4010.0))

    monkeypatch.setattr(poller, "_index_daily", daily)
    assert poller._prev_index_closes("2026-09-29") == {"KOSPI": 3950.0, "KOSDAQ": 3950.0}
    assert asked[0] == ("20260909", "20260929", "1001")


def test_without_a_krx_previous_session_the_index_change_is_left_out(monkeypatch):
    calls = iter([_daily(("2026-09-29", 4010.0)), RuntimeError("KRX 응답 없음")])

    def daily(start, end, code):
        answer = next(calls)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(poller, "_index_daily", daily)
    assert poller._prev_index_closes("2026-09-29") == {}


def test_handler_keeps_index_chg_pct_against_the_krx_previous_close(app_data, monkeypatch):
    monkeypatch.setattr(poller, "_fetch_krx",
        lambda today: ({"KOSPI": _snap(5.0)}, {"KOSPI": 6300.0}, _etf_snap()))
    monkeypatch.setattr(poller, "_sector_map",
        lambda: pd.DataFrame({"ticker": ["005930"], "sector": ["전기전자"], "name": ["삼성전자"]}))
    monkeypatch.setattr(poller, "_index_daily", lambda start, end, code: _daily(("2026-09-23", 6000.0)))

    out = poller.handler({}, None)
    assert out["status"] == "ok"
    tl = storage.read_parquet("kr_intraday_timeline.parquet")
    idx_row = tl[(tl["kind"] == "index") & (tl["key"] == "KOSPI")].iloc[0]
    assert idx_row["chg_pct"] == pytest.approx(5.0)  # (6300/6000-1)*100


def test_handler_leaves_index_chg_pct_out_when_the_previous_close_is_unknown(app_data, monkeypatch):
    """직전 종가를 못 받으면 등락률을 지어내지 않는다 — null로 강등."""
    monkeypatch.setattr(poller, "_fetch_krx",
        lambda today: ({"KOSPI": _snap(5.0)}, {"KOSPI": 6300.0}, _etf_snap()))
    monkeypatch.setattr(poller, "_sector_map",
        lambda: pd.DataFrame({"ticker": ["005930"], "sector": ["전기전자"], "name": ["삼성전자"]}))

    def down(start, end, code):
        raise RuntimeError("KRX 응답 없음")

    monkeypatch.setattr(poller, "_index_daily", down)
    out = poller.handler({}, None)
    assert out["status"] == "ok"
    tl = storage.read_parquet("kr_intraday_timeline.parquet")
    idx_row = tl[(tl["kind"] == "index") & (tl["key"] == "KOSPI")].iloc[0]
    assert pd.isna(idx_row["chg_pct"])


# ---- 시장 지도 (스펙 2026-11-27 §5): 폴마다 지도·시계열·데스크 입력, 기준선은 야간 배치가 만든다


def _robot_snap() -> dict:
    rows = {"005930": (1.4, 3e11, 7e11), "277810": (12.2, 6e12, 1.2e11), "053800": (7.4, 9e11, 1.7e11),
            "999990": (29.9, 9e12, 9e11)}
    frame = pd.DataFrame({"시가": 100.0, "고가": 110.0, "저가": 95.0, "종가": 105.0, "거래량": 1000,
                          "거래대금": [v for _, _, v in rows.values()], "등락률": [c for c, _, _ in rows.values()],
                          "시가총액": [cap for _, cap, _ in rows.values()]}, index=list(rows))
    frame.index.name = "티커"
    return {"KOSDAQ": frame}


def _arrange_map(monkeypatch, baseline_as_of="2026-11-26"):
    monkeypatch.setattr(poller, "_fetch_krx", lambda today: (_robot_snap(), {"KOSDAQ": 692.99}, pd.DataFrame()))
    monkeypatch.setattr(poller, "_sector_map", lambda: pd.DataFrame({
        "ticker": ["005930", "277810", "053800", "999990"], "sector": ["전기·전자", "기계·장비", "IT 서비스", "금융"],
        "name": ["삼성전자", "레인보우로보틱스", "안랩", "테스트제9호스팩"]}))
    monkeypatch.setattr(poller, "_prev_index_closes", lambda trade_date: {"KOSDAQ": 655.68})
    if baseline_as_of:
        storage.write_parquet(pd.DataFrame({"ticker": ["053800"], "avg_value": [3e10],
                                            "as_of": pd.Timestamp(baseline_as_of)}), "insight", "kr_value_baseline.parquet")


class _Clock(datetime):
    now_value = datetime(2026, 11, 27, 11, 5, tzinfo=ki.KST)

    @classmethod
    def now(cls, tz=None):
        return cls.now_value


def test_poll_publishes_the_market_map_its_day_series_and_the_desk_input(app_data, monkeypatch):
    _arrange_map(monkeypatch)
    monkeypatch.setattr(poller, "datetime", _Clock)
    out = poller.handler({}, None)
    assert out["map_status"] == "ok"
    saved = storage.read_json("kr_intraday_map.json")
    assert saved["trade_date"] == "2026-11-27" and len(saved["series"]) == 1
    latest = saved["latest"]
    assert latest["markets"]["KOSDAQ"]["contributors"]["up"][0]["name"] == "레인보우로보틱스"
    assert [s["name"] for s in latest["value_spikes"]] == ["안랩"]
    assert "테스트제9호스팩" not in json_text(latest)
    desk = storage.read_json("market_desk", "input.json")
    assert desk["map"]["observed_at"] == latest["observed_at"] and "series" not in desk["map"]
    assert desk["events"] == [{"id": "2026-11-27/cross/KOSDAQ/up", "index": "KOSDAQ", "direction": "up",
                               "threshold": 3.0, "observed_at": "2026-11-27 11:05", "chg_pct": 5.69}]
    _Clock.now_value = datetime(2026, 11, 27, 11, 15, tzinfo=ki.KST)
    poller.handler({}, None)
    assert len(storage.read_json("kr_intraday_map.json")["series"]) == 2
    _Clock.now_value = datetime(2026, 11, 30, 9, 5, tzinfo=ki.KST)
    poller.handler({}, None)
    restarted = storage.read_json("kr_intraday_map.json")
    assert restarted["trade_date"] == "2026-11-30" and len(restarted["series"]) == 1
    _Clock.now_value = datetime(2026, 11, 27, 11, 5, tzinfo=ki.KST)


def test_stale_or_missing_baseline_only_empties_the_spikes(app_data, monkeypatch):
    _arrange_map(monkeypatch, baseline_as_of="2026-11-13")
    monkeypatch.setattr(poller, "datetime", _Clock)
    poller.handler({}, None)
    latest = storage.read_json("kr_intraday_map.json")["latest"]
    assert (latest["value_spikes"], latest["value_spikes_state"]) == ([], "unavailable")
    assert latest["markets"]["KOSDAQ"]["breadth"]["up"] == 4


def test_a_baseline_from_before_a_long_holiday_is_still_used(app_data):
    """10월 개천절~한글날 연휴처럼 평일 닷새 넘게 쉰 뒤에도 하루 묵은 기준선은 쓴다. 열흘을 넘기면 버린다."""
    storage.write_parquet(pd.DataFrame({"ticker": ["053800"], "avg_value": [3e10], "as_of": pd.Timestamp("2026-10-02")}),
                          "insight", "kr_value_baseline.parquet")
    assert poller._value_baseline("2026-10-12")["ticker"].tolist() == ["053800"]
    assert poller._value_baseline("2026-10-13") is None


def test_a_failing_map_never_stops_the_snapshot(app_data, monkeypatch):
    _arrange_map(monkeypatch)
    monkeypatch.setattr(poller, "datetime", _Clock)
    monkeypatch.setattr(poller.market_map, "build_map", lambda *a, **k: (_ for _ in ()).throw(ValueError("boom")))
    out = poller.handler({}, None)
    assert out["status"] == "ok" and out["map_status"] == "degraded"
    assert storage.exists("kr_intraday_latest.parquet")


def json_text(value) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)
