"""Actual ECOS observation dates must survive weekly chart aggregation and warm caches."""

import pandas as pd
import pytest

from module import regime


@pytest.fixture(autouse=True)
def clear_caches():
    regime._ecos_for_bucket.cache_clear()
    regime._cli_for_bucket.cache_clear()
    regime._fred_for_bucket.cache_clear()
    regime._hyg_ief_for_bucket.cache_clear()
    yield
    regime._ecos_for_bucket.cache_clear()
    regime._cli_for_bucket.cache_clear()
    regime._fred_for_bucket.cache_clear()
    regime._hyg_ief_for_bucket.cache_clear()


def test_kr_snapshot_date_is_observation_date_not_friday_bucket(monkeypatch):
    ecos = pd.DataFrame(
        {
            "base_rate": pd.Series([3.0], index=pd.to_datetime(["2026-09-02"])),
            "ktb_3y": pd.Series([3.888], index=pd.to_datetime(["2026-09-03"])),
            "ktb_10y": pd.Series([4.367], index=pd.to_datetime(["2026-09-03"])),
            "usdkrw": pd.Series([1369.4], index=pd.to_datetime(["2026-09-03"])),
            "cpi": pd.Series(
                range(100, 114), index=pd.date_range("2025-07-01", periods=14, freq="MS")
            ),
        }
    )
    monkeypatch.setattr(regime, "_ecos", lambda: ecos)
    monkeypatch.setattr(
        regime, "_cli", lambda _: pd.Series([100.2], index=pd.to_datetime(["2026-07-01"]))
    )
    result = regime.kr_macro()
    assert result["base_rate"]["as_of"] == "2026-09-02"
    for key in ("ktb_3y", "ktb_10y", "usdkrw"):
        assert result[key]["as_of"] == "2026-09-03"
        assert result[key]["data"][-1]["date"] == "2026-09-04"
        assert result[key]["frequency"] == "daily"
        assert result[key]["source"] == "ECOS"
    assert result["cpi_yoy"]["as_of"] == "2026-08"
    assert result["cpi_yoy"]["frequency"] == "monthly"
    assert result["cli_kor"]["as_of"] == "2026-07"
    assert result["cli_kor"]["source"] == "OECD"


def test_warm_ecos_cache_reloads_after_five_minutes(monkeypatch):
    clock = [600.0]
    calls = []

    def load(*args, **kwargs):
        calls.append(1)
        return pd.DataFrame({"usdkrw": [float(len(calls))]})

    monkeypatch.setattr(regime.time, "time", lambda: clock[0])
    monkeypatch.setattr(regime.qdata_api, "load_ecos", load)
    assert regime._ecos().iloc[0, 0] == 1.0
    clock[0] = 899.0
    assert regime._ecos().iloc[0, 0] == 1.0
    clock[0] = 900.0
    assert regime._ecos().iloc[0, 0] == 2.0
    assert len(calls) == 2


def test_expired_ecos_cache_does_not_hide_failed_refresh(monkeypatch):
    clock = [600.0]
    monkeypatch.setattr(regime.time, "time", lambda: clock[0])
    monkeypatch.setattr(regime.qdata_api, "load_ecos", lambda *a, **k: pd.DataFrame({"value": [1]}))
    regime._ecos()

    def unavailable(*args, **kwargs):
        raise OSError("mirror unavailable")

    monkeypatch.setattr(regime.qdata_api, "load_ecos", unavailable)
    clock[0] = 900.0
    with pytest.raises(OSError, match="mirror unavailable"):
        regime._ecos()


def test_oecd_cache_expires_and_keeps_countries_separate(monkeypatch):
    clock = [600.0]
    calls = []
    monkeypatch.setattr(regime.time, "time", lambda: clock[0])

    def load(country):
        calls.append(country)
        return pd.Series([len(calls)], name=country)

    monkeypatch.setattr(regime.qdata_api, "load_oecd_cli", load)
    assert regime._cli("KOR").iloc[0] == 1
    assert regime._cli("USA").iloc[0] == 2
    assert regime._cli("KOR").iloc[0] == 1
    clock[0] = 900.0
    assert regime._cli("KOR").iloc[0] == 3


def test_us_macro_and_cpi_see_new_publication_in_warm_process(monkeypatch):
    clock = [600.0]
    calls = []
    monkeypatch.setattr(regime.time, "time", lambda: clock[0])

    def load(series):
        calls.append(series[0])
        return pd.DataFrame({series[0]: [len(calls)]})

    monkeypatch.setattr(regime.qdata_api, "load_fred", load)
    assert regime._fred("VIXCLS").iloc[0] == 1
    assert regime._cpi().iloc[0] == 2
    clock[0] = 899.0
    assert regime._cpi().iloc[0] == 2
    clock[0] = 900.0
    assert regime._fred("VIXCLS").iloc[0] == 3
    assert regime._cpi().iloc[0] == 4


def test_hy_price_cache_expires_and_failed_read_is_not_old_success(monkeypatch):
    from datastore import prices

    clock = [600.0]
    monkeypatch.setattr(regime.time, "time", lambda: clock[0])
    monkeypatch.setattr(prices, "us_adj_close_wide", lambda *a: pd.DataFrame({"HYG": [100]}))
    assert regime._hyg_ief().iloc[0, 0] == 100
    clock[0] = 900.0

    def fail(*a):
        raise OSError("price mirror unavailable")

    monkeypatch.setattr(prices, "us_adj_close_wide", fail)
    with pytest.raises(OSError, match="unavailable"):
        regime._hyg_ief()
