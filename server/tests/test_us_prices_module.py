"""US 가격 순수 계산 — TR 합성·세그먼트 스티칭·연속성 가드 손계산 픽스처."""
import numpy as np
import pandas as pd
import pytest

from module.us_prices import (
    GAP_LIMIT_TDAYS,
    apply_entity_windows,
    compose_total_return,
    continuity_issues,
    continuity_warnings,
    entity_windows,
    stitch_segments,
)


def _px(dates, close, adj_close):
    idx = pd.to_datetime(dates)
    return pd.DataFrame({"close": close, "adj_close": adj_close}, index=idx)


def test_tr_dividend_day():
    """배당락일 r = (adj + div×F)/prev − 1. 무분할이라 F=1."""
    px = _px(["2026-01-05", "2026-01-06", "2026-01-07"], [100.0, 102.0, 100.0], [100.0, 102.0, 100.0])
    div = pd.DataFrame({"ex_date": pd.to_datetime(["2026-01-07"]), "cash_amount": [2.0]})
    out = compose_total_return(px, div)
    assert np.isnan(out["gross_return"].iloc[0])
    assert out["gross_return"].iloc[1] == pytest.approx(0.02)
    assert out["gross_return"].iloc[2] == pytest.approx((100.0 + 2.0) / 102.0 - 1)
    # 앵커: 최신 adj_close(TR) = 원 adj_close 최신값
    assert out["adj_close"].iloc[-1] == pytest.approx(100.0)
    # 역누적: 전일 TR = 최신 / (1+r_최신)
    assert out["adj_close"].iloc[1] == pytest.approx(100.0 / ((100.0 + 2.0) / 102.0))


def test_tr_split_day_dividend_scaled():
    """2:1 분할 이전 배당은 당시 주수 기준 → F(=0.5) 로 현재 기준 환산."""
    px = _px(
        ["2026-01-05", "2026-01-06", "2026-01-07"],
        [100.0, 102.0, 52.0],   # 1/7 에 2:1 분할 (원주가 반토막)
        [50.0, 51.0, 52.0],     # 분할 조정 계열은 연속
    )
    div = pd.DataFrame({"ex_date": pd.to_datetime(["2026-01-06"]), "cash_amount": [1.0]})
    out = compose_total_return(px, div)
    # 1/6: F=51/102=0.5 → div_adj=0.5 → r=(51+0.5)/50−1=3.0%
    assert out["gross_return"].iloc[1] == pytest.approx(0.03)
    # 1/7 분할일 자체는 가짜 점프 없음
    assert out["gross_return"].iloc[2] == pytest.approx(52.0 / 51.0 - 1)


def test_special_dividend_same_day_summed():
    px = _px(["2026-01-05", "2026-01-06"], [100.0, 100.0], [100.0, 100.0])
    div = pd.DataFrame({
        "ex_date": pd.to_datetime(["2026-01-06", "2026-01-06"]),
        "cash_amount": [1.0, 10.0],  # 정규 + 특별
    })
    out = compose_total_return(px, div)
    assert out["gross_return"].iloc[1] == pytest.approx(11.0 / 100.0)


def test_no_dividends_is_price_return():
    px = _px(["2026-01-05", "2026-01-06"], [100.0, 103.0], [100.0, 103.0])
    out = compose_total_return(px, pd.DataFrame({"ex_date": [], "cash_amount": []}))
    assert out["gross_return"].iloc[1] == pytest.approx(0.03)


def _long(ticker, dates, price):
    return pd.DataFrame({
        "date": pd.to_datetime(dates), "ticker": ticker,
        "close": price, "adj_close": price,
    })


