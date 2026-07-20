import os
import sys
from typing import List

import pandas as pd
from fastapi import APIRouter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../..")))
import datastore
from app import schemas

router = APIRouter(prefix="/meta", tags=["Meta"])


def _records() -> list[dict]:
    df = datastore.meta_df().sort_values("meta_id")
    df = df.replace({pd.NA: None, float("nan"): None})
    return df.to_dict(orient="records")


@router.get("", response_model=List[schemas.Meta])
def get_meta():
    return _records()


@router.get("/tickers", response_model=List[schemas.Ticker])
def get_meta_tickers():
    return _records()
