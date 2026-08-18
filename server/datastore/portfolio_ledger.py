"""포트폴리오 불변 이벤트 원장과 파생 포지션·현금 상태."""

from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd

from datastore import holdings, storage

EVENT_FILE = "portfolio_ledger.parquet"
OPENING_FILE = "portfolio_opening_holdings.parquet"
NOTES_FILE = "portfolio_position_notes.parquet"
NOTE_COLUMNS = [
    "meta_id",
    "target_weight",
    "note",
    "thesis",
    "invalidation",
    "review_date",
    "updated_at",
]
EVENT_COLUMNS = [
    "event_id",
    "idempotency_key",
    "occurred_at",
    "created_at",
    "event_type",
    "meta_id",
    "shares",
    "price",
    "currency",
    "amount",
    "fees",
    "counter_currency",
    "counter_amount",
    "realized_pnl_native",
    "note",
    "thesis",
    "invalidation",
    "review_date",
]


def list_events() -> pd.DataFrame:
    if not storage.exists(EVENT_FILE):
        return pd.DataFrame(columns=EVENT_COLUMNS)
    df = storage.read_parquet(EVENT_FILE)
    for column in EVENT_COLUMNS:
        if column not in df.columns:
            df[column] = None
    return df[EVENT_COLUMNS].sort_values(["occurred_at", "created_at"])


def has_events() -> bool:
    return not list_events().empty


def ensure_opening(base: pd.DataFrame) -> None:
    if storage.exists(OPENING_FILE):
        return
    storage.write_parquet(base.reindex(columns=holdings._EMPTY), OPENING_FILE)


def opening_positions() -> pd.DataFrame:
    if not storage.exists(OPENING_FILE):
        return holdings.list_items()
    df = storage.read_parquet(OPENING_FILE)
    for column in holdings._EMPTY:
        if column not in df.columns:
            df[column] = None
    return df[holdings._EMPTY]


def _state() -> dict[int, dict]:
    state = {
        int(row.meta_id): row._asdict()
        for row in opening_positions().itertuples(index=False)
        if float(row.shares) > 0
    }
    for event in list_events().itertuples(index=False):
        if event.event_type not in {"BUY", "SELL"} or pd.isna(event.meta_id):
            continue
        mid = int(event.meta_id)
        shares = float(event.shares)
        price = float(event.price)
        fees = float(event.fees or 0)
        current = state.get(mid)
        if event.event_type == "BUY":
            old_shares = float(current["shares"]) if current else 0.0
            old_cost = old_shares * float(current["avg_cost"]) if current else 0.0
            new_shares = old_shares + shares
            avg_cost = (old_cost + shares * price + fees) / new_shares
            state[mid] = {
                "meta_id": mid,
                "shares": new_shares,
                "avg_cost": avg_cost,
                "currency": event.currency,
                "target_weight": current.get("target_weight") if current else None,
                "opened_at": current.get("opened_at") if current else event.occurred_at,
                "note": current.get("note", "") if current else event.note or "",
                "thesis": (event.thesis or "") if not current else current.get("thesis", ""),
                "invalidation": (event.invalidation or "") if not current else current.get("invalidation", ""),
                "review_date": event.review_date if not current else current.get("review_date"),
                "updated_at": event.created_at,
            }
        elif current:
            remaining = float(current["shares"]) - shares
            if remaining <= 1e-10:
                state.pop(mid, None)
            else:
                current["shares"] = remaining
                current["updated_at"] = event.created_at
    return state


def current_positions() -> pd.DataFrame:
    state = _state()
    if not state:
        return pd.DataFrame(columns=holdings._EMPTY)
    positions = pd.DataFrame(state.values()).reindex(columns=holdings._EMPTY)
    notes = position_metadata()
    if notes.empty:
        return positions
    note_map = notes.set_index("meta_id").to_dict(orient="index")
    for index, row in positions.iterrows():
        metadata = note_map.get(int(row["meta_id"]))
        if not metadata:
            continue
        for column in ["target_weight", "note", "thesis", "invalidation", "review_date"]:
            positions.at[index, column] = metadata.get(column)
    return positions