def test_stitch_qqq_like_three_segments():
    prices = pd.concat([
        _long("QQQ", ["2004-11-29", "2004-11-30"], [36.0, 36.5]),
        _long("QQQQ", ["2004-12-01", "2011-03-22"], [36.6, 55.4]),
        _long("QQQ", ["2011-03-23", "2011-03-24"], [55.7, 56.7]),
        _long("SPY", ["2004-11-29"], [120.0]),  # 무관 티커는 그대로
    ])
    divs = pd.DataFrame({
        "ticker": ["QQQQ", "SPY"],
        "ex_date": pd.to_datetime(["2005-04-25", "2004-12-17"]),
        "cash_amount": [0.1, 0.5],
    })
    segments = {"QQQ": [("QQQ", None, "2004-11-30"), ("QQQQ", "2004-12-01", "2011-03-22"),
                        ("QQQ", "2011-03-23", None)]}
    p, d = stitch_segments(prices, divs, segments)
    qqq = p[p.ticker == "QQQ"].sort_values("date")
    assert len(qqq) == 6 and "QQQQ" not in set(p.ticker)
    assert not qqq["date"].duplicated().any()
    assert d[d.ticker == "QQQ"]["cash_amount"].tolist() == [0.1]  # QQQQ 배당이 QQQ 로
    assert d[d.ticker == "SPY"]["cash_amount"].tolist() == [0.5]


def test_stitch_overlap_raises():
    prices = pd.concat([
        _long("META", ["2022-06-08", "2022-06-09"], [1.5, 184.0]),
        _long("FB", ["2022-06-08", "2022-06-09"], [183.0, 184.0]),
    ])
    segments = {"META": [("FB", None, "2022-06-08"), ("META", "2022-06-08", None)]}  # 하루 겹침
    with pytest.raises(ValueError, match="겹침"):
        stitch_segments(prices, prices.rename(columns={"date": "ex_date"}), segments)


def test_continuity_gap_flagged():
    idx = list(pd.bdate_range("2026-01-05", periods=5)) + list(pd.bdate_range("2026-03-02", periods=5))
    px = _px(idx, [100.0] * 10, [100.0] * 10)
    issues = continuity_issues(px)
    assert len(issues) == 1 and "공백" in issues[0]


def test_continuity_jump_bands_split_warn_and_exclude():
    """무분할 40% 점프는 경고 밴드(제외 아님), 150% 는 제외 — 개별주 정상 급등 보존."""
    warn_px = _px(
        pd.bdate_range("2026-01-05", periods=3), [100.0, 140.0, 141.0], [100.0, 140.0, 141.0]
    )
    assert continuity_issues(warn_px) == []
    warns = continuity_warnings(warn_px)
    assert len(warns) == 1 and "40%" in warns[0]

    hard_px = _px(
        pd.bdate_range("2026-01-05", periods=3), [100.0, 250.0, 251.0], [100.0, 250.0, 251.0]
    )
    issues = continuity_issues(hard_px)
    assert len(issues) == 1 and "150%" in issues[0]
    assert continuity_warnings(hard_px) == []


def test_continuity_split_day_not_flagged():
    """진짜 분할: adj_close 연속·close 점프·F 변동 → 무경고."""
    px = _px(pd.bdate_range("2026-01-05", periods=3), [100.0, 102.0, 51.5], [50.0, 51.0, 51.5])
    assert continuity_issues(px) == []


def test_continuity_clean_passes():
    px = _px(pd.bdate_range("2026-01-05", periods=30), [100.0] * 30, [100.0] * 30)
    assert continuity_issues(px) == []


def _events(rows):
    return pd.DataFrame(rows, columns=["ticker", "event_type", "event_date", "event_ticker"])


def _details(rows):
    return pd.DataFrame(rows, columns=["ticker", "list_date"])


