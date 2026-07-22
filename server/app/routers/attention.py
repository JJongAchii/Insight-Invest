"""개인화 attention API — 관심종목·보유종목 union에 대한 트리아지.

수급 신호(flows_signals)·가격 급변·보유 손익·매크로 레짐·위험게이지·전략 드로다운을
severity(high/medium/low)로 묶어 정렬 반환한다. 각 소스는 독립 try/except로 감싸
부분 실패가 전체를 죽이지 않는다. 소스가 전부 비어도 레짐+게이지 매크로 맥락은 남는다.
"""

import logging
import os
import sys
from datetime import date

import pandas as pd
from fastapi import APIRouter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))

from datastore import meta, portfolio, storage
from datastore import holdings as holdings_store
from datastore import watchlist as watchlist_store
from module import regime as regime_mod

from .holdings import build_price_map

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attention", tags=["Attention"])

_SEV_RANK = {"high": 0, "medium": 1, "low": 2}
_PERSONAL = {"signal", "price", "holding"}  # 매크로/전략보다 앞에 정렬
_MACRO_PHASES = {"Stagflation", "Deflation"}
CAP = 20


def _sort_key(item: dict):
    grp = 0 if item.get("category") in _PERSONAL else 1
    return (_SEV_RANK.get(item.get("severity"), 3), grp)


