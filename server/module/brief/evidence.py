"""Evidence Pack 조립 — 브리프의 유일한 사실 출처.

기저율 조인이 이 모듈의 핵심이다. build_insights의 signal_study(이벤트 스터디)와
flows_signals(종목별 현재값)이 같은 정의를 쓰므로, 조건식을 재계산해 조인하면
"신호"에 표본 수·승률·중앙값이 붙어 "확률"이 된다.
"""

from typing import Optional

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
                    None if pd.isna(r.median_excess) else round(float(r.median_excess), 2)
                ),
                "hit_rate": None if pd.isna(r.hit_rate) else round(float(r.hit_rate), 1),
            }
            for r in rows.itertuples()
        }
    return out


def _flows_by_investor(fs: pd.DataFrame, ticker: str) -> dict:
    """flows_signals에서 종목 행을 투자자별 dict로. 없으면 빈 dict."""
    rows = fs[fs["ticker"] == ticker]
    out = {}
    for r in rows.itertuples():
        out[r.investor] = {
            "streak": int(r.streak),
            "net_20d": float(r.net_20d),
            "intensity_20d": round(float(r.intensity_20d), 3),
            "ret_20d": round(float(r.ret_20d), 2) if pd.notna(r.ret_20d) else None,
            "divergence": r.divergence,
        }
    return out


def _factors(fp: pd.DataFrame, ticker: str) -> Optional[dict]:
    rows = fp[fp["ticker"] == ticker] if not fp.empty else fp
    if rows.empty:
        return None
    r = rows.iloc[0]
    return {
        f: (None if pd.isna(r[f]) else round(float(r[f]), 1))
        for f in ("momentum", "value", "size", "lowvol")
    }


def _sector(sp: pd.DataFrame, market: str, sector: str) -> Optional[dict]:
    rows = sp[(sp["market"] == market) & (sp["sector"] == sector)] if not sp.empty else sp
    if rows.empty:
        return None
    r = rows.iloc[0]
    keys = ("ret_1d", "ret_1w", "ret_1m", "ret_3m", "ret_ytd", "weight")
    return {k: (None if pd.isna(r[k]) else round(float(r[k]), 2)) for k in keys}


def build_evidence_pack(ticker: str, sources: dict) -> dict:
    """종목 1개의 Evidence Pack. LLM은 이 안의 값만 쓸 수 있다.

    sources 키: meta, flows_signals, signal_study, factor_pct, sector_perf,
                breadth, valuation, regime, holdings, news, prior_brief
    개별 소스가 비어 있으면 해당 섹션만 None/빈값이 되고 예외를 올리지 않는다.
    단 flows_signals에 종목이 없으면 브리프를 만들 근거가 없으므로 ValueError.
    """
    fs = sources["flows_signals"]
    flows = _flows_by_investor(fs, ticker)
    if not flows:
        raise ValueError(f"flows_signals에 {ticker} 없음 — 브리프 생성 불가")

    meta = sources.get("meta") or {}
    snap = fs[fs["ticker"] == ticker].iloc[0]

    matched = match_base_rate_signals(flows.get("frgn", {}))
    base_rates = attach_base_rates(matched, sources["signal_study"])

    return {
        "identity": {
            "ticker": ticker,
            "name": meta.get("name", ticker),
            "market": meta.get("market"),
            "sector": meta.get("sector"),
            "mktcap": float(snap["mktcap"]),
            "close": float(snap["close"]),
            "chg_pct": (round(float(snap["chg_pct"]), 2) if pd.notna(snap["chg_pct"]) else None),
        },
        "flows": flows,
        "base_rates": base_rates,
        "factors": _factors(sources["factor_pct"], ticker),
        "sector": _sector(sources["sector_perf"], meta.get("market"), meta.get("sector")),
        "market": {
            "regime": sources.get("regime"),
            "breadth": sources.get("breadth"),
            "valuation": sources.get("valuation"),
        },
        "holding": (sources.get("holdings") or {}).get(ticker),
        "news": sources.get("news") or [],
        "prior_brief": sources.get("prior_brief"),
    }
