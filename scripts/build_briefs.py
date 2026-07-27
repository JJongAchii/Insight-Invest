#!/usr/bin/env python
"""종목 브리프 생성 — Bull/Bear 대립 리서치 (설계: docs/superpowers/specs/2026-07-27-stock-brief-design.md).

로컬 파이프라인(EC2 qdata-collector)에서 build_insights 다음, send_briefing 앞에 실행한다.
- 인사이트 parquet: APP_DATA (기본 s3://insight-invest-datalake/app)
- Claude 키: 환경변수 ANTHROPIC_API_KEY 또는 BRIEFING_ENV_FILE 의 .env

ANTHROPIC_API_KEY가 없으면 조용히 스킵(exit 0) — 파이프라인은 warn-only로 감싼다.

사용:
    APP_DATA=... QDATA_LAKE=... BRIEFING_ENV_FILE=... python scripts/build_briefs.py
"""

import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))

from datastore import briefs as briefs_store  # noqa: E402
from datastore import holdings as holdings_store  # noqa: E402
from datastore import meta as meta_store  # noqa: E402
from datastore import storage  # noqa: E402
from datastore import watchlist as watchlist_store  # noqa: E402
from module.brief.evidence import build_evidence_pack  # noqa: E402
from module.brief.llm import MODEL, generate_brief  # noqa: E402
from module.brief.select import select_targets  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("build_briefs")

# 비용 가드레일 2단
#   MAX_COST_USD       1회 실행 상한 — 한 번의 폭주를 막는다 (2종목 기준 1회 ~$0.14)
#   MAX_MONTH_COST_USD 월 예산 상한 — 매일 조금씩 새는 것을 막는다
# 월 상한은 briefs.parquet의 generated_at(UTC) 기준으로 누적을 세므로, 실행이
# 여러 번 나뉘어도 합산된다.
MAX_COST_USD = 5.0
MAX_MONTH_COST_USD = 30.0

# 뉴스 헤드라인은 Task 14에서 연결한다 (NewsService.fetch_news가 async라 배관이 별건).
# 그때까지 evidence pack의 news는 빈 목록이고, 프롬프트는 정량 근거만 쓴다.


def _load_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    env_file = os.environ.get("BRIEFING_ENV_FILE")
    if env_file and os.path.exists(env_file):
        for line in open(env_file, encoding="utf-8"):
            k, _, v = line.partition("=")
            if k.strip() == "ANTHROPIC_API_KEY":
                return v.strip()
    return None


def _read(name: str, default=None):
    """insight parquet 안전 읽기 — 없거나 실패하면 default."""
    try:
        if not storage.exists(f"insight/{name}"):
            return default
        return storage.read_parquet(f"insight/{name}")
    except Exception:
        logger.warning("insight/%s 읽기 실패", name)
        return default


def _market_context(breadth, valuation, regime) -> str:
    """캐시 접두부에 들어갈 종목 무관 시장 맥락 (한 번만 만든다)."""
    return json.dumps(
        {"breadth": breadth, "valuation": valuation, "regime": regime},
        ensure_ascii=False,
        default=str,
    )


def _latest_row(df, **filters) -> dict | None:
    if df is None or df.empty:
        return None
    sub = df
    for k, v in filters.items():
        sub = sub[sub[k] == v]
    return sub.iloc[-1].to_dict() if not sub.empty else None


