"""포트폴리오 리스크 — 고정 현재비중의 역사적 위험 특성 (순수 계산).

라우터(holdings.py)가 가격(KRW 환산 완료)·비중을 조립해 넘기고, 여기는
pandas 계산만 한다. 모든 수치는 '현재 비중을 과거에 고정 적용했다면'이라는
반사실 위에 있다 — 실제 과거 실적이 아니다 (매일 리밸런싱 가정).
동결·정지 이력은 clean_panel의 ffill로 0수익 평탄화되는데, 이는 변동성을
과소평가한다 — 감지와 경고는 라우터가 한다 (조용히 계산하지 않는다).
"""

import numpy as np
import pandas as pd

MIN_OVERLAP_DAYS = 60  # 공통 이력이 이보다 짧으면 위험 수치 전체 생략
ROLL_WINDOWS = (20, 60)  # 최악 롤링 탐색 창 (거래일)
RECENT_DAYS = 20
MIN_CRISIS_DAYS = 15  # 고정 구간 내 최소 거래일 — 미달이면 계산하지 않는다
# 고정 위기 구간 — 전 종목 이력이 구간 시작을 덮을 때만 계산한다. 일부 종목만
# 덮는 경우 비중 재정규화는 조용히 다른 포트폴리오를 재는 것이라 금지.
CRISIS_WINDOWS = {"covid_2020": ("2020-02-14", "2020-03-23")}

SCENARIO_LABELS = {
    "recent_20d": "최근 20거래일 (진행 중)",
    "worst_20d": "역사적 최악 20거래일",
    "worst_60d": "역사적 최악 60거래일",
    "covid_2020": "코로나 급락 재현 (2020-02~03)",
}


def clean_panel(prices: pd.DataFrame) -> pd.DataFrame:
    """선두는 전 종목 공통 시점으로 절단, 이후 결측은 ffill.

    ffill은 상폐·동결 이력을 0수익으로 평탄화한다 — 위험 과소평가 방향이므로
    호출부가 stale 감지와 경고를 반드시 병행한다.
    """
    starts = [c.first_valid_index() for _, c in prices.items()]
    starts = [s for s in starts if s is not None]
    if not starts:
        return prices.iloc[0:0]
    # 공통 시작일에 정확히 NaN인 컬럼(캘린더 불일치)은 첫 수익률 하루가 0 기여로 빠진다 — 60일+ 창에서 무시 가능
    return prices.loc[max(starts) :].ffill()


def portfolio_returns(prices: pd.DataFrame, weights: dict) -> pd.Series:
    """고정비중 일별 포트 수익률 — r_p(t) = Σ w_i · r_i(t)."""
    rets = prices.pct_change(fill_method=None)
    w = pd.Series(weights, dtype="float64").reindex(prices.columns).fillna(0.0)
    return rets.mul(w, axis=1).sum(axis=1).iloc[1:]


def _scenario_row(key: str, sub: pd.Series) -> dict:
    return {
        "key": key,
        "label": SCENARIO_LABELS[key],
        "ret_pct": float(((1 + sub).prod() - 1) * 100),
        "start": str(sub.index.min().date()),
        "end": str(sub.index.max().date()),
        "note": None,
    }


def _null_row(key: str, note: str) -> dict:
    return {
        "key": key,
        "label": SCENARIO_LABELS[key],
        "ret_pct": None,
        "start": None,
        "end": None,
        "note": note,
    }


def scenario_rows(rp: pd.Series) -> list:
    rows = [_scenario_row("recent_20d", rp.tail(RECENT_DAYS))]
    for k in ROLL_WINDOWS:
        key = f"worst_{k}d"
        if len(rp) < k:
            rows.append(_null_row(key, f"이력 {len(rp)}일 — {k}일 창 미달"))
            continue
        roll = (1 + rp).rolling(k).apply(np.prod, raw=True) - 1
        end = roll.idxmin()
        rows.append(_scenario_row(key, rp.loc[:end].tail(k)))
    for key, (w0, w1) in CRISIS_WINDOWS.items():
        if rp.index.min() > pd.Timestamp(w0):
            rows.append(_null_row(key, "보유 종목 이력이 구간을 덮지 못함"))
            continue
        sub = rp.loc[w0:w1]
        if len(sub) < MIN_CRISIS_DAYS:
            rows.append(_null_row(key, "구간 내 거래일 부족"))
        else:
            rows.append(_scenario_row(key, sub))
    return rows


def build_report(prices: pd.DataFrame, weights: dict, min_overlap: int = MIN_OVERLAP_DAYS) -> dict:
    prices = clean_panel(prices)
    if len(prices) < min_overlap + 1:
        return {"insufficient": True, "overlap_days": int(len(prices))}

    rp = portfolio_returns(prices, weights)
    nav = (1 + rp).cumprod()
    dd = nav / nav.cummax() - 1
    trough = dd.idxmin()
    peak = nav.loc[:trough].idxmax()

    corr, avg_corr = None, None
    if prices.shape[1] >= 2:
        corr = prices.pct_change(fill_method=None).iloc[1:].corr()
        off = corr.where(~np.eye(len(corr), dtype=bool)).stack()
        avg_corr = float(off.mean()) if not off.empty else None

    return {
        "overlap_days": int(len(prices)),
        "ann_vol": float(rp.std() * np.sqrt(252) * 100),
        "max_drawdown": float(dd.min() * 100),
        "mdd_from": str(peak.date()),
        "mdd_to": str(trough.date()),
        "avg_pair_corr": avg_corr,
        "corr": corr,
        "scenarios": scenario_rows(rp),
        "window": {"start": str(prices.index.min().date()), "end": str(prices.index.max().date())},
    }
