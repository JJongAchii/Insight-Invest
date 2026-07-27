"""종목 브리프 저장소 — {APP_DATA}/briefs.parquet.

watchlist.py·holdings.py와 같은 read-modify-write(파일 통째 교체) 패턴.
15종목 × 250거래일 = 연 3,750행이라 파티셔닝은 불필요하다.
"""

import logging

import pandas as pd

from datastore import storage

logger = logging.getLogger(__name__)

FILE = "briefs.parquet"
COLUMNS = [
    "ticker",
    "meta_id",
    "name",
    "as_of",
    "generated_at",
    "one_liner",
    "summary",
    "tension",
    "decisive_question",
    "watch",
    "confidence",
    "confidence_reason",
    "stance_note",
    "bull_points",
    "bear_points",
    "bull_could_not_argue",
    "bear_could_not_argue",
    "evidence_snapshot",
    "dropped_refs",
    "model",
    "input_tokens",
    "output_tokens",
    "cost_usd",
]


def list_items() -> pd.DataFrame:
    if not storage.exists(FILE):
        return pd.DataFrame(columns=COLUMNS)
    return storage.read_parquet(FILE)


def latest(ticker: str) -> dict | None:
    """해당 종목의 가장 최근 브리프 1건. 없으면 None."""
    df = list_items()
    rows = df[df["ticker"] == ticker]
    if rows.empty:
        return None
    return rows.sort_values("as_of").iloc[-1].to_dict()


def by_date(as_of: str) -> pd.DataFrame:
    df = list_items()
    return df[df["as_of"] == as_of] if not df.empty else df


def month_cost(yyyymm: str) -> float:
    """해당 월(YYYY-MM)에 실제로 지출한 cost_usd 합계.

    거래일(as_of)이 아니라 생성 시각(generated_at, UTC ISO 문자열) 기준으로 센다 —
    이건 예산 가드레일이고, 청구는 벽시계 시각을 따르기 때문이다. 파이프라인은
    19:00 KST(=10:00 UTC)에 돌아 UTC 월 경계와 멀다.

    파일이 없거나 컬럼이 비어도 0.0을 반환한다 (호출자가 상한 비교만 하면 되게).
    """
    df = list_items()
    if df.empty or "generated_at" not in df.columns:
        return 0.0
    rows = df[df["generated_at"].astype(str).str.startswith(yyyymm)]
    if rows.empty:
        return 0.0
    return float(pd.to_numeric(rows["cost_usd"], errors="coerce").fillna(0).sum())


def upsert_many(rows: list) -> None:
    """(ticker, as_of) 기준 교체 후 통째로 쓴다."""
    if not rows:
        return
    new = pd.DataFrame(rows).reindex(columns=COLUMNS)
    old = list_items()
    if not old.empty:
        keys = set(zip(new["ticker"], new["as_of"]))
        mask = [(t, a) not in keys for t, a in zip(old["ticker"], old["as_of"])]
        old = old[mask]
        out = pd.concat([old, new], ignore_index=True)
    else:
        out = new
    storage.write_parquet(out, FILE)
    logger.info("briefs %d건 저장 (총 %d행)", len(new), len(out))
