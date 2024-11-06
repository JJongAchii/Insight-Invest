import os
import sys
from fastapi import Depends, APIRouter
from sqlalchemy.orm import Session
from typing import List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../..")))
import db
from app import schemas

router = APIRouter(
    prefix="/meta",
    tags=["Meta"]
)


@router.get("", response_model=List[schemas.Meta])
def get_meta(ss: Session = Depends(db.get_db)):
    
    return ss.query(db.TbMeta).order_by(db.TbMeta.meta_id.asc()).all()


@router.get("/tickers", response_model=List[schemas.Ticker])
def get_meta_tickers(ss: Session = Depends(db.get_db)):
    
    return ss.query(db.TbMeta).order_by(db.TbMeta.meta_id.asc()).all()