"""홈 의사결정 요약 — 레짐·시장폭·수급·배치 신선도를 한 계약으로 묶는다.

각 수치는 기존의 원천 API/사전계산 parquet에서 읽고, 매수·매도 처방 대신 서로
독립적인 관측이 같은 방향인지 또는 충돌하는지를 표시한다.
"""

import math
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import APIRouter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))

from datastore import storage
from module import regime as regime_mod

router = APIRouter(prefix="/overview", tags=["Overview"])

CORE_DATASETS = {
    "us_prices": "미국 종가",
    "breadth_daily": "KR 시장폭",
    "flows_summary": "KR 수급",
    "factor_current": "KR 팩터",
    "valuation_daily": "KR 밸류에이션",
}

EXPECTED_LAG_SESSIONS = {
    "us_prices": 1,
    "breadth_daily": 2,
    "flows_summary": 2,
    "factor_current": 2,
    "valuation_daily": 2,
}


def _finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _data_status() -> list[dict]:
    """배치가 발행한 sidecar를 홈에서 읽기 쉬운 신선도 상태로 변환한다."""
    try:
        df = storage.read_parquet("data_status.parquet")
    except (FileNotFoundError, OSError):
        return []

    today = pd.Timestamp(datetime.now(ZoneInfo("Asia/Seoul")).date())
    rows = []
    for dataset, label in CORE_DATASETS.items():
        hit = df[df["dataset"] == dataset]
        if hit.empty:
            rows.append(
                {
                    "dataset": dataset,
                    "label": label,
                    "level": "unknown",
                    "as_of": None,
                    "age_days": None,
                    "market_sessions_old": None,
                    "detail": "상태표 미발행",
                    "built_at": None,
                    "row_count": None,
                    "message": None,
                    "build_version": None,
                    "expected_lag_sessions": EXPECTED_LAG_SESSIONS[dataset],
                }
            )
            continue
        row = hit.iloc[-1]
        raw_status = str(row.get("status", "unknown"))
        as_of = None if pd.isna(row.get("as_of")) else str(row.get("as_of"))[:10]
        age = None
        session_age = None
        if as_of:
            try:
                age = max(0, int((today - pd.Timestamp(as_of)).days))
                session_age = len(pd.bdate_range(pd.Timestamp(as_of) + pd.Timedelta(days=1), today))
            except (TypeError, ValueError):
                pass
        if raw_status == "error":
            level, detail = "error", "최근 빌드 실패"
        elif raw_status == "preserved":
            level, detail = "warn", "이전 파일 보존"
        elif session_age is not None and session_age > EXPECTED_LAG_SESSIONS[dataset]:
            level, detail = "warn", f"시장일 기준 {session_age}세션 경과"
        else:
            level, detail = "ok", "정상"
        # factor_current는 4행뿐이라 구성 팩터 결측을 별도로 확인한다. sidecar의
        # 파일 생성 성공이 내용의 완전성을 뜻하지는 않는다.
        if dataset == "factor_current" and level == "ok":
            try:
                factor = storage.read_parquet("insight", "factor_current.parquet")
                metrics = ["ret_1d", "ret_1w", "ret_1m", "ret_ytd"]
                broken = factor[factor[metrics].isna().all(axis=1)]["factor"].astype(str).tolist()
                if broken:
                    level, detail = "warn", f"부분 결측: {', '.join(broken)}"
            except Exception:
                pass
        rows.append(
            {
                "dataset": dataset,
                "label": label,
                "level": level,
                "as_of": as_of,
                "age_days": age,
                "market_sessions_old": session_age,
                "detail": detail,
                "built_at": None if pd.isna(row.get("built_at")) else str(row.get("built_at")),
                "row_count": None if pd.isna(row.get("row_count")) else int(row.get("row_count")),
                "message": None if pd.isna(row.get("message")) else str(row.get("message")),
                "build_version": None if pd.isna(row.get("build_version")) else str(row.get("build_version")),
                "expected_lag_sessions": EXPECTED_LAG_SESSIONS[dataset],
            }
        )
    return rows


def _phase_evidence() -> tuple[dict | None, int, int]:
    try:
        hist = regime_mod.phase_history()
        cur = hist.iloc[-1]
        previous = hist.iloc[-2] if len(hist) > 1 else None
        changed = previous is not None and previous["phase"] != cur["phase"]
        phase = str(cur["phase"])
        defensive = phase in {"Stagflation", "Deflation"}
        tone = "negative" if defensive else "positive"
        growth = "상승" if cur["growth_up"] else "하락"
        inflation = "상승" if cur["inflation_up"] else "하락"
        detail = f"성장 {growth} · 물가 {inflation}"
        if changed:
            detail = f"{previous['phase']} → {phase} 전환 · {detail}"
        item = {
            "key": "phase",
            "tone": tone,
            "title": f"매크로 국면 {phase}",
            "detail": detail,
            "as_of": str(cur.name),
            "link": "/regime",
            "changed": changed,
        }
        return item, int(tone == "positive"), int(tone == "negative")
    except Exception:
        return None, 0, 0


