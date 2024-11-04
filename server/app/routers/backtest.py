import os
import sys
import json
from fastapi import APIRouter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))
from app import schemas
from module.backtest import Backtest
from module.util import calculate_nav

router = APIRouter(
    prefix="/backtest",
    tags=["Backtest"]
)


@router.post("/")
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
    
    weights_json = weights.get(strategy_name).to_json(orient="split")
    nav_json = nav.to_json(orient="split")
    metrics_json = metrics.to_json(orient="records")
    
    return {
        "weights": weights_json,
        "nav": nav_json,
        "metrics": metrics_json
    }
