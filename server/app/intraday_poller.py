"""KR 장중 폴러 — Lambda 엔트리포인트 (스펙 2026-08-11 D1).

서빙과 같은 컨테이너 이미지에서 CMD 오버라이드("app.intraday_poller.handler")로
뜬다. EventBridge는 UTC 00:05~05:55와 06:05~06:55 두 룰로 나눠
09:05~15:55 KST에 정확히 10분 간격으로 호출한다. KRX 시세가 약 20분 늦어 15:30 종가는 15:55 폴에 들어온다.
실패 시 파일을 갱신하지 않고 예외를 올린다 — 강등은 서빙의 스테일 가드 책임이므로
여기서 삼키지 않는다.
"""

import logging
import os
from datetime import datetime

import pandas as pd

from datastore import storage
from module import kr_intraday as ki
from module import market_map
from module.market_desk import market_input
from module.market_groups import load_themes

logger = logging.getLogger(__name__)

INDICES = {"KOSPI": "1001", "KOSDAQ": "2001"}
LATEST_KEY = "kr_intraday_latest.parquet"
ETF_LATEST_KEY = "kr_intraday_etf_latest.parquet"
TIMELINE_KEY = "kr_intraday_timeline.parquet"
MAP_KEY = "kr_intraday_map.json"
BASELINE_PATH = ("insight", "kr_value_baseline.parquet")
# 야간 배치가 며칠 실패해도 20거래일 평균은 크게 변하지 않는다. 그보다 오래되면 쏠림을 비운다. 달력일로 세서
# 추석·설 연휴(평일 5일 남짓 휴장) 다음 날의 하루 묵은 기준선을 버리지 않는다 — 약 5~7거래일.
BASELINE_MAX_AGE_DAYS = 10


def _fetch_krx(today: str):
    """pykrx 5호출(직전 종가 2호출은 _prev_index_closes). KRX_ID/KRX_PW는 Lambda env — pykrx가 import 시점에 로그인하고
    세션 만료(1h)는 pykrx 1.2+ get_auth_session이 자동 재로그인한다."""
    from pykrx import stock  # lazy: env 자격증명 로그인 선행

    frames = {m: stock.get_market_ohlcv_by_ticker(today, market=m)
              for m in ("KOSPI", "KOSDAQ")}
    levels = {}
    for key, code in INDICES.items():
        idx = stock.get_index_ohlcv_by_date(today, today, code)
        if not idx.empty:
            levels[key] = float(idx["종가"].iloc[-1])
    try:
        etfs = stock.get_etf_price_change_by_ticker(today, today)
    except Exception:  # ETF 실패가 주식 시장 전체 스냅샷을 중단하지 않게 격리
        logger.warning("ETF 장중 조회 실패 — ETF 직전 스냅샷 유지", exc_info=True)
        etfs = pd.DataFrame()
    return frames, levels, etfs


def _sector_map() -> pd.DataFrame:
    lake = os.environ["QDATA_LAKE"]
    df = pd.read_parquet(f"{lake}/clean/krx_sector.parquet",
                         columns=["date", "ticker", "sector", "name"])
    latest = df[df["date"] == df["date"].max()]
    return latest[["ticker", "sector", "name"]].drop_duplicates("ticker")


def _index_daily(start: str, end: str, code: str) -> pd.DataFrame:
    from pykrx import stock  # lazy: env 자격증명 로그인 선행

    return stock.get_index_ohlcv_by_date(start, end, code)


def _prev_index_closes(trade_date: str) -> dict[str, float]:
    """KRX가 준 직전 거래일 종가. 거래일은 KRX가 알므로 공휴일 다음 날에도 맞고, 야간 미러가 며칠 낡아도 그 값을
    '전일 종가'로 쓰는 일이 없다(2026-08 스모크의 7/28 스테일 미러 +6%/+20% 왜곡). 조회가 실패하거나 직전 거래일이
    없으면 그 지수만 빼고, index_rows()가 chg_pct=NaN으로 넘겨 서빙이 null로 강등한다."""
    end = pd.Timestamp(trade_date)
    out = {}
    for key, code in INDICES.items():
        try:
            daily = _index_daily((end - pd.Timedelta(days=20)).strftime("%Y%m%d"), end.strftime("%Y%m%d"), code)
            before = daily[pd.to_datetime(daily.index) < end]
        except Exception:
            logger.warning(f"{key} 직전 거래일 종가 조회 실패 — chg_pct 생략", exc_info=True)
            continue
        if before.empty:
            logger.warning(f"{key} 직전 거래일 종가 없음({trade_date} 기준) — chg_pct 생략")
            continue
        out[key] = float(before["종가"].iloc[-1])
    return out


