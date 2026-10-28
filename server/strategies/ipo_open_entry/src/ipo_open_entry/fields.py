"""상장 전 공시 관측값 → 사건별 원시 필드 (brief §3·§11).

모든 값은 `filed_date < listing_date`인 판본에서, 그 항목이 실린 마지막 판본
(접수일, 접수번호 순)으로 정한다. 정정 공시가 있으면 상장일 전 마지막 정정 판본이 이긴다.
값이 없으면 NaN으로 두고 0이나 추정값으로 채우지 않는다.
"""

from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd

#: 기관 수요예측 의무보유확약 기간 키(데이터셋 정규화 값).
#: 보호예수 표에서 섞여 들어온 라벨은 무시한다
COMMITTED = {"3D", "15D", "2W", "30D", "1M", "2M", "3M", "90D", "4M", "5M", "6M", "12M"}
#: 의무보유확약 표에 섞여 들어온 보호예수 표(주주별 보유주식) 열 라벨의 표지
NOT_INVESTOR = ("주식수", "보유주식", "매각제한", "유통가능")
RETAIL_GROUPS = {"일반투자자", "일반청약자", "일반청약", "일반"}
INST_GROUPS = {"기관투자자", "기관", "기관청약자"}
#: 장기 기관(H9): 수요예측 투자자군 라벨에 이 말이 들어 있으면 연기금·운용사(고유)·은행·보험 군이다
LONG_TERM_MARK = "연기금"
#: 확정 공모가 타당성 경계(밴드 하단의 30% 미만, 상단의 2배 초과는 파싱 오류로 본다)
PRICE_BAND_FLOOR = 0.3
PRICE_BAND_CEIL = 2.0

FIELDS = [
    "final_price",
    "band_low",
    "band_high",
    "offer_shares",
    "sell_shares",
    "listed_shares",
    "float_shares",
    "float_pct",
    "bookbuild_ratio",
    "bid_top_share",
    "lockup_bid_share",
    "lockup_alloc_share",
    "inst_final_alloc_shares",
    "retail_sub_shares",
    "retail_sub_amount",
    "retail_initial_alloc_shares",
    "retail_final_alloc_amount",
    "longterm_bookbuild_share",
    # brief v2 §4 확장
    "total_bid_shares",
    "restricted_pct",
    "bookbuild_count",
    "retail_sub_count",
    "offer_price_planned",
    "underwriter_fee",
    "underwriter_amount",
]
#: 문자열 필드(범주·날짜). 코드 접두("055:")는 떼고 이름만 남긴다
TEXT_FIELDS = [
    "industry",
    "lead_underwriter",
    "company_size",
    "listing_market",
    "is_venture",
    "subscription_end",
    "price_announce_date",
]
#: 유통가능 비율(%)이 이 값을 넘으면 파싱 오류로 본다
FLOAT_PCT_CEIL = 100.0
#: 비중(0~1) 필드가 이 값을 넘으면 계산이 맞지 않은 것으로 보고 결측으로 둔다
SHARE_CEIL = 1.0 + 1e-6


