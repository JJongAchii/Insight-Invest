import json
import logging
import math
import os
import sys
import uuid
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))
import datastore
from app import schemas
from datastore import fx, index_prices, portfolio
from datastore import meta as meta_store
from module import analytics
from module.backtest import Backtest
from module.util import backtest_result, result_metrics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtest", tags=["Backtest"])

METRIC_COLS = ["ann_ret", "ann_vol", "sharpe", "mdd", "skew", "kurt", "var", "cvar"]

# API v2 지표 키 ← module.util.result_metrics 키
METRIC_KEY_MAP = {
    "ann_ret": "ann_returns",
    "ann_vol": "ann_volatilities",
    "sharpe": "sharpe_ratios",
    "sortino": "sortino_ratios",
    "calmar": "calmar_ratio",
    "omega": "omega_ratios",
    "mdd": "max_drawdowns",
    "skew": "skewness",
    "kurt": "kurtosis",
    "var": "value_at_risk",
    "cvar": "conditional_value_at_risk",
}

ALGORITHMS = {"eq", "momentum", "dual_mmt", "custom"}
REBAL_FREQS = {"M", "Q", "Y"}
CURRENCIES = {"USD", "KRW"}

# Lambda는 요청마다 다른 컨테이너일 수 있어 인메모리 결과 공유 불가 —
# 백테스트 결과를 S3(tmp_results/{token}/)에 보관하고 저장 시 토큰으로 리로드한다.
TMP_DIR = "tmp_results"


def _finite(x) -> Optional[float]:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _short_metrics(metric_series: pd.Series) -> dict:
    """result_metrics Series → API v2 short-key dict (비유한값은 None)."""
    return {k: _finite(metric_series.get(v)) for k, v in METRIC_KEY_MAP.items()}


def _persist_result(
    token: str,
    weights: pd.DataFrame,
    nav: pd.Series,
    metrics_row: pd.DataFrame,
    config: dict,
):
    from datastore import storage

    storage.write_parquet(weights.reset_index(names="__idx"), TMP_DIR, token, "weights.parquet")
    nav_df = nav.rename("value").rename_axis("__idx").reset_index()
    storage.write_parquet(nav_df, TMP_DIR, token, "nav.parquet")
    storage.write_parquet(metrics_row, TMP_DIR, token, "metrics.parquet")
    params_row = pd.DataFrame(
        [{
            "algorithm": config["algorithm"],
            "rebal_freq": config["rebal_freq"],
            "cost_bps": float(config["cost_bps"]),
            "currency": config["currency"],
            "benchmark": config["benchmark"],
            "params": json.dumps(config.get("params") or {}),
        }]
    )
    storage.write_parquet(params_row, TMP_DIR, token, "params.parquet")


def _load_result(token: str):
    from datastore import storage

    try:
        weights = storage.read_parquet(TMP_DIR, token, "weights.parquet").set_index("__idx")
        nav = storage.read_parquet(TMP_DIR, token, "nav.parquet").set_index("__idx")["value"]
        metrics = storage.read_parquet(TMP_DIR, token, "metrics.parquet")
        return weights, nav, metrics
    except FileNotFoundError:
        return None


def _load_config(token: str) -> Optional[dict]:
    from datastore import storage

    try:
        row = storage.read_parquet(TMP_DIR, token, "params.parquet").iloc[0].to_dict()
    except (FileNotFoundError, IndexError):
        return None
    try:
        row["params"] = json.loads(row.get("params") or "{}")
    except (TypeError, ValueError):
        row["params"] = {}
    return row


def _serialize_series(s: pd.Series, ndigits: int = 4) -> List[dict]:
    return [
        {"date": d.strftime("%Y-%m-%d"), "value": round(float(v), ndigits)}
        for d, v in s.items()
        if _finite(v) is not None
    ]


def _merged_period_returns(nav: pd.Series, bm: Optional[pd.Series], freq: str) -> List[dict]:
    s = analytics.period_returns(nav, freq)
    b = (
        analytics.period_returns(bm, freq)
        if bm is not None and not bm.empty
        else pd.Series(dtype=float)
    )
    labels = sorted(set(s.index) | set(b.index))
    return [
        {
            "label": label,
            "strategy": round(float(s[label]) * 100, 2) if label in s.index else None,
            "benchmark": round(float(b[label]) * 100, 2) if label in b.index else None,
        }
        for label in labels
    ]


