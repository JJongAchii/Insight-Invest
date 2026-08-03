import json
import logging
import math
import os
import sys
import uuid
from datetime import datetime
from typing import List, Optional
from zoneinfo import ZoneInfo  # 상단 import

import pandas as pd
from fastapi import APIRouter, HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))
import datastore
from app import schemas
from datastore import fx, index_prices
from datastore import meta as meta_store
from datastore import portfolio
from module import analytics, portfolio_risk, regime, strategy_analytics
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
VALID_STATUS = {"saved", "active"}

# Lambda는 요청마다 다른 컨테이너일 수 있어 인메모리 결과 공유 불가 —
# 백테스트 결과를 S3(tmp_results/{token}/)에 보관하고 저장 시 토큰으로 리로드한다.
TMP_DIR = "tmp_results"


def _finite(x) -> Optional[float]:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _round(x, ndigits: int = 2) -> Optional[float]:
    """_finite 후 반올림 — None-safe."""
    v = _finite(x)
    return round(v, ndigits) if v is not None else None


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
        [
            {
                "algorithm": config["algorithm"],
                "rebal_freq": config["rebal_freq"],
                "cost_bps": float(config["cost_bps"]),
                "currency": config["currency"],
                "benchmark": config["benchmark"],
                "params": json.dumps(config.get("params") or {}),
            }
        ]
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


@router.get("/strategy/live/{port_id}")
async def get_strategy_live(port_id: int):
    """실전 추적 (P7) — 저장 시점 이후 실제 데이터 NAV + 라이브 지표 vs 백테스트 지표.

    live_nav.parquet은 로컬 파이프라인(build_insights의 track_strategies)이 생성한다.
    파일이 없거나 해당 포트폴리오 행이 없으면 nav=[]로 200 응답.
    """
    reg = portfolio.records()
    row = reg[reg["port_id"] == port_id]
    saved_at = (
        pd.Timestamp(row["created_at"].iloc[0]).strftime("%Y-%m-%d") if not row.empty else None
    )

    try:
        live = portfolio.live_nav(port_id)
    except Exception as e:
        logger.warning(f"live_nav 조회 실패: port_id={port_id}, error={e}")
        live = pd.DataFrame(columns=["trade_date", "value", "as_of"])

    nav_points: List[dict] = []
    as_of = None
    metrics_live: dict = {}
    if not live.empty:
        s = pd.Series(
            live["value"].astype(float).to_numpy(), index=pd.to_datetime(live["trade_date"])
        )
        as_of = str(live["as_of"].iloc[-1])
        nav_points = _serialize_series(s)
        if len(s) >= 10:  # 표본이 너무 짧으면 지표 생략 (None-safe)
            metrics_live = _short_metrics(result_metrics(s))

    metrics_df = portfolio.metrics(port_id=port_id)
    metrics_backtest: dict = {}
    if not metrics_df.empty:
        metrics_backtest = {
            k: _finite(metrics_df.iloc[0][k]) if k in metrics_df.columns else None
            for k in METRIC_KEY_MAP  # 저장본에는 sortino/calmar/omega가 없음 → None
        }

    weights: Optional[List[dict]] = None
    try:
        lw = portfolio.live_weights(port_id)
        if not lw.empty:
            lw = lw.copy()
            lw["trade_date"] = pd.to_datetime(lw["trade_date"])
            last_date = lw["trade_date"].max()
            last = lw[lw["trade_date"] == last_date]
            weights = [
                {
                    "trade_date": last_date.strftime("%Y-%m-%d"),
                    "ticker": r.ticker,
                    "weight": _round(r.weight, 6),
                }
                for r in last.itertuples()
            ]
    except Exception as e:
        logger.warning(f"live_weights 조회 실패: port_id={port_id}, error={e}")

    expectation: Optional[dict] = None
    try:
        if not live.empty:
            bt_nav_df = portfolio.nav(port_id=port_id)
            if not bt_nav_df.empty:
                bt_nav = pd.Series(
                    bt_nav_df["value"].astype(float).to_numpy(),
                    index=pd.to_datetime(bt_nav_df["trade_date"]),
                ).sort_index()
                exp = strategy_analytics.live_percentile(bt_nav, s)
                if exp is not None:
                    expectation = {
                        "n_days": exp["n_days"],
                        "live_ret_pct": _round(exp["live_ret_pct"], 2),
                        "ret_percentile": _round(exp["ret_percentile"], 2),
                        "live_dd_pct": _round(exp["live_dd_pct"], 2),
                        "dd_percentile": _round(exp["dd_percentile"], 2),
                    }
    except Exception as e:
        logger.warning(f"live_percentile 계산 실패: port_id={port_id}, error={e}")

    return {
        "port_id": port_id,
        "saved_at": saved_at,
        "as_of": as_of,
        "nav": nav_points,
        "metrics_live": metrics_live,
        "metrics_backtest": metrics_backtest,
        "weights": weights,
        "expectation": expectation,
    }


