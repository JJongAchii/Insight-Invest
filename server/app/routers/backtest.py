import logging
import os
import sys
from typing import List

import pandas as pd
from fastapi import APIRouter, HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))
import datastore
from app import schemas
from datastore import portfolio
from module.backtest import Backtest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtest", tags=["Backtest"])

METRIC_COLS = ["ann_ret", "ann_vol", "sharpe", "mdd", "skew", "kurt", "var", "cvar"]

# Lambda는 요청마다 다른 컨테이너일 수 있어 인메모리 결과 공유 불가 —
# 백테스트 결과를 S3(tmp_results/{token}/)에 보관하고 저장 시 토큰으로 리로드한다.
TMP_DIR = "tmp_results"


def _persist_result(token: str, weights: pd.DataFrame, nav: pd.Series, metrics: pd.DataFrame):
    from datastore import storage

    storage.write_parquet(weights.reset_index(names="__idx"), TMP_DIR, token, "weights.parquet")
    nav_df = nav.rename("value").rename_axis("__idx").reset_index()
    storage.write_parquet(nav_df, TMP_DIR, token, "nav.parquet")
    storage.write_parquet(metrics, TMP_DIR, token, "metrics.parquet")


def _load_result(token: str):
    from datastore import storage

    try:
        weights = storage.read_parquet(TMP_DIR, token, "weights.parquet").set_index("__idx")
        nav = storage.read_parquet(TMP_DIR, token, "nav.parquet").set_index("__idx")["value"]
        metrics = storage.read_parquet(TMP_DIR, token, "metrics.parquet")
        return weights, nav, metrics
    except FileNotFoundError:
        return None


@router.get("/algorithm", response_model=List[schemas.Strategy])
async def get_algorithm():
    return datastore.strategy_df().to_dict(orient="records")


@router.get("/strategy", response_model=List[schemas.Portfolio])
async def get_strategy():
    return portfolio.port_summary().to_dict(orient="records")


@router.get("/strategy/monthlynav", response_model=List[schemas.PortNav])
async def get_all_monthly_nav():
    return portfolio.monthly_nav().to_dict(orient="records")


@router.get("/strategy/{port_id}")
async def get_strategy_id_info(port_id: int):
    """포트폴리오 정보 + 성과지표 (parquet 스토어)"""
    portfolio_info = portfolio.port_id_info(port_id=port_id)
    if portfolio_info.empty:
        return []

    metrics_df = portfolio.metrics(port_id=port_id)
    for col in METRIC_COLS:
        portfolio_info[col] = metrics_df[col].values[0] if not metrics_df.empty else None

    return portfolio_info.to_dict(orient="records")


