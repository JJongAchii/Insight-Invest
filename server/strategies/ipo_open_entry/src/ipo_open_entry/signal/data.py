"""Fixed input identity and execution-aligned labels; no performance aggregation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from ipo_open_entry import engine, evaluate
from ipo_open_entry.config import CONFIG_PATH, LINE_DIR, load_config

SIGNAL_CONFIG = LINE_DIR / "config-signal-v1.yaml"
FILES = ("events", "fields", "bars", "index")


def spec() -> dict:
    return yaml.safe_load(SIGNAL_CONFIG.read_text())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config_digest(variant: dict) -> str:
    payload = {"base": digest(CONFIG_PATH), "signal": digest(SIGNAL_CONFIG), "variant": variant}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def load(
    path: Path,
    *,
    listing_before: pd.Timestamp | None = None,
    price_before: pd.Timestamp | None = None,
) -> tuple[dict, dict]:
    cfg = spec()
    if digest(path / "manifest.json") != cfg["dataset_manifest_sha256"]:
        raise ValueError("dataset manifest differs from the approved input")
    manifest = json.loads((path / "manifest.json").read_text())
    for name in FILES:
        if digest(path / f"{name}.parquet") != manifest["files"][name]:
            raise ValueError(f"input checksum mismatch: {name}")
    if (listing_before is None) != (price_before is None):
        raise ValueError("smoke listing and price cutoffs must be supplied together")
    if listing_before is None:
        data = {name: pd.read_parquet(path / f"{name}.parquet") for name in FILES}
    else:
        # Qualification verifies all bytes but decodes only pre-evaluation rows.
        # Predicates are applied at parquet loading, not after loading future outcomes.
        ev = pd.read_parquet(
            path / "events.parquet", filters=[("listing_date", "<", listing_before)]
        )
        ids = ev.event_id.tolist()
        if not ids:
            raise ValueError("empty qualification event window")
        data = {
            "events": ev,
            "fields": pd.read_parquet(path / "fields.parquet", filters=[("event_id", "in", ids)]),
            "bars": pd.read_parquet(
                path / "bars.parquet",
                filters=[("event_id", "in", ids), ("date", "<", price_before)],
            ),
            "index": pd.read_parquet(path / "index.parquet", filters=[("date", "<", price_before)]),
        }
    ev, bars = data["events"], data["bars"]
    if not ev["listing_date"].between(cfg["dev_start"], cfg["dev_end"]).all():
        raise ValueError("event outside approved development window")
    if not (bars["date"] <= pd.Timestamp(cfg["price_end"])).all():
        raise ValueError("price beyond approved cutoff")
    if not (data["index"]["date"] <= pd.Timestamp(cfg["price_end"])).all():
        raise ValueError("index beyond approved cutoff")
    if not ev["event_id"].is_unique or not data["fields"]["event_id"].is_unique:
        raise ValueError("duplicate event identity")
    if set(ev.event_id) != set(data["fields"].event_id):
        raise ValueError("field/event coverage mismatch")
    return data, manifest


def subset(data: dict, listing_before: pd.Timestamp, price_before: pd.Timestamp) -> dict:
    ev = data["events"][data["events"].listing_date < listing_before]
    ids = set(ev.event_id)
    return {
        "events": ev.copy(),
        "fields": data["fields"][data["fields"].event_id.isin(ids)].copy(),
        "bars": data["bars"][
            data["bars"].event_id.isin(ids) & (data["bars"].date < price_before)
        ].copy(),
        "index": data["index"][data["index"].date < price_before].copy(),
    }


def exact_labels(data: dict, config: dict, signal: dict) -> pd.DataFrame:
    """Potential GFD order outcomes for every event, learned only after completion."""
    ev = data["events"]
    dec = pd.DataFrame({"event_id": ev.event_id, "buy": True, "limit_mult": signal["entry_cap"]})
    trades = engine.build_trades(ev, data["bars"], dec, config)
    t = trades[trades.horizon == signal["horizon"]].set_index("event_id")
    filled = t["filled"].astype(bool)
    if t.loc[filled, "truncated"].fillna(True).astype(bool).any():
        raise ValueError("unfinished H2 exit: last-price substitution is prohibited")
    out = pd.DataFrame(index=t.index)
    out["sig_filled"] = filled
    out["sig_net"] = t["net_stress"].where(filled, 0.0)
    out["sig_gross"] = t["gross"].where(filled, 0.0)
    opening = data["bars"].loc[data["bars"].day == 0].set_index("event_id")["open"].reindex(t.index)
    open_fill = filled & ~t["at_cap"] & (opening < t["limit_price"])
    out["sig_fill_type"] = np.where(open_fill, "open", np.where(filled, "intraday", "unfilled"))
    out["sig_entry_price"] = t["entry_price"]
    out["sig_limit_price"] = t["limit_price"]
    out["sig_exit_price"] = t["exit_price"]
    weight = (t["entry_price"] / t["limit_price"]).where(filled, 0.0)
    out["sig_growth"] = np.log1p(weight * out["sig_net"] / float(config["sizing"]["slots"]))
    # An unfilled GFD order is known after that listing day's close.
    out["sig_available"] = t["exit_date"].where(filled, t["listing_date"])
    if out["sig_available"].isna().any() or not np.isfinite(out["sig_growth"]).all():
        raise ValueError("invalid exact label or maturity")
    return out


def build_table(data: dict, config: dict | None = None) -> pd.DataFrame:
    config = config or load_config()
    base = evaluate.build_table(data, config).set_index("event_id")
    exact = exact_labels(data, config, spec())
    table = base.join(exact, how="left", validate="one_to_one")
    table["label_available"] = table[
        ["exit_date_h1", "exit_date_h2", "exit_date_h3", "sig_available"]
    ].max(axis=1)
    # The incumbent's conservative H1/H2/H3 purge remains common to every model.
    return table.reset_index().sort_values(["listing_date", "event_id"]).reset_index(drop=True)


def predictors(table: pd.DataFrame) -> pd.DataFrame:
    from ipo_open_entry.models import blocks as B
    from ipo_open_entry.models.linear import CONTROL

    columns = [*evaluate.KEY_COLUMNS, *B.feature_columns(tuple(spec()["blocks"])), CONTROL]
    return table[columns].copy()


def mature_before(table: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    return table[(table.listing_date < cutoff) & (table.label_available < cutoff)].copy()