@router.get("/strategy/analytics/{port_id}")
async def get_strategy_analytics(port_id: int):
    """전략 분석(P1) — 투입 판정 재료. 섹션 단위 degrade, 모르는 포트는 empty, 500 금지.

    라우터는 로드·조인·반올림만 한다 — 판단(백분위·에피소드 경계·국면 그룹핑)은
    module.strategy_analytics/portfolio_risk가 하고, "좋다/나쁘다"는 붙이지 않는다.
    crisis는 예외가 나도 빈 배열([])로 떨어진다 — 다른 섹션과 달리 null이 아니다
    (Phase 2는 항상 배열로 소비할 수 있다).
    """
    reg = portfolio.records()
    row = reg[reg["port_id"] == port_id]
    if row.empty:
        return {"empty": True}

    nav_df = portfolio.nav(port_id=port_id)
    if nav_df.empty:
        return {"empty": True}
    nav = pd.Series(
        nav_df["value"].astype(float).to_numpy(), index=pd.to_datetime(nav_df["trade_date"])
    ).sort_index()

    # bm_nav·rebal은 여러 섹션이 공유하는 로드라 try 밖에 있으면 I/O 실패(부재가
    # 아니라 S3 타임아웃·손상 parquet 등)가 응답 전체를 500으로 끌고 간다 — 각각
    # 독립 try/except로 격리해 의존 섹션만 null로 떨어지게 한다.
    bm_nav: Optional[pd.Series] = None
    try:
        bm_df = portfolio.benchmark_nav(port_id=port_id)
        if not bm_df.empty:
            bm_nav = pd.Series(
                bm_df["value"].astype(float).to_numpy(), index=pd.to_datetime(bm_df["trade_date"])
            ).sort_index()
    except Exception as e:
        logger.warning(f"analytics benchmark_nav 조회 실패: port_id={port_id}, error={e}")

    rebal = pd.DataFrame()
    rebal_failed = False
    try:
        rebal = portfolio.rebalance(port_id=port_id)
        if not rebal.empty:
            rebal = rebal.copy()
            rebal["rebal_date"] = pd.to_datetime(rebal["rebal_date"])
    except Exception as e:
        logger.warning(f"analytics rebalance 조회 실패: port_id={port_id}, error={e}")
        rebal = pd.DataFrame()
        rebal_failed = True  # 빈 것과 실패를 구분 — n_rebals=0(확인된 무리밸)과 다르다

    try:
        cfg_raw = row["config"].iloc[0]
        cfg = json.loads(cfg_raw) if cfg_raw else {}
    except (TypeError, ValueError):
        cfg = {}

    premise = None
    try:
        cost_bps = cfg.get("cost_bps")
        if rebal_failed:
            n_rebals = None  # 0(확인된 무리밸)과 구분 — 로드 실패라 알 수 없음
        else:
            n_rebals = int(rebal["rebal_date"].nunique()) if not rebal.empty else 0
        premise = {
            "algorithm": cfg.get("algorithm"),
            "rebal_freq": cfg.get("rebal_freq"),
            "cost_bps": _finite(cost_bps) if cost_bps is not None else None,
            "currency": cfg.get("currency"),
            "universe_n": len(portfolio.universe(port_id)),
            "saved_at": pd.Timestamp(row["created_at"].iloc[0]).strftime("%Y-%m-%d"),
            "bt_start": nav.index.min().strftime("%Y-%m-%d"),
            "bt_end": nav.index.max().strftime("%Y-%m-%d"),
            "bt_days": int(len(nav)),
            "n_rebals": n_rebals,
            "cost_warning": cost_bps is None or cost_bps == 0,
        }
    except Exception as e:
        logger.warning(f"analytics premise 조립 실패: port_id={port_id}, error={e}")

    rolling = None
    try:
        rs = strategy_analytics.rolling_stats(nav)
        if not rs.empty:
            weekly = rs.resample("W-FRI").last().dropna()
            rows = [
                {
                    "date": d.strftime("%Y-%m-%d"),
                    "roll_ret": _round(r.roll_ret, 2),
                    "roll_sharpe": _round(r.roll_sharpe, 3),
                }
                for d, r in weekly.iterrows()
            ]
            bm_rows = None
            if bm_nav is not None and len(bm_nav):
                bm_rs = strategy_analytics.rolling_stats(bm_nav)
                if not bm_rs.empty:
                    bm_weekly = bm_rs.resample("W-FRI").last().dropna()
                    bm_rows = [
                        {
                            "date": d.strftime("%Y-%m-%d"),
                            "roll_ret": _round(r.roll_ret, 2),
                            "roll_sharpe": _round(r.roll_sharpe, 3),
                        }
                        for d, r in bm_weekly.iterrows()
                    ]
            rolling = {
                "window": strategy_analytics.TRADING_DAYS,
                "rows": rows,
                "bm_rows": bm_rows,
            }
    except Exception as e:
        logger.warning(f"analytics rolling 계산 실패: port_id={port_id}, error={e}")

    drawdowns = None
    try:
        dd = analytics.drawdown_series(nav) * 100
        weekly_dd = dd.resample("W-FRI").last().dropna()
        underwater = [
            {"date": d.strftime("%Y-%m-%d"), "dd_pct": _round(v, 2)} for d, v in weekly_dd.items()
        ]
        episodes = [
            {
                "depth_pct": _round(e["depth_pct"], 2),
                "peak": e["peak"].strftime("%Y-%m-%d") if e["peak"] is not None else None,
                "trough": e["trough"].strftime("%Y-%m-%d") if e["trough"] is not None else None,
                "recover": e["recover"].strftime("%Y-%m-%d") if e["recover"] is not None else None,
                "days_to_recover": e["days_to_recover"],
            }
            for e in strategy_analytics.drawdown_episodes(nav)
        ]
        drawdowns = {"underwater": underwater, "episodes": episodes}
    except Exception as e:
        logger.warning(f"analytics drawdowns 계산 실패: port_id={port_id}, error={e}")

    phases = None
    try:
        phase_series = regime.phase_history()["phase"]
        monthly = strategy_analytics.monthly_returns(nav)
        pm = strategy_analytics.phase_monthly_means(monthly, phase_series)
        if not pm.empty:
            bm_pm = None
            if bm_nav is not None and len(bm_nav):
                bm_monthly = strategy_analytics.monthly_returns(bm_nav)
                bm_pm = strategy_analytics.phase_monthly_means(bm_monthly, phase_series)
            rows = []
            for phase, r in pm.iterrows():
                bm_val = None
                if bm_pm is not None and phase in bm_pm.index:
                    bm_val = _round(bm_pm.loc[phase, "mean_ret_pct"], 2)
                rows.append(
                    {
                        "phase": phase,
                        "mean_ret_pct": _round(r["mean_ret_pct"], 2),
                        "n_months": int(r["n_months"]),
                        "bm_mean_ret_pct": bm_val,
                    }
                )
            phases = {"rows": rows}
    except Exception as e:
        logger.warning(f"analytics phases 계산 실패: port_id={port_id}, error={e}")

    crisis: List[dict] = []
    try:
        crisis = [
            {"key": c["key"], "ret_pct": _round(c["ret_pct"], 2), "note": c["note"]}
            for c in strategy_analytics.crisis_returns(nav, portfolio_risk.CRISIS_WINDOWS)
        ]
    except Exception as e:
        logger.warning(f"analytics crisis 계산 실패: port_id={port_id}, error={e}")

    monthly_section = None
    try:
        ms = strategy_analytics.monthly_stats(nav, bm_nav)
        monthly_section = {
            "win_rate": _round(ms["win_rate"], 2),
            "win_rate_vs_bm": _round(ms["win_rate_vs_bm"], 2),
            "best": [{"month": r["month"], "ret_pct": _round(r["ret_pct"], 2)} for r in ms["best"]],
            "worst": [
                {"month": r["month"], "ret_pct": _round(r["ret_pct"], 2)} for r in ms["worst"]
            ],
        }
    except Exception as e:
        logger.warning(f"analytics monthly 계산 실패: port_id={port_id}, error={e}")

    trading = None
    if rebal_failed:
        logger.warning(f"analytics trading 생략: port_id={port_id}, rebal 로드 실패")
    else:
        try:
            ts = strategy_analytics.turnover_stats(rebal)
            cost_drag_10 = cost_drag_30 = None
            if ts["rebals_per_year"] is not None and ts["avg_turnover"] is not None:
                cost_drag_10 = ts["rebals_per_year"] * ts["avg_turnover"] * 10 / 1e4 * 100
                cost_drag_30 = ts["rebals_per_year"] * ts["avg_turnover"] * 30 / 1e4 * 100
            trading = {
                "n_rebals": ts["n_rebals"],
                "rebals_per_year": _round(ts["rebals_per_year"], 2),
                "avg_turnover": _round(ts["avg_turnover"], 4),
                "cost_drag_pct_10bps": _round(cost_drag_10, 3),
                "cost_drag_pct_30bps": _round(cost_drag_30, 3),
            }
        except Exception as e:
            logger.warning(f"analytics trading 계산 실패: port_id={port_id}, error={e}")

    return {
        "premise": premise,
        "rolling": rolling,
        "drawdowns": drawdowns,
        "phases": phases,
        "crisis": crisis,
        "monthly": monthly_section,
        "trading": trading,
        "as_of": nav.index.max().strftime("%Y-%m-%d"),
    }


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


