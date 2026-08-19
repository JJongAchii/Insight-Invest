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
JUMP_LIMIT = 1.00     # 분할 계수 변동 없는 날의 미확인 실체 경계 상한. 상장일/개명 창으로
                      # 동일 실체가 확인되면 실제 급등으로 보존하고 경고만 남긴다. 실체가
                      # 미확인되면 경계 이후 현재 세그먼트만 제공한다 (전체 종목 삭제 금지).
JUMP_WARN = 0.25      # 경고 밴드 하한 — 25~100% 는 제외하지 않고 로그로만 남긴다


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


def _no_factor_jumps(px: pd.DataFrame) -> pd.Series:
    """분할 계수 변동이 없는 날의 |일수익| 시리즈 (계수 변동일 제외)."""
    r = px["adj_close"].pct_change().abs()
    f_changed = (px["adj_close"] / px["close"]).pct_change().abs() > 0.005
    return r[~f_changed]


def continuity_issues(px: pd.DataFrame, allow_large_jumps: bool = False) -> list[str]:
    """티커 계보 오염 감지 — 공백과 미확인 실체의 무분할 초대형 점프.

    ``allow_large_jumps``는 상장일/개명 창으로 동일 실체가 확인된 경우에만 쓴다.
    이때 실제 급등은 보존하되 별도 경고 대상으로 남긴다.
    """
    issues: list[str] = []
    d = px.index.values.astype("datetime64[D]")
    if len(d) > 1:
        gaps = np.busday_count(d[:-1], d[1:])
        if gaps.max() > GAP_LIMIT_TDAYS:
            i = int(gaps.argmax())
            issues.append(
                f"공백 {int(gaps.max())}영업일 ({px.index[i].date()}→{px.index[i+1].date()})"
            )
    if not allow_large_jumps:
        r = _no_factor_jumps(px)
        for dt, v in r[r > JUMP_LIMIT].items():
            issues.append(f"{dt.date()} |일수익| {v:.0%} (분할 계수 변동 없음)")
    return issues


def continuity_cutoff(
    px: pd.DataFrame, allow_large_jumps: bool = False
) -> pd.Timestamp | None:
    """마지막 미해결 연속성 경계에서 시작하는 현재 가격 세그먼트를 반환할 기준일.

    경계 이전 이력을 현재 실체와 잇는 것은 실패 폐쇄 원칙에 어긋나지만, 과거의
    정상 급등 하나 때문에 현재가까지 포함한 종목 전체를 삭제해서도 안 된다.
    공백이면 재관측 첫날, 무분할 초대형 점프면 점프 당일을 새 세그먼트 시작으로
    삼는다. 경계가 없으면 ``None``이다.
    """
    boundaries: list[pd.Timestamp] = []
    d = px.index.values.astype("datetime64[D]")
    if len(d) > 1:
        gaps = np.busday_count(d[:-1], d[1:])
        boundaries.extend(
            pd.Timestamp(px.index[i + 1])
            for i in np.flatnonzero(gaps > GAP_LIMIT_TDAYS)
        )
    if not allow_large_jumps:
        jumps = _no_factor_jumps(px)
        boundaries.extend(pd.Timestamp(value) for value in jumps[jumps > JUMP_LIMIT].index)
    return max(boundaries) if boundaries else None


def continuity_warnings(px: pd.DataFrame, include_large: bool = False) -> list[str]:
    """제외하지 않는 무분할 가격 점프. 검증된 실체면 100% 초과도 포함한다."""
    r = _no_factor_jumps(px)
    upper = pd.Series(True, index=r.index) if include_large else r <= JUMP_LIMIT
    return [
        f"{dt.date()} |일수익| {v:.0%}" for dt, v in r[(r > JUMP_WARN) & upper].items()
    ]


def entity_windows(
    events: pd.DataFrame, details: pd.DataFrame, finals: set[str], manual=None
) -> pd.DataFrame:
    """벤더 실체 경계 창 [final, src, start, end] — 개명 체인·상장일 기반 (D6).

    - 개명 체인(ticker_change 이벤트 ≥2)은 (src=event_ticker, start=event_date,
      end=다음 이벤트 전일) — T=SBC+T·META=FB+META 를 자동 재구성하고, 경계 밖
      행(다른 실체의 티커 재사용: Metamaterial 의 "META")은 창에 안 들어와 잘린다
    - 단일 이벤트는 개명 체인이 아니다 (동일 티커 리브랜드 실측: QQQ 2018) —
      상장일(list_date) 플로어만 적용해 상장 전 행(재사용 실체: COIN 2021 이전)을 자른다
    - manual(TICKER_SEGMENTS) 대상 final 은 창을 만들지 않는다 — ETF 개명은 벤더
      커버리지가 불완전해(QQQQ 부재 실측) 수동이 우선한다
    """
    manual = TICKER_SEGMENTS if manual is None else manual
    rows: list[dict] = []
    ev = events[events["event_type"] == "ticker_change"].dropna(subset=["event_date"])
    for t, g in ev.groupby("ticker"):
        if t not in finals or t in manual:
            continue
        g = g.sort_values("event_date")
        if len(g) < 2:
            continue
        starts = pd.to_datetime(g["event_date"]).tolist()
        srcs = g["event_ticker"].tolist()
        for i, (src, st) in enumerate(zip(srcs, starts)):
            end = starts[i + 1] - pd.Timedelta(days=1) if i + 1 < len(starts) else None
            rows.append({"final": t, "src": src, "start": st, "end": end})
    chained = {r["final"] for r in rows}
    if len(details):
        for t, ld in zip(details["ticker"], details["list_date"]):
            if t in finals and t not in manual and t not in chained and pd.notna(ld):
                rows.append({"final": t, "src": t, "start": pd.Timestamp(ld), "end": None})
    return pd.DataFrame(rows, columns=["final", "src", "start", "end"])


