"""공식 외부 일정·공시를 Action Center Event 계약으로 정규화한다.

미래 날짜는 공급자가 발표한 일정만 저장한다. DART·SEC 공시는 접수일 이후에만
``observed``로 만들며, 가격이나 재무 데이터의 날짜를 공시 예정일로 추정하지 않는다.
"""

from __future__ import annotations

import html
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from xml.etree import ElementTree

import httpx
import pandas as pd

EVENT_COLUMNS = [
    "event_key",
    "kind",
    "category",
    "market",
    "scope",
    "severity",
    "title",
    "detail",
    "link",
    "meta_id",
    "ticker",
    "name",
    "occurred_at",
    "available_at",
    "data_as_of",
    "scheduled_for",
    "source",
    "event_status",
]


@dataclass
class ProviderResult:
    events: pd.DataFrame
    coverage: str
    data_as_of: str | None = None
    message: str | None = None


class ProviderUnavailable(RuntimeError):
    """자격증명·네트워크·응답 계약 때문에 공급자를 갱신할 수 없음."""


class EntitlementRequired(ProviderUnavailable):
    """API 키는 유효하지만 현재 구독에 데이터 권한이 없음."""


class ConfigurationRequired(ProviderUnavailable):
    """공급자 사용에 필요한 API 키가 없거나 유효하지 않음."""


FRED_RELEASES = {
    9: ("US Retail Sales", "high"),
    10: ("US CPI", "high"),
    13: ("US Industrial Production", "medium"),
    46: ("US PPI", "medium"),
    50: ("US Employment Situation", "high"),
    53: ("US GDP", "high"),
    54: ("US Personal Income & Outlays", "high"),
    192: ("US JOLTS", "medium"),
}

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def empty_events() -> pd.DataFrame:
    return pd.DataFrame(columns=EVENT_COLUMNS)


def _frame(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return empty_events()
    return pd.DataFrame(rows).reindex(columns=EVENT_COLUMNS)


def _request_json(
    client: httpx.Client,
    url: str,
    *,
    params: dict,
    entitlement_name: str | None = None,
    auth_name: str | None = None,
) -> dict:
    try:
        response = client.get(url, params=params)
    except httpx.HTTPError as exc:
        raise ProviderUnavailable(f"요청 실패: {type(exc).__name__}") from exc
    if response.status_code in {401, 403} and auth_name:
        raise ConfigurationRequired(f"{auth_name} API 키를 확인하세요")
    if response.status_code in {401, 402, 403} and entitlement_name:
        raise EntitlementRequired(f"{entitlement_name} 구독 권한이 필요합니다")
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ProviderUnavailable(f"HTTP {response.status_code}") from exc
    try:
        return response.json()
    except ValueError as exc:
        raise ProviderUnavailable("JSON 응답을 해석하지 못했습니다") from exc


def fetch_fred_events(
    api_key: str,
    start: date,
    end: date,
    available_at: str,
    *,
    client: httpx.Client | None = None,
) -> ProviderResult:
    """FRED가 게시한 고영향 미국 지표 발표일만 가져온다."""
    owns_client = client is None
    client = client or httpx.Client(timeout=20, follow_redirects=True)
    rows: list[dict] = []
    try:
        for release_id, (title, severity) in FRED_RELEASES.items():
            payload = _request_json(
                client,
                "https://api.stlouisfed.org/fred/release/dates",
                params={
                    "release_id": release_id,
                    "api_key": api_key,
                    "file_type": "json",
                    "realtime_start": start.isoformat(),
                    "realtime_end": end.isoformat(),
                    "include_release_dates_with_no_data": "true",
                    "order_by": "release_date",
                    "sort_order": "asc",
                    "limit": 1000,
                },
            )
            for item in payload.get("release_dates", []):
                scheduled = str(item.get("date", ""))
                if not (start.isoformat() <= scheduled <= end.isoformat()):
                    continue
                rows.append(
                    {
                        "event_key": f"fred:{release_id}:{scheduled}",
                        "kind": "event",
                        "category": "macro",
                        "market": "US",
                        "scope": "market",
                        "severity": severity,
                        "title": title,
                        "detail": "FRED 공식 Release Calendar에 게시된 발표일입니다. 실제 FRED 데이터 반영 시각과는 다를 수 있습니다.",
                        "link": f"https://fred.stlouisfed.org/release?rid={release_id}",
                        "occurred_at": scheduled,
                        "available_at": available_at,
                        "data_as_of": scheduled,
                        "scheduled_for": scheduled,
                        "source": "fred",
                        "event_status": "confirmed",
                    }
                )
    finally:
        if owns_client:
            client.close()
    events = _frame(rows).drop_duplicates("event_key")
    return ProviderResult(
        events=events,
        coverage="US high-impact releases",
        data_as_of=available_at[:10],
        message=f"향후 {len(events)}건",
    )


def _text(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value)).strip()