@router.get("/strategy/nav/{port_id}")
async def get_strategy_id_nav(port_id: int):
    try:
        return portfolio.nav(port_id=port_id).to_dict(orient="records")
    except Exception as e:
        logger.error(f"NAV 조회 실패: port_id={port_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"NAV 데이터 조회 실패: {str(e)}")


@router.get("/strategy/rebal/{port_id}")
async def get_strategy_id_rebal(port_id: int):
    try:
        return portfolio.rebalance(port_id=port_id).to_dict(orient="records")
    except Exception as e:
        logger.error(f"Rebalance 조회 실패: port_id={port_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"리밸런싱 데이터 조회 실패: {str(e)}")


@router.get("/strategy/bm/{port_id}")
async def set_benchmark(port_id: int):
    """벤치마크 조회 — 저장된 데이터 우선, 없으면 실시간 계산"""
    bm_nav_df = portfolio.benchmark_nav(port_id=port_id)
    bm_metrics_df = portfolio.benchmark_metrics(port_id=port_id)

    if not bm_nav_df.empty and not bm_metrics_df.empty:
        bm_nav_df = bm_nav_df.copy()
        bm_nav_df["bm_name"] = "BM(SPY)"
        nav_stack = bm_nav_df[["trade_date", "bm_name", "value"]]

        bm_metrics_df = bm_metrics_df.copy()
        bm_metrics_df["strategy"] = "BM(SPY)"
        bm_metrics_df = bm_metrics_df.rename(columns={"ann_ret": "ann_returns"})

        logger.info(f"Benchmark 조회 완료 (저장본): port_id={port_id}")
        return {
            "nav": nav_stack.to_json(orient="records"),
            "metrics": bm_metrics_df[
                ["strategy", "ann_returns", "ann_vol", "sharpe", "mdd"]
            ].to_json(orient="records"),
        }

    # 저장된 벤치마크가 없으면 실시간 계산
    period = portfolio.port_start_end_date(port_id=port_id)
    if period.empty:
        raise HTTPException(status_code=404, detail="Portfolio NAV data not found")

    start = pd.Timestamp(period.start_date.values[0]).date()
    end = pd.Timestamp(period.end_date.values[0]).date()

    bt = Backtest(strategy_name="BM(SPY)")
    price = bt.data(tickers="SPY", start_date=start, end_date=end)

    weight = pd.DataFrame({"SPY": 1}, index=period.start_date)
    weights, nav, metrics = bt.result(price=price, weight=weight, end=end)
    nav_stack = nav.stack().reset_index()
    nav_stack.columns = ["trade_date", "bm_name", "value"]

    logger.info(f"Benchmark 계산 완료 (실시간): port_id={port_id}")
    return {
        "nav": nav_stack.to_json(orient="records"),
        "metrics": metrics.to_json(orient="records"),
    }


@router.post("")
async def run_backtest(request: schemas.BacktestRequest):
    import uuid

    strategy_name = request.strategy_name
    bt = Backtest(strategy_name=strategy_name)
    price = bt.data(meta_id=request.meta_id)
    weight = bt.rebalance(
        price=price, method=request.algorithm, start=request.startDate, end=request.endDate
    )
    weights, nav, metrics = bt.result(price=price, weight=weight)

    token = uuid.uuid4().hex
    _persist_result(
        token,
        weights=weights.get(strategy_name),
        nav=nav[strategy_name],
        metrics=metrics,
    )

    return {
        "result_token": token,
        "weights": weights.get(strategy_name).to_json(orient="split"),
        "nav": nav.to_json(orient="split"),
        "metrics": metrics.to_json(orient="records"),
    }


@router.post("/savestrategy")
async def save_strategy(request: schemas.SaveStrategyRequest):
    strategy_name = request.strategy_name
    result = _load_result(request.result_token)
    if result is None:
        raise HTTPException(status_code=404, detail="Backtest result not found or expired.")

    weights, nav, metrics = result

    if portfolio.exists_name(strategy_name):
        raise HTTPException(status_code=400, detail="Portfolio name already exists.")

    port_id = None
    try:
        port_id = portfolio.create(
            port_name=strategy_name, algorithm=request.algorithm, meta_ids=request.meta_id
        )
        portfolio.save_rebalance(port_id=port_id, weights=weights)
        portfolio.save_nav(port_id=port_id, nav_series=nav)

        own = metrics[metrics.strategy == strategy_name]
        own = own.set_axis(["strategy", *METRIC_COLS], axis=1)
        portfolio.save_metrics(port_id=port_id, values=own.iloc[0][METRIC_COLS].to_dict())

        # 벤치마크 미리 계산 (조회 성능)
        start_date = nav.index.min().date()
        end_date = nav.index.max().date()
        bt_bm = Backtest(strategy_name="BM(SPY)")
        bm_price = bt_bm.data(tickers="SPY", start_date=start_date, end_date=end_date)

        if not bm_price.empty:
            bm_weight = pd.DataFrame({"SPY": 1}, index=[nav.index.min()])
            _, bm_nav_dict, bm_metrics = bt_bm.result(
                price=bm_price, weight=bm_weight, end=end_date
            )
            bm_nav = bm_nav_dict.get("BM(SPY)")
            if bm_nav is not None and not bm_nav.dropna().empty:
                portfolio.save_benchmark_nav(port_id=port_id, nav_series=bm_nav.dropna())
                bm_row = bm_metrics[bm_metrics["strategy"] == "BM(SPY)"]
                if not bm_row.empty:
                    bm_row = bm_row.set_axis(["strategy", *METRIC_COLS], axis=1)
                    portfolio.save_benchmark_metrics(
                        port_id=port_id, values=bm_row.iloc[0][METRIC_COLS].to_dict()
                    )
                logger.info(f"Benchmark saved for port_id={port_id}")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Strategy save failed, rolling back: {e}")
        if port_id is not None:
            try:
                portfolio.delete(port_id)
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")
        raise HTTPException(status_code=500, detail=f"Failed to save strategy: {str(e)}")

    return {"message": "Strategy saved successfully"}


@router.post("/clearstrategy")
async def clear_strategy():
    Backtest().clear_backtest_result()
    return {"message": "Clear strategies"}
