"""Publish comparable KRX observations for the private editorial worker."""

from datetime import datetime
from math import isfinite

import pandas as pd

from module.kr_intraday import KST


def market_input(timeline: pd.DataFrame, stocks: pd.DataFrame, now: datetime) -> dict:
    day = now.astimezone(KST).date().isoformat()
    rows = timeline[timeline["trade_date"] == day].drop_duplicates(["as_of", "kind", "key"], keep="last")
    samples = sorted(rows["as_of"].unique())[-7:]
    leaders = {}
    for sector, group in stocks.groupby("sector"):
        leaders[sector] = [name for name in group.nlargest(6, "value")["name"] if isinstance(name, str) and name]
    moves = []
    for before, after in zip(samples, samples[1:]):
        start = datetime.fromisoformat(before).replace(tzinfo=KST)
        end = datetime.fromisoformat(after).replace(tzinfo=KST)
        if not 5 <= (end - start).total_seconds() / 60 <= 15:
            continue
        current = rows[rows["as_of"] == after].merge(
            rows[rows["as_of"] == before], on=["kind", "key"], suffixes=("", "_prev"), validate="one_to_one"
        )
        for row in current.itertuples():
            if row.kind == "index" and row.level_prev > 0:
                change = (row.level / row.level_prev - 1) * 100
                unit, threshold = "%", 0.6
            elif row.kind == "sector" and row.key != "기타" and row.n >= 5 and row.n_prev >= 5:
                change = row.chg_pct - row.chg_pct_prev
                unit, threshold = "%p", 1.0
            else:
                continue
            if not isfinite(change) or abs(change) < threshold:
                continue
            direction = "up" if change > 0 else "down"
            moves.append({
                "id": f"{day}/{row.kind}/{row.key}/{direction}", "subject": row.key, "kind": row.kind,
                "from_at": start.isoformat(), "observed_at": end.isoformat(), "change": round(change, 2),
                "unit": unit, "companies": leaders.get(row.key, []),
            })
    large_companies = [name for name in stocks.nlargest(40, "cap")["name"] if isinstance(name, str) and name]
    return {"version": 1, "trade_date": day, "observed_at": now.isoformat(),
            "quote_delay_minutes": 20, "large_companies": large_companies, "moves": moves}