def _resolve_benchmark(bm_name: str, nav: pd.Series) -> pd.Series:
    """전략 NAV 구간의 벤치마크 시계열 — 전략 시작(첫 공통 날짜) 기준 1000으로 리베이스."""
    bm = index_prices.benchmark_nav(bm_name, nav.index.min().date(), nav.index.max().date())
    bm = bm.loc[nav.index.min() : nav.index.max()].dropna()
    if bm.empty:
        return bm
    common = bm.index.intersection(nav.index)
    base = bm.loc[common[0]] if len(common) else bm.iloc[0]
    return bm / base * 1000.0


def _build_response(
    token: str,
    strategy_name: str,
    weight: pd.DataFrame,
    book: pd.DataFrame,
    nav: pd.Series,
    metric_series: pd.Series,
    price: pd.DataFrame,
    bm_name: str,
) -> dict:
    bm = _resolve_benchmark(bm_name, nav)
    bm_metrics = _short_metrics(result_metrics(bm)) if len(bm) > 1 else {}

    weights_long = weight.stack().reset_index()
    weights_long.columns = ["date", "ticker", "w"]
    weights_long = weights_long.dropna(subset=["w"])

    contrib = analytics.contribution(book, price)

    return {
        "result_token": token,
        "strategy_name": strategy_name,
        "nav": _serialize_series(nav),
        "benchmark": {"name": bm_name, "nav": _serialize_series(bm)},
        "weights": [
            {
                "date": pd.Timestamp(r.date).strftime("%Y-%m-%d"),
                "ticker": r.ticker,
                "weight": round(float(r.w), 6),
            }
            for r in weights_long.itertuples()
        ],
        "metrics": {
            "strategy": _short_metrics(metric_series),
            "benchmark": bm_metrics,
        },
        "analytics": {
            # drawdown은 % 값, rolling_sharpe는 비율 그대로
            "drawdown": _serialize_series(analytics.drawdown_series(nav) * 100, ndigits=2),
            "rolling_sharpe": _serialize_series(analytics.rolling_sharpe(nav), ndigits=3),
            "yearly_returns": _merged_period_returns(nav, bm, "Y"),
            "monthly_returns": _merged_period_returns(nav, bm, "M"),
            # 종목별 근사 기여도 (%)
            "contribution": [
                {"ticker": t, "value": round(float(v) * 100, 2)} for t, v in contrib.items()
            ],
            "crisis": analytics.crisis_windows(nav),
        },
    }


def _validate_common(algorithm: str, rebal_freq: str, benchmark: str, currency: str):
    if algorithm not in ALGORITHMS:
        raise HTTPException(status_code=400, detail=f"unknown algorithm: {algorithm}")
    if rebal_freq not in REBAL_FREQS:
        raise HTTPException(status_code=400, detail=f"rebal_freq must be one of {REBAL_FREQS}")
    if benchmark not in index_prices.BENCHMARKS:
        raise HTTPException(
            status_code=400, detail=f"benchmark must be one of {index_prices.BENCHMARKS}"
        )
    if currency not in CURRENCIES:
        raise HTTPException(status_code=400, detail=f"currency must be one of {CURRENCIES}")


def _run_and_respond(
    strategy_name: str,
    price: pd.DataFrame,
    tickers_iso: dict,
    algorithm: str,
    rebal_freq: str,
    cost_bps: float,
    benchmark: str,
    currency: str,
    params: Optional[dict],
    custom_weight: Optional[dict],
    start,
    end,
) -> dict:
    if price.empty:
        raise HTTPException(status_code=404, detail="No price data found for given assets")

    if currency == "KRW":
        price = fx.to_krw(price, tickers_iso)

    bt = Backtest(strategy_name=strategy_name)
    weight = bt.rebalance(
        price=price,
        method=algorithm,
        freq=rebal_freq,
        custom_weight=custom_weight,
        params=params,
        start=start,
        end=end,
    )
    if weight is None or weight.empty:
        raise HTTPException(
            status_code=400,
            detail="No rebalance weights produced — check the date range (momentum needs "
            "lookback history) and the selected assets.",
        )

    book, nav, metric_series = backtest_result(
        weight=weight, price=price, end_date=end, cost_bps=cost_bps
    )

    token = uuid.uuid4().hex
    config = {
        "algorithm": algorithm,
        "rebal_freq": rebal_freq,
        "cost_bps": cost_bps,
        "currency": currency,
        "params": params or {},
        "benchmark": benchmark,
    }
    metrics_row = pd.DataFrame([_short_metrics(metric_series)])
    _persist_result(token, weights=weight, nav=nav, metrics_row=metrics_row, config=config)

    return _build_response(
        token=token,
        strategy_name=strategy_name,
        weight=weight,
        book=book,
        nav=nav,
        metric_series=metric_series,
        price=price,
        bm_name=benchmark,
    )


