import os
import sys

from fastapi import APIRouter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))
import db

router = APIRouter(prefix="/regime", tags=["Regime"])


@router.get("/info")
async def get_macro_info():

    return db.TbMacro.query_df().to_dict(orient="records")


@router.get("/data")
async def get_macro_data():
    data = db.get_macro_data()

    data.loc[data.fred == "CPIAUCSL", "value"] = data[data.fred == "CPIAUCSL"].value.pct_change(
        periods=12
    )

    return data.dropna().to_dict(orient="records")
