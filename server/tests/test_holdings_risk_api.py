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
