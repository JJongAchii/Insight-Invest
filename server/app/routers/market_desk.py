"""Serve finished publications. This endpoint has no access to an editorial runtime."""

import logging
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import AwareDatetime, BaseModel, Field, HttpUrl

from datastore import storage
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


@router.get("")
def get_market_desk():
    try:
        board = Board.model_validate(storage.read_json("market_desk", "board.json"))
    except FileNotFoundError:
        return {"state": "awaiting", "board": None}
    except Exception:
        logger.exception("장중 해설 발행본 조회 실패")
        raise HTTPException(503, "장중 해설을 불러올 수 없습니다.") from None
    now = datetime.now(KST)
    stale = now - board.checked_at > timedelta(minutes=25 if is_open_kst(now) else 100)
    return {"state": "stale" if stale else "ready", "board": board}
