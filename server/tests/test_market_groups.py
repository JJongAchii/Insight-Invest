import json

import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import insight
from datastore import storage
from module import market_groups as mg


def inputs():
    dates = pd.bdate_range("2025-12-29", periods=26)
    rows = []
    for ticker, cap, last in [("001", 300, 110), ("002", 100, 90), ("003", 200, 100)]:
        for date in dates:
            close = last if date == dates[-1] else 100
            rows.append(
                dict(
                    date=date,
                    ticker=ticker,
                    market="KOSPI",
                    close=close,
                    adj_close=close,
                    mktcap=cap,
                    value=20,
                )
            )
    px = pd.DataFrame(rows)
    sec = pd.DataFrame(
        [
            dict(date=dates[0], ticker=t, sector="반도체", market="KOSPI")
            for t in ["001", "002", "003"]
        ]
    )
    master = pd.DataFrame(
        [
            dict(ticker=t, name=t, sector="반도체", market="KOSPI", meta_id=i)
            for i, t in enumerate(["001", "002", "003"], 1)
        ]
    )
    flows = pd.DataFrame(
        [
            dict(date=d, ticker=t, investor=inv, net_value=10)
            for d in dates
            for t in ["001", "002", "003"]
            for inv in ["frgn", "inst"]
        ]
    )
    fund = pd.DataFrame(
        [
            dict(date=dates[-1], ticker="001", per=10, pbr=1, div=2),
            dict(date=dates[-1], ticker="002", per=0, pbr=-1, div=0),
        ]
    )
    idx = pd.DataFrame(
        [dict(date=d, index_code="1001", close=105 if d == dates[-1] else 100) for d in dates]
    )
    themes = [
        dict(
            id="test",
            name="대표 테마",
            description="설명",
            reviewed_at="2026-02-03",
            source_as_of="2026-01-01",
            sources=[dict(label="출처", url="https://example.com")],
            members=[dict(ticker="001", name="001"), dict(ticker="002", name="002")],
        )
    ]
    return px, sec, master, flows, fund, idx, themes


def detail(out, kind="theme", period="1d", group="test", market="ALL"):
    row = out[
        (out.kind == kind)
        & (out.period == period)
        & (out.group_id == group)
        & (out.market == market)
    ]
    return json.loads(row.iloc[0].detail_json)


def test_lagged_cap_contribution_and_market_comparison():
    out = mg.build_snapshots(*inputs())
    d = detail(out)
    assert d["summary"]["return_pct"] == pytest.approx(5)
    assert [m["contribution_1d_pp"] for m in d["members"]] == pytest.approx([7.5, -2.5])
    assert sum(m["contribution_1d_pp"] for m in d["members"]) == pytest.approx(
        d["summary"]["ret_1d"]
    )
    assert d["summary"]["advancing_pct"] == 50
    assert d["summary"]["history_basis"] == "current_representatives"
    kr = detail(out, market="KOSPI")
    assert kr["summary"]["benchmark_return_pct"] == 5
    assert kr["summary"]["excess_pp"] == pytest.approx(0)
    assert len(kr["history"]) == 2
    assert kr["history"][0]["group_pct"] == 0


def test_missing_flows_are_not_zero_and_incomplete_windows_are_visible():
    args = list(inputs())
    last = args[0].date.max()
    args[3] = args[3][
        ~((args[3].ticker == "002") & (args[3].investor == "frgn") & (args[3].date == last))
    ]
    d = detail(mg.build_snapshots(*args), period="1w")
    by_ticker = {m["ticker"]: m for m in d["members"]}
    assert by_ticker["002"]["frgn_net"] is None
    assert by_ticker["002"]["frgn_days"] == 4
    assert by_ticker["001"]["frgn_net"] == 50
    assert d["summary"]["frgn_net"] == 50
    assert d["summary"]["frgn_covered_count"] == 1
    assert d["summary"]["inst_covered_count"] == 2


