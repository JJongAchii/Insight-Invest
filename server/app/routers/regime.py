import os
import sys

import pandas as pd
from fastapi import APIRouter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))
import datastore
from datastore import storage

router = APIRouter(prefix="/regime", tags=["Regime"])


@router.get("/info")
async def get_macro_info():
    return datastore.macro_df().to_dict(orient="records")


def _macro_data() -> pd.DataFrame:
    """매크로 시계열 [base_date, macro_id, fred, value].

    소스 = RDS 시절 아카이브(macro_data.parquet) ∪ qdata FRED(레이크에 있는 시리즈만,
    일일 갱신). 같은 날짜는 최신 수집(qdata) 우선.
    """
    macro = datastore.macro_df()[["macro_id", "fred"]]
    archive = storage.read_parquet("macro_data.parquet").merge(macro, on="macro_id", how="inner")
    archive = archive[["base_date", "macro_id", "fred", "value"]]

    try:
        from qdata import api as qdata_api

        live = qdata_api.load_fred(macro["fred"].tolist())
        live = live.stack().rename("value").reset_index()
        live.columns = ["base_date", "fred", "value"]
        live = live.merge(macro, on="fred", how="inner")[
            ["base_date", "macro_id", "fred", "value"]
        ]
    except (FileNotFoundError, KeyError):
        live = pd.DataFrame(columns=archive.columns)

    merged = pd.concat([archive, live], ignore_index=True)
    merged["base_date"] = pd.to_datetime(merged["base_date"])
    merged = merged.drop_duplicates(subset=["fred", "base_date"], keep="last")
    merged = merged[merged["base_date"] >= "1980-01-01"]
    return merged.sort_values("base_date").reset_index(drop=True)


@router.get("/data")
async def get_macro_data():
    data = _macro_data()
    data.loc[data.fred == "CPIAUCSL", "value"] = data[data.fred == "CPIAUCSL"].value.pct_change(
        periods=12
    )
    return data.dropna().to_dict(orient="records")
