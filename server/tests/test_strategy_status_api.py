"""status 토글·신호 리더 계약 — 구 행 후방호환(saved)과 404/422를 못박는다."""

import asyncio

import pandas as pd
import pytest
from fastapi import HTTPException


def _seed_ports(tmp_path, monkeypatch, with_status=False):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    d = tmp_path / "portfolio"
    d.mkdir(exist_ok=True)
    cols = {
        "port_id": [1],
        "port_name": ["막포"],
        "strategy_id": [1],
        "created_at": [pd.Timestamp("2026-07-01")],
        "config": [None],
    }
    if with_status:
        cols["status"] = ["active"]
    pd.DataFrame(cols).to_parquet(d / "portfolio.parquet", index=False)


def test_records_backfills_saved(tmp_path, monkeypatch):
    _seed_ports(tmp_path, monkeypatch)
    from datastore import portfolio

    df = portfolio.records()
    assert list(df["status"]) == ["saved"]


def test_set_status_and_read_back(tmp_path, monkeypatch):
    _seed_ports(tmp_path, monkeypatch)
    from datastore import portfolio

    portfolio.set_status(1, "active")
    assert list(portfolio.records()["status"]) == ["active"]
    with pytest.raises(KeyError):
        portfolio.set_status(999, "active")


def test_status_endpoint_contract(tmp_path, monkeypatch):
    _seed_ports(tmp_path, monkeypatch)
    import app.routers.backtest as bt
    from app import schemas

    r = asyncio.run(bt.post_strategy_status(1, schemas.StrategyStatusRequest(status="active")))
    assert r == {"port_id": 1, "status": "active"}
    with pytest.raises(HTTPException) as e404:
        asyncio.run(bt.post_strategy_status(999, schemas.StrategyStatusRequest(status="active")))
    assert e404.value.status_code == 404
    with pytest.raises(HTTPException) as e422:
        asyncio.run(bt.post_strategy_status(1, schemas.StrategyStatusRequest(status="hot")))
    assert e422.value.status_code == 422


def test_rebal_signals_absent_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    import app.routers.backtest as bt

    assert asyncio.run(bt.get_rebal_signals()) == {"as_of": None, "signals": []}


def test_rebal_signals_nonempty_contract(tmp_path, monkeypatch):
    """리밸 신호 응답 — groupby, rank 정렬(None 후순), is_stale, itertuples name 충돌."""
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    d = tmp_path / "portfolio"
    d.mkdir(exist_ok=True)

    pd.DataFrame(
        {
            "port_id": [7, 7, 7],
            "port_name": ["막포"] * 3,
            "freq": ["M"] * 3,
            "as_of": ["2026-08-01"] * 3,
            "next_rebal": ["2026-09-01"] * 3,
            "ticker": ["AAA", "BBB", "CCC"],
            "name": ["에이", "비", "씨"],
            "target_weight": [0.6, 0.4, 0.0],
            "prev_weight": [0.0, 0.5, 0.5],
            "action": ["enter", "keep", "exit"],
            "rank": [1.0, 2.0, None],
        }
    ).to_parquet(d / "rebal_signals.parquet", index=False)

    from datetime import date as _date

    import app.routers.backtest as bt

    result = asyncio.run(bt.get_rebal_signals())

    assert result["as_of"] == "2026-08-01"
    assert len(result["signals"]) == 1

    sig = result["signals"][0]
    assert sig["port_id"] == 7
    assert sig["port_name"] == "막포"
    assert sig["freq"] == "M"
    assert sig["next_rebal"] == "2026-09-01"

    # is_stale은 오늘 날짜 기준이므로 동적으로 계산
    expected_stale = _date.today().isoformat() > "2026-09-01"
    assert sig["is_stale"] == expected_stale

    # items는 rank 순으로 정렬 (None이 마지막)
    items = sig["items"]
    assert len(items) == 3

    # rank 1.0: AAA, enter, target_weight 0.6
    assert items[0]["ticker"] == "AAA"
    assert items[0]["name"] == "에이"
    assert items[0]["target_weight"] == 0.6
    assert items[0]["action"] == "enter"
    assert items[0]["rank"] == 1

    # rank 2.0: BBB, keep, target_weight 0.4
    assert items[1]["ticker"] == "BBB"
    assert items[1]["name"] == "비"
    assert items[1]["target_weight"] == 0.4
    assert items[1]["action"] == "keep"
    assert items[1]["rank"] == 2

    # rank None: CCC, exit, target_weight 0.0
    assert items[2]["ticker"] == "CCC"
    assert items[2]["name"] == "씨"
    assert items[2]["target_weight"] == 0.0
    assert items[2]["action"] == "exit"
    assert items[2]["rank"] is None


def test_portfolio_schema_preserves_status():
    """Portfolio 스키마가 status 필드를 보존한다."""
    from app import schemas

    # status 명시 → "active" 유지
    row = {
        "port_id": 1,
        "port_name": "포트폴리오1",
        "strategy_name": "전략A",
        "ann_ret": 0.10,
        "ann_vol": 0.05,
        "sharpe": 2.0,
        "status": "active",
    }
    p = schemas.Portfolio(**row)
    assert p.status == "active"

    # status 미명시 → "saved" 기본값
    row_no_status = {
        "port_id": 1,
        "port_name": "포트폴리오1",
        "strategy_name": "전략A",
        "ann_ret": 0.10,
        "ann_vol": 0.05,
        "sharpe": 2.0,
    }
    p2 = schemas.Portfolio(**row_no_status)
    assert p2.status == "saved"
