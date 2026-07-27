"""Evidence Pack 조립 — 브리프의 유일한 사실 출처.

기저율 조인이 이 모듈의 핵심이다. build_insights의 signal_study(이벤트 스터디)와
flows_signals(종목별 현재값)이 같은 정의를 쓰므로, 조건식을 재계산해 조인하면
"신호"에 표본 수·승률·중앙값이 붙어 "확률"이 된다.
"""

import pandas as pd

# signal_study의 conds와 반드시 동일해야 한다 (scripts/build_insights.py:build_signal_study).
# flows_signals의 divergence 라벨은 ret_20d < 0 기준이라 여기 쓰면 안 된다.
BASE_RATE_SIGNALS = {
    "frgn_streak10": lambda r: r["streak"] >= 10,
    "high_intensity": lambda r: r["intensity_20d"] >= 1.0,
    "bull_divergence": lambda r: r["ret_20d"] < -5 and r["intensity_20d"] > 0.3,
}

SIGNAL_HORIZONS = (5, 20, 60)


def match_base_rate_signals(frgn_row: dict) -> list[str]:
    """flows_signals의 investor=='frgn' 행 → 현재 발화 중인 signal_study 신호명 목록.

    결측치나 키 부재는 미발화로 취급한다 (예외를 올리지 않는다).
    """
    matched = []
    for name, cond in BASE_RATE_SIGNALS.items():
        try:
            if cond(frgn_row):
                matched.append(name)
        except (KeyError, TypeError):
            continue
    return matched


def attach_base_rates(matched: list[str], study: pd.DataFrame) -> dict:
    """신호명 목록 → {signal: {"h5"|"h20"|"h60": {n_events, median_excess, hit_rate}}}."""
    out: dict = {}
    for sig in matched:
        rows = study[study["signal_type"] == sig]
        if rows.empty:
            continue
        out[sig] = {
            f"h{int(r.horizon)}": {
                "n_events": int(r.n_events),
                "median_excess": (
                    None
                    if pd.isna(r.median_excess)
                    else round(float(r.median_excess), 2)
                ),
                "hit_rate": None if pd.isna(r.hit_rate) else round(float(r.hit_rate), 1),
            }
            for r in rows.itertuples()
        }
    return out
