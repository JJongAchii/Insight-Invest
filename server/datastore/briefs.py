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