def parse_fomc_calendar(
    page: str, start: date, end: date, available_at: str
) -> ProviderResult:
    """연준 공식 HTML의 연도별 패널에서 회의 종료일(정책 발표일)을 읽는다."""
    headings = list(
        re.finditer(r"(20\d{2}) FOMC Meetings</a>", page, flags=re.IGNORECASE)
    )
    rows: list[dict] = []
    pair = re.compile(
        r"fomc-meeting__month[^>]*>\s*<strong>(.*?)</strong>.*?"
        r"fomc-meeting__date[^>]*>(.*?)</div>",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for index, match in enumerate(headings):
        year = int(match.group(1))
        section_end = (
            headings[index + 1].start() if index + 1 < len(headings) else len(page)
        )
        section = page[match.end() : section_end]
        for month_html, dates_html in pair.findall(section):
            month_label = _text(month_html).lower()
            date_label = _text(dates_html)
            if "notation vote" in date_label.lower():
                continue
            numbers = [int(value) for value in re.findall(r"\d{1,2}", date_label)]
            if not numbers:
                continue
            month_name = month_label.split("/")[-1].strip()
            month = MONTHS.get(month_name)
            if month is None:
                continue
            try:
                decision_day = date(year, month, numbers[-1])
            except ValueError:
                continue
            if decision_day < start or decision_day > end:
                continue
            has_projections = "*" in date_label
            detail = "Federal Reserve 공식 회의 일정의 정책결정일입니다. 미래 회의일은 직전 회의에서 확정될 때까지 잠정 일정입니다."
            if has_projections:
                detail += " Summary of Economic Projections 발표 회의입니다."
            scheduled = decision_day.isoformat()
            rows.append(
                {
                    "event_key": f"federal-reserve:fomc:{scheduled}",
                    "kind": "event",
                    "category": "macro",
                    "market": "US",
                    "scope": "market",
                    "severity": "high",
                    "title": "FOMC Rate Decision",
                    "detail": detail,
                    "link": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
                    "occurred_at": scheduled,
                    "available_at": available_at,
                    "data_as_of": scheduled,
                    "scheduled_for": scheduled,
                    "source": "federal_reserve",
                    "event_status": "projected",
                }
            )
    events = _frame(rows).drop_duplicates("event_key")
    return ProviderResult(
        events=events,
        coverage="Scheduled FOMC decisions",
        data_as_of=available_at[:10],
        message=f"향후 {len(events)}건",
    )


def fetch_fomc_events(
    start: date,
    end: date,
    available_at: str,
    *,
    client: httpx.Client | None = None,
) -> ProviderResult:
    owns_client = client is None
    client = client or httpx.Client(timeout=20, follow_redirects=True)
    try:
        try:
            response = client.get(
                "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"요청 실패: {type(exc).__name__}") from exc
        result = parse_fomc_calendar(response.text, start, end, available_at)
        if result.events.empty:
            raise ProviderUnavailable(
                "공식 페이지에서 향후 FOMC 일정을 찾지 못했습니다"
            )
        return result
    finally:
        if owns_client:
            client.close()


def fetch_massive_earnings(
    api_key: str,
    assets: pd.DataFrame,
    start: date,
    end: date,
    available_at: str,
    *,
    client: httpx.Client | None = None,
) -> ProviderResult:
    """Massive Benzinga 일정 중 사용자의 US 보유·관심 종목만 남긴다."""
    us = assets[assets["iso_code"].eq("US")].drop_duplicates("ticker")
    if us.empty:
        return ProviderResult(empty_events(), "0 tracked US assets", available_at[:10])
    owns_client = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=True)
    try:
        payload = _request_json(
            client,
            "https://api.massive.com/benzinga/v1/earnings",
            params={
                "apiKey": api_key,
                "date.gte": start.isoformat(),
                "date.lte": end.isoformat(),
                "limit": 50000,
                "sort": "date.asc",
            },
            entitlement_name="Massive Benzinga Earnings",
        )
    finally:
        if owns_client:
            client.close()

    by_ticker = {str(row.ticker).upper(): row for row in us.itertuples(index=False)}
    rows = []
    for item in payload.get("results", []):
        ticker = str(item.get("ticker", "")).upper()
        asset = by_ticker.get(ticker)
        scheduled = str(item.get("date", ""))
        if asset is None or not (start.isoformat() <= scheduled <= end.isoformat()):
            continue
        status = str(item.get("date_status") or "projected").lower()
        if status not in {"confirmed", "projected"}:
            status = "projected"
        period = " ".join(
            str(value)
            for value in (item.get("fiscal_period"), item.get("fiscal_year"))
            if value not in {None, ""}
        )
        estimate = item.get("estimated_eps")
        detail_parts = [f"{period} 실적 발표" if period else "실적 발표"]
        if estimate is not None:
            detail_parts.append(f"EPS 컨센서스 {float(estimate):g}")
        if item.get("time"):
            detail_parts.append(f"미 동부시간 {item['time']}")
        rows.append(
            {
                "event_key": f"massive:earnings:{item.get('benzinga_id') or ticker + ':' + scheduled}",
                "kind": "event",
                "category": "earnings",
                "market": "US",
                "scope": asset.scope,
                "severity": "high" if asset.scope == "portfolio" else "medium",
                "title": f"{asset.name or ticker} Earnings",
                "detail": " · ".join(detail_parts),
                "link": f"/stock/{int(asset.meta_id)}",
                "meta_id": int(asset.meta_id),
                "ticker": ticker,
                "name": asset.name,
                "occurred_at": scheduled,
                "available_at": available_at,
                "data_as_of": scheduled,
                "scheduled_for": scheduled,
                "source": "massive_earnings",
                "event_status": status,
            }
        )
    events = _frame(rows).drop_duplicates("event_key")
    return ProviderResult(
        events,
        f"{len(us)} tracked US assets",
        available_at[:10],
        f"향후 {len(events)}건",
    )


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if pd.notna(number) else None


def _money(value) -> str | None:
    number = _number(value)
    if number is None:
        return None
    absolute = abs(number)
    if absolute >= 1_000_000_000:
        return f"${number / 1_000_000_000:.2f}B"
    if absolute >= 1_000_000:
        return f"${number / 1_000_000:.1f}M"
    return f"${number:,.0f}"


def fetch_finnhub_earnings(
    api_key: str,
    assets: pd.DataFrame,
    start: date,
    end: date,
    available_at: str,
    *,
    client: httpx.Client | None = None,
) -> ProviderResult:
    """Finnhub 공식 Calendar에서 추적 US 종목의 예정·발표 실적을 읽는다.

    Finnhub 응답은 일정의 confirmed/projected 구분을 제공하지 않는다. 따라서
    실제 EPS/매출이 도착한 과거 행만 ``observed``이고, 나머지는 보수적으로
    ``projected``다. 미래 날짜를 과거 보고 패턴으로 직접 추정하지 않는다.
    """
    if not api_key.strip():
        raise ConfigurationRequired("FINNHUB_API_KEY가 없습니다")
    us = assets[assets["iso_code"].eq("US")].drop_duplicates("ticker")
    if us.empty:
        return ProviderResult(empty_events(), "0 tracked US assets", available_at[:10])

    owns_client = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=True)
    items: list[dict] = []
    try:
        # 무심볼 달력 조회는 응답이 1,500건에서 잘릴 수 있다. 긴 범위를 한 번에
        # 받아 사후 필터링하면 보유·관심 종목이 응답에 있어야 한다는 보장이 없다.
        # 통합 마스터의 추적 티커를 하나씩 명시해 누락을 조용히 만들지 않는다.
        for ticker in sorted(us["ticker"].astype(str).str.upper().unique()):
            payload = _request_json(
                client,
                "https://finnhub.io/api/v1/calendar/earnings",
                params={
                    "token": api_key,
                    "from": start.isoformat(),
                    "to": end.isoformat(),
                    "symbol": ticker,
                    "international": "false",
                },
                auth_name="Finnhub",
            )
            ticker_items = payload.get("earningsCalendar")
            if not isinstance(ticker_items, list):
                raise ProviderUnavailable("Finnhub Earnings 응답 계약이 변경되었습니다")
            items.extend(ticker_items)
    finally:
        if owns_client:
            client.close()

    by_ticker = {str(row.ticker).upper(): row for row in us.itertuples(index=False)}
    retrieved_on = date.fromisoformat(available_at[:10])
    rows: list[dict] = []
    upcoming = 0
    reported = 0
    hour_labels = {
        "bmo": "미국장 개장 전",
        "amc": "미국장 마감 후",
        "dmh": "미국장 거래 중",
    }
    for item in items:
        ticker = str(item.get("symbol", "")).upper()
        asset = by_ticker.get(ticker)
        scheduled = str(item.get("date", ""))
        if asset is None or not (start.isoformat() <= scheduled <= end.isoformat()):
            continue
        try:
            scheduled_date = date.fromisoformat(scheduled)
        except ValueError:
            continue

        eps_actual = _number(item.get("epsActual"))
        eps_estimate = _number(item.get("epsEstimate"))
        revenue_actual = _number(item.get("revenueActual"))
        revenue_estimate = _number(item.get("revenueEstimate"))
        has_actual = scheduled_date <= retrieved_on and (
            eps_actual is not None or revenue_actual is not None
        )
        status = "observed" if has_actual else "projected"
        if has_actual:
            reported += 1
        else:
            upcoming += 1

        period = " ".join(
            str(value)
            for value in (
                item.get("year"),
                f"Q{item.get('quarter')}" if item.get("quarter") else None,
            )
            if value not in {None, ""}
        )
        detail_parts = [f"{period} 실적" if period else "실적"]
        if eps_actual is not None:
            eps_text = f"EPS actual {eps_actual:g}"
            if eps_estimate is not None:
                eps_text += f" / estimate {eps_estimate:g}"
                if eps_estimate != 0:
                    surprise = (eps_actual - eps_estimate) / abs(eps_estimate) * 100
                    eps_text += f" ({surprise:+.1f}%)"
            detail_parts.append(eps_text)
        elif eps_estimate is not None:
            detail_parts.append(f"EPS estimate {eps_estimate:g}")

        actual_money = _money(revenue_actual)
        estimate_money = _money(revenue_estimate)
        if actual_money:
            revenue_text = f"Revenue actual {actual_money}"
            if estimate_money:
                revenue_text += f" / estimate {estimate_money}"
            detail_parts.append(revenue_text)
        elif estimate_money:
            detail_parts.append(f"Revenue estimate {estimate_money}")
        if item.get("hour") in hour_labels:
            detail_parts.append(hour_labels[item["hour"]])
        if not has_actual:
            detail_parts.append("공급자가 확정 여부를 구분하지 않아 Projected로 표시")

        rows.append(
            {
                "event_key": f"finnhub:earnings:{ticker}:{scheduled}",
                "kind": "event",
                "category": "earnings",
                "market": "US",
                "scope": asset.scope,
                "severity": "high" if asset.scope == "portfolio" else "medium",
                "title": f"{asset.name or ticker} Earnings",
                "detail": " · ".join(detail_parts),
                "link": f"/stock/{int(asset.meta_id)}",
                "meta_id": int(asset.meta_id),
                "ticker": ticker,
                "name": asset.name,
                "occurred_at": scheduled,
                "available_at": available_at,
                "data_as_of": available_at[:10],
                "scheduled_for": scheduled,
                "source": "finnhub_earnings",
                "event_status": status,
            }
        )
    events = _frame(rows).drop_duplicates("event_key")
    return ProviderResult(
        events,
        f"{len(us)} tracked US assets",
        available_at[:10],
        f"Finnhub 공식 API · 예정 {upcoming}건 / 발표 {reported}건",
    )


