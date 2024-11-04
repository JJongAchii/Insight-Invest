import os
import sys
from fastapi import Depends, APIRouter
from sqlalchemy.orm import Session
from typing import List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../..")))
from db.client import get_db
from db.models import TbMeta
from app import schemas

router = APIRouter(
    prefix="/meta",
    tags=["Meta"]
)


@router.get("/", response_model=List[schemas.Meta])
def get_meta(db: Session = Depends(get_db)):
    
    return db.query(TbMeta).order_by(TbMeta.meta_id.asc()).all()


@router.get("/tickers", response_model=List[schemas.Ticker])
def get_meta_tickers(db: Session = Depends(get_db)):
    
    return db.query(TbMeta).order_by(TbMeta.meta_id.asc()).all()