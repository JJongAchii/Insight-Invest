"""인사이트 배치 선택 실행·필수 산출물 실패 계약."""

import os
import sys

import pandas as pd
import pytest

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import build_insights as bi  # noqa: E402


def test_only_runs_selected_builder_and_records_status(monkeypatch):
    called = []
    written = []

    def selected():
        called.append("selected")
        return pd.DataFrame({"value": [1], "as_of": ["2026-08-17"]})

    def unselected():
        raise AssertionError("선택되지 않은 빌더가 실행됨")

    monkeypatch.setattr(
        bi,
        "BUILDERS",
        [("selected.parquet", selected, {}), ("unselected.parquet", unselected, {})],
    )
    monkeypatch.setattr(bi.storage, "write_parquet", lambda df, *parts, **kwargs: "/tmp/out")
    monkeypatch.setattr(bi, "_write_status", lambda rows: written.extend(rows))

    bi.main(["--only", "selected", "--require", "selected"])

    assert called == ["selected"]
    assert written[0]["dataset"] == "selected"
    assert written[0]["status"] == "ok"
    assert written[0]["as_of"] == "2026-08-17"


def test_required_builder_none_is_pipeline_failure(monkeypatch):
    monkeypatch.setattr(bi, "BUILDERS", [("us_prices.parquet", lambda: None, {})])
    statuses = []
    monkeypatch.setattr(bi, "_write_status", lambda rows: statuses.extend(rows))

    with pytest.raises(SystemExit) as exc:
        bi.main(["--only", "us_prices", "--require", "us_prices"])

    assert exc.value.code == 1
    assert statuses[0]["status"] == "error"


def test_us_price_as_of_comes_from_us_panel(monkeypatch):
    dates = pd.to_datetime(["2026-08-14", "2026-08-17"])
    px = pd.DataFrame(
        {
            "date": dates,
            "ticker": "SPY",
            "close": [640.0, 642.0],
            "adj_close": [640.0, 642.0],
        }
    )
    div = pd.DataFrame({"ticker": [], "ex_date": [], "cash_amount": []})
    md = pd.DataFrame({"meta_id": [1], "ticker": ["SPY"], "iso_code": ["US"]})
    monkeypatch.setenv("US_PRICES_CUTOVER", "1")
    monkeypatch.setattr(bi.meta, "meta_df", lambda: md)
    monkeypatch.setattr(
        bi.qdata_api,
        "load_us_prices",
        lambda start=None, end=None, tickers=None, columns=None: px[
            (px["date"] >= start) & (px["date"] <= end)
        ].copy(),
    )
    monkeypatch.setattr(bi.qdata_api, "load_us_dividends", lambda **kwargs: div.copy())
    monkeypatch.setattr(
        bi.qdata_api,
        "load_us_ticker_events",
        lambda **kwargs: (_ for _ in ()).throw(FileNotFoundError()),
        raising=False,
    )
    monkeypatch.setattr(
        bi.qdata_api,
        "load_us_ticker_details",
        lambda **kwargs: (_ for _ in ()).throw(FileNotFoundError()),
        raising=False,
    )
    monkeypatch.setattr(bi, "_as_of", lambda: "2099-12-31")

    out = bi.build_us_prices()

    assert set(out["as_of"]) == {"2026-08-17"}