def _gauge_evidence() -> tuple[dict | None, int, int]:
    try:
        gauge = regime_mod.risk_gauge()
        score = float(gauge["score"])
        if score >= 65:
            tone, label, pos, neg = "negative", "위험도 높음", 0, 1
        elif score <= 35:
            tone, label, pos, neg = "positive", "위험도 낮음", 1, 0
        else:
            tone, label, pos, neg = "neutral", "중립 구간", 0, 0
        return (
            {
                "key": "gauge",
                "tone": tone,
                "title": f"시장 위험도 {score:.0f} · {label}",
                "detail": "금리곡선·크레딧·VIX·실업 모멘텀의 동일가중 종합",
                "as_of": gauge.get("as_of"),
                "link": "/regime",
                "changed": False,
            },
            pos,
            neg,
        )
    except Exception:
        return None, 0, 0


def _valuation_evidence() -> tuple[dict | None, int, int]:
    """구조적 가격 수준. 백분위는 '하위 N%'가 아니라 비싼 쪽 위치로 표현한다."""
    try:
        df = storage.read_parquet("insight", "valuation_daily.parquet")
        if df.empty:
            return None, 0, 0
        latest_date = pd.to_datetime(df["date"]).max()
        latest = df[pd.to_datetime(df["date"]) == latest_date]
        kospi = latest[latest["market"] == "KOSPI"]
        row = kospi.iloc[-1] if not kospi.empty else latest.iloc[-1]
        ranks = [_finite(row.get("pct_rank_per")), _finite(row.get("pct_rank_pbr"))]
        ranks = [value for value in ranks if value is not None]
        if not ranks:
            return None, 0, 0
        rank = float(sum(ranks) / len(ranks))
        if rank >= 80:
            tone, label, pos, neg = "negative", f"역사적 상위 {100 - rank:.1f}%의 높은 가격", 0, 1
        elif rank <= 20:
            tone, label, pos, neg = "positive", f"역사적 하위 {rank:.1f}%의 낮은 가격", 1, 0
        else:
            tone, label, pos, neg = "neutral", "역사적 중립 가격대", 0, 0
        return (
            {
                "key": "valuation",
                "tone": tone,
                "title": f"KOSPI 밸류에이션 · {label}",
                "detail": "PER·PBR의 전체 가용 역사 내 백분위 평균",
                "as_of": pd.Timestamp(latest_date).strftime("%Y-%m-%d"),
                "link": "/insight",
                "changed": False,
            },
            pos,
            neg,
        )
    except Exception:
        return None, 0, 0


def _intraday_evidence() -> tuple[dict | None, int, int]:
    """실제 장중 스냅샷이 활성일 때만 당일 환경을 방향성 근거로 사용한다."""
    try:
        from app.routers.intraday import _build

        market = _build()
        if not market.get("active"):
            return (
                {
                    "key": "intraday",
                    "tone": "neutral",
                    "title": "장중 세션 비활성",
                    "detail": "개장 중에는 상승·하락 종목 비중으로 당일 참여 폭을 표시합니다.",
                    "as_of": None,
                    "link": "/insight?tab=intraday",
                    "changed": False,
                },
                0,
                0,
            )
        breadth = market.get("breadth") or {}
        adv = int(breadth.get("advancers") or 0)
        dec = int(breadth.get("decliners") or 0)
        ratio = adv / (adv + dec) * 100 if adv + dec else 50.0
        if ratio >= 55:
            tone, label, pos, neg = "positive", "상승 참여 우세", 1, 0
        elif ratio <= 45:
            tone, label, pos, neg = "negative", "하락 참여 우세", 0, 1
        else:
            tone, label, pos, neg = "neutral", "상승·하락 균형", 0, 0
        return (
            {
                "key": "intraday",
                "tone": tone,
                "title": f"장중 시장폭 {ratio:.0f}% · {label}",
                "detail": f"상승 {adv:,} · 하락 {dec:,} 종목",
                "as_of": market.get("as_of"),
                "link": "/insight?tab=intraday",
                "changed": ratio >= 60 or ratio <= 40,
            },
            pos,
            neg,
        )
    except Exception:
        return None, 0, 0


def _horizon(key: str, label: str, window: str, items: list[dict]) -> dict:
    directional = [item["tone"] for item in items if item["tone"] != "neutral"]
    if directional and all(tone == "positive" for tone in directional):
        tone, summary = "positive", "우호적 근거 우세"
    elif directional and all(tone == "negative" for tone in directional):
        tone, summary = "negative", "경계 근거 우세"
    elif directional:
        tone, summary = "neutral", "내부 근거 엇갈림"
    else:
        tone, summary = "neutral", "방향 판단 보류"
    return {
        "key": key,
        "label": label,
        "window": window,
        "tone": tone,
        "summary": summary,
        "evidence": items,
    }


