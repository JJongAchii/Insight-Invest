"""미국 주요 기업 Earnings Hub의 유니버스·일정·실적 계약.

앱 통합 종목 마스터의 현재 시가총액과 qdata의 활성 미국 종목 참조축을 정확히
조인한다. Finnhub 일정은 발표일·장전/장후·컨센서스·실제치만 제공하므로 모든
미래 일정은 ``estimated``로 표시하고, 정확한 어닝콜 시각·웹캐스트·전문은
제공된 것으로 추정하지 않는다.
"""

from __future__ import annotations

import hashlib
import re
import time
from datetime import date, timedelta
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx
import pandas as pd

from module import external_events

UNIVERSE_COLUMNS = [
    "meta_id",
    "ticker",
    "name",
    "cik",
    "scope",
    "is_market_leader",
    "marketcap_rank",
    "marketcap",
    "universe_as_of",
]

OFFICIAL_RESULT_TEXT_COLUMNS = [
    "official_result_status",
    "official_result_source",
    "official_result_form",
    "official_result_url",
    "official_result_filed_at",
    "official_result_detected_at",
    "official_actual_status",
    "official_actual_url",
    "official_actual_extracted_at",
]

OFFICIAL_RESULT_VALUE_COLUMNS = [
    "official_eps_gaap_actual",
    "official_eps_adjusted_actual",
    "official_revenue_actual",
]

OFFICIAL_RESULT_COLUMNS = [*OFFICIAL_RESULT_TEXT_COLUMNS, *OFFICIAL_RESULT_VALUE_COLUMNS]

EVENT_COLUMNS = [
    "event_id",
    "identity_quality",
    "meta_id",
    "ticker",
    "name",
    "cik",
    "scope",
    "is_market_leader",
    "marketcap_rank",
    "fiscal_year",
    "fiscal_quarter",
    "release_date",
    "release_timing",
    "schedule_status",
    "lifecycle",
    "eps_actual",
    "eps_estimate",
    "eps_surprise_pct",
    "revenue_actual",
    "revenue_estimate",
    "revenue_surprise_pct",
    "result_signal",
    *OFFICIAL_RESULT_COLUMNS,
    "source",
    "source_url",
    "stock_link",
    "call_time",
    "webcast_url",
    "transcript_status",
    "first_seen_at",
    "available_at",
    "data_as_of",
    "universe_as_of",
    "as_of",
]

REVISION_COLUMNS = [
    "revision_id",
    "event_id",
    "ticker",
    "fiscal_year",
    "fiscal_quarter",
    "previous_release_date",
    "release_date",
    "observed_at",
    "source",
    "as_of",
]

SEC_RESULT_8K_FORMS = {"8-K", "8-K/A"}
SEC_PERIODIC_RESULT_FORMS = {
    "10-Q",
    "10-Q/A",
    "10-K",
    "10-K/A",
    "20-F",
    "20-F/A",
    "40-F",
    "40-F/A",
}
SEC_DOCUMENT_MAX_BYTES = 5_000_000


