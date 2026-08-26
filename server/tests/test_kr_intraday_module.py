"""kr_intraday 순수 로직 테스트 — 스펙 2026-08-11 D2·D3."""

from datetime import datetime

import pandas as pd
import pytest

from module import kr_intraday as ki


def _snap_frame(rows: dict) -> pd.DataFrame:
    """pykrx get_market_ohlcv_by_ticker 형태(한글 컬럼, 티커 인덱스) 재현."""
    df = pd.DataFrame.from_dict(rows, orient="index",
        columns=["시가", "고가", "저가", "종가", "거래량", "거래대금", "등락률", "시가총액"])
    df.index.name = "티커"
    return df


@pytest.fixture
def latest():
    frames = {
        "KOSPI": _snap_frame({
            "005930": [100, 110, 95, 105, 1000, 5e9, 5.0, 4e11],
            "000660": [200, 200, 180, 190, 500, 4e9, -5.0, 2e11],
            "999999": [0, 0, 0, 0, 0, 0, 0.0, 1e10],   # 거래정지 → 제외돼야 함
        }),
        "KOSDAQ": _snap_frame({
            "035720": [50, 55, 50, 50, 100, 1e9, 0.0, 5e10],
        }),
    }
    return ki.normalize_snapshot(frames, "2026-08-11 11:35", "2026-08-11")


def test_normalize_snapshot(latest):
    assert len(latest) == 3  # close=0 제외
    assert set(latest.columns) >= {"ticker", "market", "open", "high", "low",
                                   "close", "volume", "value", "chg_pct", "cap",
                                   "as_of", "trade_date"}
    assert latest.set_index("ticker").loc["005930", "chg_pct"] == 5.0
    assert (latest["market"] == "KOSDAQ").sum() == 1


def test_normalize_etf_snapshot_preserves_krx_change_rate():
    frame = pd.DataFrame(
        {"시가": [1032], "종가": [1011], "변동폭": [-21], "등락률": [-2.03],
         "거래량": [688072177], "거래대금": [706209042605]},
        index=["114800"],
    )
    frame.index.name = "티커"

    out = ki.normalize_etf_snapshot(frame, "2026-08-26 14:05", "2026-08-26")

    assert out.to_dict("records") == [{
        "ticker": "114800", "close": 1011, "volume": 688072177,
        "value": 706209042605, "chg_pct": -2.03,
        "as_of": "2026-08-26 14:05", "trade_date": "2026-08-26",
    }]


def test_normalize_etf_snapshot_rejects_silent_schema_drop():
    with pytest.raises(ValueError, match="ETF 장중 필수 열 누락"):
        ki.normalize_etf_snapshot(
            pd.DataFrame({"종가": [1011]}, index=["114800"]),
            "2026-08-26 14:05",
            "2026-08-26",
        )


def test_with_sector_fills_unknown(latest):
    smap = pd.DataFrame({"ticker": ["005930"], "sector": ["전기전자"], "name": ["삼성전자"]})
    d = ki.with_sector(latest, smap)
    assert d.set_index("ticker").loc["005930", "sector"] == "전기전자"
    assert d.set_index("ticker").loc["000660", "sector"] == "기타"
    assert d.set_index("ticker").loc["000660", "name"] == ""


def test_index_rows_chg_vs_prev_close():
    rows = ki.index_rows({"KOSPI": 6300.0}, {"KOSPI": 6000.0}, "2026-08-11 11:35", "2026-08-11")
    assert rows.iloc[0]["kind"] == "index"
    assert rows.iloc[0]["chg_pct"] == pytest.approx(5.0)


def test_breadth_counts(latest):
    row = ki.breadth_row(latest, "2026-08-11 11:35", "2026-08-11").iloc[0]
    assert (row["advancers"], row["decliners"], row["unchanged"]) == (1, 1, 1)


def test_sector_rows_cap_weighted(latest):
    smap = pd.DataFrame({"ticker": ["005930", "000660"],
                         "sector": ["전기전자", "전기전자"], "name": ["삼성전자", "하이닉스"]})
    d = ki.with_sector(latest, smap)
    rows = ki.sector_rows(d, "2026-08-11 11:35", "2026-08-11").set_index("key")
    # 시총가중: (4e11*5 + 2e11*-5) / 6e11 = +1.667
    assert rows.loc["전기전자", "chg_pct"] == pytest.approx(10 / 6, rel=1e-3)
    assert rows.loc["전기전자", "value_krw"] == pytest.approx(9e9)
    assert rows.loc["기타", "n"] == 1


