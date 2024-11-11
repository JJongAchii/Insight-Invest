import os
import sys
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))
import db
from app import schemas
from module.backtest import Backtest


router = APIRouter(
    prefix="/backtest",
    tags=["Backtest"]
)

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
    
    return db.get_port_id_info(port_id=port_id).to_dict(orient="records")

@router.get("/strategy/nav/{port_id}")
async def get_strategy_id_nav(port_id: int):
    
    return db.TbNav.query_df(port_id=port_id).to_dict(orient="records")
    
@router.get("/strategy/rebal/{port_id}")
async def get_strategy_id_rebal(port_id: int):
    
    return db.get_port_id_rebal(port_id=port_id).to_dict(orient="records")    
    
@router.post("")
async def run_backtest(request: schemas.BacktestRequest):
    
    strategy_name = request.strategy_name
    meta_id = request.meta_id
    algorithm = request.algorithm
    start_date = request.startDate
    end_date = request.endDate
    
    bt = Backtest(strategy_name=strategy_name)
    price = bt.data(meta_id=meta_id, source="db")
    weight = bt.rebalance(
        price=price,
        method=algorithm,
        start=start_date,
        end=end_date
    )
    
    weights, nav, metrics = bt.result(price=price, weight=weight)
    
    BACKTEST_RESULT[strategy_name] = {
        "weights": weights,
        "nav": nav,
        "metrics": metrics
    }
    
    return {
        "weights": weights.get(strategy_name).to_json(orient="split"),
        "nav": nav.to_json(orient="split"),
        "metrics": metrics.to_json(orient="records")
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
    
    try:
        # 포트폴리오 생성
        db.create_portfolio(port_name=strategy_name, algorithm=request.algorithm)
    except IntegrityError:
        # port_name이 이미 존재할 경우 예외 처리
        raise HTTPException(status_code=400, detail="Portfolio name already exists.")
    
    # 나머지 데이터베이스 등록 로직
    db.upload_universe(port_name=strategy_name, tickers=request.meta_id)
    db.upload_rebalance(port_name=strategy_name, weights=weights)
    db.upload_nav(port_name=strategy_name, nav=nav)
    db.upload_metrics(port_name=strategy_name, metrics=metrics[metrics.strategy==strategy_name])
    
    return {"message": "Strategy saved successfully"}
    
@router.post("/clearstrategy")
async def clear_strategy():
    bt = Backtest()
    bt.clear_backtest_result()
    
    return {"message": "Clear strategies"}