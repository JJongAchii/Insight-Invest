"""장중 시장 지도 — 누가 지수를 움직였고, 얼마나 넓게 움직였고, 어디에 돈이 몰렸나 (스펙 2026-11-27 §5).

표시와 해설 입력에만 쓴다. 레이크·신호·백테스트에 쓰지 않는다(2026-08-11 장중 격리 불변식). 종목 등락률은 KRX 제공값을
그대로 쓰고 종가로 다시 계산하지 않는다. 시장 폭은 거래소 통계처럼 상장 종목 전부를 세고, 종목 목록(기여·상하한가·쏠림·묶음)은
스팩을 뺀다 — 스팩은 공모가에 묶여 목록을 오염시킨다.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

MARKETS = ("KOSPI", "KOSDAQ")
LIMIT_PCT = 29.5          # 가격제한폭 ±30%
BIG_MOVE_PCT = 10.0
GROUP_MOVE_PCT = 7.0
GROUP_MIN = 3
TOP = 5
SPIKES = 8
SPIKE_MIN_VALUE = 1e10    # 거래대금 100억 원 이상
SPIKE_MIN_MULTIPLE = 3.0  # 평소 하루치의 3배 이상
CROSSINGS = {"KOSPI": 2.0, "KOSDAQ": 3.0}
SINCE_MIN_DELTA = 0.3     # 노트 이후 지수 변화가 이보다 작고 새 종목도 없으면 보이지 않는다


def _listed(latest: pd.DataFrame) -> pd.DataFrame:
    """종목 목록에 올릴 수 있는 종목: 스팩·등락률 결측·시총 없음·이름 없음 제외. 이름이 없는 것은 업종표에 아직 없는
    신규상장이다 — 상장 첫날 등락률은 공모가 기준(가격제한폭 60~400%)이라 상한가·기여에 섞으면 틀리고, 스팩인지도 모른다."""
    names = latest["name"].fillna("")
    return latest[names.ne("") & ~names.str.contains("스팩") & latest["chg_pct"].notna() & latest["cap"].gt(0)]


def _stock(row, **extra) -> dict:
    return {"ticker": row.ticker, "name": row.name, "sector": row.sector, "chg_pct": round(float(row.chg_pct), 2),
            "value": float(row.value), **extra}


def _market(latest: pd.DataFrame, market: str) -> dict:
    everyone = latest[latest["market"].eq(market) & latest["chg_pct"].notna()]
    chg = everyone["chg_pct"]
    listed = _listed(everyone).copy()
    listed["prev_cap"] = listed["cap"] / (1 + listed["chg_pct"] / 100)
    listed["contrib_pp"] = (listed["cap"] - listed["prev_cap"]) / listed["prev_cap"].sum() * 100
    approx = float(listed["contrib_pp"].sum())
    rising = listed[listed["contrib_pp"].gt(0)].nlargest(TOP, "contrib_pp")
    falling = listed[listed["contrib_pp"].lt(0)].nsmallest(TOP, "contrib_pp")
    # 상위 10종목 비중은 기여 절댓값으로 잰다. 부호 있는 합을 지수 변화로 나누면 보합·혼조 날 수천 %가 된다.
    moved = listed["contrib_pp"].abs()
    top10 = moved.nlargest(10).sum() / moved.sum() if moved.sum() > 0 else None
    sectors = listed[listed["sector"].ne("기타")].groupby("sector").agg(
        contrib_pp=("contrib_pp", "sum"), median=("chg_pct", "median"), n=("chg_pct", "size"))
    sectors = sectors[sectors["n"].ge(5)].sort_values("contrib_pp")
    sector_rows = [{"sector": name, "contrib_pp": round(float(r["contrib_pp"]), 3), "median": round(float(r["median"]), 2),
                    "n": int(r["n"])} for name, r in pd.concat([sectors.tail(3).iloc[::-1], sectors.head(3)]).iterrows()]

    def limit(mask):
        return [_stock(r) for r in listed[mask(listed["chg_pct"])].sort_values("name").itertuples()]

    return {
        "approx_chg_pct": round(approx, 2),
        "top10_share": None if top10 is None else round(float(top10), 2),
        "breadth": {"up": int((chg > 0).sum()), "down": int((chg < 0).sum()), "flat": int((chg == 0).sum()),
                    "median": round(float(chg.median()), 2), "up10": int((chg >= BIG_MOVE_PCT).sum()),
                    "down10": int((chg <= -BIG_MOVE_PCT).sum()),
                    "limit_up": limit(lambda s: s >= LIMIT_PCT), "limit_down": limit(lambda s: s <= -LIMIT_PCT)},
        "contributors": {"up": [_stock(r, contrib_pp=round(float(r.contrib_pp), 3)) for r in rising.itertuples()],
                         "down": [_stock(r, contrib_pp=round(float(r.contrib_pp), 3)) for r in falling.itertuples()]},
        "sectors": sector_rows,
    }


def _spikes(latest: pd.DataFrame, baseline: pd.DataFrame | None) -> list[dict]:
    if baseline is None or baseline.empty:
        return []
    joined = _listed(latest).merge(baseline[["ticker", "avg_value"]], on="ticker")
    joined = joined[joined["avg_value"].gt(0) & joined["value"].ge(SPIKE_MIN_VALUE)].copy()
    joined["multiple"] = joined["value"] / joined["avg_value"]
    joined = joined[joined["multiple"].ge(SPIKE_MIN_MULTIPLE)].nlargest(SPIKES, "multiple")
    return [_stock(r, market=r.market, multiple=round(float(r.multiple), 2)) for r in joined.itertuples()]


def _groups(latest: pd.DataFrame, themes: list[dict]) -> list[dict]:
    listed = _listed(latest).set_index("ticker")
    found = []
    for theme in themes:
        members = listed.reindex([m["ticker"] for m in theme["members"]]).dropna(subset=["chg_pct"])
        for direction, mask in (("up", members["chg_pct"] >= GROUP_MOVE_PCT), ("down", members["chg_pct"] <= -GROUP_MOVE_PCT)):
            moved = members[mask].sort_values("chg_pct", ascending=direction == "down")
            if len(moved) >= GROUP_MIN:
                found.append({"id": theme["id"], "name": theme["name"], "direction": direction,
                              "members": [{"ticker": t, "name": r["name"], "chg_pct": round(float(r["chg_pct"]), 2)}
                                          for t, r in moved.iterrows()]})
    return sorted(found, key=lambda g: (-len(g["members"]), -abs(np.median([m["chg_pct"] for m in g["members"]]))))


def build_map(latest: pd.DataFrame, indices: dict, baseline: pd.DataFrame | None, themes: list[dict],
              observed_at: str) -> dict:
    """KRX 같은 시각 스냅샷 하나로 만든 지도. `indices`는 {"KOSPI": {"level", "chg_pct"}, ...}."""
    spikes = _spikes(latest, baseline)
    return {
        "version": 1,
        "trade_date": datetime.fromisoformat(observed_at).date().isoformat(),
        "observed_at": observed_at,
        "indices": {key: {"level": value.get("level"),
                          "chg_pct": None if value.get("chg_pct") is None else round(float(value["chg_pct"]), 2)}
                    for key, value in indices.items()},
        "markets": {market: _market(latest, market) for market in MARKETS},
        "value_spikes": spikes,
        "value_spikes_state": "ready" if baseline is not None and not baseline.empty else "unavailable",
        "groups": _groups(latest, themes),
    }


def series_entry(map_: dict) -> dict:
    """노트 이후 변화를 셀 수 있을 만큼만 남긴 지도."""
    markets = map_["markets"].values()
    names = {}

    def tickers(rows):
        for row in rows:
            names[row["ticker"]] = row["name"]
        return [row["ticker"] for row in rows]

    return {
        "observed_at": map_["observed_at"],
        "indices": {key: value["chg_pct"] for key, value in map_["indices"].items()},
        "limit_up": tickers([s for m in markets for s in m["breadth"]["limit_up"]]),
        "limit_down": tickers([s for m in markets for s in m["breadth"]["limit_down"]]),
        "leaders": tickers([s for m in markets for side in ("up", "down") for s in m["contributors"][side][:3]]),
        "spikes": tickers(map_["value_spikes"]),
        "names": names,
    }


def since(old: dict, new: dict) -> dict | None:
    """두 시점 사이에 달라진 것. 지수 변화가 작고 새 종목도 없으면 None."""
    indices = {}
    for key, to in new["indices"].items():
        start = old["indices"].get(key)
        if start is not None and to is not None:
            indices[key] = {"from": start, "to": to, "delta": round(to - start, 2)}

    def added(field):
        known = set(old[field])
        return [{"ticker": t, "name": new["names"].get(t, t)} for t in new[field] if t not in known]

    change = {"from": old["observed_at"], "to": new["observed_at"], "indices": indices,
              "new_limit_up": added("limit_up"), "new_limit_down": added("limit_down"),
              "new_leaders": added("leaders"), "new_spikes": added("spikes")}
    moved = any(abs(item["delta"]) >= SINCE_MIN_DELTA for item in indices.values())
    named = any(change[field] for field in ("new_limit_up", "new_limit_down", "new_spikes"))
    return change if moved or named else None


def value_baseline(daily: pd.DataFrame, trade_date: str, sessions: int = 20) -> pd.DataFrame:
    """trade_date 이전 거래일 `sessions`개의 종목별 평균 거래대금. 당일 값은 장중 누적이라 넣지 않는다."""
    dates = pd.to_datetime(daily["date"])
    before = daily[dates < pd.Timestamp(trade_date)]
    recent = sorted(pd.to_datetime(before["date"]).unique())[-sessions:]
    window = before[pd.to_datetime(before["date"]).isin(recent)]
    out = window.groupby("ticker", as_index=False)["value"].mean()
    return out.rename(columns={"value": "avg_value"})


def index_crossings(timeline: pd.DataFrame, thresholds: dict[str, float] = CROSSINGS) -> list[dict]:
    """전일 대비 등락률이 기준(코스피 ±2%, 코스닥 ±3%)을 처음 넘은 수집 시각. 방향별 하루 한 번.
    화면에 보이는 소수 둘째 자리 값으로 비교한다(+3.00%로 보이면 넘은 것이다)."""
    index = timeline[timeline["kind"].eq("index") & timeline["chg_pct"].notna()].sort_values("as_of")
    found = []
    for key, threshold in thresholds.items():
        rows = index[index["key"].eq(key)]
        shown = rows["chg_pct"].round(2)
        for direction, mask in (("up", shown >= threshold), ("down", shown <= -threshold)):
            hit = rows[mask]
            if not hit.empty:
                first = hit.iloc[0]
                found.append({"id": f"{first['trade_date']}/cross/{key}/{direction}", "index": key,
                              "direction": direction, "threshold": threshold, "observed_at": first["as_of"],
                              "chg_pct": round(float(first["chg_pct"]), 2)})
    return sorted(found, key=lambda c: c["observed_at"])