def test_missing_price_new_listing_and_fundamentals_preserve_members():
    args = list(inputs())
    last = args[0].date.max()
    args[0] = args[0][~((args[0].ticker == "002") & (args[0].date == last))]
    d = detail(mg.build_snapshots(*args), period="1m")
    assert d["summary"]["member_count"] == 2
    assert d["summary"]["price_covered_count"] == 1
    second = next(m for m in d["members"] if m["ticker"] == "002")
    assert second["return_pct"] is None
    assert second["contribution_1d_pp"] is None
    assert second["per"] is None and second["pbr"] is None
    args = list(inputs())
    args[0] = args[0][(args[0].ticker != "002") | (args[0].date >= last - pd.Timedelta(days=5))]
    d = detail(mg.build_snapshots(*args), period="1m")
    assert d["summary"]["period_covered_count"] == 1
    assert next(m for m in d["members"] if m["ticker"] == "002")["return_pct"] is None


def test_ytd_uses_last_previous_year_close_and_short_windows_are_unknown():
    out = mg.build_snapshots(*inputs())
    d = detail(out, period="ytd")
    assert d["summary"]["start_date"] == "2025-12-31"
    assert d["summary"]["return_pct"] == pytest.approx(5)
    short = detail(out, period="3m")
    assert short["summary"]["return_pct"] is None
    assert short["summary"]["start_date"] is None
    assert short["history"] == []
    assert all(m["return_pct"] is None for m in short["members"])


def test_sector_uses_dated_membership_and_keeps_small_groups():
    args = list(inputs())
    dates = sorted(args[0].date.unique())
    # 001 rose 10% before moving into a different sector. It must not become
    # a historical member of the new sector through today's master.
    args[0].loc[(args[0].ticker == "001") & (args[0].date >= dates[-3]), "adj_close"] = 110
    args[2].loc[args[2].ticker == "001", "sector"] = "새업종"
    out = mg.build_snapshots(*args)
    d = detail(out, kind="sector", group="반도체", market="KOSPI", period="1w")
    assert d["summary"]["member_count"] == 2
    assert d["summary"]["history_basis"] == "dated_classification"
    assert d["history"][-3]["group_pct"] == pytest.approx(5)
    new = detail(out, kind="sector", group="새업종", market="KOSPI")
    assert new["summary"]["member_count"] == 1


def test_duplicate_inputs_fail_instead_of_multiplying_members():
    args = list(inputs())
    args[0] = pd.concat([args[0], args[0].iloc[:1]])
    with pytest.raises(ValueError, match="prices: duplicate"):
        mg.build_snapshots(*args)


def test_missing_session_does_not_turn_a_multi_day_move_into_daily_return():
    args = list(inputs())
    dates = sorted(args[0].date.unique())
    args[0] = args[0][~((args[0].ticker == "002") & (args[0].date == dates[-2]))]
    d = detail(mg.build_snapshots(*args))
    row = next(m for m in d["members"] if m["ticker"] == "002")
    assert row["ret_1d"] is None
    assert row["relative_value20"] is None
    assert row["contribution_1d_pp"] is None


def test_unavailable_theme_member_is_retained_and_missing_benchmark_is_null():
    args = list(inputs())
    args[6][0]["members"].append(dict(ticker="404", name="미확인 종목"))
    args[5] = pd.DataFrame()
    d = detail(mg.build_snapshots(*args))
    assert d["summary"]["member_count"] == 3
    assert d["summary"]["price_covered_count"] == 2
    assert next(m for m in d["members"] if m["ticker"] == "404")["meta_id"] is None
    d = detail(mg.build_snapshots(*args), market="KOSPI")
    assert d["summary"]["benchmark_return_pct"] is None


def test_api_filters_one_atomic_snapshot_and_validates_queries(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    app = FastAPI()
    app.include_router(insight.router)
    client = TestClient(app)
    assert client.get("/insight/groups").json() == {"as_of": None, "rows": []}
    out = mg.build_snapshots(*inputs())
    storage.write_parquet(out, "insight", "market_groups.parquet", row_group_size=1)
    overview = client.get("/insight/groups?kind=theme&market=ALL&period=1w").json()
    selected = client.get(
        "/insight/groups/detail?group=test&kind=theme&market=ALL&period=1w"
    ).json()
    assert overview["rows"] == [selected["summary"]]
    assert client.get("/insight/groups?period=bad").status_code == 422
    assert client.get("/insight/groups/detail").status_code == 422
    assert client.get("/insight/groups/detail?group=missing").json()["summary"] is None


def test_shipped_theme_registry_has_unique_members_and_reviewable_sources():
    themes = mg.load_themes()
    assert len(themes) == 6
    for theme in themes:
        assert theme["source_as_of"] <= theme["reviewed_at"]
        assert all(source["url"].startswith("https://") for source in theme["sources"])