class _SecTableParser(HTMLParser):
    """SEC filing tables as visible cell text plus links, without an HTML dependency."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[dict]]] = []
        self._table_depth = 0
        self._table: list[list[dict]] | None = None
        self._row: list[dict] | None = None
        self._cell_text: list[str] | None = None
        self._cell_links: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        tag = tag.lower()
        if tag == "table":
            if self._table_depth == 0:
                self._table = []
            self._table_depth += 1
        elif tag == "tr" and self._table_depth:
            self._row = []
        elif tag in {"td", "th"} and self._table_depth and self._row is not None:
            self._cell_text = []
            self._cell_links = []
        elif tag == "a" and self._cell_text is not None and self._cell_links is not None:
            href = dict(attrs).get("href")
            if href:
                self._cell_links.append(href)

    def handle_data(self, data: str):
        if self._cell_text is not None:
            self._cell_text.append(data)

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag in {"td", "th"} and self._cell_text is not None and self._row is not None:
            text = " ".join("".join(self._cell_text).replace("\xa0", " ").split())
            self._row.append({"text": text, "links": self._cell_links or []})
            self._cell_text = None
            self._cell_links = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table_depth:
            self._table_depth -= 1
            if self._table_depth == 0 and self._table is not None:
                self.tables.append(self._table)
                self._table = None


def _sec_tables(page: str) -> list[list[list[dict]]]:
    parser = _SecTableParser()
    parser.feed(page)
    return parser.tables


def _normalized_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _cell_number(value: str) -> float | None:
    text = value.strip().replace("$", "").replace(",", "")
    if not text or "%" in text or not re.fullmatch(r"\(?-?\d+(?:\.\d+)?\)?", text):
        return None
    negative = text.startswith("(") and text.endswith(")")
    number = float(text.strip("()"))
    return -number if negative else number


def _first_row_number(row: list[dict]) -> float | None:
    for cell in row[1:]:
        value = _cell_number(str(cell.get("text", "")))
        if value is not None:
            return value
    return None


def _revenue_scale(table_text: str) -> float | None:
    normalized = _normalized_label(table_text)
    if "$" not in table_text and "dollars in" not in normalized:
        return None
    if "in billions" in normalized:
        return 1_000_000_000
    if "in millions" in normalized:
        return 1_000_000
    if "in thousands" in normalized:
        return 1_000
    return None


def _table_official_actuals(table: list[list[dict]]) -> dict | None:
    table_text = " ".join(str(cell.get("text", "")) for row in table for cell in row)
    normalized_table = _normalized_label(table_text)
    period_table = any(
        marker in normalized_table
        for marker in ("three months ended", "quarter ended", "quarterly results")
    ) or re.search(r"\bq[1-4] fy\d{2,4}\b", normalized_table)
    if not period_table:
        return None
    scale = _revenue_scale(table_text)
    standalone_labels = set()
    for row in table:
        nonempty = [cell for cell in row if str(cell.get("text", "")).strip()]
        if len(nonempty) == 1:
            standalone_labels.add(_normalized_label(str(nonempty[0].get("text", ""))))
    non_gaap_table = "non gaap" in standalone_labels or "adjusted" in standalone_labels
    values = {
        "official_revenue_actual": None,
        "official_eps_gaap_actual": None,
        "official_eps_adjusted_actual": None,
    }
    revenue_labels = {
        "revenue",
        "revenues",
        "net revenue",
        "net revenues",
        "total revenue",
        "total revenues",
        "total net revenue",
        "net sales",
        "total net sales",
    }
    eps_section = False
    for row in table:
        nonempty = [cell for cell in row if str(cell.get("text", "")).strip()]
        if not nonempty:
            continue
        label = _normalized_label(str(nonempty[0].get("text", "")))
        value = _first_row_number(row)
        eps_label = "diluted" in label and (
            "earnings per share" in label
            or "net income per share" in label
            or "net earnings per share" in label
            or label.endswith("diluted eps")
        )
        if value is None:
            if eps_label and not any(
                marker in label for marker in ("weighted average", "shares used", "computation")
            ):
                eps_section = True
            continue
        if label in revenue_labels and scale is not None:
            values["official_revenue_actual"] = value * scale
            continue
        if eps_section and label in {"gaap", "non gaap", "adjusted", "adjusted non gaap"}:
            key = (
                "official_eps_gaap_actual"
                if label == "gaap"
                else "official_eps_adjusted_actual"
            )
            values[key] = value
            continue
        is_eps = eps_label and not any(
            marker in label for marker in ("weighted average", "shares used", "computation")
        )
        if not is_eps:
            continue
        if non_gaap_table or "non gaap" in label or "adjusted" in label:
            values["official_eps_adjusted_actual"] = value
        else:
            values["official_eps_gaap_actual"] = value
    return values if any(value is not None for value in values.values()) else None


def parse_sec_earnings_exhibit(page: str) -> dict:
    """Extract current-quarter official figures only when each metric is unambiguous."""
    keys = (
        "official_revenue_actual",
        "official_eps_gaap_actual",
        "official_eps_adjusted_actual",
    )
    candidates = {key: set() for key in keys}
    for table in _sec_tables(page):
        values = _table_official_actuals(table)
        if values:
            for key in keys:
                if values[key] is not None:
                    candidates[key].add(values[key])
    empty = {key: None for key in keys}
    if not any(candidates.values()):
        return {"status": "not_found", **empty}
    if any(len(values) > 1 for values in candidates.values()):
        return {"status": "ambiguous", **empty}
    return {
        "status": "extracted",
        **{
            key: next(iter(values)) if values else None
            for key, values in candidates.items()
        },
    }


def _sec_exhibit_urls(index_page: str, index_url: str) -> list[str]:
    candidates: list[tuple[int, str]] = []
    for table in _sec_tables(index_page):
        for row in table:
            texts = [_normalized_label(str(cell.get("text", ""))) for cell in row]
            joined = " ".join(texts)
            if not any(text.startswith("ex 99") for text in texts):
                continue
            score = 2 if any(text == "ex 99 1" for text in texts) else 1
            if any(word in joined for word in ("earnings", "results", "press release")):
                score += 2
            for cell in row:
                for href in cell.get("links", []):
                    url = urljoin(index_url, href)
                    parsed = urlparse(url)
                    if (
                        parsed.scheme == "https"
                        and parsed.netloc.lower() in {"sec.gov", "www.sec.gov"}
                        and parsed.path.startswith("/Archives/")
                        and parsed.path.lower().endswith((".htm", ".html"))
                    ):
                        candidates.append((score, url))
    ordered = sorted(candidates, key=lambda item: (-item[0], item[1]))
    return list(dict.fromkeys(url for _, url in ordered))[:3]


def _request_sec_text(
    client: httpx.Client, url: str, *, max_bytes: int = SEC_DOCUMENT_MAX_BYTES
) -> str:
    try:
        response = client.get(url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        detail = f"HTTP {status}" if status else type(exc).__name__
        raise external_events.ProviderUnavailable(f"SEC 문서 요청 실패: {detail}") from exc
    if len(response.content) > max_bytes:
        raise external_events.ProviderUnavailable("SEC 문서가 허용 크기를 초과했습니다")
    return response.text


def empty_universe() -> pd.DataFrame:
    return pd.DataFrame(columns=UNIVERSE_COLUMNS)


def empty_events() -> pd.DataFrame:
    return pd.DataFrame(columns=EVENT_COLUMNS)


def empty_revisions() -> pd.DataFrame:
    return pd.DataFrame(columns=REVISION_COLUMNS)


def _cik(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return text.zfill(10) if text.isdigit() else text


def build_universe(
    master: pd.DataFrame,
    us_reference: pd.DataFrame,
    tracked: pd.DataFrame,
    *,
    leader_count: int = 50,
) -> tuple[pd.DataFrame, dict]:
    """시총 상위 기업과 내 종목의 합집합을 만든다.

    qdata 참조축의 ``CS``·``ADRC``만 earnings 대상이다. 동일 CIK의 복수
    클래스는 시총이 가장 큰 클래스 하나만 시장 대표기업 순위에 남긴다.
    """
    required_master = {
        "meta_id",
        "ticker",
        "name",
        "iso_code",
        "security_type",
        "marketcap",
        "as_of",
    }
    required_ref = {"ticker", "cik", "type"}
    missing_master = required_master - set(master.columns)
    missing_ref = required_ref - set(us_reference.columns)
    if missing_master:
        raise ValueError(f"asset master 필수 컬럼 없음: {sorted(missing_master)}")
    if missing_ref:
        raise ValueError(f"qdata US ticker 필수 컬럼 없음: {sorted(missing_ref)}")

    app = master[master["iso_code"].eq("US") & master["security_type"].eq("STOCK")].copy()
    app["ticker"] = app["ticker"].astype(str).str.upper()
    app["marketcap"] = pd.to_numeric(app["marketcap"], errors="coerce")
    app = app[app["marketcap"].gt(0)].copy()
    if app["ticker"].duplicated().any():
        duplicates = app.loc[app["ticker"].duplicated(False), "ticker"].unique()
        raise ValueError(f"asset master US ticker 중복: {duplicates[:20].tolist()}")

    ref = us_reference.copy()
    ref["ticker"] = ref["ticker"].astype(str).str.upper()
    ref = ref[ref["type"].isin({"CS", "ADRC"})].copy()
    if ref["ticker"].duplicated().any():
        duplicates = ref.loc[ref["ticker"].duplicated(False), "ticker"].unique()
        raise ValueError(f"qdata active US ticker 중복: {duplicates[:20].tolist()}")
    ref["cik"] = ref["cik"].map(_cik)

    eligible = app.merge(
        ref[["ticker", "cik", "type"]], on="ticker", how="inner", validate="one_to_one"
    )
    eligible["entity_key"] = eligible.apply(
        lambda row: f"cik:{row['cik']}" if row["cik"] else f"ticker:{row['ticker']}",
        axis=1,
    )
    eligible = eligible.sort_values(
        ["marketcap", "ticker"], ascending=[False, True]
    ).drop_duplicates("entity_key", keep="first")
    eligible["marketcap_rank"] = range(1, len(eligible) + 1)

    leaders = eligible.head(leader_count).copy()
    leaders["is_market_leader"] = True
    leaders["scope"] = "market"

    tracked_scopes: dict[int, str] = {}
    if not tracked.empty:
        for row in tracked.itertuples(index=False):
            if getattr(row, "iso_code", None) != "US":
                continue
            meta_id = int(row.meta_id)
            scope = str(getattr(row, "scope", "watchlist"))
            if tracked_scopes.get(meta_id) != "portfolio":
                tracked_scopes[meta_id] = scope
    mine = eligible[eligible["meta_id"].isin(tracked_scopes)].copy()
    mine["scope"] = mine["meta_id"].map(tracked_scopes)
    mine["is_market_leader"] = mine["meta_id"].isin(leaders["meta_id"])

    combined = pd.concat([leaders, mine], ignore_index=True)
    combined["scope_priority"] = combined["scope"].map(
        {"portfolio": 0, "watchlist": 1, "market": 2}
    )
    combined = combined.sort_values(
        ["scope_priority", "marketcap_rank"], ascending=True
    ).drop_duplicates("meta_id", keep="first")
    universe_as_of = str(pd.to_datetime(app["as_of"], errors="coerce").max().date())
    combined["universe_as_of"] = universe_as_of
    combined = combined.sort_values("marketcap_rank").reindex(columns=UNIVERSE_COLUMNS)
    combined["meta_id"] = combined["meta_id"].astype(int)
    combined["marketcap_rank"] = combined["marketcap_rank"].astype(int)

    requested_mine = len(tracked_scopes)
    matched_mine = len(mine)
    coverage = {
        "master_us_stocks": int(
            len(master[master["iso_code"].eq("US") & master["security_type"].eq("STOCK")])
        ),
        "master_us_stocks_with_marketcap": int(len(app)),
        "reference_eligible": int(len(ref)),
        "joined_eligible": int(len(eligible)),
        "reference_match_pct": round(len(eligible) / len(app) * 100, 2) if len(app) else 0.0,
        "requested_tracked_us": requested_mine,
        "matched_tracked_us": matched_mine,
        "ineligible_or_unmatched_tracked_us": requested_mine - matched_mine,
        "market_leaders": int(len(leaders)),
        "universe_total": int(len(combined)),
        "cik_coverage_pct": (
            float(round(combined["cik"].notna().mean() * 100, 2)) if len(combined) else 0.0
        ),
        "universe_as_of": universe_as_of,
    }
    if len(leaders) != min(leader_count, len(eligible)):
        raise AssertionError("Earnings market leader cardinality mismatch")
    return combined.reset_index(drop=True), coverage


def _request_calendar(
    client: httpx.Client,
    api_key: str,
    start: date,
    end: date,
    *,
    symbol: str | None = None,
) -> list[dict]:
    params = {
        "token": api_key,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "international": "false",
    }
    if symbol:
        params["symbol"] = symbol
    payload = external_events._request_json(
        client,
        "https://finnhub.io/api/v1/calendar/earnings",
        params=params,
        auth_name="Finnhub",
    )
    items = payload.get("earningsCalendar")
    if not isinstance(items, list):
        raise external_events.ProviderUnavailable("Finnhub Earnings 응답 계약이 변경되었습니다")
    return items


def _fetch_complete_window(
    client: httpx.Client,
    api_key: str,
    start: date,
    end: date,
    *,
    response_cap: int = 1500,
) -> tuple[list[dict], int]:
    """응답 상한에 닿은 날짜 구간을 재귀 분할해 조용한 절단을 막는다."""
    items = _request_calendar(client, api_key, start, end)
    if len(items) < response_cap:
        return items, 1
    if start >= end:
        raise external_events.ProviderUnavailable(
            f"Finnhub 일별 Earnings 응답이 {response_cap}건 상한에 도달했습니다"
        )
    midpoint = start + timedelta(days=(end - start).days // 2)
    left, left_calls = _fetch_complete_window(
        client, api_key, start, midpoint, response_cap=response_cap
    )
    right, right_calls = _fetch_complete_window(
        client, api_key, midpoint + timedelta(days=1), end, response_cap=response_cap
    )
    return left + right, left_calls + right_calls + 1


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def _surprise(actual: float | None, estimate: float | None) -> float | None:
    if actual is None or estimate is None or estimate == 0:
        return None
    return (actual - estimate) / abs(estimate) * 100


def _signal(
    eps_actual: float | None,
    eps_estimate: float | None,
    revenue_actual: float | None,
    revenue_estimate: float | None,
) -> str | None:
    comparisons = []
    if eps_actual is not None and eps_estimate is not None:
        comparisons.append((eps_actual > eps_estimate) - (eps_actual < eps_estimate))
    if revenue_actual is not None and revenue_estimate is not None:
        comparisons.append(
            (revenue_actual > revenue_estimate) - (revenue_actual < revenue_estimate)
        )
    if not comparisons:
        return None
    if all(value > 0 for value in comparisons):
        return "beat"
    if all(value < 0 for value in comparisons):
        return "miss"
    if all(value == 0 for value in comparisons):
        return "in_line"
    return "mixed"


def _event_id(asset, item: dict, release_date: str) -> tuple[str, str]:
    year = item.get("year")
    quarter = item.get("quarter")
    if year not in {None, ""} and quarter not in {None, ""}:
        return f"earnings:{int(asset.meta_id)}:{int(year)}:q{int(quarter)}", "fiscal_period"
    return f"earnings:{int(asset.meta_id)}:date:{release_date}", "release_date"


def normalize_calendar(
    items: list[dict], universe: pd.DataFrame, available_at: str
) -> pd.DataFrame:
    by_ticker = {str(row.ticker).upper(): row for row in universe.itertuples(index=False)}
    today = date.fromisoformat(available_at[:10])
    rows = []
    for item in items:
        ticker = str(item.get("symbol", "")).upper()
        asset = by_ticker.get(ticker)
        release_date = str(item.get("date", ""))
        try:
            scheduled = date.fromisoformat(release_date)
        except ValueError:
            continue
        if asset is None:
            continue
        eps_actual = _number(item.get("epsActual"))
        eps_estimate = _number(item.get("epsEstimate"))
        revenue_actual = _number(item.get("revenueActual"))
        revenue_estimate = _number(item.get("revenueEstimate"))
        has_actual = scheduled <= today and (eps_actual is not None or revenue_actual is not None)
        event_id, identity_quality = _event_id(asset, item, release_date)
        cik = _cik(asset.cik)
        rows.append(
            {
                "event_id": event_id,
                "identity_quality": identity_quality,
                "meta_id": int(asset.meta_id),
                "ticker": ticker,
                "name": asset.name,
                "cik": cik,
                "scope": asset.scope,
                "is_market_leader": bool(asset.is_market_leader),
                "marketcap_rank": int(asset.marketcap_rank),
                "fiscal_year": int(item["year"]) if item.get("year") not in {None, ""} else None,
                "fiscal_quarter": (
                    int(item["quarter"]) if item.get("quarter") not in {None, ""} else None
                ),
                "release_date": release_date,
                "release_timing": str(item.get("hour") or "tbd").lower(),
                "schedule_status": "estimated",
                "lifecycle": "reported" if has_actual else "scheduled",
                "eps_actual": eps_actual,
                "eps_estimate": eps_estimate,
                "eps_surprise_pct": _surprise(eps_actual, eps_estimate),
                "revenue_actual": revenue_actual,
                "revenue_estimate": revenue_estimate,
                "revenue_surprise_pct": _surprise(revenue_actual, revenue_estimate),
                "result_signal": _signal(
                    eps_actual, eps_estimate, revenue_actual, revenue_estimate
                ),
                "source": "finnhub",
                "source_url": f"https://www.sec.gov/edgar/browse/?CIK={cik}" if cik else None,
                "stock_link": f"/stock/{int(asset.meta_id)}",
                "call_time": None,
                "webcast_url": None,
                "transcript_status": "not_available",
                "first_seen_at": available_at,
                "available_at": available_at,
                "data_as_of": today.isoformat(),
                "universe_as_of": asset.universe_as_of,
                "as_of": today.isoformat(),
            }
        )
    if not rows:
        return empty_events()
    frame = pd.DataFrame(rows).reindex(columns=EVENT_COLUMNS)
    for column in OFFICIAL_RESULT_TEXT_COLUMNS:
        frame[column] = frame[column].astype("object")
    # 심볼별 보강 호출과 전역 호출이 같은 이벤트를 돌려준다. 실제치가 더 많이
    # 채워진 행을 우선해 안정 식별자당 한 행만 남긴다.
    frame["richness"] = (
        frame[["eps_actual", "eps_estimate", "revenue_actual", "revenue_estimate"]]
        .notna()
        .sum(axis=1)
    )
    return (
        frame.sort_values(["event_id", "richness"])
        .drop_duplicates("event_id", keep="last")
        .drop(columns="richness")
        .reset_index(drop=True)
    )


def fetch_finnhub_calendar(
    api_key: str,
    universe: pd.DataFrame,
    start: date,
    end: date,
    available_at: str,
    *,
    client: httpx.Client | None = None,
    chunk_days: int = 7,
    response_cap: int = 1500,
) -> tuple[pd.DataFrame, dict]:
    """대표기업은 짧은 전역 창, 내 종목은 심볼 호출로 이중 확인한다."""
    if not api_key.strip():
        raise external_events.ConfigurationRequired("FINNHUB_API_KEY가 없습니다")
    if universe.empty:
        return empty_events(), {"calendar_calls": 0, "raw_events": 0, "matched_events": 0}

    owns_client = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=True)
    items: list[dict] = []
    calls = 0
    try:
        cursor = start
        while cursor <= end:
            chunk_end = min(cursor + timedelta(days=chunk_days - 1), end)
            chunk, chunk_calls = _fetch_complete_window(
                client,
                api_key,
                cursor,
                chunk_end,
                response_cap=response_cap,
            )
            items.extend(chunk)
            calls += chunk_calls
            cursor = chunk_end + timedelta(days=1)

        mine = universe[universe["scope"].isin(["portfolio", "watchlist"])]
        for ticker in sorted(mine["ticker"].astype(str).unique()):
            items.extend(_request_calendar(client, api_key, start, end, symbol=ticker))
            calls += 1
    finally:
        if owns_client:
            client.close()

    events = normalize_calendar(items, universe, available_at)
    covered = set(events["ticker"]) if not events.empty else set()
    return events, {
        "calendar_calls": calls,
        "raw_events": len(items),
        "matched_events": len(events),
        "companies_with_events": len(covered),
        "universe_without_window_event": len(universe) - len(covered),
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
    }


def _sec_result_filing(form: object, items: object) -> bool:
    form_name = str(form or "").upper()
    if form_name in SEC_PERIODIC_RESULT_FORMS:
        return True
    if form_name not in SEC_RESULT_8K_FORMS:
        return False
    item_codes = {part.strip() for part in str(items or "").split(",")}
    return "2.02" in item_codes


def _sec_filing_url(cik: str, accession: str) -> str:
    accession_path = accession.replace("-", "")
    return (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{int(cik)}/{accession_path}/{accession}-index.html"
    )


def enrich_sec_result_filings(
    events: pd.DataFrame,
    contact: str,
    start: date,
    end: date,
    available_at: str,
    *,
    client: httpx.Client | None = None,
    max_match_days: int = 3,
    request_interval_seconds: float = 0.11,
) -> tuple[pd.DataFrame, dict]:
    """최근 Earnings에 SEC 공식 결과 접수 신호와 공식 발표 수치를 붙인다.

    8-K는 Item 2.02가 명시된 경우만 실적 결과로 인정한다. 10-Q·10-K 등
    정기보고서는 그 자체를 공식 결과 문서로 인정한다. 실제 수치는 정확히 매칭된
    8-K의 SEC-hosted EX-99 HTML에서만 별도 필드로 추출하고, Finnhub 필드에는
    복사하지 않는다.
    """
    if not contact.strip():
        raise external_events.ConfigurationRequired("SEC 요청용 연락처가 없습니다")
    if events.empty:
        return empty_events(), {
            "status": "ok",
            "companies_queried": 0,
            "filings_scanned": 0,
            "result_filings": 0,
            "events_enriched": 0,
            "official_actuals_attempted": 0,
            "official_actuals_extracted": 0,
            "official_actuals_reused": 0,
            "official_actuals_failed": 0,
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
        }

    enriched = events.reindex(columns=EVENT_COLUMNS).copy()
    for column in OFFICIAL_RESULT_TEXT_COLUMNS:
        enriched[column] = enriched[column].astype("object")
    release_days = pd.to_datetime(enriched["release_date"], errors="coerce").dt.date
    candidates = enriched[
        release_days.between(start, end, inclusive="both") & enriched["cik"].notna()
    ].copy()
    if candidates.empty:
        return enriched, {
            "status": "ok",
            "companies_queried": 0,
            "filings_scanned": 0,
            "result_filings": 0,
            "events_enriched": 0,
            "official_actuals_attempted": 0,
            "official_actuals_extracted": 0,
            "official_actuals_reused": 0,
            "official_actuals_failed": 0,
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
        }
    candidates["release_day"] = pd.to_datetime(candidates["release_date"], errors="coerce").dt.date

    owns_client = client is None
    client = client or httpx.Client(
        timeout=20,
        follow_redirects=True,
        headers={
            "User-Agent": f"Insight-Invest {contact}",
            "Accept-Encoding": "gzip, deflate",
        },
    )
    filings_scanned = 0
    result_filings = 0
    official_actuals_attempted = 0
    official_actuals_extracted = 0
    official_actuals_reused = 0
    official_actuals_failed = 0
    matches: dict[str, tuple[int, str, dict]] = {}
    ciks = sorted({_cik(value) for value in candidates["cik"] if _cik(value)})
    previous_request_at: float | None = None

    def wait_for_request_slot():
        nonlocal previous_request_at
        if previous_request_at is not None and request_interval_seconds > 0:
            elapsed = time.monotonic() - previous_request_at
            if elapsed < request_interval_seconds:
                time.sleep(request_interval_seconds - elapsed)

    def request_json(url: str) -> dict:
        nonlocal previous_request_at
        wait_for_request_slot()
        try:
            return external_events._request_json(client, url, params={})
        finally:
            previous_request_at = time.monotonic()

    def request_text(url: str) -> str:
        nonlocal previous_request_at
        wait_for_request_slot()
        try:
            return _request_sec_text(client, url)
        finally:
            previous_request_at = time.monotonic()

    try:
        for cik in ciks:
            payload = request_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
            recent = payload.get("filings", {}).get("recent", {})
            required_keys = [
                "accessionNumber",
                "filingDate",
                "acceptanceDateTime",
                "reportDate",
                "form",
            ]
            length = min((len(recent.get(key, [])) for key in required_keys), default=0)
            items = recent.get("items", [])
            company_events = candidates[candidates["cik"].map(_cik).eq(cik)]
            for index in range(length):
                filing_date_text = str(recent["filingDate"][index] or "")
                try:
                    filing_day = date.fromisoformat(filing_date_text)
                except ValueError:
                    continue
                if not (
                    start - timedelta(days=max_match_days)
                    <= filing_day
                    <= end + timedelta(days=max_match_days)
                ):
                    continue
                filings_scanned += 1
                form = str(recent["form"][index] or "").upper()
                item_codes = items[index] if index < len(items) else ""
                if not _sec_result_filing(form, item_codes):
                    continue
                result_filings += 1

                anchor_days = [filing_day]
                if form in SEC_RESULT_8K_FORMS:
                    try:
                        report_day = date.fromisoformat(str(recent["reportDate"][index]))
                        anchor_days.insert(0, report_day)
                    except ValueError:
                        pass
                event_index = None
                match_distance = max_match_days + 1
                for anchor_day in anchor_days:
                    distances = company_events["release_day"].map(
                        lambda release_day: abs((release_day - anchor_day).days)
                    )
                    if not distances.empty and int(distances.min()) < match_distance:
                        event_index = distances.idxmin()
                        match_distance = int(distances.min())
                if event_index is None or match_distance > max_match_days:
                    continue
                event = company_events.loc[event_index]
                accession = str(recent["accessionNumber"][index])
                accepted = str(recent["acceptanceDateTime"][index] or filing_date_text)
                priority = 0 if form in SEC_RESULT_8K_FORMS else 1
                match = {
                    "official_result_status": "filed",
                    "official_result_source": "sec",
                    "official_result_form": form,
                    "official_result_url": _sec_filing_url(cik, accession),
                    "official_result_filed_at": accepted,
                    "official_result_detected_at": available_at,
                }
                current = matches.get(str(event["event_id"]))
                rank = (priority, accepted)
                if (
                    current is None
                    or priority < current[0]
                    or (priority == current[0] and accepted > current[1])
                ):
                    matches[str(event["event_id"])] = (rank[0], rank[1], match)

        for event_id, (_, _, match) in matches.items():
            if match["official_result_form"] not in SEC_RESULT_8K_FORMS:
                continue
            existing = enriched[enriched["event_id"].astype(str).eq(event_id)].iloc[0]
            if (
                str(existing.get("official_actual_status")) == "extracted"
                and existing.get("official_result_url") == match["official_result_url"]
            ):
                official_actuals_extracted += 1
                official_actuals_reused += 1
                continue
            official_actuals_attempted += 1
            try:
                index_page = request_text(match["official_result_url"])
                exhibit_urls = _sec_exhibit_urls(index_page, match["official_result_url"])
                if not exhibit_urls:
                    match["official_actual_status"] = "unsupported"
                    continue
                parsed = None
                parsed_url = None
                ambiguous = False
                for exhibit_url in exhibit_urls:
                    result = parse_sec_earnings_exhibit(request_text(exhibit_url))
                    if result["status"] == "ambiguous":
                        ambiguous = True
                    if result["status"] == "extracted":
                        parsed = result
                        parsed_url = exhibit_url
                        break
                if parsed is None:
                    match["official_actual_status"] = "ambiguous" if ambiguous else "not_found"
                    continue
                match["official_actual_status"] = "extracted"
                for key in OFFICIAL_RESULT_VALUE_COLUMNS:
                    match[key] = parsed[key]
                match["official_actual_url"] = parsed_url
                match["official_actual_extracted_at"] = available_at
                match["lifecycle"] = "reported"
                official_actuals_extracted += 1
            except external_events.ProviderUnavailable:
                match["official_actual_status"] = "fetch_failed"
                official_actuals_failed += 1
    finally:
        if owns_client:
            client.close()

    for event_id, (_, _, match) in matches.items():
        mask = enriched["event_id"].astype(str).eq(event_id)
        for key, value in match.items():
            enriched.loc[mask, key] = value
    return enriched, {
        "status": "ok",
        "companies_queried": len(ciks),
        "filings_scanned": filings_scanned,
        "result_filings": result_filings,
        "events_enriched": len(matches),
        "official_actuals_attempted": official_actuals_attempted,
        "official_actuals_extracted": official_actuals_extracted,
        "official_actuals_reused": official_actuals_reused,
        "official_actuals_failed": official_actuals_failed,
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
    }


def merge_history(
    previous: pd.DataFrame,
    current: pd.DataFrame,
    previous_revisions: pd.DataFrame,
    *,
    available_at: str,
    retention_years: int = 3,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """현재 수집분으로 갱신하되 과거 발표와 일정 변경 이력을 보존한다."""
    old = previous.reindex(columns=EVENT_COLUMNS).copy() if not previous.empty else empty_events()
    new = current.reindex(columns=EVENT_COLUMNS).copy() if not current.empty else empty_events()
    revisions = []
    if not old.empty and not new.empty:
        old_by_id = old.drop_duplicates("event_id", keep="last").set_index("event_id")
        for row in new.itertuples(index=False):
            if row.event_id not in old_by_id.index:
                continue
            before = old_by_id.loc[row.event_id]
            if str(before.get("release_date")) != str(row.release_date):
                identity = f"{row.event_id}|{before.get('release_date')}|{row.release_date}"
                revisions.append(
                    {
                        "revision_id": hashlib.sha256(identity.encode()).hexdigest()[:24],
                        "event_id": row.event_id,
                        "ticker": row.ticker,
                        "fiscal_year": row.fiscal_year,
                        "fiscal_quarter": row.fiscal_quarter,
                        "previous_release_date": before.get("release_date"),
                        "release_date": row.release_date,
                        "observed_at": available_at,
                        "source": row.source,
                        "as_of": available_at[:10],
                    }
                )

    # current의 비결측 값이 우선하되, 공급자가 실제치를 일시적으로 비우더라도
    # 이전 발표 값을 지우지 않는다.
    merged_by_id: dict[str, dict] = {}
    for frame in (old, new):
        for record in frame.to_dict("records"):
            event_id = record.get("event_id")
            if not event_id:
                continue
            base = merged_by_id.setdefault(event_id, {})
            for key, value in record.items():
                if pd.notna(value):
                    if key == "first_seen_at" and base.get(key):
                        continue
                    base[key] = value
    merged = pd.DataFrame(merged_by_id.values()).reindex(columns=EVENT_COLUMNS)
    if not merged.empty:
        observed_on = date.fromisoformat(available_at[:10])
        cutoff = observed_on - timedelta(days=366 * retention_years)
        dates = pd.to_datetime(merged["release_date"], errors="coerce").dt.date
        merged = merged[dates.ge(cutoff)].copy()
        release_days = pd.to_datetime(merged["release_date"], errors="coerce").dt.date
        provider_actual = merged[["eps_actual", "revenue_actual"]].notna().any(axis=1)
        official_actual = (
            merged["official_actual_status"].fillna("").eq("extracted")
            & merged[OFFICIAL_RESULT_VALUE_COLUMNS].notna().any(axis=1)
        )
        has_actual = provider_actual | official_actual
        merged["lifecycle"] = [
            "reported" if actual and day <= observed_on else "scheduled"
            for actual, day in zip(has_actual, release_days, strict=True)
        ]
        merged["eps_surprise_pct"] = [
            _surprise(_number(actual), _number(estimate))
            for actual, estimate in zip(merged["eps_actual"], merged["eps_estimate"], strict=True)
        ]
        merged["revenue_surprise_pct"] = [
            _surprise(_number(actual), _number(estimate))
            for actual, estimate in zip(
                merged["revenue_actual"], merged["revenue_estimate"], strict=True
            )
        ]
        merged["result_signal"] = [
            _signal(
                _number(eps_actual),
                _number(eps_estimate),
                _number(revenue_actual),
                _number(revenue_estimate),
            )
            for eps_actual, eps_estimate, revenue_actual, revenue_estimate in zip(
                merged["eps_actual"],
                merged["eps_estimate"],
                merged["revenue_actual"],
                merged["revenue_estimate"],
                strict=True,
            )
        ]
        merged["as_of"] = available_at[:10]
        merged = merged.sort_values(["release_date", "marketcap_rank", "event_id"])

    old_revisions = (
        previous_revisions.reindex(columns=REVISION_COLUMNS).copy()
        if not previous_revisions.empty
        else empty_revisions()
    )
    revision_frames = [old_revisions]
    if revisions:
        revision_frames.append(pd.DataFrame(revisions).reindex(columns=REVISION_COLUMNS))
    revision_history = pd.concat(revision_frames, ignore_index=True)
    if not revision_history.empty:
        revision_history = revision_history.drop_duplicates("revision_id", keep="last").sort_values(
            "observed_at"
        )
    return merged.reset_index(drop=True), revision_history.reset_index(drop=True)
