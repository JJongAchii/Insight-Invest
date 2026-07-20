#!/usr/bin/env python
"""로컬 일일 파이프라인용 인사이트 사전계산 빌더 (P4에서 확장 예정).

Lambda가 아닌 로컬에서 실행한다 — qdata 레이크(QDATA_LAKE)를 읽어
APP_DATA(기본 s3://insight-invest-datalake/app) 아래 parquet로 결과를 쓴다.

현재 빌더:
- regime_asset_perf: 매크로 4국면(module.regime.phase_history) × 자산 월간수익
  (SPY/QQQ/TLT/GLD/DBC + KOSPI) — 국면별 평균 월수익/연환산/승률/표본수.
  국면 라벨은 발표시차 반영(look-ahead 없음), 같은 달 수익과 동월 조인 —
  "이 국면일 때 무엇이 좋았나"의 기술통계 용도.

사용:
    APP_DATA=... QDATA_LAKE=... python scripts/build_insights.py
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))

from datastore import storage  # noqa: E402
from module import regime  # noqa: E402
from qdata import api as qdata_api  # noqa: E402

ETF_TICKERS = ["SPY", "QQQ", "TLT", "GLD", "DBC"]


def _monthly_returns() -> pd.DataFrame:
    """자산별 월간 수익률(%) — 월말 종가 기준, 인덱스는 월간 Period."""
    px = qdata_api.load_prices(ETF_TICKERS, fields=("adj_close",))["adj_close"]
    rets = px.resample("ME").last().pct_change() * 100

    idx = qdata_api.load_krx_index()
    kospi = (
        idx[idx["index"] == "KOSPI"].set_index("date")["close"].sort_index()
    )
    rets["KOSPI"] = kospi.resample("ME").last().pct_change() * 100

    rets.index = pd.PeriodIndex(rets.index, freq="M")
    return rets


def build_regime_asset_perf() -> pd.DataFrame:
    phases = regime.phase_history()["phase"]
    rets = _monthly_returns()

    long = rets.stack().rename("ret").reset_index()
    long.columns = ["month", "ticker", "ret"]
    long["phase"] = long["month"].map(phases)
    long = long.dropna(subset=["phase", "ret"])

    rows = []
    for (phase, ticker), g in long.groupby(["phase", "ticker"]):
        mean_pct = g["ret"].mean()
        rows.append(
            {
                "phase": phase,
                "ticker": ticker,
                "mean_monthly_ret": mean_pct,
                "ann_ret": ((1 + mean_pct / 100) ** 12 - 1) * 100,
                "hit_rate": (g["ret"] > 0).mean() * 100,
                "n_months": int(len(g)),
            }
        )
    df = pd.DataFrame(rows).sort_values(["phase", "ticker"]).reset_index(drop=True)
    df["as_of"] = pd.Timestamp.today().strftime("%Y-%m-%d")
    return df


def main():
    df = build_regime_asset_perf()
    target = storage.write_parquet(df, "insight", "regime_asset_perf.parquet")
    print(f"regime_asset_perf → {target} ({len(df)} rows, as_of={df['as_of'].iloc[0]})")
    with pd.option_context("display.width", 120, "display.max_rows", 50):
        print(df.drop(columns="as_of").round(2).to_string(index=False))


if __name__ == "__main__":
    main()
