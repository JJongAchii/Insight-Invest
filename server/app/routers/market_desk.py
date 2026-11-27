"""Serve finished publications. These endpoints have no access to an editorial runtime."""

import logging
from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import AwareDatetime, BaseModel, Field, HttpUrl

from datastore import desk_news as news_store
from datastore import storage
from module import desk_news, market_map
from module.kr_intraday import KST, is_open_kst

router = APIRouter(prefix="/market-desk", tags=["market desk"])
logger = logging.getLogger(__name__)


class Source(BaseModel):
    title: str
    publisher: str
    url: HttpUrl
    published_at: AwareDatetime
    license_url: HttpUrl | None = None
    license_name: str | None = None


class LeadPassage(BaseModel):
    text: str = Field(min_length=15, max_length=350)
    sources: list[Source] = Field(min_length=1, max_length=4)


class CloseComparison(BaseModel):
    index: Literal["코스피", "코스닥"]
    previous_points: float = Field(allow_inf_nan=False)
    current_points: float = Field(allow_inf_nan=False)
    share_pct: float = Field(ge=0, le=100)


class MarketLead(BaseModel):
    phase: Literal["intraday", "close"]
    trade_date: date
    as_of: AwareDatetime
    cutoff: AwareDatetime
    close_at: AwareDatetime
    published_at: AwareDatetime
    headline: str = Field(min_length=1, max_length=75)
    reading: LeadPassage
    qualification: LeadPassage
    watch: str = Field(min_length=1, max_length=170)
    comparison: CloseComparison | None = None


def _current_lead(raw, now):
    if not raw:
        return None
    try:
        lead = MarketLead.model_validate(raw)
    except ValueError:
        logger.warning("시장 해설 발행 형식 오류")
        return None
    if (lead.trade_date != now.date() or any(stamp.astimezone(KST).date() != lead.trade_date
            for stamp in (lead.as_of, lead.cutoff, lead.close_at))
            or not lead.as_of <= lead.cutoff <= lead.published_at <= now):
        return None
    if any(src.published_at > lead.as_of for block in (lead.reading, lead.qualification) for src in block.sources):
        return None
    if lead.phase == "close":
        return lead if lead.as_of >= lead.close_at else None
    return lead if now < lead.close_at and now - lead.as_of <= timedelta(minutes=90) else None


class Issue(BaseModel):
    id: str
    kind: Literal["move", "filing", "news"]
    origin: Literal["desk", "reporter"] = "desk"
    status: Literal["unconfirmed", "analysis", "reported"]
    headline: str
    fact: str
    interpretation: str
    watch: str
    published_at: AwareDatetime
    observed_at: AwareDatetime | None
    observation: str
    sources: list[Source] = Field(max_length=8)
    followups: list[Source] = Field(default_factory=list, max_length=3)
    # Reporter news may arrive as fields instead of one formatted text.
    category: str | None = None
    priority: Literal["major", "urgent"] | None = None
    update: bool = False
    attribution: str | None = None
    significance: str = ""
    change: str = ""


class Brief(BaseModel):
    id: str
    kind: Literal["am", "pm"]
    published_at: AwareDatetime
    as_of: AwareDatetime
    body: str


class Board(BaseModel):
    version: Literal[1]
    checked_at: AwareDatetime
    monitoring: bool = False
    market_at: AwareDatetime | None
    filings_at: AwareDatetime | None
    issues: list[Issue] = Field(max_length=15)
    briefings: list[Brief] = Field(max_length=2)
    market_reports: list[Source] = Field(default_factory=list, max_length=3)


Label = Literal["데이터", "보도", "해석"]


class Claim(BaseModel):
    text: str = Field(min_length=1, max_length=240)
    label: Label
    sources: list[Source] = Field(default_factory=list, max_length=4)


