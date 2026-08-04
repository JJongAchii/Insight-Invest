"""US 가격 순수 계산 — massive 미러 기반 총수익 합성·세그먼트 스티칭·연속성 가드.

스펙: docs/superpowers/specs/2026-08-04-us-price-source-unification-design.md D3·D5.
massive adj_close 는 분할만 조정, 배당은 us_dividends 원액면(당시 주수 기준) —
그날의 수정계수 F 를 곱해 현재 주수 기준으로 환산한 뒤 총수익을 합성한다.
"""

import numpy as np
import pandas as pd

# 같은 티커에 다른 실체가 살았던 구간을 날짜 경계로 잇는다 (QQQQ 시대 1,588거래일).
# 단순 합집합이면 META 처럼 남의 회사 구간까지 끌려온다 — 반드시 경계를 명시한다.
TICKER_SEGMENTS: dict[str, list[tuple[str, str | None, str | None]]] = {
    "QQQ": [("QQQ", None, "2004-11-30"), ("QQQQ", "2004-12-01", "2011-03-22"),
            ("QQQ", "2011-03-23", None)],
}

GAP_LIMIT_TDAYS = 10  # 관측 간 영업일 공백 상한 — 초과는 티커 재배정·수집 구멍 신호
JUMP_LIMIT = 0.25     # 분할 계수 변동 없는 날의 일수익 상한 — 초과는 계보 오염 신호


def _cut(df: pd.DataFrame, col: str, src: str, start: str | None, end: str | None) -> pd.DataFrame:
    m = df["ticker"] == src
    if start:
        m &= df[col] >= pd.Timestamp(start)
    if end:
        m &= df[col] <= pd.Timestamp(end)
    return df[m]


def stitch_segments(prices, dividends, segments):
    """세그먼트 대상 티커의 가격·배당 행을 날짜 경계로 잘라 현행 티커로 병합."""
    for final, segs in segments.items():
        p_parts = [_cut(prices, "date", s, a, b).assign(ticker=final) for s, a, b in segs]
        d_parts = [_cut(dividends, "ex_date", s, a, b).assign(ticker=final) for s, a, b in segs]
        stitched = pd.concat(p_parts, ignore_index=True)
        if stitched["date"].duplicated().any():
            raise ValueError(f"{final}: 세그먼트 겹침 — 경계 날짜 재확인 필요")
        involved = {s for s, _, _ in segs} | {final}
        prices = pd.concat(
            [prices[~prices["ticker"].isin(involved)], stitched], ignore_index=True
        )
        dividends = pd.concat(
            [dividends[~dividends["ticker"].isin(involved)],
             pd.concat(d_parts, ignore_index=True)],
            ignore_index=True,
        )
    return prices, dividends


def compose_total_return(px: pd.DataFrame, div: pd.DataFrame) -> pd.DataFrame:
    """단일 티커 TR 합성 — r_t = (adj_t + div_t×F_t)/adj_{t-1} − 1.

    adj_close(TR)는 최신 관측치를 앵커로 역누적 — 최신값이 원 adj_close 와 같아
    기존 소비자(모멘텀·NAV)와 연속적이다. 첫 행 gross_return 은 NaN (pct_change 관례).
    """
    f = px["adj_close"] / px["close"]
    cash = (
        div.groupby("ex_date")["cash_amount"].sum().reindex(px.index).fillna(0.0)
        if len(div)
        else pd.Series(0.0, index=px.index)
    )
    r = (px["adj_close"] + cash * f) / px["adj_close"].shift(1) - 1
    growth = (1 + r.fillna(0.0)).cumprod()
    tr = px["adj_close"].iloc[-1] * growth / growth.iloc[-1]
    return pd.DataFrame({"adj_close": tr, "gross_return": r})


def continuity_issues(px: pd.DataFrame) -> list[str]:
    """티커 계보 오염 감지 — 공백(영업일)·무분할 점프. 빈 리스트 = 통과."""
    issues: list[str] = []
    d = px.index.values.astype("datetime64[D]")
    if len(d) > 1:
        gaps = np.busday_count(d[:-1], d[1:])
        if gaps.max() > GAP_LIMIT_TDAYS:
            i = int(gaps.argmax())
            issues.append(
                f"공백 {int(gaps.max())}영업일 ({px.index[i].date()}→{px.index[i+1].date()})"
            )
    r = px["adj_close"].pct_change().abs()
    f_changed = (px["adj_close"] / px["close"]).pct_change().abs() > 0.005
    for dt, v in r[(r > JUMP_LIMIT) & ~f_changed].items():
        issues.append(f"{dt.date()} |일수익| {v:.0%} (분할 계수 변동 없음)")
    return issues