@router.get("")
def get_attention():
    items: list[dict] = []
    as_of = None

    # 내 종목 집합 (관심 ∪ 보유)
    try:
        wl = watchlist_store.list_items()
        wl_ids = [int(x) for x in wl["meta_id"]] if not wl.empty else []
    except Exception:
        logger.debug("attention watchlist 조회 실패", exc_info=True)
        wl_ids = []
    try:
        hd = holdings_store.list_items()
    except Exception:
        logger.debug("attention holdings 조회 실패", exc_info=True)
        hd = pd.DataFrame(columns=holdings_store._EMPTY)
    hd_ids = [int(x) for x in hd["meta_id"]] if not hd.empty else []
    my_ids = sorted(set(wl_ids) | set(hd_ids))

    md = meta.meta_df()[["meta_id", "ticker", "name", "iso_code", "security_type", "sector"]]
    mine = md[md["meta_id"].isin(my_ids)] if my_ids else md.iloc[0:0]
    tk2meta = {r.ticker: int(r.meta_id) for r in mine.itertuples()}
    name_by_id = {int(r.meta_id): r.name for r in mine.itertuples()}
    tk_by_id = {int(r.meta_id): r.ticker for r in mine.itertuples()}

    price_map: dict = {}
    if not mine.empty:
        try:
            price_map = build_price_map(mine[["meta_id", "ticker", "iso_code"]])
        except Exception:
            logger.warning("attention price_map 실패", exc_info=True)

    # ── 수급 신호 (flows_signals, 외인) ──────────────────────────────
    try:
        kr_tickers = mine[mine["iso_code"] == "KR"]["ticker"].dropna().tolist()
        if kr_tickers:
            sig = storage.read_parquet(
                "insight",
                "flows_signals.parquet",
                filters=[("ticker", "in", kr_tickers), ("investor", "==", "frgn")],
            )
            if not sig.empty:
                as_of = str(sig["as_of"].iloc[0]) if "as_of" in sig.columns else as_of
                for r in sig.itertuples():
                    mid = tk2meta.get(r.ticker)
                    if mid is None:
                        continue
                    name = name_by_id.get(mid)
                    link = f"/stock/{mid}"
                    intensity = float(r.intensity_20d) if pd.notna(r.intensity_20d) else None
                    streak = int(r.streak) if pd.notna(r.streak) else 0
                    base = dict(category="signal", ticker=r.ticker, name=name, meta_id=mid, link=link)
                    if r.divergence == "bull":
                        items.append({
                            **base, "severity": "high", "title": "매집 신호",
                            "detail": (
                                f"주가↓·외인 매집, 20일 강도 {intensity:.1f}%"
                                if intensity is not None else "주가↓·외인 매집"
                            ),
                        })
                    elif streak >= 10:
                        items.append({
                            **base, "severity": "medium",
                            "title": f"외인 {streak}일 연속 순매수",
                            "detail": (
                                f"20일 강도 {intensity:.1f}%" if intensity is not None else "외인 연속 순매수"
                            ),
                        })
                    elif intensity is not None and abs(intensity) >= 1:
                        direction = "매집" if intensity > 0 else "매도"
                        items.append({
                            **base, "severity": "medium",
                            "title": f"외인 {direction} 강도 {intensity:.1f}%",
                            "detail": f"20일 순매수/시총 {intensity:.1f}%",
                        })
    except Exception:
        logger.debug("attention signals 실패 (flows_signals 부재 가능)", exc_info=True)

    # ── 가격 급변 (|오늘 등락| ≥ 5%) ─────────────────────────────────
    try:
        for mid, (price, chg) in price_map.items():
            if chg is None or abs(chg) < 5:
                continue
            up = chg > 0
            items.append({
                "severity": "medium", "category": "price",
                "ticker": tk_by_id.get(mid), "name": name_by_id.get(mid), "meta_id": mid,
                "title": f"오늘 {chg:+.1f}% ({'관심' if up else '주의'})",
                "detail": f"{'급등' if up else '급락'} {chg:+.1f}% — {'관심' if up else '주의'} 종목",
                "link": f"/stock/{mid}",
            })
    except Exception:
        logger.debug("attention price moves 실패", exc_info=True)

    # ── 보유 손익 ────────────────────────────────────────────────────
    try:
        for r in hd.itertuples():
            mid = int(r.meta_id)
            price = price_map.get(mid, (None, None))[0]
            avg = float(r.avg_cost)
            if price is None or not avg:
                continue
            pnl_pct = price / avg - 1.0
            base = dict(
                category="holding", ticker=tk_by_id.get(mid),
                name=name_by_id.get(mid), meta_id=mid, link=f"/stock/{mid}",
            )
            if pnl_pct <= -0.15:
                items.append({
                    **base, "severity": "high",
                    "title": f"보유 손실 {pnl_pct * 100:.1f}%",
                    "detail": "손절 라인 점검 필요",
                })
            elif pnl_pct >= 0.30:
                items.append({
                    **base, "severity": "low",
                    "title": f"보유 수익 +{pnl_pct * 100:.1f}% (익절 검토)",
                    "detail": "목표 수익 도달 — 부분 익절 검토",
                })
    except Exception:
        logger.debug("attention holdings P&L 실패", exc_info=True)

    # ── 매크로 레짐 ──────────────────────────────────────────────────
    try:
        ph = regime_mod.current_phase()
        phase = ph.get("phase")
        if as_of is None:
            as_of = ph.get("as_of")
        if phase in _MACRO_PHASES:
            items.append({
                "severity": "high", "category": "macro",
                "title": f"레짐 {phase} — 주식비중 점검",
                "detail": f"성장 {ph.get('growth_dir')}·물가 {ph.get('inflation_dir')}",
                "link": "/regime",
            })
        else:
            items.append({
                "severity": "low", "category": "macro",
                "title": f"레짐 {phase}",
                "detail": f"성장 {ph.get('growth_dir')}·물가 {ph.get('inflation_dir')}",
                "link": "/regime",
            })
    except Exception:
        logger.warning("attention regime 실패", exc_info=True)

    # ── 위험 게이지 ──────────────────────────────────────────────────
    try:
        g = regime_mod.risk_gauge()
        score = float(g["score"])
        if score >= 65:
            sev, label = "high", "Risk-Off"
        elif score <= 35:
            sev, label = "low", "Risk-On"
        else:
            sev, label = "low", "중립"
        items.append({
            "severity": sev, "category": "macro",
            "title": f"위험게이지 {score:.0f} ({label})",
            "detail": "리스크오프 게이지 0~100 (높을수록 위험회피)",
            "link": "/regime",
        })
    except Exception:
        logger.warning("attention risk gauge 실패", exc_info=True)

    # ── 전략 드로다운 (live_nav) ─────────────────────────────────────
    try:
        reg = portfolio.registry()
        for pr in reg.itertuples():
            try:
                ln = portfolio.live_nav(int(pr.port_id))
            except Exception:
                continue
            if ln.empty:
                continue
            vals = pd.to_numeric(ln["value"], errors="coerce").dropna()
            if vals.empty:
                continue
            peak = float(vals.cummax().iloc[-1])
            cur = float(vals.iloc[-1])
            if peak <= 0:
                continue
            dd = cur / peak - 1.0
            if dd <= -0.15:
                items.append({
                    "severity": "medium", "category": "strategy",
                    "title": f"전략 {pr.port_name} 드로다운 {dd * 100:.1f}%",
                    "detail": "실전 추적 NAV 고점 대비 하락",
                    "link": f"/backtest/strategy_list/{int(pr.port_id)}",
                })
    except Exception:
        logger.debug("attention strategy drawdown 실패", exc_info=True)

    items.sort(key=_sort_key)
    items = items[:CAP]
    if as_of is None:
        as_of = date.today().isoformat()
    return {"as_of": as_of, "items": items}