def _dart_corp_map(content: bytes) -> dict[str, str]:
    try:
        if content.startswith(b"PK"):
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                xml = archive.read(archive.namelist()[0])
        else:
            xml = content
        root = ElementTree.fromstring(xml)
    except (KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise ProviderUnavailable("DART 고유번호 파일을 해석하지 못했습니다") from exc
    mapping = {}
    for item in root.findall("list"):
        ticker = (item.findtext("stock_code") or "").strip()
        corp_code = (item.findtext("corp_code") or "").strip()
        if ticker and corp_code:
            mapping[ticker.zfill(6)] = corp_code
    return mapping


def _filing_severity(report_name: str) -> str:
    high = (
        "부도",
        "회생절차",
        "상장폐지",
        "영업정지",
        "유상증자",
        "무상감자",
        "횡령",
        "배임",
        "최대주주변경",
        "매매거래정지",
        "공개매수",
        "합병",
        "분할",
        "해산",
        "감사의견",
    )
    medium = (
        "사업보고서",
        "반기보고서",
        "분기보고서",
        "주요사항보고서",
        "잠정실적",
        "실적",
        "배당",
        "자기주식",
        "전환사채",
        "신주인수권",
        "대량보유",
        "단일판매",
        "공급계약",
        "타법인주식",
        "출자증권",
        "유형자산",
        "소송",
        "투자판단",
        "공정공시",
        "기업설명회",
    )
    if any(word in report_name for word in high):
        return "high"
    if any(word in report_name for word in medium):
        return "medium"
    return "low"


def fetch_dart_filings(
    api_key: str,
    assets: pd.DataFrame,
    start: date,
    end: date,
    available_at: str,
    *,
    client: httpx.Client | None = None,
) -> ProviderResult:
    """관심·보유 KR 종목의 실제 DART 접수 공시를 가져온다."""
    kr = assets[assets["iso_code"].eq("KR")].drop_duplicates("ticker")
    if kr.empty:
        return ProviderResult(empty_events(), "0 tracked KR assets", available_at[:10])
    owns_client = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=True)
    try:
        try:
            corp_response = client.get(
                "https://opendart.fss.or.kr/api/corpCode.xml",
                params={"crtfc_key": api_key},
            )
            corp_response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(
                f"DART 고유번호 요청 실패: {type(exc).__name__}"
            ) from exc
        corp_map = _dart_corp_map(corp_response.content)
        if not corp_map:
            raise ProviderUnavailable("DART 고유번호 응답에 상장 종목이 없습니다")
        rows = []
        mapped = 0
        for asset in kr.itertuples(index=False):
            ticker = str(asset.ticker).zfill(6)
            corp_code = corp_map.get(ticker)
            if not corp_code:
                continue
            mapped += 1
            payload = _request_json(
                client,
                "https://opendart.fss.or.kr/api/list.json",
                params={
                    "crtfc_key": api_key,
                    "corp_code": corp_code,
                    "bgn_de": start.strftime("%Y%m%d"),
                    "end_de": end.strftime("%Y%m%d"),
                    "last_reprt_at": "Y",
                    "page_count": 100,
                },
            )
            status = str(payload.get("status", ""))
            if status == "013":
                continue
            if status != "000":
                raise ProviderUnavailable(
                    f"DART 응답 오류 {status or 'unknown'}: {payload.get('message', '')}"
                )
            for item in payload.get("list", []):
                received = str(item.get("rcept_dt", ""))
                if len(received) != 8:
                    continue
                occurred = f"{received[:4]}-{received[4:6]}-{received[6:]}"
                report_name = str(item.get("report_nm") or "공시")
                receipt = str(item.get("rcept_no") or "")
                severity = _filing_severity(report_name)
                if severity == "low":
                    continue
                rows.append(
                    {
                        "event_key": f"dart:{receipt}",
                        "kind": "event",
                        "category": "filing",
                        "market": "KR",
                        "scope": asset.scope,
                        "severity": severity,
                        "title": f"{asset.name or ticker} Filing",
                        "detail": f"{report_name} · {item.get('flr_nm') or 'DART 접수'}",
                        "link": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}",
                        "meta_id": int(asset.meta_id),
                        "ticker": ticker,
                        "name": asset.name,
                        "occurred_at": occurred,
                        "available_at": available_at,
                        "data_as_of": occurred,
                        "scheduled_for": occurred,
                        "source": "dart",
                        "event_status": "observed",
                    }
                )
    finally:
        if owns_client:
            client.close()
    events = _frame(rows).drop_duplicates("event_key")
    return ProviderResult(
        events,
        f"{mapped}/{len(kr)} tracked KR assets",
        available_at[:10],
        f"최근 중요 공시 {len(events)}건",
    )


