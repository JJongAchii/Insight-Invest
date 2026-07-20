"""포트폴리오 저장소 — RDS(tb_portfolio/tb_universe) + Iceberg(portfolio.*) 대체.

{APP_DATA}/portfolio/ 아래 parquet 테이블. 쓰기는 port_id 단위 delete-then-append
후 파일 교체(단일 사용자 앱 전제). 읽기는 요청마다 다시 읽는다 — 수 KB~MB 규모.
"""

import json
import logging
from datetime import datetime

import pandas as pd

from datastore import meta, storage

logger = logging.getLogger(__name__)

DIR = "portfolio"
METRIC_COLS = ["ann_ret", "ann_vol", "sharpe", "mdd", "skew", "kurt", "var", "cvar"]

_EMPTY = {
    # config: 백테스트 실행 설정 JSON 문자열 (스키마 확장 — 구 행은 컬럼 부재 → None)
    "portfolio.parquet": ["port_id", "port_name", "strategy_id", "created_at", "config"],
    "universe.parquet": ["port_id", "meta_id"],
    "nav.parquet": ["port_id", "trade_date", "value"],
    "rebalance.parquet": ["port_id", "rebal_date", "ticker", "weight"],
    "metrics.parquet": ["port_id", *METRIC_COLS, "updated_at"],
    "benchmark_nav.parquet": ["port_id", "trade_date", "value"],
    "benchmark_metrics.parquet": ["port_id", *METRIC_COLS, "updated_at"],
}


def _read(name: str, filters=None) -> pd.DataFrame:
    if not storage.exists(DIR, name):
        return pd.DataFrame(columns=_EMPTY[name])
    return storage.read_parquet(DIR, name, filters=filters)


def _upsert(name: str, port_id: int, rows: pd.DataFrame) -> None:
    """해당 port_id 행 전체 교체 후 append."""
    table = _read(name)
    table = table[table["port_id"] != port_id]
    table = pd.concat([table, rows], ignore_index=True)
    storage.write_parquet(table, DIR, name)


# ---------- 조회 (기존 db.get_* / portfolio_reader 계약) ----------


def registry() -> pd.DataFrame:
    """[port_id, port_name, strategy_name] — tb_portfolio ⋈ tb_strategy."""
    ports = _read("portfolio.parquet")
    if ports.empty:
        return pd.DataFrame(columns=["port_id", "port_name", "strategy_name"])
    st = meta.strategy_df()[["strategy_id", "strategy_name"]]
    return ports.merge(st, on="strategy_id", how="left")[["port_id", "port_name", "strategy_name"]]


def port_summary() -> pd.DataFrame:
    """[port_id, port_name, strategy_name, ann_ret, ann_vol, sharpe]."""
    reg = registry()
    if reg.empty:
        return reg
    m = _read("metrics.parquet")[["port_id", "ann_ret", "ann_vol", "sharpe"]]
    return reg.merge(m, on="port_id", how="left")


def port_id_info(port_id: int) -> pd.DataFrame:
    reg = registry()
    return reg[reg["port_id"] == port_id].reset_index(drop=True)


def exists_name(port_name: str) -> bool:
    ports = _read("portfolio.parquet")
    return bool((ports["port_name"] == port_name).any())


def nav(port_id: int) -> pd.DataFrame:
    df = _read("nav.parquet", filters=[("port_id", "==", port_id)])
    return df[["trade_date", "value"]].sort_values("trade_date").reset_index(drop=True)


def monthly_nav() -> pd.DataFrame:
    """전 포트폴리오 월말 NAV [port_id, trade_date, value]."""
    df = _read("nav.parquet")
    if df.empty:
        return pd.DataFrame(columns=["port_id", "trade_date", "value"])
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df["ym"] = df["trade_date"].dt.to_period("M")
    idx = df.groupby(["port_id", "ym"])["trade_date"].idxmax()
    out = df.loc[idx, ["port_id", "trade_date", "value"]]
    return out.sort_values(["port_id", "trade_date"]).reset_index(drop=True)


def port_start_end_date(port_id: int) -> pd.DataFrame:
    df = nav(port_id)
    if df.empty:
        return pd.DataFrame(columns=["start_date", "end_date"])
    d = pd.to_datetime(df["trade_date"])
    return pd.DataFrame({"start_date": [d.min()], "end_date": [d.max()]})


