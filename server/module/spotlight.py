"""마켓 스포트라이트 선정 — 전시장 신호 스캔의 순수 로직.

build_insights.build_spotlight()가 이 모듈로 그룹을 선정해 parquet으로
떨어뜨리고, insight 라우터·텔레그램 브리핑이 그 parquet을 읽는다.
조건식은 반드시 build_signal_study()의 신호 정의와 같아야 한다 — 통계
(signal_study)와 선정(spotlight)이 다른 조건을 재면 실측치가 거짓말이 된다.
"""

import json

import numpy as np
import pandas as pd

# 그룹 순서 = 20일 기준선 대비 중앙값 내림차순 (2026-07-27 측정).
# 라우터는 서빙 시점의 signal_study로 다시 정렬한다 — 이 상수는 그 폴백이자
# 텔레그램의 표시 순서다.
GROUP_ORDER = ("near_52w_high_hold", "frgn_streak10", "bull_divergence")
GROUP_TITLES = {
    "near_52w_high_hold": "52주 신고가 근접 유지",
    "frgn_streak10": "외인 연속 순매수 10일+",
    "bull_divergence": "매집형 (주가↓·외인 매집)",
}
CAP_PER_GROUP = 5
NEAR_HIGH_RATIO = 0.98  # build_signal_study의 near_52w_high_* 와 동일
MIN_PERIODS_252 = 200

_OUT_COLS = [
    "signal_type",
    "rank",
    "ticker",
    "name",
    "market",
    "close",
    "chg_pct",
    "mktcap",
    "streak",
    "intensity_20d",
    "ret_20d",
    "hold_days",
    "dist_pct",
    "also_in",
]


def near_high_state(P: pd.DataFrame) -> pd.DataFrame:
    """마지막 거래일의 52주 신고가 근접 상태 [dist_pct, hold_days] (index=ticker).

    P: 일자×종목 adj_close 패널(index 오름차순). 상태 = adj_close >= 252일
    rolling max × 0.98 (min_periods 200 — build_signal_study와 동일).
    hold_days는 마지막 날짜에서 거슬러 올라간 연속 상태 일수로, 패널 길이에서
    포화된다 — 호출부는 충분한 창(>=520거래일)을 줘야 한다.
    """
    hi = P.rolling(252, min_periods=MIN_PERIODS_252).max()
    state = P >= hi * NEAR_HIGH_RATIO  # NaN 비교 → False
    last = state.iloc[-1]
    tickers = last[last].index
    if len(tickers) == 0:
        return pd.DataFrame(columns=["dist_pct", "hold_days"])

    sv = state[tickers].to_numpy()
    hold = np.cumprod(sv[::-1], axis=0).sum(axis=0)  # 말일부터 연속 True 길이
    dist = (P[tickers].iloc[-1] / hi[tickers].iloc[-1] - 1) * 100
    return pd.DataFrame({"dist_pct": dist.to_numpy(), "hold_days": hold.astype(int)}, index=tickers)


def _membership(flows_frgn: pd.DataFrame, near_high: pd.DataFrame) -> dict:
    """그룹별 후보 전체 (상한 적용 전, 그룹 내 정렬 완료)."""
    f = flows_frgn
    near = f.join(near_high, on="ticker", how="inner").sort_values(
        ["hold_days", "mktcap"], ascending=False
    )
    streak = f[f["streak"] >= 10].sort_values(["streak", "intensity_20d"], ascending=False)
    bull = f[(f["ret_20d"] < -5) & (f["intensity_20d"] > 0.3)].sort_values(
        "intensity_20d", ascending=False
    )
    return {"near_52w_high_hold": near, "frgn_streak10": streak, "bull_divergence": bull}


def select_spotlight(
    flows_frgn: pd.DataFrame, near_high: pd.DataFrame, cap: int = CAP_PER_GROUP
) -> tuple[pd.DataFrame, dict]:
    """그룹 3개 선정 → (긴 형식 DataFrame, 그룹별 잘린 종목 수).

    also_in은 상한 적용 전 조건 만족 기준이다 — 다른 그룹 상위 5에 못 들었어도
    조건에 해당하면 표시한다 (교집합은 배지일 뿐, 결합 성과는 측정된 바 없다).
    """
    members = _membership(flows_frgn, near_high)
    sets = {g: set(df["ticker"]) for g, df in members.items()}

    frames, dropped = [], {}
    for g in GROUP_ORDER:
        cand = members[g]
        if len(cand) > cap:
            dropped[g] = len(cand) - cap
        top = cand.head(cap).copy()
        top["signal_type"] = g
        top["rank"] = range(1, len(top) + 1)
        top["also_in"] = [
            json.dumps([o for o in GROUP_ORDER if o != g and t in sets[o]]) for t in top["ticker"]
        ]
        frames.append(top)

    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return out.reindex(columns=_OUT_COLS), dropped
