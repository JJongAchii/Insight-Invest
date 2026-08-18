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
                    "detail": "상태표 미발행",
                }
            )
            continue
        row = hit.iloc[-1]
        raw_status = str(row.get("status", "unknown"))
        as_of = None if pd.isna(row.get("as_of")) else str(row.get("as_of"))[:10]
        age = None
        if as_of:
            try:
                age = max(0, int((today - pd.Timestamp(as_of)).days))
            except (TypeError, ValueError):
                pass
        if raw_status == "error":
            level, detail = "error", "최근 빌드 실패"
        elif raw_status == "preserved":
            level, detail = "warn", "이전 파일 보존"
        elif age is not None and age > 4:
            level, detail = "warn", f"{age}일 경과"
        else:
            level, detail = "ok", "정상"
        rows.append(
            {
                "dataset": dataset,
                "label": label,
                "level": level,
                "as_of": as_of,
                "age_days": age,
                "detail": detail,
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
            tone, label, pos, neg = "negative", "위험회피 우세", 0, 1
        elif score <= 35:
            tone, label, pos, neg = "positive", "위험선호 우세", 1, 0
        else:
            tone, label, pos, neg = "neutral", "중립 구간", 0, 0
        return (
            {
                "key": "gauge",
                "tone": tone,
                "title": f"위험 게이지 {score:.0f} · {label}",
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
    positive = negative = 0

    for fn in (_phase_evidence, _gauge_evidence):
        item, pos, neg = fn()
        if item:
            evidence.append(item)
        positive += pos
        negative += neg

    breadth, pos, neg, breadth_delta = _breadth_evidence()
    if breadth:
        evidence.append(breadth)
    positive += pos
    negative += neg

    flow, pos, neg, flow_value = _flow_evidence()
    if flow:
        evidence.append(flow)
    positive += pos
    negative += neg

    if positive >= 2 and negative == 0:
        tone, label = "risk_on", "위험선호 신호 우세"
    elif negative >= 2 and positive == 0:
        tone, label = "risk_off", "위험회피 신호 우세"
    else:
        tone, label = "mixed", "신호 혼재"

    conflicts = []
    tones = {item["key"]: item["tone"] for item in evidence}
    if tones.get("gauge") in {"positive", "negative"} and tones.get("breadth") in {
        "positive",
        "negative",
    } and tones["gauge"] != tones["breadth"]:
        conflicts.append("글로벌 위험 게이지와 KR 시장 참여 폭이 반대 방향입니다.")
    if breadth_delta is not None and flow_value is not None:
        if (breadth_delta > 0 and flow_value < 0) or (breadth_delta < 0 and flow_value > 0):
            conflicts.append("KR 시장폭 변화와 외국인 5일 수급 방향이 엇갈립니다.")

    return {
        "generated_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(),
        "tone": tone,
        "tone_label": label,
        "evidence": evidence,
        "conflicts": conflicts,
        "data_status": _data_status(),
        "method": "레짐·위험게이지·KR 시장폭·외국인 5일 수급의 방향 일치 여부",
    }
