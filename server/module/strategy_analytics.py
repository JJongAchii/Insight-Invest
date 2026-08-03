"""전략 분석 파생 지표 — 투입 판정(분석 계층)·운영 추적(기대 대비)의 순수 계산.

전부 저장된 NAV·리밸 이력의 파생이다. 판단하지 않는다 — 분포와 위치, 조건을
계산해 돌려줄 뿐, "좋다/나쁘다"는 라우터도 프론트도 붙이지 않는다.
백분위 정의: (분포 < 관측값).mean() × 100 — 낮을수록 역사적 하위.
"""

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def rolling_stats(nav: pd.Series, window: int = TRADING_DAYS) -> pd.DataFrame:
    """롤링 창 수익률(%)과 샤프 — 기간 의존성 진단 재료."""
    ret = nav / nav.shift(window) - 1
    daily = nav.pct_change()
    mean = daily.rolling(window).mean()
    std = daily.rolling(window).std()
    sharpe = (mean / std) * np.sqrt(TRADING_DAYS)
    out = pd.DataFrame({"roll_ret": ret * 100, "roll_sharpe": sharpe}).dropna()
    return out


def drawdown_episodes(nav: pd.Series, top_n: int = 5) -> list:
    """낙폭 에피소드 — 깊이 순 top N. 회복일수는 거래일 기준, 미회복은 None.

    에피소드 = dd<0 연속 구간. peak는 구간 직전 고점일, recover는 dd가 0으로
    복귀한 날(신고점 회복일).
    """
    dd = nav / nav.cummax() - 1
    at_high = dd >= 0
    group = at_high.cumsum()
    episodes = []
    for _, g in dd[~at_high].groupby(group[~at_high]):
        trough = g.idxmin()
        start_pos = nav.index.get_loc(g.index[0])
        peak = nav.index[start_pos - 1]
        end_pos = nav.index.get_loc(g.index[-1])
        if end_pos + 1 < len(nav.index):
            recover = nav.index[end_pos + 1]
            # 고점 다음 거래일부터 회복일까지의 거래일 수 (peak→recover 위치 차)
            days = int(nav.index.get_loc(recover) - nav.index.get_loc(peak))
        else:
            recover, days = None, None
        episodes.append(
            {
                "depth_pct": float(g.min() * 100),
                "peak": peak,
                "trough": trough,
                "recover": recover,
                "days_to_recover": days,
            }
        )
    episodes.sort(key=lambda e: e["depth_pct"])
    return episodes[:top_n]


def monthly_returns(nav: pd.Series) -> pd.Series:
    m = nav.resample("ME").last().pct_change().dropna() * 100
    m.index = m.index.to_period("M")
    return m


def monthly_stats(nav: pd.Series, bm_nav) -> dict:
    m = monthly_returns(nav)
    if m.empty:
        return {"win_rate": None, "win_rate_vs_bm": None, "best": [], "worst": []}
    win_vs_bm = None
    if bm_nav is not None and len(bm_nav):
        bm = monthly_returns(bm_nav)
        joined = pd.concat([m, bm], axis=1, keys=["s", "b"]).dropna()
        if not joined.empty:
            win_vs_bm = float((joined["s"] > joined["b"]).mean() * 100)

    def _rows(s):
        return [{"month": str(i), "ret_pct": float(v)} for i, v in s.items()]

    return {
        "win_rate": float((m > 0).mean() * 100),
        "win_rate_vs_bm": win_vs_bm,
        "best": _rows(m.nlargest(5)),
        "worst": _rows(m.nsmallest(5)),
    }


def turnover_stats(rebal: pd.DataFrame) -> dict:
    """리밸 이력(long)에서 회전율 재료. 첫 리밸은 전액 매수로 계산 — 엔진과 동일."""
    if rebal.empty:
        return {"n_rebals": 0, "rebals_per_year": None, "avg_turnover": None}
    wide = rebal.pivot_table(index="rebal_date", columns="ticker", values="weight", aggfunc="sum")
    wide = wide.sort_index().fillna(0.0)
    prev = wide.shift(1).fillna(0.0)
    turnover = (wide - prev).abs().sum(axis=1)
    years = max((wide.index[-1] - wide.index[0]).days / 365.25, 1 / 365.25)
    n = len(wide)
    return {
        "n_rebals": int(n),
        "rebals_per_year": float(n / years) if n > 1 else None,
        "avg_turnover": float(turnover.mean()),
    }


def live_percentile(bt_nav: pd.Series, live_nav: pd.Series):
    """저장 후 실전 성과의 '백테스트 동일 기간 분포 내 위치'. 표본 부족 시 None."""
    n = len(live_nav) - 1
    if n < 5 or len(bt_nav) < n + 60:  # 최소 60개 분포 표본
        return None
    live_ret = float(live_nav.iloc[-1] / live_nav.iloc[0] - 1)
    roll = (bt_nav / bt_nav.shift(n) - 1).dropna()
    if len(roll) < 60:
        return None
    live_dd = float(live_nav.iloc[-1] / live_nav.cummax().iloc[-1] - 1)
    bt_dd = (bt_nav / bt_nav.cummax() - 1).dropna()
    return {
        "n_days": int(n),
        "live_ret_pct": live_ret * 100,
        "ret_percentile": float((roll < live_ret).mean() * 100),
        "live_dd_pct": live_dd * 100,
        "dd_percentile": float((bt_dd < live_dd).mean() * 100),
    }


def crisis_returns(nav: pd.Series, windows: dict) -> list:
    """고정 위기 구간 수익 — 이력이 구간 시작을 덮을 때만 (portfolio_risk와 동일 규칙)."""
    out = []
    for key, (w0, w1) in windows.items():
        if nav.index.min() > pd.Timestamp(w0):
            out.append({"key": key, "ret_pct": None, "note": "이력이 구간을 덮지 못함"})
            continue
        sub = nav.loc[w0:w1]
        if len(sub) < 2:
            out.append({"key": key, "ret_pct": None, "note": "구간 내 데이터 부족"})
            continue
        out.append(
            {"key": key, "ret_pct": float((sub.iloc[-1] / sub.iloc[0] - 1) * 100), "note": None}
        )
    return out


def phase_monthly_means(monthly: pd.Series, phases: pd.Series) -> pd.DataFrame:
    """국면별 월수익 평균 — 인덱스 교집합만 (레짐 결측 월 제외)."""
    joined = pd.concat([monthly.rename("ret"), phases.rename("phase")], axis=1).dropna()
    g = joined.groupby("phase")["ret"]
    return pd.DataFrame({"mean_ret_pct": g.mean(), "n_months": g.size()})