@router.post("/strategy/{port_id}/status")
async def post_strategy_status(port_id: int, request: schemas.StrategyStatusRequest):
    """운영 시작/중지 토글."""
    if request.status not in VALID_STATUS:
        raise HTTPException(status_code=422, detail=f"status must be one of {VALID_STATUS}")
    try:
        portfolio.set_status(port_id, request.status)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown port_id: {port_id}")
    return {"port_id": port_id, "status": request.status}


@router.get("/rebal-signals")
async def get_rebal_signals():
    """active 전략의 리밸 전일 신호 (parquet 리더). 부재 시 빈 배열 — 500 금지."""
    df = portfolio.rebal_signals()
    if df.empty:
        return {"as_of": None, "signals": []}
    today = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()  # Lambda UTC 보정

    signals = []
    for pid, sub in df.groupby("port_id"):
        sub = sub.sort_values(["rank", "ticker"], na_position="last")
        next_rebal = str(sub["next_rebal"].iloc[0])[:10]
        signals.append(
            {
                "port_id": int(pid),
                "port_name": sub["port_name"].iloc[0],
                "freq": sub["freq"].iloc[0],
                "next_rebal": next_rebal,
                "is_stale": today > next_rebal,
                "items": [
                    {
                        "ticker": r.ticker,
                        "name": r.name,
                        "target_weight": float(r.target_weight),
                        "prev_weight": float(r.prev_weight),
                        "action": r.action,
                        "rank": int(r.rank) if pd.notna(r.rank) else None,
                    }
                    for r in sub.itertuples()
                ],
            }
        )
    return {"as_of": str(df["as_of"].iloc[0])[:10], "signals": signals}
