"""KR 장중 폴러 — Lambda 엔트리포인트 (스펙 2026-08-11 D1).

서빙과 같은 컨테이너 이미지에서 CMD 오버라이드("app.intraday_poller.handler")로
뜬다. EventBridge cron(5,35 0-6 ? * MON-FRI *) UTC = 09:05~15:35 KST 30분 간격.
실패 시 파일을 갱신하지 않고 예외를 올린다 — 강등은 서빙의 스테일 가드 책임이므로
여기서 삼키지 않는다.
"""

import logging
import os
from datetime import datetime

import numpy as np
import pandas as pd

from datastore import storage
from module import kr_intraday as ki

logger = logging.getLogger(__name__)

INDICES = {"KOSPI": "1001", "KOSDAQ": "2001"}
LATEST_KEY = "kr_intraday_latest.parquet"
TIMELINE_KEY = "kr_intraday_timeline.parquet"


def _fetch_krx(today: str):
    """pykrx 4호출. KRX_ID/KRX_PW는 Lambda env — pykrx가 import 시점에 로그인하고
    세션 만료(1h)는 pykrx 1.2+ get_auth_session이 자동 재로그인한다."""
    from pykrx import stock  # lazy: env 자격증명 로그인 선행

    frames = {m: stock.get_market_ohlcv_by_ticker(today, market=m)
              for m in ("KOSPI", "KOSDAQ")}
    levels = {}
    for key, code in INDICES.items():
        idx = stock.get_index_ohlcv_by_date(today, today, code)
        if not idx.empty:
            levels[key] = float(idx["종가"].iloc[-1])
    return frames, levels


def _sector_map() -> pd.DataFrame:
    lake = os.environ["QDATA_LAKE"]
    df = pd.read_parquet(f"{lake}/clean/krx_sector.parquet",
                         columns=["date", "ticker", "sector", "name"])
    latest = df[df["date"] == df["date"].max()]
    return latest[["ticker", "sector", "name"]].drop_duplicates("ticker")


def _prev_index_closes(trade_date: str) -> dict[str, float]:
    """미러(krx_index_prices)의 최신 행이 전영업일 종가가 아니면 그 지수는
    통째로 뺀다. 야간 파이프라인이 실패해도 미러는 그냥 며칠 전 값을 들고
    있으므로, 프레시니스를 안 보면 폴러가 그 값을 '오늘 등락률'인 양 조용히
    거짓말한다 — 이 설계에서 유일하게 강등이 아니라 거짓말하는 실패 경로였다
    (2026-08 스모크에서 7/28 스테일 미러로 +6%/+20% 왜곡 실측). 빠진 키는
    index_rows()가 chg_pct=NaN으로 넘기고, 서빙이 그걸 null로 강등한다."""
    lake = os.environ["QDATA_LAKE"]
    df = pd.read_parquet(f"{lake}/clean/krx_index_prices.parquet",
                         columns=["date", "index_code", "close"],
                         filters=[("index_code", "in", list(INDICES.values()))])
    code_to_key = {v: k for k, v in INDICES.items()}
    prev_bday = str(np.busday_offset(trade_date, -1, roll="backward"))
    out = {}
    for code, g in df.groupby("index_code"):
        g = g.sort_values("date")
        max_date = pd.Timestamp(g["date"].iloc[-1]).strftime("%Y-%m-%d")
        key = code_to_key.get(code, code)
        if max_date != prev_bday:
            logger.warning(
                f"{key} 지수 미러 스테일 — 최신 {max_date}, 기대 전영업일 "
                f"{prev_bday}({trade_date} 기준) — chg_pct 생략")
            continue
        out[key] = float(g["close"].iloc[-1])
    return out


def handler(event, context):
    now = datetime.now(ki.KST)
    today = now.strftime("%Y%m%d")
    frames, levels = _fetch_krx(today)
    if not levels:
        logger.info("지수 당일 행 없음 — 휴장 no-op")
        return {"status": "holiday-noop"}

    trade_date = now.strftime("%Y-%m-%d")
    as_of = now.strftime("%Y-%m-%d %H:%M")
    latest = ki.normalize_snapshot(frames, as_of, trade_date)
    latest = ki.with_sector(latest, _sector_map())

    rows = pd.concat([
        ki.index_rows(levels, _prev_index_closes(trade_date), as_of, trade_date),
        ki.breadth_row(latest, as_of, trade_date),
        ki.sector_rows(latest, as_of, trade_date),
    ], ignore_index=True)
    existing = (storage.read_parquet(TIMELINE_KEY)
                if storage.exists(TIMELINE_KEY) else None)
    timeline = ki.merge_timeline(existing, rows)

    storage.write_parquet(latest, LATEST_KEY)
    storage.write_parquet(timeline, TIMELINE_KEY)
    return {"status": "ok", "tickers": len(latest),
            "polls": int(timeline["as_of"].nunique())}