class NoteStock(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    ticker: str | None = None
    chg_pct: float | None = Field(default=None, allow_inf_nan=False)
    reason: str = Field(min_length=1, max_length=160)
    label: Label
    sources: list[Source] = Field(default_factory=list, max_length=4)


class Note(BaseModel):
    """ai-company 장중 노트 한 편. 문장마다 근거 종류가 붙는다(스펙 2026-11-27 §6.4)."""
    id: str
    kind: Literal["scheduled", "urgent"]
    slot: Literal["open", "morning", "afternoon", "preclose", "close"] | None = None
    trigger: dict | None = None
    observed_at: AwareDatetime
    published_at: AwareDatetime
    headline: str = Field(min_length=1, max_length=80)
    drivers: list[Claim] = Field(min_length=1, max_length=3)
    stocks: list[NoteStock] = Field(default_factory=list, max_length=5)
    since_last: str = Field(default="", max_length=240)
    watch: list[str] = Field(default_factory=list, max_length=2)
    sources: list[Source] = Field(default_factory=list, max_length=12)


def _today_notes(raw, now):
    """당일 노트만, 발행 순서대로. 형식이 틀린 한 편은 빼고 나머지를 보인다."""
    notes = []
    for item in (raw or {}).get("notes") or []:
        try:
            note = Note.model_validate(item)
        except ValueError:
            logger.warning("장중 노트 형식 오류 — 한 편 제외: %s", item.get("id") if isinstance(item, dict) else None)
            continue
        if note.observed_at.astimezone(KST).date() == now.date():
            notes.append(note)
    return sorted(notes, key=lambda note: note.published_at)


MAP_KEY = "kr_intraday_map.json"


def _saved_map(now):
    """지도와 당일 시계열. 상태: latest(25분 이내), delayed(장중인데 오래됨), closed(오늘 장이 끝남), previous(지난 거래일)."""
    try:
        saved = storage.read_json(MAP_KEY)
    except FileNotFoundError:
        return {"state": "awaiting"}, []
    except Exception:
        logger.exception("장중 시장 지도 조회 실패")
        return {"state": "unavailable"}, []
    latest = saved["latest"]
    observed = datetime.fromisoformat(latest["observed_at"])
    if saved["trade_date"] != now.date().isoformat():
        state = "previous"
    elif now - observed <= timedelta(minutes=25):
        state = "latest"
    else:
        state = "delayed" if is_open_kst(now) else "closed"
    return {"state": state, **latest}, saved.get("series") or []


def _since_note(notes, series):
    """가장 최근 노트의 지도 시각과 최신 수집 사이에 달라진 것."""
    if not notes or len(series) < 2:
        return None
    noted = notes[-1].observed_at
    earlier = [entry for entry in series if datetime.fromisoformat(entry["observed_at"]) <= noted]
    if not earlier or earlier[-1] is series[-1]:
        return None
    return market_map.since(earlier[-1], series[-1])


class SessionReading(BaseModel):
    observed_at: AwareDatetime
    headline: str
    market: str
    sectors: str
    watch: str


def _read_session(now):
    try:
        packet = storage.read_json("market_desk", "input.json")
        if not packet.get("session"):
            return None, "awaiting"
        reading = SessionReading.model_validate(packet["session"])
        day = reading.observed_at.astimezone(KST).date()
        if packet["version"] != 1 or packet["trade_date"] != day.isoformat() or reading.observed_at > now:
            raise ValueError("invalid market reading date or version")
    except FileNotFoundError:
        return None, "awaiting"
    except Exception:
        logger.exception("장중 시황 수집본 조회 실패")
        return None, "unavailable"
    if day < now.date():
        return reading, "previous"
    regular_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    if now.weekday() < 5 and min(now, regular_close) - reading.observed_at > timedelta(minutes=25):
        return reading, "delayed"
    return reading, "latest"


def _policy_coverage(board, reading):
    """Contemporaneous policy reporting. These links are context, never evidence of index causation."""
    if not board or not reading:
        return []
    cutoff = reading.observed_at - timedelta(minutes=20)
    day = reading.observed_at.astimezone(KST).date()
    items = []
    seen = set()
    for issue in sorted(board.issues, key=lambda row: row.published_at, reverse=True):
        if issue.kind != "news" or issue.published_at > reading.observed_at or not issue.sources:
            continue
        bank = next((bank for bank, aliases in (("BOK", ("한국은행", "한은", "금통위")), ("Fed", ("연준", "FOMC")))
                     if any(alias in issue.headline for alias in aliases)), None)
        if not bank:
            continue
        if "금리" in issue.headline and any(word in issue.headline for word in ("인상", "인하", "동결")):
            terms = ("금리", "긴축", "인상", "인하", "동결")
        elif "성장률" in issue.headline and "전망" in issue.headline:
            terms = ("성장", "전망", "GDP")
        else:
            continue
        # The published summary may rely on several sources. All must already have been public.
        if (bank, terms) in seen or any(src.published_at > cutoff or src.published_at.astimezone(KST).date() != day
                                for src in issue.sources):
            continue
        source = next((src for src in issue.sources if any(term in src.title for term in terms)), None)
        if source:
            seen.add((bank, terms))
            items.append({"headline": issue.headline, "source": source})
    return items


def _freshness(checked_at, now):
    return "stale" if now - checked_at > timedelta(minutes=25 if is_open_kst(now) else 100) else "ready"


def _saved_board(now):
    """The publication as written and as validated, with its freshness. Raises when it cannot be read."""
    try:
        raw = storage.read_json("market_desk", "board.json")
    except FileNotFoundError:
        return None, None, "awaiting"
    board = Board.model_validate(raw)
    return raw, board, _freshness(board.checked_at, now)


@router.get("")
def get_market_desk():
    now = datetime.now(KST)
    session, session_state = _read_session(now)
    map_, series = _saved_map(now)
    try:
        raw, board, state = _saved_board(now)
        lead = _current_lead(raw.get("lead"), now) if raw else None
        notes = _today_notes(raw, now)
    except Exception:
        logger.exception("장중 해설 발행본 조회 실패")
        if session is None and map_["state"] in {"awaiting", "unavailable"}:
            raise HTTPException(503, "장중 해설을 불러올 수 없습니다.") from None
        board, lead, state, notes = None, None, "unavailable", []
    return {"state": state, "board": board, "lead": lead, "today": now.date(), "session": session,
            "session_state": session_state, "policy_coverage": _policy_coverage(board, session),
            "map": map_, "notes": notes, "since_note": _since_note(notes, series) if map_["state"] in ("latest", "closed") else None}


class NewsSeen(BaseModel):
    through: AwareDatetime


class Edition(BaseModel):
    version: Literal[1]
    checked_at: AwareDatetime


NEWS_LIMIT = 200


def saved_news(now):
    """News articles of the saved publication, its freshness and when it was checked.

    Raises when the publication itself cannot be read. News does not depend on the briefings or the market
    explanation beside it, and one malformed article is left out instead of taking the others with it.
    """
    try:
        raw = storage.read_json("market_desk", "board.json")
    except FileNotFoundError:
        return [], "awaiting", None
    edition = Edition.model_validate(raw)
    # The week list is the news page. A publisher that has not learned it still lists news for the home.
    listed = raw["news"] if isinstance(raw.get("news"), list) else raw["issues"]
    articles = []
    for issue in listed[:NEWS_LIMIT]:
        try:
            Issue.model_validate(issue)
        except ValueError:
            logger.warning("뉴스 발행 형식 오류 — 한 건 제외: %s", issue.get("id") if isinstance(issue, dict) else None)
        else:
            articles.append(issue)
    return desk_news.normalize(articles), _freshness(edition.checked_at, now), raw["checked_at"]


def _news_status(items, seen):
    stamps = [datetime.fromisoformat(item["published_at"]) for item in items]
    return {"unseen": sum(stamp > seen for stamp in stamps) if seen else len(stamps),
            "latest_at": items[0]["published_at"] if items else None,
            "seen_through": seen.isoformat() if seen else None}


def _news_for_badge(now):
    """The navigation badge is not where a publication failure is reported; the news page is."""
    try:
        return saved_news(now)[0]
    except Exception:
        logger.exception("뉴스 발행본 조회 실패")
        return []


@router.get("/news")
def get_desk_news():
    try:
        items, state, checked_at = saved_news(datetime.now(KST))
    except Exception:
        logger.exception("뉴스 발행본 조회 실패")
        raise HTTPException(503, "뉴스를 불러올 수 없습니다.") from None
    status = _news_status(items, news_store.load_seen_through())
    return {"state": state, "checked_at": checked_at, "items": items,
            "seen_through": status["seen_through"], "unseen": status["unseen"]}


@router.get("/news/status")
def get_desk_news_status():
    return _news_status(_news_for_badge(datetime.now(KST)), news_store.load_seen_through())


@router.put("/news/seen")
def acknowledge_desk_news(request: NewsSeen):
    now = datetime.now(KST)
    items = _news_for_badge(now)
    # A visit reaches the newest published article, whose clock may run ahead of this one, and nothing later.
    newest = max([now, *(datetime.fromisoformat(item["published_at"]) for item in items[:1])])
    return _news_status(items, news_store.save_seen_through(min(request.through, newest)))