def test_entity_windows_rename_chain():
    """META 실측 케이스: FB(2012)→META(2022) 체인 → 창 2개, 경계 밖 행은 창에 없음."""
    ev = _events([
        ("META", "ticker_change", "2012-05-18", "FB"),
        ("META", "ticker_change", "2022-06-09", "META"),
    ])
    w = entity_windows(ev, _details([]), finals={"META"}, manual={})
    assert len(w) == 2
    fb = w[w["src"] == "FB"].iloc[0]
    assert fb["final"] == "META" and fb["start"] == pd.Timestamp("2012-05-18")
    assert fb["end"] == pd.Timestamp("2022-06-08")
    meta = w[w["src"] == "META"].iloc[0]
    assert meta["start"] == pd.Timestamp("2022-06-09") and pd.isna(meta["end"])


def test_entity_windows_single_event_falls_back_to_list_date():
    """단일 이벤트(QQQ 2018 리브랜드 실측)는 체인이 아니다 — 상장일 플로어만."""
    ev = _events([("QQQ", "ticker_change", "2018-06-04", "QQQ")])
    dt = _details([("QQQ", pd.Timestamp("1999-03-10"))])
    w = entity_windows(ev, dt, finals={"QQQ"}, manual={})
    assert len(w) == 1
    assert w.iloc[0]["src"] == "QQQ" and w.iloc[0]["start"] == pd.Timestamp("1999-03-10")


def test_entity_windows_manual_takes_precedence():
    ev = _events([("QQQ", "ticker_change", "2018-06-04", "QQQ")])
    dt = _details([("QQQ", pd.Timestamp("1999-03-10"))])
    w = entity_windows(ev, dt, finals={"QQQ"}, manual={"QQQ": []})
    assert w.empty  # 수동 세그먼트 대상은 벤더 창을 만들지 않는다


def test_apply_entity_windows_cuts_alien_and_merges_prior_ticker():
    """META 축소판: 상장 전 남의 회사 행 절단 + FB 행이 META 로 병합."""
    prices = pd.concat([
        _long("META", ["2021-07-01", "2022-06-08"], [1.5, 1.4]),      # Metamaterial (남의 회사)
        _long("FB", ["2022-06-07", "2022-06-08"], [183.0, 184.0]),
        _long("META", ["2022-06-09", "2022-06-10"], [184.5, 185.0]),  # 진짜 META
        _long("SPY", ["2022-06-09"], [400.0]),
    ])
    divs = pd.DataFrame({"ticker": ["FB"], "ex_date": [pd.Timestamp("2022-06-07")],
                         "cash_amount": [0.5]})
    w = pd.DataFrame([
        {"final": "META", "src": "FB", "start": pd.Timestamp("2012-05-18"),
         "end": pd.Timestamp("2022-06-08")},
        {"final": "META", "src": "META", "start": pd.Timestamp("2022-06-09"), "end": None},
    ])
    p, d = apply_entity_windows(prices, divs, w)
    meta = p[p.ticker == "META"].sort_values("date")
    assert len(meta) == 4  # FB 2행 + META 2행 — Metamaterial 2행은 절단
    assert meta["date"].min() == pd.Timestamp("2022-06-07")
    assert "FB" not in set(p.ticker)
    assert len(p[p.ticker == "SPY"]) == 1  # 무관 티커 보존
    assert d[d.ticker == "META"]["cash_amount"].tolist() == [0.5]  # 배당도 병합


def test_apply_entity_windows_overlap_raises():
    prices = _long("AAA", ["2026-01-05"], [10.0])
    w = pd.DataFrame([
        {"final": "AAA", "src": "AAA", "start": pd.Timestamp("2026-01-01"), "end": None},
        {"final": "AAA", "src": "AAA", "start": pd.Timestamp("2026-01-02"), "end": None},
    ])
    with pytest.raises(ValueError, match="겹침"):
        apply_entity_windows(prices, prices.rename(columns={"date": "ex_date"}), w)


def test_apply_entity_windows_none_is_noop():
    prices = _long("AAA", ["2026-01-05"], [10.0])
    divs = pd.DataFrame({"ticker": [], "ex_date": [], "cash_amount": []})
    p, d = apply_entity_windows(prices, divs, None)
    assert p.equals(prices)