def _value_baseline(trade_date: str) -> pd.DataFrame | None:
    """야간 배치가 만든 종목별 평소 거래대금. 없거나 오래됐으면 None — 쏠림만 비운다."""
    try:
        df = storage.read_parquet(*BASELINE_PATH)
    except (FileNotFoundError, OSError):
        return None
    if df.empty:
        return None
    as_of = pd.Timestamp(df["as_of"].max()).strftime("%Y-%m-%d")
    if as_of >= trade_date or (pd.Timestamp(trade_date) - pd.Timestamp(as_of)).days > BASELINE_MAX_AGE_DAYS:
        logger.warning(f"거래대금 기준선 {as_of} — {trade_date} 기준으로 쓰지 않음")
        return None
    return df[["ticker", "avg_value"]]


def _publish_map(rows: pd.DataFrame, latest: pd.DataFrame, trade_date: str, observed_at: str) -> dict:
    """지도와 당일 시계열(노트 이후 변화용). 날짜가 바뀌면 시계열을 새로 시작한다."""
    indices = {r.key: {"level": float(r.level), "chg_pct": None if pd.isna(r.chg_pct) else float(r.chg_pct)}
               for r in rows[rows["kind"].eq("index")].itertuples()}
    built = market_map.build_map(latest, indices, _value_baseline(trade_date), load_themes(), observed_at)
    previous = storage.read_json(MAP_KEY) if storage.exists(MAP_KEY) else None
    series = previous["series"] if previous and previous.get("trade_date") == trade_date else []
    storage.write_json({"version": 1, "trade_date": trade_date, "latest": built,
                        "series": [*series, market_map.series_entry(built)]}, MAP_KEY)
    return built


def handler(event, context):
    now = datetime.now(ki.KST)
    today = now.strftime("%Y%m%d")
    frames, levels, etfs = _fetch_krx(today)
    if not levels:
        logger.info("지수 당일 행 없음 — 휴장 no-op")
        return {"status": "holiday-noop"}

    trade_date = now.strftime("%Y-%m-%d")
    as_of = now.strftime("%Y-%m-%d %H:%M")
    latest = ki.normalize_snapshot(frames, as_of, trade_date)
    latest = ki.with_sector(latest, _sector_map())
    etf_latest = ki.normalize_etf_snapshot(etfs, as_of, trade_date)

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
    etf_status = "degraded"
    if not etf_latest.empty:
        try:
            storage.write_parquet(etf_latest, ETF_LATEST_KEY)
            etf_status = "ok"
        except Exception:  # 핵심 주식 스냅샷은 이미 정상 발행됐으므로 ETF만 격리
            logger.warning("ETF 장중 스냅샷 저장 실패 — 직전 파일 유지", exc_info=True)
    else:
        logger.warning("ETF 장중 응답이 비어 있음 — 직전 스냅샷 유지")
    # A map failure must not stop the snapshot the rest of the app reads.
    try:
        built = _publish_map(rows, latest, trade_date, now.replace(second=0, microsecond=0).isoformat())
        map_status = "ok"
    except Exception:
        logger.exception("장중 시장 지도 저장 실패")
        built, map_status = None, "degraded"
    # The web app and the private editor share observations, never model credentials.
    try:
        storage.write_json(market_input(timeline, latest, now, built), "market_desk", "input.json")
        desk_status = "ok"
    except Exception:
        logger.exception("장중 해설 관측값 저장 실패")
        desk_status = "degraded"
    return {"status": "ok", "tickers": len(latest),
            "etfs": len(etf_latest), "etf_status": etf_status,
            "market_desk_status": desk_status, "map_status": map_status,
            "polls": int(timeline["as_of"].nunique())}