def pre_listing(obs: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """상장일 전에 접수된 정상 관측값만 남긴다(사건마다 자기 상장일로 자른다)."""
    o = obs.merge(events[["event_id", "listing_date"]], on="event_id", how="inner")
    # 'dash'(원문 칸이 '-')는 값이 없는 행으로 두되,
    # 구주매출처럼 '-'가 0을 뜻하는 항목을 위해 남긴다
    keep = (o["filed_date"] < o["listing_date"]) & o["value_status"].isin(["ok", "dash"])
    return o.loc[keep].drop(columns="listing_date")


def latest_doc(rows: pd.DataFrame) -> pd.DataFrame:
    """그 항목이 실린 마지막 판본의 행들."""
    if rows.empty:
        return rows
    key = rows[["filed_date", "rcept_no"]].astype(str).agg("|".join, axis=1)
    return rows[key == key.max()]


def _scalar(
    o: pd.DataFrame, metric: str, groups: set[str] | None = None, positive: bool = False
) -> float:
    rows = o[o["metric"] == metric]
    if groups is not None:
        rows = rows[rows["investor_group"].isin(groups)]
    rows = rows.dropna(subset=["value"])
    if (
        positive
    ):  # 가격이 0 이하로 파싱된 판본은 값이 없는 것으로 본다(2020년 2건, 문장 속 숫자 공백)
        rows = rows[rows["value"] > 0]
    rows = latest_doc(rows)
    return float(rows["value"].iloc[0]) if len(rows) else math.nan


def _norm(label: object) -> str:
    return re.sub(r"\s+", "", str(label))


def _table(rows: pd.DataFrame) -> pd.Series:
    """관측값이 나온 원문 표 번호(source_locator 첫 마디, 예: 'T82'). 표가 없으면 빈 문자열."""
    if "source_locator" not in rows:
        return pd.Series("", index=rows.index)
    return rows["source_locator"].fillna("").astype(str).str.split(">").str[0]


def _one_table(rows: pd.DataFrame) -> pd.DataFrame:
    """한 판본 안에 같은 항목의 표가 여럿이면 합계 행이 있는 첫 표 하나만 쓴다.

    구간을 이중으로 세지 않게 한다.
    """
    if rows.empty:
        return rows
    tables = _table(rows)
    has_total = rows.groupby(tables)["price_bucket"].apply(lambda s: (s == "total").any())
    order = sorted(tables.unique(), key=lambda x: (not has_total.get(x, False), x))
    return rows[tables == order[0]]


def _text(o: pd.DataFrame, metric: str, rows_filter=None) -> str | None:
    """문자열 항목의 상장 전 마지막 판본 값. '055:한국투자증권' 같은 코드 접두는 뗀다."""
    rows = o[(o["metric"] == metric) & (o["value_status"] == "ok")].dropna(subset=["value_text"])
    if rows_filter is not None:
        rows = rows_filter(rows)
    rows = latest_doc(rows)
    if rows.empty:
        return None
    text = str(rows["value_text"].iloc[0]).strip()
    head, sep, tail = text.partition(":")
    return tail.strip() if sep and head.strip().isalnum() and len(head.strip()) <= 4 else text


def _bucket_at_or_above_top(label: str, basis: str, band_high: float) -> bool:
    """가격대 구간이 밴드 상단 이상(또는 가격 미제시)인가.

    밴드 위치형은 라벨로, 가격 수준형은 구간 하한이 밴드 상단 이상인지로 판정한다.
    미제시 신청은 어떤 공모가든 받겠다는 신청이라 상단 이상으로 센다.
    """
    s = _norm(label)
    if "미제시" in s:
        return True
    if basis == "band_position":
        return "상단" in s and "%" not in s and "미만" not in s and "이하" not in s
    nums = [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", s)]
    if not nums or not math.isfinite(band_high):
        return False
    first = nums[0]
    head = s[s.find("원") + 1 :] if "원" in s else s
    if head.startswith(("미만", "이하")) and len(nums) == 1:
        return False
    return first >= band_high


def sell_shares(o: pd.DataFrame) -> float:
    """구주매출 주식 수. 상장 전 마지막 판본의 칸이 '-'면 구주매출이 없다는 원문 표기라 0이다."""
    rows = latest_doc(o[o["metric"] == "sell_shares"])
    values = rows.loc[rows["value_status"] == "ok", "value"].dropna()
    if len(values):
        return float(values.iloc[0])
    return 0.0 if (rows["value_status"] == "dash").any() else math.nan


def _bid_rows(o: pd.DataFrame) -> pd.DataFrame:
    """수요예측 가격대별 신청수량(합계 행)의 한 기준·한 표.

    밴드 위치 기준을 먼저, 없으면 가격 수준 기준을 쓴다.

    같은 공시에 밴드 위치 기준 표와 가격 수준 기준 표가 함께 실리는 서식이 있다
    (2019년 무렵부터 흔하다).
    두 표의 구간을 함께 더하면 약 2배가 된다 — 기준과 표를 하나만 고른다.
    """
    rows = o[(o["metric"] == "bid_shares") & (o["investor_group"].fillna("total") == "total")]
    rows = latest_doc(rows.dropna(subset=["value"]))
    if rows.empty:
        return rows
    for basis in ("band_position", "price_level"):
        part = rows[rows["basis"] == basis]
        if len(part):
            return _one_table(part)
    return _one_table(rows)


def bid_total(o: pd.DataFrame) -> float:
    """수요예측 총 신청수량(한 표의 합계 행, 없으면 구간 합)."""
    rows = _bid_rows(o)
    if rows.empty:
        return math.nan
    is_total = rows["price_bucket"] == "total"
    total = float(rows.loc[is_total, "value"].iloc[0]) if is_total.any() else rows["value"].sum()
    return total if math.isfinite(total) and total > 0 else math.nan


def bid_top_share(o: pd.DataFrame, band_high: float) -> float:
    """수요예측 신청수량 중 밴드 상단 이상(미제시 포함) 비중.

    1을 넘으면 계산이 어긋난 것이라 결측이다.
    """
    rows = _bid_rows(o)
    total = bid_total(o)
    if rows.empty or not math.isfinite(total):
        return math.nan
    buckets = rows[rows["price_bucket"] != "total"]
    at_top = np.array(
        [
            _bucket_at_or_above_top(r.price_bucket, r.basis, band_high)
            for r in buckets.itertuples(index=False)
        ],
        dtype=bool,
    )
    share = float(buckets.loc[at_top, "value"].sum() / total)
    return share if share <= SHARE_CEIL else math.nan


def lockup_bid_share(o: pd.DataFrame, total_bids: float = math.nan) -> float:
    """기관 수요예측 신청수량 중 의무보유확약 신청 비중(합계 행 기준, 한 표).

    미확약 행이 있으면 확약 / (확약 + 미확약).
    확약 기간별 행과 확약 합계만 싣는 서식(미확약 행 없음)은
    수요예측 총 신청수량(`total_bids`)을 분모로 쓴다 — 확약 수량만 분모로 쓰면 늘 1이 된다.
    합계 열 없이 투자자군 열만 싣는 서식은 `_lockup_share_by_group`.
    """
    shares = o[(o["metric"] == "lockup_bid_shares") & (o["unit"] == "shares")]
    rows = shares[shares["investor_group"].fillna("total") == "total"]
    rows = latest_doc(rows.dropna(subset=["value"]))
    if rows.empty:
        return _lockup_share_by_group(shares, total_bids)
    tables = _table(rows)
    rows = rows[tables == sorted(tables.unique())[0]]
    committed = rows.loc[rows["lockup"].isin(COMMITTED), "value"].sum()
    none = rows.loc[rows["lockup"] == "none", "value"].sum()
    denom = committed + none if none > 0 else total_bids
    if not math.isfinite(denom) or denom <= 0:
        return math.nan
    share = float(committed / denom)
    return share if share <= SHARE_CEIL else math.nan


def _lockup_share_by_group(shares: pd.DataFrame, total_bids: float) -> float:
    """투자자군 열만 있는 확약 표(2024년 하반기 이후 다수): 군마다 확약 수량을 더한다.

    하위 군이 따로 실린 상위 군(예: '… | 운용사(집합)' 아래 '… | 공모')은 빼서
    이중으로 세지 않는다. 이 서식은 국내 기관 군만 싣는다. 분모는 해외 기관까지 든
    수요예측 총 신청수량이라 해외 기관의 확약은 빠진다 — 합계 열 서식과 같은 분모를
    쓰려는 선택이다. 표의 수량 합이 총 신청보다 크면 이중 계산으로 보고 결측으로 둔다.
    """
    rows = shares.dropna(subset=["value"])
    rows = rows[~rows["investor_group"].astype(str).str.contains("|".join(NOT_INVESTOR))]
    rows = latest_doc(rows)
    if rows.empty:
        return math.nan
    tables = _table(rows)
    rows = rows[tables == sorted(tables.unique())[0]]
    groups = list(rows["investor_group"].unique())
    leaves = [g for g in groups if not any(h.startswith(f"{g} | ") for h in groups)]
    rows = rows[rows["investor_group"].isin(leaves)]
    committed = rows.loc[rows["lockup"].isin(COMMITTED), "value"].sum()
    listed = committed + rows.loc[rows["lockup"] == "none", "value"].sum()
    denom = total_bids if math.isfinite(total_bids) and total_bids > 0 else listed
    if denom <= 0 or listed > denom * SHARE_CEIL:
        return math.nan
    return float(committed / denom)


def lockup_alloc_share(o: pd.DataFrame, inst_final: float) -> float:
    """실적보고서 기준 확약 배정 수량 / 기관 최종 배정(2021년 이후 서식)."""
    rows = o[
        (o["metric"] == "lockup_alloc_shares")
        & (o["stage"] == "allocation")
        & (o["investor_group"].fillna("total") == "total")
    ]
    rows = latest_doc(rows.dropna(subset=["value"]))
    committed = rows.loc[rows["lockup"].isin(COMMITTED), "value"].sum()
    if not len(rows) or not math.isfinite(inst_final) or inst_final <= 0:
        return math.nan
    return float(committed / inst_final)


def longterm_bookbuild_share(o: pd.DataFrame) -> float:
    """수요예측 신청수량 중 연기금·운용사(고유)·은행·보험 군 비중(최근 서식에만 있다)."""
    rows = o[o["metric"] == "bookbuild_shares"]
    rows = latest_doc(rows.dropna(subset=["value"]))
    if rows.empty:
        return math.nan
    groups = rows["investor_group"].fillna("")
    total_rows = rows[groups.isin(["total"]) | groups.str.contains("합계")]
    longterm = rows.loc[groups.str.contains(LONG_TERM_MARK), "value"].sum()
    if total_rows.empty or not longterm:
        return math.nan
    total = float(total_rows["value"].max())
    return float(longterm / total) if total > 0 else math.nan


def plausible_price(price: float, band_low: float, band_high: float) -> bool:
    """확정 공모가가 희망 밴드와 양립하는가.

    밴드보다 낮게 정해진 실제 사례는 밴드 상단의 46% 수준까지다. 각주 표시('주1')가 1원으로,
    문장 속 액면가가 500원으로 읽힌 파싱 오류를 걸러낸다. 밴드가 없으면 판단하지 않는다.
    """
    if not math.isfinite(price) or price <= 0:
        return False
    if math.isfinite(band_low) and price < PRICE_BAND_FLOOR * band_low:
        return False
    if math.isfinite(band_high) and price > PRICE_BAND_CEIL * band_high:
        return False
    return True


def lead_underwriter(o: pd.DataFrame) -> str | None:
    """대표 주관사 이름(상장 전 마지막 증권신고서의 역할 '대표' 행, 여럿이면 첫 행)."""
    rows = o[o["metric"].isin(["underwriter_name", "underwriter_role"])]
    rows = latest_doc(rows[rows["value_status"] == "ok"].dropna(subset=["value_text"]))
    if rows.empty:
        return None
    names = rows[rows["metric"] == "underwriter_name"].reset_index(drop=True)
    roles = rows[rows["metric"] == "underwriter_role"].reset_index(drop=True)
    for i in range(min(len(names), len(roles))):
        if str(roles.loc[i, "value_text"]).startswith("1"):
            return str(names.loc[i, "value_text"]).partition(":")[2].strip() or None
    return None


def event_fields(o: pd.DataFrame) -> dict:
    """한 사건의 상장 전 관측값에서 원시 필드를 뽑는다."""
    out = {name: math.nan for name in FIELDS}
    for name in ("band_low", "band_high"):
        out[name] = _scalar(o, name, positive=True)
    price = _scalar(o, "final_price", positive=True)
    if not plausible_price(price, out["band_low"], out["band_high"]):
        amount = _scalar(o, "final_alloc_amount", {"total"})
        shares = _scalar(o, "final_alloc_shares", {"total"})
        price = amount / shares if math.isfinite(shares) and shares > 0 else math.nan
    ok = plausible_price(price, out["band_low"], out["band_high"])
    out["final_price"] = price if ok else math.nan
    out["offer_shares"] = _scalar(o, "offer_shares", positive=True)
    out["sell_shares"] = sell_shares(o)
    for name in ("listed_shares", "float_shares", "float_pct"):
        out[name] = _scalar(o, name, positive=True)
    if out["float_pct"] > FLOAT_PCT_CEIL:
        out["float_pct"] = math.nan
    out["bookbuild_ratio"] = _scalar(o, "bookbuild_ratio", {"total"})
    out["total_bid_shares"] = bid_total(o)
    out["bid_top_share"] = bid_top_share(o, out["band_high"])
    out["lockup_bid_share"] = lockup_bid_share(o, out["total_bid_shares"])
    out["inst_final_alloc_shares"] = _scalar(o, "final_alloc_shares", INST_GROUPS)
    out["lockup_alloc_share"] = lockup_alloc_share(o, out["inst_final_alloc_shares"])
    out["retail_sub_shares"] = _scalar(o, "sub_shares", RETAIL_GROUPS)
    out["retail_sub_amount"] = _scalar(o, "sub_amount", RETAIL_GROUPS)
    out["retail_initial_alloc_shares"] = _scalar(o, "initial_alloc_shares", RETAIL_GROUPS)
    out["retail_final_alloc_amount"] = _scalar(o, "final_alloc_amount", RETAIL_GROUPS)
    out["longterm_bookbuild_share"] = longterm_bookbuild_share(o)
    restricted = _scalar(o, "restricted_pct")
    out["restricted_pct"] = restricted if 0 <= restricted <= FLOAT_PCT_CEIL else math.nan
    out["bookbuild_count"] = _scalar(o, "bookbuild_count", {"total"}, positive=True)
    out["retail_sub_count"] = _scalar(o, "sub_count", RETAIL_GROUPS, positive=True)
    out["offer_price_planned"] = _scalar(o, "offer_price_planned", positive=True)
    uw = latest_doc(
        o[o["metric"].isin(["underwriter_fee", "underwriter_amount"])].dropna(subset=["value"])
    )
    for name in ("underwriter_fee", "underwriter_amount"):
        vals = uw.loc[uw["metric"] == name, "value"]
        out[name] = float(vals.sum()) if len(vals) else math.nan
    out["lead_underwriter"] = lead_underwriter(o)
    for name in (
        "company_size",
        "listing_market",
        "is_venture",
        "subscription_end",
        "price_announce_date",
    ):
        out[name] = _text(o, name)
    industry = o[(o["metric"] == "industry") & (o["value_status"] == "ok")]
    industry = industry.dropna(subset=["value_text"])
    industry = latest_doc(industry)
    out["industry"] = str(industry["value_text"].iloc[0]) if len(industry) else None
    return out


def build_fields(obs: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """사건별 원시 필드 표(index = event_id). 사건마다 자기 상장일로 자른 관측값만 쓴다."""
    o = pre_listing(obs, events)
    groups = dict(tuple(o.groupby("event_id")))
    empty = o.iloc[0:0]
    rows = {e: event_fields(groups.get(e, empty)) for e in events["event_id"]}
    out = pd.DataFrame.from_dict(rows, orient="index")
    out.index.name = "event_id"
    return out.astype({name: np.float64 for name in FIELDS})
