"""KRX 거래일 — 계획 상장일의 전 거래일(결정 시점)을 정한다.

`exchange_calendars`의 XKRX를 쓰고, 그 달력이 모르는 휴장을 뺀다(kr-etf-mp `forward/calendar.py`와
같은 규칙). 한국거래소는 2026-06-03(지방선거일)과 2026-07-17(제헌절 — 2026년 법정공휴일 재지정)에
휴장했다. 제헌절은 2026년부터 해마다 빼고, 그 밖의 임시 휴장은 `EXTRA_CLOSURES`에 적는다.
달력이 틀려도 기록이 틀린 시점의 정보를 쓰지는 않는다 — 기록 장치는 레이크의 마지막 KRX 날짜가
여기서 정한 결정 시점과 같을 때만 쓴다.
"""

from __future__ import annotations

from functools import lru_cache

import exchange_calendars as xc
import pandas as pd

EXTRA_CLOSURES = (pd.Timestamp("2026-06-03"), pd.Timestamp("2026-07-17"))
CONSTITUTION_DAY_FROM = 2026  # 7월 17일
CALENDAR_START, CALENDAR_END = "2015-01-01", "2032-12-31"


@lru_cache(maxsize=1)
def _calendar():
    return xc.get_calendar("XKRX", start=CALENDAR_START, end=CALENDAR_END)


def sessions(start, end) -> pd.DatetimeIndex:
    out = _calendar().sessions_in_range(pd.Timestamp(start), pd.Timestamp(end))
    out = pd.DatetimeIndex(out.tz_localize(None) if out.tz is not None else out)
    out = out.difference(pd.DatetimeIndex(EXTRA_CLOSURES))
    constitution = (out.month == 7) & (out.day == 17) & (out.year >= CONSTITUTION_DAY_FROM)
    return out[~constitution].as_unit("ns")


def is_session(t) -> bool:
    t = pd.Timestamp(t).normalize()
    return t in sessions(t, t)


def previous_session(t) -> pd.Timestamp:
    """t 바로 앞 KRX 거래일."""
    t = pd.Timestamp(t).normalize()
    earlier = sessions(t - pd.Timedelta(days=21), t - pd.Timedelta(days=1))
    if earlier.empty:
        raise ValueError(f"{t.date()} 앞 3주 안에 KRX 거래일이 없다 — 달력을 갱신한다")
    return earlier[-1]
