"""가격이 비어 있어도 종목 메타데이터는 JSON 안전하게 응답한다."""

import json

import numpy as np
import pandas as pd

from app.routers import price


def test_empty_price_history_is_json_serializable(monkeypatch):
    monkeypatch.setattr(
        price.datastore,
        "meta_df",
        lambda: pd.DataFrame(
            [
                {
                    "meta_id": np.int64(8919),
                    "ticker": "CPSH",
                    "name": "CPS Technologies",
                    "sector": pd.NA,
                    "iso_code": "US",
                    "marketcap": pd.NA,
                }
            ]
        ),
    )
    monkeypatch.setattr(price.datastore, "read_price_data", lambda **_kwargs: pd.DataFrame())

    result = price.get_price_history(8919)

    assert result["prices"] == []
    assert result["meta"] == {
        "meta_id": 8919,
        "ticker": "CPSH",
        "name": "CPS Technologies",
        "sector": None,
        "iso_code": "US",
        "marketcap": None,
    }
    json.dumps(result)