def position_metadata() -> pd.DataFrame:
    if not storage.exists(NOTES_FILE):
        return pd.DataFrame(columns=NOTE_COLUMNS)
    df = storage.read_parquet(NOTES_FILE)
    for column in NOTE_COLUMNS:
        if column not in df.columns:
            df[column] = None
    return df[NOTE_COLUMNS]


def upsert_position_metadata(meta_id: int, values: dict) -> None:
    if meta_id not in _state():
        raise ValueError("원장상 보유 중인 종목만 판단 메모를 수정할 수 있습니다")
    rows = position_metadata()
    rows = rows[rows["meta_id"] != meta_id]
    row = {
        **{column: None for column in NOTE_COLUMNS},
        **values,
        "meta_id": int(meta_id),
        "updated_at": datetime.now(timezone.utc),
    }
    out = pd.concat([rows, pd.DataFrame([row], columns=NOTE_COLUMNS)], ignore_index=True)
    storage.write_parquet(out, NOTES_FILE)


def record(event: dict, base: pd.DataFrame) -> tuple[str, bool]:
    """멱등키로 이벤트를 한 번만 append. 반환 (event_id, created)."""
    events = list_events()
    duplicate = events[events["idempotency_key"] == event["idempotency_key"]]
    if not duplicate.empty:
        return str(duplicate.iloc[-1]["event_id"]), False

    ensure_opening(base)
    event_type = event["event_type"]
    realized = None
    if event_type == "SELL":
        current = _state().get(int(event["meta_id"]))
        available = float(current["shares"]) if current else 0.0
        if float(event["shares"]) > available + 1e-10:
            raise ValueError(f"매도 수량 {event['shares']}주가 원장상 보유 {available}주를 초과합니다")
        realized = (
            (float(event["price"]) - float(current["avg_cost"])) * float(event["shares"])
            - float(event.get("fees") or 0)
        )

    event_id = str(uuid4())
    row = {
        **{column: None for column in EVENT_COLUMNS},
        **event,
        "event_id": event_id,
        "created_at": datetime.now(timezone.utc),
        "realized_pnl_native": realized,
    }
    new = pd.DataFrame([row], columns=EVENT_COLUMNS)
    out = pd.concat([events, new], ignore_index=True) if not events.empty else new
    storage.write_parquet(out, EVENT_FILE)
    return event_id, True


def cash_balances() -> dict[str, float]:
    balances: dict[str, float] = {}
    for row in list_events().itertuples(index=False):
        currency = str(row.currency)
        fees = float(row.fees or 0)
        delta = 0.0
        if row.event_type == "DEPOSIT":
            delta = float(row.amount)
        elif row.event_type == "WITHDRAW":
            delta = -float(row.amount)
        elif row.event_type == "BUY":
            delta = -(float(row.shares) * float(row.price) + fees)
        elif row.event_type == "SELL":
            delta = float(row.shares) * float(row.price) - fees
        elif row.event_type == "DIVIDEND":
            delta = float(row.amount) - fees
        elif row.event_type == "FEE":
            delta = -float(row.amount)
        elif row.event_type == "FX":
            delta = -float(row.amount)
            counter = str(row.counter_currency)
            balances[counter] = balances.get(counter, 0.0) + float(row.counter_amount)
        balances[currency] = balances.get(currency, 0.0) + delta
    return balances


def realized_pnl() -> dict[str, float]:
    out: dict[str, float] = {}
    for row in list_events().itertuples(index=False):
        if pd.notna(row.realized_pnl_native):
            out[str(row.currency)] = out.get(str(row.currency), 0.0) + float(row.realized_pnl_native)
    return out
