import importlib.util
import json
from pathlib import Path

import polars as pl
import pytest

spec = importlib.util.spec_from_file_location(
    "verify_research_release",
    Path(__file__).resolve().parents[2] / "scripts/verify_research_release.py",
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


@pytest.fixture
def snapshots(tmp_path):
    for side in ("before", "after"):
        item = {
            "entry_id": "a",
            "research_lane": "core",
            "editorial_selection_status": "core",
        }
        (tmp_path / f"feed-{side}.json").write_text(json.dumps({"items": [item]}))
        (tmp_path / f"seen-{side}.json").write_text(
            json.dumps({"seen_through": "2026-09-10T00:00:00+00:00"})
        )
        for kind in ("read", "deliveries"):
            pl.DataFrame(
                {"entry_id": ["a"], "value": ["PRIVATE_LIBRARY_VALUE"]}
            ).write_parquet(tmp_path / f"{kind}-{side}.parquet")
    return tmp_path


def test_snapshot_receipt_preserves_private_rows(snapshots):
    result = release.verify(snapshots)
    assert result["previous_feed_ids_preserved"] and result["seen_cursor_not_reset"]
    assert result["library"]["read"]["previous_rows_preserved"]
    assert "PRIVATE_LIBRARY_VALUE" not in json.dumps(result)


@pytest.mark.parametrize("target", ["feed", "read", "seen"])
def test_lost_rows_or_rewound_cursor_fail_closed(snapshots, target):
    if target == "read":
        pl.DataFrame({"entry_id": ["a"], "value": ["reset"]}).write_parquet(
            snapshots / "read-after.parquet"
        )
    else:
        value = (
            {"items": []}
            if target == "feed"
            else {"seen_through": "2026-09-09T00:00:00+00:00"}
        )
        (snapshots / f"{target}-after.json").write_text(json.dumps(value))
    with pytest.raises(ValueError):
        release.verify(snapshots)
