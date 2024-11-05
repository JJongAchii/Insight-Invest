import os
import sys
from fastapi import Depends, APIRouter, Query
from sqlalchemy.orm import Session
from typing import List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../..")))
from db.client import get_db
from db import TbPrice
from app import schemas

router = APIRouter(
    prefix="/price",
    tags=["Price"]
)


@router.get("/", response_model=List[schemas.Price])
def get_price(meta_id: List[int] = Query(...), ss: Session = Depends(get_db)):
    return ss.query(TbPrice.meta_id, TbPrice.trade_date, TbPrice.adj_close).filter(TbPrice.meta_id.in_(meta_id)).all()