@router.get("/algorithm", response_model=List[schemas.Strategy])
async def get_algorithm():
    return datastore.strategy_df().to_dict(orient="records")


@router.get("/strategy", response_model=List[schemas.Portfolio])
async def get_strategy():
    return portfolio.port_summary().to_dict(orient="records")


@router.get("/strategy/monthlynav", response_model=List[schemas.PortNav])
async def get_all_monthly_nav():
    return portfolio.monthly_nav().to_dict(orient="records")


@router.get("/strategy/{port_id}")
async def get_strategy_id_info(port_id: int):
    """포트폴리오 정보 + 성과지표 (parquet 스토어)"""
    portfolio_info = portfolio.port_id_info(port_id=port_id)
    if portfolio_info.empty:
        return []

    metrics_df = portfolio.metrics(port_id=port_id)
    for col in METRIC_COLS:
        portfolio_info[col] = metrics_df[col].values[0] if not metrics_df.empty else None

    return portfolio_info.to_dict(orient="records")


@router.get("/strategy/nav/{port_id}")
async def get_strategy_id_nav(port_id: int):
    try:
        return portfolio.nav(port_id=port_id).to_dict(orient="records")
    except Exception as e:
        logger.error(f"NAV 조회 실패: port_id={port_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"NAV 데이터 조회 실패: {str(e)}")


@router.get("/strategy/rebal/{port_id}")
async def get_strategy_id_rebal(port_id: int):
    try:
        return portfolio.rebalance(port_id=port_id).to_dict(orient="records")
    except Exception as e:
        logger.error(f"Rebalance 조회 실패: port_id={port_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"리밸런싱 데이터 조회 실패: {str(e)}")


@router.get("/strategy/bm/{port_id}")
async def set_benchmark(port_id: int):
    """벤치마크 조회 — 저장된 데이터 우선, 없으면 실시간 계산"""
    bm_nav_df = portfolio.benchmark_nav(port_id=port_id)
    bm_metrics_df = portfolio.benchmark_metrics(port_id=port_id)

    if not bm_nav_df.empty and not bm_metrics_df.empty:
        bm_nav_df = bm_nav_df.copy()
        bm_nav_df["bm_name"] = "BM(SPY)"
        nav_stack = bm_nav_df[["trade_date", "bm_name", "value"]]

        bm_metrics_df = bm_metrics_df.copy()
        bm_metrics_df["strategy"] = "BM(SPY)"
        bm_metrics_df = bm_metrics_df.rename(columns={"ann_ret": "ann_returns"})

        logger.info(f"Benchmark 조회 완료 (저장본): port_id={port_id}")
        return {
            "nav": nav_stack.to_json(orient="records"),
            "metrics": bm_metrics_df[
                ["strategy", "ann_returns", "ann_vol", "sharpe", "mdd"]
            ].to_json(orient="records"),
        }

    # 저장된 벤치마크가 없으면 실시간 계산
    period = portfolio.port_start_end_date(port_id=port_id)
    if period.empty:
        raise HTTPException(status_code=404, detail="Portfolio NAV data not found")

    start = pd.Timestamp(period.start_date.values[0]).date()
    end = pd.Timestamp(period.end_date.values[0]).date()

    bt = Backtest(strategy_name="BM(SPY)")
    price = bt.data(tickers="SPY", start_date=start, end_date=end)

    weight = pd.DataFrame({"SPY": 1}, index=period.start_date)
    _, nav, metrics = bt.result(price=price, weight=weight, end=end)
    nav_stack = nav.stack().reset_index()
    nav_stack.columns = ["trade_date", "bm_name", "value"]

    logger.info(f"Benchmark 계산 완료 (실시간): port_id={port_id}")
    return {
        "nav": nav_stack.to_json(orient="records"),
        "metrics": metrics.to_json(orient="records"),
    }


@router.post("")
async def run_backtest(request: schemas.BacktestRequest):
    _validate_common(request.algorithm, request.rebal_freq, request.benchmark, request.currency)

    params = request.params or {}
    custom_weight = None
    if request.algorithm == "custom":
        custom_weight = params.get("weights")
        if not custom_weight:
            raise HTTPException(
                status_code=400, detail='custom algorithm requires params.weights: {"SPY": 0.6, …}'
            )

    bt = Backtest(strategy_name=request.strategy_name)
    price = bt.data(meta_id=request.meta_id)

    mapping = meta_store.resolve(meta_ids=request.meta_id)
    tickers_iso = dict(zip(mapping["ticker"], mapping["iso_code"]))

    return _run_and_respond(
        strategy_name=request.strategy_name,
        price=price,
        tickers_iso=tickers_iso,
        algorithm=request.algorithm,
        rebal_freq=request.rebal_freq,
        cost_bps=request.cost_bps,
        benchmark=request.benchmark,
        currency=request.currency,
        params=params,
        custom_weight=custom_weight,
        start=request.startDate,
        end=request.endDate,
    )


@router.post("/from-weights")
async def run_backtest_from_weights(request: schemas.FromWeightsRequest):
    _validate_common("custom", request.rebal_freq, request.benchmark, request.currency)

    tickers = list(request.weights.keys())
    mapping = meta_store.resolve(tickers=tickers)
    if mapping.empty:
        raise HTTPException(status_code=404, detail=f"No known tickers among {tickers}")
    tickers_iso = dict(zip(mapping["ticker"], mapping["iso_code"]))

    bt = Backtest(strategy_name=request.strategy_name)
    price = bt.data(tickers=mapping["ticker"].tolist())

    return _run_and_respond(
        strategy_name=request.strategy_name,
        price=price,
        tickers_iso=tickers_iso,
        algorithm="custom",
        rebal_freq=request.rebal_freq,
        cost_bps=request.cost_bps,
        benchmark=request.benchmark,
        currency=request.currency,
        params={"weights": request.weights},
        custom_weight=request.weights,
        start=request.startDate,
        end=request.endDate,
    )


@router.post("/savestrategy")
async def save_strategy(request: schemas.SaveStrategyRequest):
    strategy_name = request.strategy_name
    result = _load_result(request.result_token)
    if result is None:
        raise HTTPException(status_code=404, detail="Backtest result not found or expired.")

    weights, nav, metrics_df = result
    config = _load_config(request.result_token)

    if portfolio.exists_name(strategy_name):
        raise HTTPException(status_code=400, detail="Portfolio name already exists.")

    port_id = None
    try:
        port_id = portfolio.create(
            port_name=strategy_name,
            algorithm=request.algorithm,
            meta_ids=request.meta_id,
            config=config,
        )
        portfolio.save_rebalance(port_id=port_id, weights=weights)
        portfolio.save_nav(port_id=port_id, nav_series=nav)

        values = {col: float(metrics_df.iloc[0][col]) for col in METRIC_COLS}
        portfolio.save_metrics(port_id=port_id, values=values)

        # 벤치마크 미리 계산 (조회 성능)
        bm_name = (config or {}).get("benchmark") or "SPY"
        nav = nav.copy()
        nav.index = pd.to_datetime(nav.index)
        bm = index_prices.benchmark_nav(bm_name, nav.index.min().date(), nav.index.max().date())
        bm = bm.loc[nav.index.min() : nav.index.max()].dropna()
        if not bm.empty:
            bm = bm / bm.iloc[0] * 1000.0
            portfolio.save_benchmark_nav(port_id=port_id, nav_series=bm)
            if len(bm) > 1:
                bm_metrics = _short_metrics(result_metrics(bm))
                if all(bm_metrics.get(col) is not None for col in METRIC_COLS):
                    portfolio.save_benchmark_metrics(
                        port_id=port_id,
                        values={col: bm_metrics[col] for col in METRIC_COLS},
                    )
            logger.info(f"Benchmark({bm_name}) saved for port_id={port_id}")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Strategy save failed, rolling back: {e}")
        if port_id is not None:
            try:
                portfolio.delete(port_id)
            except Exception as rollback_error:
                logger.error(f"Rollback failed: {rollback_error}")
        raise HTTPException(status_code=500, detail=f"Failed to save strategy: {str(e)}")

    return {"message": "Strategy saved successfully"}
