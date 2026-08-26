"""KR 장중 스냅샷 순수 로직 (스펙 2026-08-11 D2·D3).

불변식: 종목 등락률은 KRX 제공값을 그대로 쓴다(자체 계산 금지 — 당일 배당락·
분할이 있으면 보관 종가 기반 계산이 어긋나는 것이 정상이고, 그래서 금지다).
산출물은 앱 평면 두 파일 전용이며 레이크·백테스트 경로와 무관하다.
"""

from __future__ import annotations

from datetime import datetime, time as dtime, timedelta, timezone

import numpy as np
import pandas as pd

KST = timezone(timedelta(hours=9))
STALE_MINUTES = 20      # 10분 폴 주기 + 여유 10분
MOVER_MIN_CAP = 1e11    # 급등락 순위: 시총 1,000억 이상
MOVER_MIN_VALUE = 3e9   # 급등락 순위: 당일 거래대금 30억 이상
TOP_N = 10

_SNAP_COLS = {"시가": "open", "고가": "high", "저가": "low", "종가": "close",
              "거래량": "volume", "거래대금": "value", "등락률": "chg_pct",
              "시가총액": "cap"}
_ETF_SNAP_COLS = {"종가": "close", "거래량": "volume", "거래대금": "value",
                  "등락률": "chg_pct"}


def normalize_snapshot(
    frames: dict[str, pd.DataFrame], as_of: str, trade_date: str
) -> pd.DataFrame:
    """pykrx 시장별 프레임(한글 컬럼, 티커 인덱스) → 영문 스키마 단일 프레임."""
    parts = []
    for market, df in frames.items():
        d = df.rename(columns=_SNAP_COLS)[list(_SNAP_COLS.values())].copy()
        d.index.name = "ticker"
        d = d.reset_index()
        d["market"] = market
        parts.append(d)
    out = pd.concat(parts, ignore_index=True)
    out = out[out["close"] > 0].reset_index(drop=True)  # 거래정지·미형성 봉 제외
    out["as_of"] = as_of
    out["trade_date"] = trade_date
    return out


def normalize_etf_snapshot(
    frame: pd.DataFrame, as_of: str, trade_date: str
) -> pd.DataFrame:
    """pykrx ETF 전종목 등락률 → 내 종목 표시 전용 장중 스냅샷.

    ETF는 일반 주식의 시총·업종 집계에 섞지 않는다. 등락률은 가격비로 다시
    계산하지 않고 KRX ``FLUC_RT``를 pykrx가 변환한 값을 그대로 보존한다.
    """
    columns = ["ticker", *list(_ETF_SNAP_COLS.values()), "as_of", "trade_date"]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    missing = set(_ETF_SNAP_COLS) - set(frame.columns)
    if missing:
        raise ValueError(f"ETF 장중 필수 열 누락: {sorted(missing)}")
    out = frame.rename(columns=_ETF_SNAP_COLS)[list(_ETF_SNAP_COLS.values())].copy()
    out.index.name = "ticker"
    out = out.reset_index()
    out["ticker"] = out["ticker"].astype(str).str.zfill(6)
    out = out[out["close"] > 0].reset_index(drop=True)
    out["as_of"] = as_of
    out["trade_date"] = trade_date
    return out[columns]


def with_sector(latest: pd.DataFrame, sector_map: pd.DataFrame) -> pd.DataFrame:
    """업종·종목명 병합. 미분류(월초 이후 신규상장 등)는 sector='기타', name=''."""
    d = latest.merge(sector_map[["ticker", "sector", "name"]], on="ticker", how="left")
    d["sector"] = d["sector"].fillna("기타")
    d["name"] = d["name"].fillna("")
    return d


def index_rows(levels, prev_closes, as_of: str, trade_date: str) -> pd.DataFrame:
    rows = []
    for key, level in levels.items():
        prev = prev_closes.get(key)
        chg = (level / prev - 1) * 100 if prev else np.nan
        rows.append({"as_of": as_of, "trade_date": trade_date, "kind": "index",
                     "key": key, "level": float(level), "chg_pct": chg})
    return pd.DataFrame(rows)


def breadth_row(latest: pd.DataFrame, as_of: str, trade_date: str) -> pd.DataFrame:
    s = latest["chg_pct"]
    return pd.DataFrame([{
        "as_of": as_of, "trade_date": trade_date, "kind": "breadth", "key": "ALL",
        "advancers": int((s > 0).sum()), "decliners": int((s < 0).sum()),
        "unchanged": int((s == 0).sum()),
    }])


def sector_rows(latest_with_sector: pd.DataFrame, as_of: str, trade_date: str) -> pd.DataFrame:
    """등락률 NaN 종목은 집계에서 제외한다(np.average는 NaN을 skip하지 않고
    전파한다 — 종목 하나만 결측이어도 섹터 전체가 NaN이 되고, 그게 타임라인에
    박히면 서빙 JSONResponse(allow_nan=False)가 라우터 try/except 밖에서 500을
    낸다). value_krw/n은 결측 종목도 포함한 전체 그룹 기준을 유지한다."""
    rows = []
    for sector, g in latest_with_sector.groupby("sector"):
        gv = g.dropna(subset=["chg_pct"])
        if gv.empty:
            chg = float("nan")
        else:
            w = gv["cap"].clip(lower=0)
            chg = float(np.average(gv["chg_pct"], weights=w)) if w.sum() > 0 \
                else float(gv["chg_pct"].mean())
        rows.append({"as_of": as_of, "trade_date": trade_date, "kind": "sector",
                     "key": sector, "chg_pct": chg,
                     "value_krw": float(g["value"].sum()), "n": len(g)})
    return pd.DataFrame(rows)


def merge_timeline(existing: pd.DataFrame | None, new_rows: pd.DataFrame) -> pd.DataFrame:
    """당일이면 append, 날짜가 바뀌면 리셋 — 타임라인은 당일만 보존한다."""
    if existing is None or existing.empty:
        return new_rows
    today = new_rows["trade_date"].iloc[0]
    if (existing["trade_date"] != today).any():
        return new_rows
    return pd.concat([existing, new_rows], ignore_index=True)


def is_open_kst(now: datetime) -> bool:
    t = now.astimezone(KST)
    return t.weekday() < 5 and dtime(9, 0) <= t.time() < dtime(15, 30)


def snapshot_active(trade_date: str, as_of: str, now: datetime) -> bool:
    """서빙 강등 판정. 장중 20분 스테일 또는 2영업일 이상 낡음 → False."""
    t = now.astimezone(KST)
    if int(np.busday_count(trade_date, t.strftime("%Y-%m-%d"))) >= 2:
        return False
    if is_open_kst(t):
        as_of_dt = datetime.strptime(as_of, "%Y-%m-%d %H:%M").replace(tzinfo=KST)
        if (t - as_of_dt) > timedelta(minutes=STALE_MINUTES):
            return False
    return True


def top_value(latest: pd.DataFrame, n: int = TOP_N) -> pd.DataFrame:
    return latest.nlargest(n, "value")


def top_movers(latest: pd.DataFrame, n: int = TOP_N) -> tuple[pd.DataFrame, pd.DataFrame]:
    eligible = latest[(latest["cap"] >= MOVER_MIN_CAP) & (latest["value"] >= MOVER_MIN_VALUE)]
    return eligible.nlargest(n, "chg_pct"), eligible.nsmallest(n, "chg_pct")
