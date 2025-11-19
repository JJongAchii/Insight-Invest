import os
import sys
from typing import List

import pandas as pd
from fastapi import APIRouter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../..")))
import db
from app import schemas

router = APIRouter(prefix="/meta", tags=["Meta"])


@router.get("", response_model=List[schemas.Meta])
def get_meta():
    df = db.TbMeta.query_df().sort_values("meta_id")
    # Replace NaN values with None
    df = df.replace({pd.NA: None, float("nan"): None})

    return df.to_dict(orient="records")


@router.get("/tickers", response_model=List[schemas.Ticker])
def get_meta_tickers():
    df = db.TbMeta.query_df().sort_values("meta_id")
    # Replace NaN values with None
    df = df.replace({pd.NA: None, float("nan"): None})

    return df.to_dict(orient="records")
