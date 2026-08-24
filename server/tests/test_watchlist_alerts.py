import pandas as pd

from datastore import storage, watchlist


def test_old_watchlist_schema_upgrades_alert_columns(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    storage.write_parquet(
        pd.DataFrame(
            [
                {
                    "meta_id": 7,
                    "added_at": pd.Timestamp("2026-01-01"),
                    "note": "legacy",
                }
            ]
        ),
        watchlist.FILE,
    )

    upgraded = watchlist.list_items()
    assert (
        upgraded.iloc[0]["alerts_enabled"] is False
        or not upgraded.iloc[0]["alerts_enabled"]
    )
    assert pd.isna(upgraded.iloc[0]["alert_price_above"])

    assert watchlist.update(
        7,
        note="legacy",
        alerts_enabled=True,
        alert_price_above=100.0,
        alert_price_below=80.0,
        alert_change_pct=5.0,
    )
    saved = watchlist.list_items().iloc[0]
    assert bool(saved["alerts_enabled"]) is True
    assert saved["alert_price_above"] == 100.0
