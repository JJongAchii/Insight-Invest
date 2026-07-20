import math
import os
import sys
from typing import Optional

import pandas as pd
from fastapi import APIRouter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))
import datastore
from datastore import storage
from module import regime as regime_mod

router = APIRouter(prefix="/regime", tags=["Regime"])


def _finite(x) -> Optional[float]:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _round2(obj):
    """응답 트리의 float를 2자리 반올림, NaN/inf → None (재귀)."""
    if isinstance(obj, dict):
        return {k: _round2(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round2(v) for v in obj]
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, str)) or obj is None:
        return obj
    f = _finite(obj)
    return round(f, 2) if f is not None else None


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


@router.get("/phase")
async def get_phase():
    """성장(CLI) × 물가(CPI YoY) 4국면 — 현재 + 월간 히스토리 (1998~)."""
    hist = regime_mod.phase_history()
    history = [
        {
            "month": str(idx),
            "phase": row["phase"],
            "cli": _finite(row["cli"]),
            "cli_delta": _finite(row["cli_delta"]),
            "cpi_yoy": _finite(row["cpi_yoy"]),
            "cpi_yoy_delta": _finite(row["cpi_yoy_delta"]),
        }
        for idx, row in hist.iterrows()
    ]
    return _round2({"current": regime_mod.current_phase(), "history": history})


@router.get("/gauge")
async def get_gauge():
    """리스크오프 게이지 0~100 (높을수록 위험회피) + 구성 지표."""
    return _round2(regime_mod.risk_gauge())


@router.get("/kr")
async def get_kr_macro():
    """한국 매크로 시계열 (기준금리·국고채·환율·CPI YoY·CLI)."""
    return _round2(regime_mod.kr_macro())


@router.get("/phase/performance")
async def get_phase_performance():
    """국면별 자산 성과 — scripts/build_insights.py가 만든 사전계산 parquet."""
    try:
        df = storage.read_parquet("insight", "regime_asset_perf.parquet")
    except FileNotFoundError:
        return {"phases": {}, "as_of": None}

    as_of = str(df["as_of"].iloc[0]) if "as_of" in df.columns and not df.empty else None
    phases: dict = {}
    for row in df.itertuples():
        phases.setdefault(row.phase, []).append(
            {
                "ticker": row.ticker,
                "mean_monthly_ret": _finite(row.mean_monthly_ret),
                "ann_ret": _finite(row.ann_ret),
                "hit_rate": _finite(row.hit_rate),
                "n_months": int(row.n_months),
            }
        )
    return _round2({"phases": phases, "as_of": as_of})