def _breadth_evidence() -> tuple[dict | None, int, int, float | None]:
    try:
        df = storage.read_parquet(
            "insight", "breadth_daily.parquet", columns=["date", "market", "pct_above_ma20"]
        ).dropna(subset=["pct_above_ma20"])
        dates = sorted(pd.to_datetime(df["date"]).unique())
        if not dates:
            return None, 0, 0, None
        latest = dates[-1]
        previous = dates[-6] if len(dates) >= 6 else dates[0]
        now = float(df[pd.to_datetime(df["date"]) == latest]["pct_above_ma20"].mean())
        before = float(df[pd.to_datetime(df["date"]) == previous]["pct_above_ma20"].mean())
        delta = now - before
        if now >= 55:
            tone, label, pos, neg = "positive", "참여 확산", 1, 0
        elif now <= 45:
            tone, label, pos, neg = "negative", "참여 위축", 0, 1
        else:
            tone, label, pos, neg = "neutral", "중립", 0, 0
        item = {
            "key": "breadth",
            "tone": tone,
            "title": f"KR 시장폭 {now:.0f}% · {label}",
            "detail": f"KOSPI·KOSDAQ MA20 상회 비중 평균, 5거래일 대비 {delta:+.1f}%p",
            "as_of": pd.Timestamp(latest).strftime("%Y-%m-%d"),
            "link": "/insight",
            "changed": abs(delta) >= 5,
        }
        return item, pos, neg, delta
    except Exception:
        return None, 0, 0, None


def _flow_evidence() -> tuple[dict | None, int, int, float | None]:
    try:
        df = storage.read_parquet(
            "insight",
            "flows_summary.parquet",
            columns=["date", "market", "investor", "net_value"],
            filters=[("market", "==", "ALL"), ("investor", "==", "frgn")],
        ).sort_values("date")
        if df.empty:
            return None, 0, 0, None
        daily = df.groupby("date")["net_value"].sum().tail(10)
        current = daily.tail(5)
        total = float(current.sum())
        previous = float(daily.iloc[:-5].sum()) if len(daily) >= 10 else None
        eok = total / 1e8
        tone = "positive" if total > 0 else "negative" if total < 0 else "neutral"
        item = {
            "key": "flow",
            "tone": tone,
            "title": f"외국인 5일 {'순매수' if total >= 0 else '순매도'} {abs(eok):,.0f}억",
            "detail": (
                f"KOSPI·KOSDAQ 합산 · 직전 5일 대비 {(total - previous) / 1e8:+,.0f}억"
                if previous is not None
                else "KOSPI·KOSDAQ 합산 순매수대금"
            ),
            "as_of": pd.Timestamp(current.index[-1]).strftime("%Y-%m-%d"),
            "link": "/insight",
            "changed": previous is not None and (total >= 0) != (previous >= 0),
        }
        return item, int(total > 0), int(total < 0), total
    except Exception:
        return None, 0, 0, None


@router.get("")
def get_overview():
    """현재 톤, 무엇이 변했는지, 관측 간 충돌, 데이터 신선도를 반환한다."""
    evidence = []

    phase, _, _ = _phase_evidence()
    valuation, _, _ = _valuation_evidence()
    structural_items = [item for item in (phase, valuation) if item]
    evidence.extend(structural_items)

    gauge, _, _ = _gauge_evidence()
    tactical_items = [item for item in (gauge,) if item]
    evidence.extend(tactical_items)

    breadth, pos, neg, breadth_delta = _breadth_evidence()
    if breadth:
        evidence.append(breadth)
    if breadth:
        tactical_items.append(breadth)

    flow, pos, neg, flow_value = _flow_evidence()
    if flow:
        evidence.append(flow)
    if flow:
        tactical_items.append(flow)

    intraday, _, _ = _intraday_evidence()
    intraday_items = [intraday] if intraday else []
    evidence.extend(intraday_items)

    horizons = [
        _horizon("intraday", "장중", "당일", intraday_items),
        _horizon("tactical", "전술", "1~4주", tactical_items),
        _horizon("structural", "구조적", "3~12개월", structural_items),
    ]
    horizon_tones = [h["tone"] for h in horizons]
    if horizon_tones and all(item == "positive" for item in horizon_tones):
        tone, label = "risk_on", "모든 시간축 우호"
    elif horizon_tones and all(item == "negative" for item in horizon_tones):
        tone, label = "risk_off", "모든 시간축 경계"
    else:
        tone, label = "mixed", "시간축별 혼조"

    conflicts = []
    tones = {item["key"]: item["tone"] for item in evidence}
    if tones.get("gauge") in {"positive", "negative"} and tones.get("breadth") in {
        "positive",
        "negative",
    } and tones["gauge"] != tones["breadth"]:
        conflicts.append("글로벌 시장 위험도와 KR 시장 참여 폭이 반대 방향입니다.")
    if breadth_delta is not None and flow_value is not None:
        if (breadth_delta > 0 and flow_value < 0) or (breadth_delta < 0 and flow_value > 0):
            conflicts.append("KR 시장폭 변화와 외국인 5일 수급 방향이 엇갈립니다.")

    return {
        "generated_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "tone": tone,
        "tone_label": label,
        "horizons": horizons,
        "evidence": evidence,
        "conflicts": conflicts,
        "data_status": _data_status(),
        "method": "장중·전술(1~4주)·구조적(3~12개월) 근거를 분리하며, 전 시간축이 일치할 때만 전체 방향을 표시",
    }
