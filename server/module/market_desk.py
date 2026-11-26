"""Publish comparable KRX observations for the private editorial worker."""

from datetime import datetime
from math import isfinite

import numpy as np
import pandas as pd

from module.kr_intraday import KST


INDEX_NAMES = {"KOSPI": "코스피", "KOSDAQ": "코스닥"}


def _sector_reading(stocks, stamp):
    # Use the same collection as the indices. Missing prices or weights cannot explain a sector return.
    required = {"as_of", "sector", "chg_pct", "cap", "name"}
    if not required.issubset(stocks.columns):
        return "", ""
    sample = stocks.loc[stocks["as_of"].eq(stamp) & stocks["sector"].ne("기타")
                        & np.isfinite(stocks["chg_pct"]) & np.isfinite(stocks["cap"]) & stocks["cap"].gt(0)].reset_index(drop=True)
    sample["contribution"] = sample["cap"].astype(float) * sample["chg_pct"]
    sectors = sample.groupby("sector").agg(
        count=("chg_pct", "size"), median=("chg_pct", "median"), cap=("cap", "sum"), total=("contribution", "sum"),
    )
    sectors = sectors.loc[sectors["count"].ge(5)]
    if len(sectors) < 2:
        return "", ""
    returns = (sectors["total"] / sectors["cap"]).sort_values()
    weak, strong = returns.index[0], returns.index[-1]
    if returns.iloc[-1] - returns.iloc[0] < 0.1:
        return "비교 가능한 업종의 시가총액 가중 등락률 차이는 0.1%p 미만입니다.", ""
    summary = (f"업종별 시가총액 가중 등락률은 {strong}({returns.iloc[-1]:+.2f}%)에서 가장 높고 "
               f"{weak}({returns.iloc[0]:+.2f}%)에서 가장 낮았습니다.")
    # Within the strongest rising or weakest falling sector, distinguish one large mover from broad participation.
    focus = strong if returns.iloc[-1] > 0 else weak
    sign = 1 if returns[focus] > 0 else -1
    side = "상승" if sign > 0 else "하락"
    group = sample.loc[sample["sector"].eq(focus)]
    same_direction = group.loc[group["contribution"].mul(sign).gt(0)]
    if same_direction.empty:
        return summary, ""
    leader = same_direction.loc[same_direction["contribution"].mul(sign).idxmax()]
    share = leader["contribution"] / same_direction["contribution"].sum()
    if share >= 0.5 and isinstance(leader["name"], str) and leader["name"]:
        summary += (f" {focus} 종목의 등락률 중간값은 {sectors.at[focus, 'median']:+.2f}%였습니다. "
                    f"이 업종의 {side} 기여분 중 {share:.0%}가 {leader['name']} 한 종목에서 나왔습니다.")
        return summary, f"{focus}의 {side} 흐름이 업종 전반으로 번지는지는 {leader['name']} 외 종목들의 등락률에서 확인할 수 있습니다."
    return summary, f"{strong}와 {weak} 사이의 등락률 차이({returns.iloc[-1] - returns.iloc[0]:.2f}%p)가 다음 수집에서도 이어지는지 볼 수 있습니다."


