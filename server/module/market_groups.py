"""Descriptive KR sector/theme snapshots. No strategy signals or portfolio weights.

The batch publishes each period's summary, members and chart together in one
parquet object. The API only projects/filters it; it never joins the lake.
Sector history uses dated classifications. Theme history explicitly reconstructs
today's curated basket, not historical membership or an ETF's return.
"""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

PERIODS = {"1d": 1, "1w": 5, "1m": 21, "3m": 63, "ytd": None}
MARKETS = ("KOSPI", "KOSDAQ")


def load_themes() -> list[dict]:
    data = json.loads(Path(__file__).with_name("market_themes.json").read_text())
    themes = data["themes"]
    if len({t["id"] for t in themes}) != len(themes):
        raise ValueError("Duplicate theme id")
    for theme in themes:
        tickers = [m["ticker"] for m in theme["members"]]
        if not tickers or len(set(tickers)) != len(tickers):
            raise ValueError(f"Invalid theme members: {theme['id']}")
        if not theme["sources"] or not theme["reviewed_at"]:
            raise ValueError(f"Missing theme provenance: {theme['id']}")
    return themes


def _unique(df, keys, label):
    if df.duplicated(keys).any():
        raise ValueError(f"{label}: duplicate {keys}")


def _clean(value):
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return round(float(value), 6) if math.isfinite(value) else None
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    return value


def _daily(panel):
    valid = panel[panel["ret_1d"].notna() & panel["previous_cap"].gt(0)].copy()
    valid["weighted"] = valid["ret_1d"] * valid["previous_cap"]
    grouped = valid.groupby("date").agg(
        weighted=("weighted", "sum"), cap=("previous_cap", "sum"), n=("ticker", "size")
    )
    return grouped["weighted"] / grouped["cap"]


def _path(daily, dates):
    """Missing sessions are unknown, not flat. The base is the previous close."""
    if len(dates) < 2:
        return pd.Series(dtype=float)
    changes = daily.reindex(dates[1:])
    values = ((1 + changes / 100).cumprod(skipna=False) - 1) * 100
    return pd.concat([pd.Series([0.0], index=dates[:1]), values])


