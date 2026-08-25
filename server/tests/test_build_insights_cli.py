"""인사이트 배치 선택 실행·필수 산출물 실패 계약."""

import os
import sys
from datetime import timedelta

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


def test_external_events_preserve_last_good_provider_rows(monkeypatch, tmp_path):
    today = pd.Timestamp.now(tz="Asia/Seoul").date()
    scheduled = (today + timedelta(days=3)).isoformat()
    previous = bi.external_events.empty_events()
    previous.loc[0] = {
        "event_key": f"fred:10:{scheduled}",
        "kind": "event",
        "category": "macro",
        "market": "US",
        "scope": "market",
        "severity": "high",
        "title": "US CPI",
        "detail": "last good",
        "link": "https://fred.stlouisfed.org/release?rid=10",
        "meta_id": None,
        "ticker": None,
        "name": None,
        "occurred_at": scheduled,
        "available_at": f"{today.isoformat()}T10:00:00+09:00",
        "data_as_of": scheduled,
        "scheduled_for": scheduled,
        "source": "fred",
        "event_status": "confirmed",
    }
    previous["as_of"] = today.isoformat()
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    bi.storage.write_parquet(previous, "insight", "external_events.parquet")
    monkeypatch.setattr(
        bi,
        "_tracked_assets",
        lambda: pd.DataFrame(
            columns=["meta_id", "ticker", "name", "iso_code", "scope"]
        ),
    )
    monkeypatch.setattr(bi.qdata_settings, "lake_root", lambda: tmp_path)
    monkeypatch.setattr(bi.qdata_settings, "fred_api_key", lambda: "key")

    def fred_failure(*args, **kwargs):
        raise bi.external_events.ProviderUnavailable("temporary failure")

    monkeypatch.setattr(bi.external_events, "fetch_fred_events", fred_failure)
    monkeypatch.setattr(
        bi.external_events,
        "fetch_fomc_events",
        lambda *args, **kwargs: bi.external_events.ProviderResult(
            bi.external_events.empty_events(), "none", today.isoformat()
        ),
    )

    out = bi.build_external_events()
    statuses = bi.storage.read_parquet(
        "insight", "external_event_sources.parquet"
    ).set_index("provider")

    assert out["event_key"].tolist() == [f"fred:10:{scheduled}"]
    assert statuses.loc["fred", "status"] == "preserved"
    assert statuses.loc["fred", "coverage"] == "이전 1건 보존"
