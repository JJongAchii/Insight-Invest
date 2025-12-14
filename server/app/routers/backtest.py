import logging
import os
import sys
from typing import List

import pandas as pd
from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))
import db
from app import schemas
from module.backtest import Backtest
from module.data_lake.portfolio_reader import (
    get_benchmark_metrics,
    get_benchmark_nav,
    get_portfolio_metrics,
    get_portfolio_nav,
    get_portfolio_rebalance,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtest", tags=["Backtest"])

BACKTEST_RESULT = {}


@router.get("/algorithm", response_model=List[schemas.Strategy])
async def get_algorithm():

    return db.TbStrategy.query_df().to_dict(orient="records")


@router.get("/strategy", response_model=List[schemas.Portfolio])
async def get_strategy():

    return db.get_port_summary().to_dict(orient="records")


@router.get("/strategy/monthlynav", response_model=List[schemas.PortNav])
async def get_all_monthly_nav():

    return db.get_monthly_nav().to_dict(orient="records")


@router.get("/strategy/{port_id}")
async def get_strategy_id_info(port_id: int):
    """포트폴리오 정보 조회 (메타데이터: MySQL, 성과지표: Iceberg)"""
    # 포트폴리오 메타데이터 (MySQL)
    portfolio_info = db.get_port_id_info(port_id=port_id)

    if portfolio_info.empty:
        return []

    # 성과지표 (Iceberg)
    metrics_cols = ["ann_ret", "ann_vol", "sharpe", "mdd", "skew", "kurt", "var", "cvar"]
    try:
        metrics_df = get_portfolio_metrics(port_id=port_id)
        if not metrics_df.empty:
            for col in metrics_cols:
                if col in metrics_df.columns:
                    portfolio_info[col] = metrics_df[col].values[0]
                else:
                    portfolio_info[col] = None
        else:
            # Iceberg에 데이터 없으면 None으로 채움
            for col in metrics_cols:
                portfolio_info[col] = None
    except Exception as e:
        logger.warning(f"Iceberg Metrics 조회 실패: {e}")
        for col in metrics_cols:
            portfolio_info[col] = None

    return portfolio_info.to_dict(orient="records")


@router.get("/strategy/nav/{port_id}")
async def get_strategy_id_nav(port_id: int):
    """포트폴리오 NAV 조회 (Iceberg)"""
    try:
        nav_df = get_portfolio_nav(port_id=port_id)
        return nav_df.to_dict(orient="records")
    except Exception as e:
        logger.error(f"NAV 조회 실패: port_id={port_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"NAV 데이터 조회 실패: {str(e)}")


@router.get("/strategy/rebal/{port_id}")
async def get_strategy_id_rebal(port_id: int):
    """포트폴리오 리밸런싱 가중치 조회 (Iceberg)"""
    try:
        rebal_df = get_portfolio_rebalance(port_id=port_id)
        return rebal_df.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Rebalance 조회 실패: port_id={port_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"리밸런싱 데이터 조회 실패: {str(e)}")


@router.get("/strategy/bm/{port_id}")
async def set_benchmark(port_id: int):
    """벤치마크 데이터 조회 (Iceberg에서 미리 계산된 데이터 조회, 없으면 실시간 계산)"""
    # 1. Iceberg에서 미리 계산된 벤치마크 데이터 조회 시도
    try:
        bm_nav_df = get_benchmark_nav(port_id=port_id)
        bm_metrics_df = get_benchmark_metrics(port_id=port_id)

        if not bm_nav_df.empty and not bm_metrics_df.empty:
            # 미리 계산된 데이터 반환
            bm_nav_df["bm_name"] = "BM(SPY)"
            nav_stack = bm_nav_df[["trade_date", "bm_name", "value"]]

            # metrics를 JSON 형식으로 변환
            bm_metrics_df["strategy"] = "BM(SPY)"
            metrics_cols = [
                "strategy",
                "ann_ret",
                "ann_vol",
                "sharpe",
                "mdd",
                "skew",
                "kurt",
                "var",
                "cvar",
            ]
            # ann_ret을 ann_returns로 변경 (프론트엔드 호환성)
            bm_metrics_df = bm_metrics_df.rename(columns={"ann_ret": "ann_returns"})
            metrics_cols[1] = "ann_returns"

            logger.info(f"Benchmark 조회 완료 (Iceberg): port_id={port_id}")
            return {
                "nav": nav_stack.to_json(orient="records"),
                "metrics": bm_metrics_df[
                    ["strategy", "ann_returns", "ann_vol", "sharpe", "mdd"]
                ].to_json(orient="records"),
            }
    except Exception as e:
        logger.warning(f"Iceberg 벤치마크 조회 실패, 실시간 계산 시도: {e}")

    # 2. Iceberg에 데이터가 없으면 실시간 계산 (기존 로직)
    period = db.get_port_start_end_date(port_id=port_id)

    if period.empty:
        raise HTTPException(status_code=404, detail="Portfolio NAV data not found")

    start = pd.Timestamp(period.start_date.values[0]).date()
    end = pd.Timestamp(period.end_date.values[0]).date()

    bt = Backtest(strategy_name="BM(SPY)")
    # 기간 필터링으로 성능 개선
    price = bt.data(tickers="SPY", start_date=start, end_date=end)

    w_dict = {"SPY": 1}
    weight = pd.DataFrame(w_dict, index=period.start_date)

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

    strategy_name = request.strategy_name
    meta_id = request.meta_id
    algorithm = request.algorithm
    start_date = request.startDate
    end_date = request.endDate

    bt = Backtest(strategy_name=strategy_name)
    price = bt.data(meta_id=meta_id)  # Iceberg에서 조회
    weight = bt.rebalance(price=price, method=algorithm, start=start_date, end=end_date)

    weights, nav, metrics = bt.result(price=price, weight=weight)

    BACKTEST_RESULT[strategy_name] = {"weights": weights, "nav": nav, "metrics": metrics}

    return {
        "weights": weights.get(strategy_name).to_json(orient="split"),
        "nav": nav.to_json(orient="split"),
        "metrics": metrics.to_json(orient="records"),
    }


@router.post("/savestrategy")
async def save_strategy(request: schemas.BacktestRequest):
    strategy_name = request.strategy_name
    result = BACKTEST_RESULT.get(strategy_name)

    if not result:
        raise HTTPException(status_code=404, detail="Backtest result not found.")

    weights = result["weights"].get(strategy_name)
    nav = result["nav"].get(strategy_name)
    metrics = result["metrics"]

    # 먼저 포트폴리오가 이미 존재하는지 확인
    existing = db.TbPortfolio.query(port_name=strategy_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Portfolio name already exists.")

    try:
        # 포트폴리오 생성 (MySQL)
        db.create_portfolio(port_name=strategy_name, algorithm=request.algorithm)
        db.upload_universe(port_name=strategy_name, tickers=request.meta_id)

        # Iceberg에 데이터 저장
        db.upload_rebalance(port_name=strategy_name, weights=weights)
        db.upload_nav(port_name=strategy_name, nav=nav)
        db.upload_metrics(
            port_name=strategy_name, metrics=metrics[metrics.strategy == strategy_name]
        )

        # 벤치마크 계산 및 저장 (성능 최적화: 저장 시 미리 계산)
        port_id = db.TbPortfolio.query(port_name=strategy_name).first().port_id
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
            if bm_nav is not None:
                db.upload_benchmark_nav(port_id=port_id, nav=bm_nav)
                db.upload_benchmark_metrics(port_id=port_id, metrics=bm_metrics)
                logger.info(f"Benchmark saved for port_id={port_id}")

    except IntegrityError:
        raise HTTPException(status_code=400, detail="Portfolio name already exists.")
    except Exception as e:
        # Iceberg 저장 실패 시 MySQL에서 포트폴리오 삭제 (rollback)
        logger.error(f"Strategy save failed, rolling back: {e}")
        try:
            portfolio = db.TbPortfolio.query(port_name=strategy_name).first()
            if portfolio:
                db.TbUniverse.delete(port_id=portfolio.port_id)
                db.TbPortfolio.delete(port_id=portfolio.port_id)
        except Exception as rollback_error:
            logger.error(f"Rollback failed: {rollback_error}")
        raise HTTPException(status_code=500, detail=f"Failed to save strategy: {str(e)}")

    return {"message": "Strategy saved successfully"}


@router.post("/clearstrategy")
async def clear_strategy():
    bt = Backtest()
    bt.clear_backtest_result()

    return {"message": "Clear strategies"}
