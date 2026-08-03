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