def rebalance(port_id: int) -> pd.DataFrame:
    """[rebal_date, port_id, ticker, name, weight] — name은 meta 조인."""
    df = _read("rebalance.parquet", filters=[("port_id", "==", port_id)])
    if df.empty:
        return pd.DataFrame(columns=["rebal_date", "port_id", "ticker", "name", "weight"])
    names = meta.meta_df()[["ticker", "name"]].drop_duplicates("ticker")
    out = df.merge(names, on="ticker", how="left")
    return out[["rebal_date", "port_id", "ticker", "name", "weight"]].sort_values(
        ["rebal_date", "ticker"]
    ).reset_index(drop=True)


def metrics(port_id: int) -> pd.DataFrame:
    df = _read("metrics.parquet", filters=[("port_id", "==", port_id)])
    return df[METRIC_COLS].reset_index(drop=True)


def benchmark_nav(port_id: int) -> pd.DataFrame:
    df = _read("benchmark_nav.parquet", filters=[("port_id", "==", port_id)])
    return df[["trade_date", "value"]].sort_values("trade_date").reset_index(drop=True)


def benchmark_metrics(port_id: int) -> pd.DataFrame:
    df = _read("benchmark_metrics.parquet", filters=[("port_id", "==", port_id)])
    return df[METRIC_COLS].reset_index(drop=True)


# ---------- 생성·저장 (기존 db.create_portfolio / upload_* 계약) ----------


def create(port_name: str, algorithm: str, meta_ids: list[int], config: dict | None = None) -> int:
    """포트폴리오 등록 + 유니버스 기록. 반환: 새 port_id.

    config: 백테스트 실행 설정 (algorithm/rebal_freq/cost_bps/currency/params/benchmark).
    JSON 문자열로 portfolio.parquet의 config 컬럼에 저장된다 — 실전 추적(P7) 재료.
    구 행은 컬럼이 없거나 None으로 읽힌다.
    """
    st = meta.strategy_df()
    row = st[st["strategy"] == algorithm]
    if row.empty:
        raise ValueError(f"unknown algorithm: {algorithm}")
    strategy_id = int(row["strategy_id"].iloc[0])

    ports = _read("portfolio.parquet")
    if (ports["port_name"] == port_name).any():
        raise ValueError(f"portfolio name exists: {port_name}")
    port_id = int(ports["port_id"].max()) + 1 if not ports.empty else 1

    new = pd.DataFrame(
        [{
            "port_id": port_id,
            "port_name": port_name,
            "strategy_id": strategy_id,
            "created_at": datetime.utcnow(),
            "config": json.dumps(config) if config is not None else None,
        }]
    )
    storage.write_parquet(pd.concat([ports, new], ignore_index=True), DIR, "portfolio.parquet")

    uni = pd.DataFrame({"port_id": port_id, "meta_id": meta_ids})
    _upsert("universe.parquet", port_id, uni)
    return port_id


def save_nav(port_id: int, nav_series: pd.Series) -> None:
    df = nav_series.dropna().reset_index()
    df.columns = ["trade_date", "value"]
    df.insert(0, "port_id", port_id)
    _upsert("nav.parquet", port_id, df)


def save_rebalance(port_id: int, weights: pd.DataFrame) -> None:
    """weights: index=rebal_date, columns=tickers."""
    long = weights.stack().rename("weight").reset_index()
    long.columns = ["rebal_date", "ticker", "weight"]
    long = long[long["weight"].notna()]
    long.insert(0, "port_id", port_id)
    _upsert("rebalance.parquet", port_id, long)


def _save_metrics(name: str, port_id: int, values: dict) -> None:
    row = {"port_id": port_id, **{k: float(values[k]) for k in METRIC_COLS}}
    row["updated_at"] = datetime.utcnow()
    _upsert(name, port_id, pd.DataFrame([row]))


def save_metrics(port_id: int, values: dict) -> None:
    _save_metrics("metrics.parquet", port_id, values)


def save_benchmark_nav(port_id: int, nav_series: pd.Series) -> None:
    df = nav_series.dropna().reset_index()
    df.columns = ["trade_date", "value"]
    df.insert(0, "port_id", port_id)
    _upsert("benchmark_nav.parquet", port_id, df)


def save_benchmark_metrics(port_id: int, values: dict) -> None:
    _save_metrics("benchmark_metrics.parquet", port_id, values)


def delete(port_id: int) -> None:
    """포트폴리오와 부속 기록 전체 삭제 (저장 실패 롤백용)."""
    for name in _EMPTY:
        table = _read(name)
        if "port_id" in table.columns and (table["port_id"] == port_id).any():
            storage.write_parquet(table[table["port_id"] != port_id], DIR, name)