def build_snapshots(prices, sectors, master, flows, fundamentals, indices, themes):
    """Pure producer, with explicit input frames for causal/coverage tests.

    Period returns require both exact endpoints. Investor totals require every
    session in the period; incomplete tickers remain in the members with null
    totals and observed-day counts. Contribution is always for the latest day.
    All percentages are 0..100 units; contributions/excess are percentage points.
    """
    px = prices.copy()
    px["date"] = pd.to_datetime(px["date"]).astype("datetime64[ns]").dt.normalize()
    px = px[px["market"].isin(MARKETS)].sort_values(["ticker", "date"])
    _unique(px, ["date", "ticker"], "prices")
    if px.empty:
        raise ValueError("No KR prices")
    dates = pd.DatetimeIndex(sorted(px["date"].unique()))
    as_of = dates[-1]
    previous_date = pd.Series(dates[:-1], index=dates[1:])
    grouped = px.groupby("ticker", sort=False)
    prior_close = grouped["adj_close"].shift()
    consecutive = grouped["date"].shift().eq(px["date"].map(previous_date))
    px["ret_1d"] = ((px["adj_close"] / prior_close - 1) * 100).where(
        consecutive & prior_close.gt(0) & px["adj_close"].gt(0)
    )
    px["previous_cap"] = grouped["mktcap"].shift().where(consecutive)
    px["value_mean20"] = grouped["value"].transform(
        lambda values: values.shift().rolling(20, min_periods=20).mean()
    )
    previous_twenty = pd.Series(dates[:-20], index=dates[20:])
    px["value_mean20"] = px["value_mean20"].where(
        grouped["date"].shift(20).eq(px["date"].map(previous_twenty))
    )

    sec = sectors.copy()
    sec["date"] = pd.to_datetime(sec["date"]).astype("datetime64[ns]").dt.normalize()
    sec = sec[sec["date"] <= as_of]
    _unique(sec, ["date", "ticker"], "classification")
    current = master[master["market"].isin(MARKETS)].copy()
    _unique(current, ["ticker"], "stock master")
    missing_master = set(px.loc[px["date"].eq(as_of), "ticker"]) - set(current["ticker"])
    if missing_master:
        raise ValueError(f"Latest prices missing from stock master: {len(missing_master)}")
    current["sector"] = current["sector"].fillna("미분류").replace("", "미분류")
    # The settled stock master can classify a new listing between irregular
    # sector snapshots. Apply that observation only on its own date.
    current_class = current[["ticker", "sector"]].assign(date=as_of)
    sec = pd.concat([sec, current_class], ignore_index=True).drop_duplicates(
        ["date", "ticker"], keep="last"
    )
    classified = pd.merge_asof(
        px.sort_values("date"),
        sec[["date", "ticker", "sector"]].sort_values("date"),
        on="date",
        by="ticker",
        direction="backward",
    )
    classified["sector"] = classified["sector"].fillna("미분류")
    latest = px[px["date"].eq(as_of)].drop(columns=["market"])
    current = current.drop(columns=["mktcap"], errors="ignore").merge(
        latest, on="ticker", how="left", validate="one_to_one"
    )
    current["price_as_of"] = current["date"]
    current["relative_value20"] = current["value"] / current["value_mean20"].where(
        current["value_mean20"].gt(0)
    )
    current["basis"] = "KRX 업종 분류"

    fund = fundamentals.copy()
    if not fund.empty:
        fund["date"] = pd.to_datetime(fund["date"]).astype("datetime64[ns]").dt.normalize()
        fund = fund[fund["date"] <= as_of]
        _unique(fund, ["date", "ticker"], "fundamentals")
        fund = fund.sort_values("date").drop_duplicates("ticker", keep="last")
    fund = fund.reindex(columns=["ticker", "date", "per", "pbr", "div"])
    fund = fund.rename(columns={"date": "valuation_as_of"})
    for field in ("per", "pbr"):
        fund[field] = pd.to_numeric(fund[field], errors="coerce").where(fund[field].gt(0))
    current = current.merge(fund, on="ticker", how="left", validate="one_to_one")

    flow = flows.copy()
    if not flow.empty:
        flow["date"] = pd.to_datetime(flow["date"]).astype("datetime64[ns]").dt.normalize()
        flow["investor"] = flow["investor"].str.lower()
        flow = flow[flow["date"].isin(dates) & flow["investor"].isin(["frgn", "inst"])]
        _unique(flow, ["date", "ticker", "investor"], "flows")
    flow = flow.reindex(columns=["date", "ticker", "investor", "net_value"])

    benchmarks = {"ALL": _daily(px)}
    idx = indices.copy()
    if not idx.empty:
        idx["date"] = pd.to_datetime(idx["date"]).astype("datetime64[ns]").dt.normalize()
        _unique(idx, ["date", "index_code"], "indices")
    idx = idx.reindex(columns=["date", "index_code", "close"])
    for market, code in (("KOSPI", "1001"), ("KOSDAQ", "2001")):
        levels = idx[idx["index_code"].eq(code)].set_index("date")["close"]
        levels = levels.reindex(dates).where(lambda x: x > 0)
        benchmarks[market] = levels.pct_change(fill_method=None) * 100

    # Each named group is defined by a composite market + classification key.
    groups = []
    for (market, sector), members in current.groupby(["market", "sector"], sort=True):
        panel = classified[classified["market"].eq(market) & classified["sector"].eq(sector)]
        groups.append(
            (
                {
                    "id": sector,
                    "kind": "sector",
                    "market": market,
                    "name": sector,
                    "description": f"{market}의 KRX 업종 분류에 속한 종목입니다.",
                    "classification_as_of": sec["date"].max(),
                    "source_as_of": sec["date"].max(),
                    "reviewed_at": None,
                    "sources": [
                        {"label": "한국거래소 업종 분류", "url": "https://data.krx.co.kr/"}
                    ],
                    "history_basis": "dated_classification",
                },
                members.copy(),
                panel,
            )
        )
    for theme in themes:
        definitions = pd.DataFrame(theme["members"]).rename(columns={"name": "reference_name"})
        _unique(definitions, ["ticker"], "theme members")
        members = definitions.merge(current, on="ticker", how="left", validate="one_to_one")
        members["name"] = members["name"].fillna(members["reference_name"])
        members["basis"] = "운용사 공개자료를 참고해 선정한 대표 종목"
        for market in ("ALL", *MARKETS):
            selected = members if market == "ALL" else members[members["market"].eq(market)]
            if selected.empty:
                continue
            panel = px[px["ticker"].isin(selected["ticker"])]
            groups.append(
                (
                    {
                        "id": theme["id"],
                        "kind": "theme",
                        "market": market,
                        "name": theme["name"],
                        "description": theme["description"],
                        "classification_as_of": theme["reviewed_at"],
                        "source_as_of": theme["source_as_of"],
                        "reviewed_at": theme["reviewed_at"],
                        "sources": theme["sources"],
                        "history_basis": "current_representatives",
                    },
                    selected.copy(),
                    panel,
                )
            )

    period_members = {}
    for period, count in PERIODS.items():
        if count is None:
            earlier = dates[dates < pd.Timestamp(as_of.year, 1, 1)]
            base = earlier[-1] if len(earlier) else None
        else:
            base = dates[-count - 1] if len(dates) > count else None
        window = dates[dates >= base] if base is not None else pd.DatetimeIndex([])
        endpoint = px[px["date"].eq(base)][["ticker", "adj_close"]].rename(
            columns={"adj_close": "base_close"}
        )
        returns = current[["ticker", "adj_close"]].merge(endpoint, on="ticker", how="left")
        returns["return_pct"] = ((returns["adj_close"] / returns["base_close"] - 1) * 100).where(
            returns["base_close"].gt(0) & returns["adj_close"].gt(0)
        )
        returns = returns[["ticker", "return_pct"]].set_index("ticker")
        for investor, label in (("frgn", "frgn"), ("inst", "inst")):
            selected = flow[flow["date"].isin(window[1:]) & flow["investor"].eq(investor)]
            sums = selected.groupby("ticker")["net_value"].agg(["sum", "count"])
            returns[f"{label}_days"] = sums["count"].reindex(returns.index).fillna(0).astype(int)
            returns[f"{label}_net"] = sums["sum"].where(
                sums["count"].eq(len(window) - 1) & (len(window) > 1)
            )
        period_members[period] = (base, window, returns)

    rows = []
    for info, members, panel in groups:
        daily = _daily(panel)
        total_cap = members["mktcap"].where(members["mktcap"].gt(0)).sum(min_count=1)
        members["weight_pct"] = members["mktcap"].where(members["mktcap"].gt(0)) / total_cap * 100
        valid = members["ret_1d"].notna() & members["previous_cap"].gt(0)
        denominator = members.loc[valid, "previous_cap"].sum(min_count=1)
        members["contribution_1d_pp"] = (
            members["ret_1d"] * members["previous_cap"] / denominator
        ).where(valid)
        market = info["market"]
        market_members = current if market == "ALL" else current[current["market"].eq(market)]
        market_cap = market_members["mktcap"].where(market_members["mktcap"].gt(0)).sum(min_count=1)
        for period, (base, window, metrics) in period_members.items():
            selected = members.join(metrics, on="ticker", validate="one_to_one")
            path = _path(daily, window)
            bench = _path(benchmarks[market], window)
            ret = path.iloc[-1] if len(path) else np.nan
            bret = bench.iloc[-1] if len(bench) else np.nan
            covered = selected["return_pct"].dropna()
            up = int(covered.gt(0).sum())
            summary = {
                **info,
                "period": period,
                "as_of": as_of,
                "start_date": base,
                "return_pct": ret,
                "benchmark_return_pct": bret,
                "excess_pp": ret - bret,
                "benchmark_name": "KR 전체 시총가중" if market == "ALL" else market,
                "ret_1d": daily.get(as_of, np.nan),
                "member_count": len(selected),
                "period_covered_count": len(covered),
                "price_covered_count": int(selected["close"].notna().sum()),
                "daily_covered_count": int(valid.sum()),
                "advancing_count": up,
                "declining_count": int(covered.lt(0).sum()),
                "unchanged_count": int(covered.eq(0).sum()),
                "advancing_pct": up / len(covered) * 100 if len(covered) else np.nan,
                "median_return_pct": covered.median(),
                "market_cap": total_cap,
                "market_weight_pct": total_cap / market_cap * 100,
                "top3_weight_pct": selected["weight_pct"].nlargest(3).sum(min_count=1),
                "flow_days": max(len(window) - 1, 0),
                "flows_as_of": flow["date"].max() if not flow.empty else None,
                "fundamentals_as_of": fund["valuation_as_of"].max() if not fund.empty else None,
            }
            for label in ("frgn", "inst"):
                summary[f"{label}_net"] = selected[f"{label}_net"].sum(min_count=1)
                summary[f"{label}_covered_count"] = int(selected[f"{label}_net"].notna().sum())
            columns = [
                "ticker",
                "name",
                "meta_id",
                "market",
                "sector",
                "close",
                "price_as_of",
                "weight_pct",
                "return_pct",
                "ret_1d",
                "contribution_1d_pp",
                "value",
                "relative_value20",
                "frgn_net",
                "frgn_days",
                "inst_net",
                "inst_days",
                "per",
                "pbr",
                "div",
                "valuation_as_of",
                "basis",
            ]
            records = selected.sort_values("weight_pct", ascending=False, na_position="last")
            history = [
                {"date": date, "group_pct": value, "benchmark_pct": bench.get(date)}
                for date, value in path.items()
            ]
            detail = {
                "summary": summary,
                "members": records.reindex(columns=columns).to_dict("records"),
                "history": history,
            }
            rows.append(
                {
                    "kind": info["kind"],
                    "market": market,
                    "group_id": info["id"],
                    "period": period,
                    "as_of": as_of.strftime("%Y-%m-%d"),
                    "summary_json": json.dumps(
                        _clean(summary), ensure_ascii=False, allow_nan=False
                    ),
                    "detail_json": json.dumps(_clean(detail), ensure_ascii=False, allow_nan=False),
                }
            )
    return (
        pd.DataFrame(rows)
        .sort_values(["kind", "market", "period", "group_id"])
        .reset_index(drop=True)
    )