def test_sector_rows_skips_nan_chg(latest):
    """np.average는 NaN을 skip하지 않고 전파한다 — 종목 하나만 결측이어도
    섹터 전체가 NaN이 되면 서빙에서 500으로 번진다(Finding 1). 결측 종목은
    가중평균에서 빼고, n·value_krw는 전체 그룹 기준을 유지해야 한다."""
    smap = pd.DataFrame({"ticker": ["005930", "000660"],
                         "sector": ["전기전자", "전기전자"], "name": ["삼성전자", "하이닉스"]})
    d = ki.with_sector(latest, smap)
    d.loc[d["ticker"] == "005930", "chg_pct"] = float("nan")
    rows = ki.sector_rows(d, "2026-08-11 11:35", "2026-08-11").set_index("key")
    # 005930(NaN) 제외 → 000660(-5.0)만 반영
    assert rows.loc["전기전자", "chg_pct"] == pytest.approx(-5.0)
    assert rows.loc["전기전자", "n"] == 2                       # n은 전체 그룹 기준
    assert rows.loc["전기전자", "value_krw"] == pytest.approx(9e9)  # value_krw도 전체 그룹 기준


def test_sector_rows_all_nan_group_emits_nan(latest):
    """그룹 전체가 NaN이면(dropna 후 빈 그룹) chg_pct는 NaN — 0으로 위장하지 않는다."""
    smap = pd.DataFrame({"ticker": ["005930"], "sector": ["전기전자"], "name": ["삼성전자"]})
    d = ki.with_sector(latest, smap)
    d.loc[d["ticker"] == "005930", "chg_pct"] = float("nan")
    rows = ki.sector_rows(d, "2026-08-11 11:35", "2026-08-11").set_index("key")
    assert pd.isna(rows.loc["전기전자", "chg_pct"])
    assert rows.loc["전기전자", "n"] == 1


def test_merge_timeline_resets_on_new_day():
    old = pd.DataFrame({"as_of": ["2026-08-10 15:35"], "trade_date": ["2026-08-10"],
                        "kind": ["breadth"], "key": ["ALL"]})
    new = pd.DataFrame({"as_of": ["2026-08-11 09:35"], "trade_date": ["2026-08-11"],
                        "kind": ["breadth"], "key": ["ALL"]})
    assert len(ki.merge_timeline(old, new)) == 1          # 리셋
    merged = ki.merge_timeline(new, new.assign(as_of="2026-08-11 10:05"))
    assert len(merged) == 2                               # 같은 날 append
    assert len(ki.merge_timeline(None, new)) == 1


def test_is_open_kst():
    assert ki.is_open_kst(datetime(2026, 8, 11, 11, 0, tzinfo=ki.KST))       # 화 11시
    assert not ki.is_open_kst(datetime(2026, 8, 11, 16, 0, tzinfo=ki.KST))   # 마감 후
    assert not ki.is_open_kst(datetime(2026, 8, 15, 11, 0, tzinfo=ki.KST))   # 토


def test_snapshot_active():
    open_now = datetime(2026, 8, 11, 11, 0, tzinfo=ki.KST)
    assert ki.snapshot_active("2026-08-11", "2026-08-11 10:40", open_now)  # 경계값 20분은 유효
    assert not ki.snapshot_active("2026-08-11", "2026-08-11 10:39", open_now)  # 21분 스테일
    evening = datetime(2026, 8, 11, 20, 0, tzinfo=ki.KST)
    assert ki.snapshot_active("2026-08-11", "2026-08-11 15:35", evening)       # 마감 현황 유지
    monday = datetime(2026, 8, 10, 8, 0, tzinfo=ki.KST)
    assert ki.snapshot_active("2026-08-07", "2026-08-07 15:35", monday)        # 월 아침, 금 스냅샷
    tuesday_pre = datetime(2026, 8, 11, 8, 0, tzinfo=ki.KST)
    assert not ki.snapshot_active("2026-08-07", "2026-08-07 15:35", tuesday_pre)  # 2영업일 낡음


def test_top_movers_filters_illiquid(latest):
    # 035720: cap 5e10 < 1e11 → 급등락 제외 대상
    up, down = ki.top_movers(latest)
    assert "035720" not in set(up["ticker"]) | set(down["ticker"])
    assert up.iloc[0]["ticker"] == "005930"
    assert down.iloc[0]["ticker"] == "000660"
    assert ki.top_value(latest).iloc[0]["ticker"] == "005930"
