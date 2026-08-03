"""GET /holdings/risk 계약 — 빈 보유 시 empty, 정상 경로의 응답 형태.

무거운 실데이터 경로는 Task 4 통합 검증이 맡고, 여기는 조립 계약만 픽스처로
고정한다 (spotlight API 테스트와 같은 monkeypatch 패턴).
"""

import numpy as np
import pandas as pd
import pytest

import app.routers.holdings as h


def test_risk_empty_holdings(monkeypatch):
    monkeypatch.setattr(
        h.holdings_store, "list_items", lambda: pd.DataFrame(columns=h.holdings_store._EMPTY)
    )
    assert h.get_holdings_risk() == {"empty": True}


@pytest.fixture()
def two_holdings(monkeypatch):
    items = pd.DataFrame(
        {
            "meta_id": [1, 2],
            "shares": [10.0, 20.0],
            "avg_cost": [90.0, 40.0],
            "currency": ["KRW", "KRW"],
        }
    )
    md = pd.DataFrame(
        {
            "meta_id": [1, 2],
            "ticker": ["000001", "000002"],
            "name": ["가나", "다라"],
            "iso_code": ["KR", "KR"],
            "security_type": ["stock", "stock"],
            "sector": ["기타", "기타"],
        }
    )
    monkeypatch.setattr(h.holdings_store, "list_items", lambda: items)
    monkeypatch.setattr(h.meta, "meta_df", lambda: md)
    # 최신가: A 100원 × 10주 = 1000, B 50원 × 20주 = 1000 → 50:50
    monkeypatch.setattr(h, "build_price_map", lambda df: {1: (100.0, 0.0), 2: (50.0, 0.0)})
    monkeypatch.setattr(h, "_usdkrw_latest", lambda: 1400.0)

    idx = pd.bdate_range("2023-01-02", periods=300)
    prices = pd.DataFrame(
        {
            "000001": np.linspace(80, 100, 300),
            "000002": np.linspace(60, 50, 300),
        },
        index=idx,
    )

    class FakeBT:
        def data(self, meta_id=None, start_date=None, **kw):
            return prices

    monkeypatch.setattr(h, "Backtest", FakeBT)
    monkeypatch.setattr(h.fx, "to_krw", lambda df, iso: df)  # KR만 — 환산 무변화
    monkeypatch.setattr(h, "_recent_kr_volume", lambda tickers: pd.DataFrame())
    return items


def test_risk_shape_and_weights(two_holdings):
    r = h.get_holdings_risk()
    assert "empty" not in r and "insufficient" not in r
    assert r["basis"]["n_assets"] == 2
    assert set(s["key"] for s in r["scenarios"]) == {
        "recent_20d",
        "worst_20d",
        "worst_60d",
        "covid_2020",
    }
    covid = next(s for s in r["scenarios"] if s["key"] == "covid_2020")
    assert covid["ret_pct"] is None  # 2023년 시작 이력 — 커버 불가
    assert r["corr"]["tickers"] == ["000001", "000002"]
    assert r["corr"]["names"] == ["가나", "다라"]
    assert isinstance(r["ann_vol"], float)
    # 가격 조회 실패 종목 경고 경로
    assert isinstance(r["warnings"], list)


def test_risk_excludes_priceless_position(two_holdings, monkeypatch):
    monkeypatch.setattr(h, "build_price_map", lambda df: {1: (100.0, 0.0), 2: (None, None)})
    r = h.get_holdings_risk()
    assert r["basis"]["n_assets"] == 1
    assert r["corr"] is None  # 단일 종목 — 상관 생략
    assert any(w["kind"] == "no_price" for w in r["warnings"])


def test_risk_history_load_failure_returns_empty(two_holdings, monkeypatch):
    """Backtest 실패는 500 없이 empty 반환."""

    class FailingBT:
        def data(self, meta_id=None, start_date=None, **kw):
            raise RuntimeError("DB connection failed")

    monkeypatch.setattr(h, "Backtest", FailingBT)
    r = h.get_holdings_risk()
    assert r == {"empty": True, "reason": "가격 이력 로드 실패"}


def test_risk_fx_failure_drops_us_with_warning(monkeypatch):
    """환율 조회 실패 시 US 제외 + no_fx 경고."""
    items = pd.DataFrame(
        {
            "meta_id": [1, 2],
            "shares": [10.0, 5.0],
            "avg_cost": [90.0, 2000.0],
            "currency": ["KRW", "USD"],
        }
    )
    md = pd.DataFrame(
        {
            "meta_id": [1, 2],
            "ticker": ["000001", "AAPL"],
            "name": ["가나", "Apple"],
            "iso_code": ["KR", "US"],
            "security_type": ["stock", "stock"],
            "sector": ["기타", "기타"],
        }
    )
    monkeypatch.setattr(h.holdings_store, "list_items", lambda: items)
    monkeypatch.setattr(h.meta, "meta_df", lambda: md)
    monkeypatch.setattr(h, "build_price_map", lambda df: {1: (100.0, 0.0), 2: (150.0, 0.0)})
    monkeypatch.setattr(h, "_usdkrw_latest", lambda: 1400.0)

    idx = pd.bdate_range("2023-01-02", periods=300)
    prices = pd.DataFrame(
        {
            "000001": np.linspace(80, 100, 300),
            "AAPL": np.linspace(140, 150, 300),
        },
        index=idx,
    )

    class FakeBT:
        def data(self, meta_id=None, start_date=None, **kw):
            return prices

    monkeypatch.setattr(h, "Backtest", FakeBT)

    def failing_to_krw(df, iso_map):
        raise KeyError("USDKRW unavailable")

    monkeypatch.setattr(h.fx, "to_krw", failing_to_krw)
    monkeypatch.setattr(h, "_recent_kr_volume", lambda tickers: pd.DataFrame())

    r = h.get_holdings_risk()
    assert "empty" not in r and "insufficient" not in r
    assert r["basis"]["n_assets"] == 1  # US 제외
    assert r["corr"] is None  # 단일 종목
    assert any(w["kind"] == "no_fx" and w["ticker"] == "AAPL" for w in r["warnings"])


def test_risk_all_kr_skips_fx(two_holdings, monkeypatch):
    """모든 보유가 KR이면 to_krw를 호출하지 않음."""
    call_count = {"to_krw": 0}

    def tracking_to_krw(df, iso_map):
        call_count["to_krw"] += 1
        raise RuntimeError("to_krw should not be called")

    monkeypatch.setattr(h.fx, "to_krw", tracking_to_krw)

    r = h.get_holdings_risk()
    assert "empty" not in r and "insufficient" not in r
    assert r["basis"]["n_assets"] == 2
    assert call_count["to_krw"] == 0  # 호출되지 않음