SEC_FORMS = {
    "8-K",
    "8-K/A",
    "10-Q",
    "10-Q/A",
    "10-K",
    "10-K/A",
    "20-F",
    "20-F/A",
    "6-K",
}


def fetch_sec_filings(
    contact: str,
    assets: pd.DataFrame,
    ticker_reference: pd.DataFrame,
    start: date,
    end: date,
    available_at: str,
    *,
    client: httpx.Client | None = None,
) -> ProviderResult:
    """SEC submissions API에서 추적 US 종목의 중요 접수 양식만 읽는다."""
    us = assets[assets["iso_code"].eq("US")].drop_duplicates("ticker")
    if us.empty:
        return ProviderResult(empty_events(), "0 tracked US assets", available_at[:10])
    refs = ticker_reference[["ticker", "cik"]].dropna().copy()
    refs["ticker"] = refs["ticker"].astype(str).str.upper()
    refs = refs.drop_duplicates("ticker").set_index("ticker")
    owns_client = client is None
    client = client or httpx.Client(
        timeout=20,
        follow_redirects=True,
        headers={
            "User-Agent": f"Insight-Invest {contact}",
            "Accept-Encoding": "gzip, deflate",
        },
    )
    rows = []
    mapped = 0
    try:
        for asset in us.itertuples(index=False):
            ticker = str(asset.ticker).upper()
            if ticker not in refs.index:
                continue
            cik = int(refs.loc[ticker, "cik"])
            mapped += 1
            payload = _request_json(
                client,
                f"https://data.sec.gov/submissions/CIK{cik:010d}.json",
                params={},
            )
            recent = payload.get("filings", {}).get("recent", {})
            keys = [
                "accessionNumber",
                "filingDate",
                "acceptanceDateTime",
                "form",
                "primaryDocument",
            ]
            length = min((len(recent.get(key, [])) for key in keys), default=0)
            for index in range(length):
                form = str(recent["form"][index])
                filed = str(recent["filingDate"][index])
                if form not in SEC_FORMS or not (
                    start.isoformat() <= filed <= end.isoformat()
                ):
                    continue
                accession = str(recent["accessionNumber"][index])
                document = str(recent["primaryDocument"][index])
                accepted = str(recent["acceptanceDateTime"][index] or filed)
                rows.append(
                    {
                        "event_key": f"sec:{accession}",
                        "kind": "event",
                        "category": "filing",
                        "market": "US",
                        "scope": asset.scope,
                        "severity": "high"
                        if form.startswith("8-K") and asset.scope == "portfolio"
                        else "medium",
                        "title": f"{asset.name or ticker} Filing",
                        "detail": f"SEC {form} 접수",
                        "link": f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{document}",
                        "meta_id": int(asset.meta_id),
                        "ticker": ticker,
                        "name": asset.name,
                        "occurred_at": accepted,
                        "available_at": available_at,
                        "data_as_of": filed,
                        "scheduled_for": filed,
                        "source": "sec",
                        "event_status": "observed",
                    }
                )
    finally:
        if owns_client:
            client.close()
    events = _frame(rows).drop_duplicates("event_key")
    return ProviderResult(
        events,
        f"{mapped}/{len(us)} tracked US assets",
        available_at[:10],
        f"최근 중요 공시 {len(events)}건",
    )


def recent_window(today: date, days: int = 7) -> tuple[date, date]:
    return today - timedelta(days=days), today