def _session_reading(rows, stocks):
    if rows.empty:
        return None
    stamp = rows["as_of"].max()
    instants = rows.loc[rows["kind"].eq("index") & rows["key"].isin(INDEX_NAMES)]
    if instants.empty or not {"level", "chg_pct"}.issubset(instants.columns):
        return None
    levels = instants.pivot(index="as_of", columns="key", values="level").reindex(columns=INDEX_NAMES)
    levels = levels.apply(pd.to_numeric, errors="coerce")
    levels = levels.where(np.isfinite(levels) & levels.gt(0)).dropna()
    if stamp not in levels.index:
        return None
    at = datetime.fromisoformat(stamp).replace(tzinfo=KST)
    changes = instants.pivot(index="as_of", columns="key", values="chg_pct").reindex(index=levels.index, columns=INDEX_NAMES)
    changes = changes.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    current = changes.loc[stamp]
    title = "코스피·코스닥 장중 흐름"
    observations = []
    if current.notna().all():
        kospi, kosdaq = current["KOSPI"], current["KOSDAQ"]
        observations.append(f"전일 종가 대비 코스피는 {kospi:+.2f}%, 코스닥은 {kosdaq:+.2f}%입니다.")
        if min(kospi, kosdaq) >= 0.1 or max(kospi, kosdaq) <= -0.1:
            rising = kospi > 0
            title = "코스피·코스닥 동반 " + ("상승" if rising else "하락")
            path = changes if rising else -changes
            retreat = path.max() - path.loc[stamp]
            key = retreat.idxmax()
            if retreat[key] >= 0.5 and retreat[key] >= path[key].max() / 3:
                peak = path[key].idxmax()
                period = "오전" if datetime.fromisoformat(peak).hour < 12 else "오후"
                retraced = retreat[key] / path[key].max()
                action = "상승분" if rising else "낙폭"
                verb = "반납" if rising else "만회"
                title = f"{INDEX_NAMES[key]}, {period} {action}의 {retraced:.0%} {verb}"
                peer = "KOSPI" if key == "KOSDAQ" else "KOSDAQ"
                observations[0] = (f"{INDEX_NAMES[key]}의 전일 대비 등락률은 {peak[-5:]} 수집 때 {changes.at[peak, key]:+.2f}%, "
                                   f"{stamp[-5:]}에는 {current[key]:+.2f}%였습니다. 같은 시각 {INDEX_NAMES[peer]}는 {current[peer]:+.2f}%였습니다.")
        elif kospi >= 0.1 and kosdaq <= -0.1:
            title = "코스피는 상승, 코스닥은 하락"
        elif kosdaq >= 0.1 and kospi <= -0.1:
            title = "코스닥은 상승, 코스피는 하락"
        elif current.abs().max() < 0.1:
            title = "코스피·코스닥 모두 전일 종가 부근"
    else:
        for key, name in INDEX_NAMES.items():
            baseline = f"전일 대비 {current[key]:+.2f}%" if pd.notna(current[key]) else "전일 종가 미확인"
            observations.append(f"{name}는 {levels.at[stamp, key]:,.2f}포인트({baseline})입니다.")

    elapsed = (pd.Timestamp(stamp) - pd.to_datetime(levels.index)).total_seconds() / 60
    previous = levels.index[(elapsed >= 45) & (elapsed <= 75)]
    if len(previous):
        start = min(previous, key=lambda s: abs((pd.Timestamp(stamp) - pd.Timestamp(s)).total_seconds() / 60 - 60))
        delta = (levels.loc[stamp] / levels.loc[start] - 1) * 100
        observations.append(f"{start[-5:]}~{stamp[-5:]} 수집분 사이 지수 변화는 코스피 {delta['KOSPI']:+.2f}%, 코스닥 {delta['KOSDAQ']:+.2f}%였습니다.")
    sector, watch = _sector_reading(stocks, stamp)
    return {"observed_at": at.isoformat(), "headline": title, "market": " ".join(observations),
            "sectors": sector, "watch": watch}


def market_input(timeline: pd.DataFrame, stocks: pd.DataFrame, now: datetime) -> dict:
    day = now.astimezone(KST).date().isoformat()
    cutoff = now.astimezone(KST).strftime("%Y-%m-%d %H:%M")
    rows = timeline.loc[timeline["trade_date"].eq(day) & timeline["as_of"].le(cutoff)].drop_duplicates(
        ["as_of", "kind", "key"], keep="last")
    samples = sorted(rows["as_of"].unique())[-7:]
    leaders = {}
    for sector, group in stocks.groupby("sector"):
        leaders[sector] = [name for name in group.nlargest(6, "value")["name"] if isinstance(name, str) and name]
    moves = []
    for before, after in zip(samples, samples[1:]):
        start = datetime.fromisoformat(before).replace(tzinfo=KST)
        end = datetime.fromisoformat(after).replace(tzinfo=KST)
        if not 5 <= (end - start).total_seconds() / 60 <= 15:
            continue
        current = rows[rows["as_of"] == after].merge(
            rows[rows["as_of"] == before], on=["kind", "key"], suffixes=("", "_prev"), validate="one_to_one"
        )
        for row in current.itertuples():
            if row.kind == "index" and row.level_prev > 0:
                change = (row.level / row.level_prev - 1) * 100
                unit, threshold = "%", 0.6
            elif row.kind == "sector" and row.key != "기타" and row.n >= 5 and row.n_prev >= 5:
                change = row.chg_pct - row.chg_pct_prev
                unit, threshold = "%p", 1.0
            else:
                continue
            if not isfinite(change) or abs(change) < threshold:
                continue
            direction = "up" if change > 0 else "down"
            moves.append({
                "id": f"{day}/{row.kind}/{row.key}/{direction}", "subject": row.key, "kind": row.kind,
                "from_at": start.isoformat(), "observed_at": end.isoformat(), "change": round(change, 2),
                "unit": unit, "companies": leaders.get(row.key, []),
            })
    large_companies = [name for name in stocks.nlargest(40, "cap")["name"] if isinstance(name, str) and name]
    return {"version": 1, "trade_date": day, "observed_at": now.isoformat(), "session": _session_reading(rows, stocks),
            "quote_delay_minutes": 20, "large_companies": large_companies, "moves": moves}
