"""NAV 분석 유틸 — 백테스트 v2 응답의 analytics 블록 재료.

모든 함수는 datetime 인덱스의 NAV pd.Series를 받는다 (contribution 제외).
"""

from typing import List, Optional

import numpy as np
import pandas as pd

# (name, start, end) — 위기 리플레이 창
CRISIS_WINDOWS = [
    ("GFC 2008", "2007-10-01", "2009-03-31"),
    ("COVID 2020", "2020-02-14", "2020-04-30"),
    ("Inflation 2022", "2022-01-01", "2022-10-31"),
]


def drawdown_series(nav: pd.Series) -> pd.Series:
    """Drawdown at each date: nav / running-max − 1 (fraction, ≤ 0)."""
    return nav / nav.cummax() - 1


def rolling_sharpe(nav: pd.Series, window: int = 252) -> pd.Series:
    """Rolling Sharpe: rolling mean/std of daily pct_change × √252 (NaN dropped)."""
    ret = nav.pct_change()
    return (ret.rolling(window).mean() / ret.rolling(window).std() * np.sqrt(252)).dropna()


def period_returns(nav: pd.Series, freq: str) -> pd.Series:
    """Period returns (fraction) resampled to month/year ends.

    freq="M": labels "YYYY-MM"; freq="Y": labels "YYYY".
    Uses resample-last then pct_change (first period dropped).
    """
    if freq == "M":
        last = nav.resample("ME").last()
        labels = last.index.strftime("%Y-%m")
    elif freq == "Y":
        last = nav.resample("YE").last()
        labels = last.index.strftime("%Y")
    else:
        raise ValueError(f"freq must be 'M' or 'Y', got '{freq}'")

    out = last.pct_change()
    out.index = labels
    return out.dropna()


def contribution(book: pd.DataFrame, price: pd.DataFrame) -> pd.Series:
    """Approximate additive per-ticker return contribution.

    contribution_i = Σ_t w_i(t) × r_i(t→t+1), using the drifted holdings `book`
    (long form: index Date, columns ticker/weights) and daily prices. This is an
    additive approximation — cross-compounding between periods is ignored, so the
    per-ticker values sum only approximately to the portfolio total return.
    """
    wide = (
        book.reset_index()
        .pivot_table(index="Date", columns="ticker", values="weights", aggfunc="mean")
        .sort_index()
    )
    px = price.loc[wide.index.min() :, wide.columns.intersection(price.columns)]
    ret = px.pct_change()
    # weight held at t applied to the return realized from t to t+1
    w = wide.reindex(px.index).ffill()
    contrib = (w.shift(1) * ret).sum()
    return contrib.reindex(wide.columns).fillna(0.0)


def crisis_windows(nav: pd.Series) -> List[dict]:
    """Crisis replay stats for predefined windows overlapping the NAV range ≥60%.

    Each entry: {name, start, end, ret (window total return %), mdd (%),
    recovery_days (days from window trough until nav regains the pre-trough
    peak, None if never)}. Windows outside the NAV range are skipped.
    """
    if nav.empty:
        return []

    nav = nav.dropna().sort_index()
    nav_start, nav_end = nav.index.min(), nav.index.max()
    out: List[dict] = []

    for name, start, end in CRISIS_WINDOWS:
        w_start, w_end = pd.Timestamp(start), pd.Timestamp(end)
        overlap = (min(w_end, nav_end) - max(w_start, nav_start)).days
        if overlap <= 0 or overlap / (w_end - w_start).days < 0.6:
            continue

        window = nav.loc[w_start:w_end]
        if len(window) < 2:
            continue

        ret = window.iloc[-1] / window.iloc[0] - 1
        dd = window / window.cummax() - 1
        mdd = dd.min()

        # Recovery: days from the window trough until nav regains the pre-trough peak
        trough_date = dd.idxmin()
        pre_trough_peak = window.loc[:trough_date].max()
        after = nav.loc[trough_date:]
        recovered = after[after >= pre_trough_peak]
        recovery_days: Optional[int] = (
            int((recovered.index[0] - trough_date).days) if not recovered.empty else None
        )

        out.append(
            {
                "name": name,
                "start": start,
                "end": end,
                "ret": round(float(ret) * 100, 2),
                "mdd": round(float(mdd) * 100, 2),
                "recovery_days": recovery_days,
            }
        )

    return out
