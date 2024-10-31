import os
import sys
from fastapi import APIRouter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))
from app import schemas
from module.backtest import Backtest

router = APIRouter(
    prefix="/backtest",
    tags=["Backtest"]
)


@router.post("/")
async def run_backtest(request: schemas.BacktestRequest):
    
    meta_id = request.meta_id
    algorithm = request.algorithm
    start_date = request.startDate
    end_date = request.endDate
    
    bt = Backtest()
    price = bt.data(meta_id=meta_id, source="db")
    weights = bt.rebalance(
        price=price,
        method=algorithm,
        start=start_date,
        end=end_date
    )
    
    print(weights)
    return 