def drop_conflicting_windows(windows) -> tuple[pd.DataFrame, set[str]]:
    """같은 소스 티커의 겹치는 구간을 복수 final 이 청구하면 — 그 final 들의 창을
    통째로 폐기하고 충돌 목록을 반환한다 (무절단 폴백, 트립와이어 가드가 방어).

    실측: 주식 클래스 분화 티커(UA/UAA·LILA/LILAK·CENT/CENTA 등)는 벤더 개명
    체인이 같은 소스(예: "UA")의 겹치는 기간을 서로 청구한다 — 어느 쪽이 맞는지
    가격 데이터만으로 판정할 수 없으므로 자동 절단을 포기하는 것이 정직하다.
    """
    if windows is None or windows.empty:
        return windows, set()
    conflicted: set[str] = set()
    inf = pd.Timestamp.max
    for _, g in windows.groupby("src"):
        if len(g) < 2:
            continue
        g = g.sort_values("start")
        ends = g["end"].fillna(inf).tolist()
        starts = g["start"].tolist()
        fins = g["final"].tolist()
        for i in range(len(g) - 1):
            if ends[i] >= starts[i + 1]:  # 구간 겹침
                conflicted.update({fins[i], fins[i + 1]})
    if conflicted:
        windows = windows[~windows["final"].isin(conflicted)].reset_index(drop=True)
    return windows, conflicted


def ambiguous_srcs(windows, finals: set[str]) -> set[str]:
    """자기 창 없이 남의 체인 소스로만 등장하는 final 티커 — 문자열 재사용 충돌 후보.

    예: OLDCO 의 옛 티커 "ABC" 를 신생 회사가 재사용해 meta 에 등록됐는데 신생
    회사의 창(상장일)이 벤더 커버리지 갭으로 없는 경우. 이 티커의 미청구 행을
    지우면 신생 회사가 조용히 사라진다 — 보존 + 경고 대상으로 분리한다.
    """
    if windows is None or windows.empty:
        return set()
    return (set(windows["src"]) - set(windows["final"])) & finals


def apply_entity_windows(prices, dividends, windows, keep_unclaimed: set[str] | None = None):
    """실체 창 적용 — 창 밖 행(다른 실체) 절단 + 이전 티커 행을 현행 티커로 병합.

    수동 stitch_segments 와 같은 의미지만 수천 티커에 벡터화로 적용된다.
    - 원본 행이 두 창에 청구되면(창 겹침) 조용히 넘기지 않고 raise — 가격뿐 아니라
      배당의 이중 계상도 여기서 잡힌다
    - keep_unclaimed 티커(ambiguous_srcs)의 미청구 행은 자기 티커로 보존한다 —
      조용한 소실 금지. 청구된 행(다른 final 의 체인 구간)은 그쪽으로 병합된다
    """
    if windows is None or windows.empty:
        return prices, dividends
    keep_unclaimed = keep_unclaimed or set()
    involved = set(windows["src"]) | set(windows["final"])
    out = []
    for df, col in ((prices, "date"), (dividends, "ex_date")):
        base = df.reset_index(drop=True)
        w = windows.rename(columns={"src": "ticker"})
        hit = base.reset_index().merge(w, on="ticker", how="inner")
        keep = hit[col] >= hit["start"]
        keep &= hit["end"].isna() | (hit[col] <= hit["end"])
        hit = hit[keep]
        if hit["index"].duplicated().any():
            bad = sorted(hit.loc[hit["index"].duplicated(), "final"].unique()[:5])
            raise ValueError(f"실체 창 겹침 — 원본 행이 복수 창에 청구됨: {bad}")
        claimed = set(hit["index"])
        hit = hit.drop(columns=["index", "ticker", "start", "end"]).rename(
            columns={"final": "ticker"}
        )
        rest = base[~base["ticker"].isin(involved)]
        amb = base[
            base["ticker"].isin(keep_unclaimed) & ~base.index.isin(claimed)
        ]
        out.append(pd.concat([rest, hit[df.columns], amb], ignore_index=True))
    prices, dividends = out
    dup = prices.duplicated(subset=["ticker", "date"])
    if dup.any():
        bad = sorted(prices.loc[dup, "ticker"].unique()[:5])
        raise ValueError(f"실체 창 겹침 — (ticker,date) 중복: {bad}")
    return prices, dividends