def main() -> int:
    key = _load_key()
    if not key:
        print("[skip] build_briefs (ANTHROPIC_API_KEY 없음)")
        return 0

    import anthropic

    client = anthropic.Anthropic(api_key=key)

    flows_signals = _read("flows_signals.parquet")
    if flows_signals is None or flows_signals.empty:
        logger.error("flows_signals 없음 — 브리프 생성 불가")
        return 1
    as_of = str(flows_signals["as_of"].iloc[0])

    signal_study = _read("signal_study.parquet", pd.DataFrame(columns=["signal_type", "horizon"]))
    factor_pct = _read(
        "factor_pct_ticker.parquet",
        pd.DataFrame(columns=["ticker", "momentum", "value", "size", "lowvol"]),
    )
    sector_perf = _read("sector_perf.parquet", pd.DataFrame(columns=["market", "sector"]))
    breadth = _latest_row(_read("breadth_daily.parquet"))
    valuation = _latest_row(_read("valuation_daily.parquet"))

    # ---- 대상 선정
    meta_df = meta_store.meta_df()
    id_to_ticker = meta_df.set_index("meta_id")["ticker"].to_dict()
    watch = {id_to_ticker.get(i) for i in watchlist_store.list_items()["meta_id"]} - {None}
    hold_ids = holdings_store.list_items()["meta_id"].tolist()
    hold = {id_to_ticker.get(i) for i in hold_ids} - {None}
    mktcap = flows_signals.drop_duplicates("ticker").set_index("ticker")["mktcap"].to_dict()

    # attention(severity=high) — get_attention()은 동기 함수이고 items가 이미
    # 우선순위순으로 정렬돼 있다. 그 순서를 그대로 우선순위로 쓴다.
    try:
        from app.routers.attention import get_attention

        att_items = get_attention()["items"]
        attention_high = [
            i["ticker"]
            for i in att_items
            if i.get("severity") == "high" and i.get("ticker")
        ]
    except Exception:
        logger.warning("attention 조회 실패 — 워치리스트·보유만 사용", exc_info=True)
        attention_high = []

    picked, dropped = select_targets(watch, hold, attention_high, mktcap)
    if dropped:
        logger.warning("상한 초과로 제외된 종목 %d개: %s", len(dropped), dropped)
    if not picked:
        logger.info("대상 종목 없음 — 종료")
        return 0
    logger.info("대상 %d종목: %s", len(picked), picked)

    # ---- 공통 재료
    meta_by_ticker = meta_df.set_index("ticker")[["name", "sector"]].to_dict("index")
    market_by_ticker = flows_signals.drop_duplicates("ticker").set_index("ticker")["market"].to_dict()
    holdings_map = {}
    for r in holdings_store.list_items().itertuples():
        t = id_to_ticker.get(r.meta_id)
        if t:
            holdings_map[t] = {"shares": float(r.shares), "avg_cost": float(r.avg_cost)}
    ticker_to_id = {v: k for k, v in id_to_ticker.items()}

    try:
        from module import regime as regime_mod

        regime = {"phase": regime_mod.current_phase(), "risk_gauge": regime_mod.risk_gauge()}
    except Exception:
        logger.warning("레짐 조회 실패 — 시장 맥락에서 생략", exc_info=True)
        regime = None

    ctx = _market_context(breadth, valuation, regime)

    # ---- 종목별 생성
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    month_spent = briefs_store.month_cost(month)
    if month_spent >= MAX_MONTH_COST_USD:
        print(
            f"[skip] build_briefs — {month} 누적 ${month_spent:.2f} 가 "
            f"월 상한 ${MAX_MONTH_COST_USD:.2f} 도달. 다음 달까지 생성하지 않는다."
        )
        return 0
    logger.info("%s 누적 $%.2f / 상한 $%.2f", month, month_spent, MAX_MONTH_COST_USD)

    rows, total_cost = [], 0.0
    for ticker in picked:
        if total_cost >= MAX_COST_USD:
            logger.error("1회 실행 상한 $%.2f 도달 — 남은 종목 중단", MAX_COST_USD)
            break
        if month_spent + total_cost >= MAX_MONTH_COST_USD:
            logger.error(
                "월 상한 $%.2f 도달 (누적 $%.2f + 이번 실행 $%.2f) — 남은 종목 중단",
                MAX_MONTH_COST_USD,
                month_spent,
                total_cost,
            )
            break
        try:
            m = meta_by_ticker.get(ticker, {})
            pack = build_evidence_pack(
                ticker,
                {
                    "meta": {
                        "name": m.get("name", ticker),
                        "sector": m.get("sector"),
                        "market": market_by_ticker.get(ticker),
                    },
                    "flows_signals": flows_signals,
                    "signal_study": signal_study,
                    "factor_pct": factor_pct,
                    "sector_perf": sector_perf,
                    "breadth": breadth,
                    "valuation": valuation,
                    "regime": regime,
                    "holdings": holdings_map,
                    "news": [],  # Task 14에서 연결
                    "prior_brief": briefs_store.latest(ticker),
                },
            )
            out = generate_brief(pack, client, ctx)
            if out is None:
                logger.warning("%s 브리프 생성 실패 — 건너뜀", ticker)
                continue
            j = out["judge"]
            total_cost += out["usage"]["cost_usd"]
            rows.append(
                {
                    "ticker": ticker,
                    "meta_id": ticker_to_id.get(ticker),
                    "name": pack["identity"]["name"],
                    "as_of": as_of,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "one_liner": j["one_liner"],
                    "summary": j["summary"],
                    "tension": j["tension"],
                    "decisive_question": j["decisive_question"],
                    "watch": json.dumps(j["watch"], ensure_ascii=False),
                    "confidence": j["confidence"],
                    "confidence_reason": j["confidence_reason"],
                    "stance_note": j["stance_note"],
                    "bull_points": json.dumps(out["bull_points"], ensure_ascii=False),
                    "bear_points": json.dumps(out["bear_points"], ensure_ascii=False),
                    "bull_could_not_argue": out["bull_could_not_argue"],
                    "bear_could_not_argue": out["bear_could_not_argue"],
                    "evidence_snapshot": json.dumps(pack, ensure_ascii=False, default=str),
                    "dropped_refs": json.dumps(out["dropped_refs"], ensure_ascii=False),
                    "model": MODEL,
                    "input_tokens": out["usage"]["input_tokens"],
                    "output_tokens": out["usage"]["output_tokens"],
                    "cost_usd": round(out["usage"]["cost_usd"], 5),
                }
            )
            logger.info("%s ✓ (%s) $%.4f", ticker, j["one_liner"], out["usage"]["cost_usd"])
        except Exception:
            logger.warning("%s 처리 중 예외 — 건너뜀", ticker)
            traceback.print_exc()

    briefs_store.upsert_many(rows)
    n_dropped = sum(len(json.loads(r["dropped_refs"])) for r in rows)
    print(
        f"브리프 {len(rows)}건 생성, 총 ${total_cost:.4f}, 근거 드롭 {n_dropped}건 "
        f"| {month} 누적 ${month_spent + total_cost:.2f} / 상한 ${MAX_MONTH_COST_USD:.2f}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
