"""Research Radar feed and single-user library state API."""

import re
import unicodedata
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from datastore import research as research_store
from module import research_jobs

router = APIRouter(prefix="/research", tags=["Research"])
ENTRY_ID = re.compile(r"^[0-9a-f]{64}$")
RESEARCH_VIEWS = frozenset({"all", "unread", "read", "saved"})
RESEARCH_LANE_FILTERS = frozenset({"core", "discovery", "all"})
MAX_QUERY_LENGTH = 200


class ResearchReadRequest(BaseModel):
    read: bool = True


class ResearchSavedRequest(BaseModel):
    saved: bool = True


class ResearchSeenRequest(BaseModel):
    through: datetime


def _validate_entry_id(entry_id: str) -> None:
    if not ENTRY_ID.fullmatch(entry_id):
        raise HTTPException(status_code=422, detail="invalid research entry id")


def _normalise_search(value: str) -> str:
    return unicodedata.normalize("NFKC", " ".join(value.split())).casefold()


def _matches_query(item: dict, query: str) -> bool:
    authors = item.get("authors", [])
    values = [
        item.get("title", ""),
        item.get("summary", ""),
        item.get("source_name", ""),
        " ".join(str(author) for author in authors if author),
    ]
    searchable = _normalise_search(" ".join(str(value) for value in values))
    return all(token in searchable for token in _normalise_search(query).split())


def _item_lane(item: dict) -> str:
    lane = item.get("research_lane", "context")
    return lane if lane in {"core", "discovery", "context"} else "context"


def _matches_lane(item: dict, lane: str) -> bool:
    return lane == "all" or _item_lane(item) == lane


def _research_status(feed: dict, seen_through: datetime | None) -> dict:
    notifiable = [item for item in feed["items"] if item.get("notification_eligible") is True]
    return {
        "schema_version": 1,
        "initialized": seen_through is not None,
        "unseen": research_store.unseen_entry_count(notifiable, seen_through),
        "generated_at": feed.get("generated_at"),
        "seen_through": seen_through.isoformat() if seen_through else None,
    }


@router.get("/status")
def get_research_status():
    feed = research_store.load_feed()
    return _research_status(feed, research_store.load_seen_through())


@router.put("/seen")
def acknowledge_research_feed(request: ResearchSeenRequest):
    if request.through.tzinfo is None:
        raise HTTPException(status_code=422, detail="research seen timestamp requires timezone")
    feed = research_store.load_feed()
    generated_at = research_store.parse_timestamp(feed.get("generated_at"))
    if generated_at is None:
        return _research_status(feed, research_store.load_seen_through())
    requested = request.through.astimezone(timezone.utc)
    seen_through = research_store.save_seen_through(min(requested, generated_at))
    return _research_status(feed, seen_through)


@router.get("/jobs/{entry_id}")
def get_research_job(entry_id: str):
    _validate_entry_id(entry_id)
    try:
        return research_jobs.get_request(entry_id)
    except Exception as exc:
        response = getattr(exc, "response", {})
        error = response.get("Error", {}) if isinstance(response, dict) else {}
        if isinstance(error, dict) and str(error.get("Code", "")) in {"NoSuchKey", "404"}:
            raise HTTPException(status_code=404, detail="research job not found") from exc
        raise


@router.get("")
def get_research_feed(
    source_id: str | None = None,
    unread_only: bool = False,
    view: str = "all",
    lane: str = "core",
    q: str | None = Query(None, max_length=MAX_QUERY_LENGTH),
    entry_id: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    if view not in RESEARCH_VIEWS:
        raise HTTPException(status_code=422, detail="invalid research view")
    if lane not in RESEARCH_LANE_FILTERS:
        raise HTTPException(status_code=422, detail="invalid research lane")
    if unread_only:
        if view not in {"all", "unread"}:
            raise HTTPException(status_code=422, detail="conflicting research view filters")
        view = "unread"
    query = " ".join((q or "").split())
    if len(query) > MAX_QUERY_LENGTH:
        raise HTTPException(status_code=422, detail="research query is too long")
    if entry_id:
        _validate_entry_id(entry_id)
    feed = research_store.load_feed()
    states = research_store.entry_states()
    all_items = [
        {
            **item,
            "is_read": states.get(item["entry_id"], {}).get("is_read", False),
            "is_saved": states.get(item["entry_id"], {}).get("is_saved", False),
        }
        for item in feed["items"]
    ]
    lane_items = [item for item in all_items if _matches_lane(item, lane)]
    sources: dict[str, dict] = {}
    for item in lane_items:
        source = sources.setdefault(
            item["source_id"],
            {"source_id": item["source_id"], "source_name": item["source_name"], "count": 0},
        )
        source["count"] += 1
    if entry_id:
        filtered = [item for item in all_items if item["entry_id"] == entry_id]
        if not filtered:
            raise HTTPException(status_code=404, detail="research entry not found")
    else:
        filtered = lane_items
        if source_id:
            filtered = [item for item in filtered if item["source_id"] == source_id]
        if view == "unread":
            filtered = [item for item in filtered if not item["is_read"]]
        elif view == "read":
            filtered = [item for item in filtered if item["is_read"]]
        elif view == "saved":
            filtered = [item for item in filtered if item["is_saved"]]
        if query:
            filtered = [item for item in filtered if _matches_query(item, query)]
    return {
        "schema_version": 1,
        "generated_at": feed["generated_at"],
        "total": len(filtered),
        "unread": sum(not item["is_read"] for item in lane_items),
        "read": sum(item["is_read"] for item in lane_items),
        "saved": sum(item["is_saved"] for item in lane_items),
        "lane": lane,
        "lane_counts": {
            "core": sum(_item_lane(item) == "core" for item in all_items),
            "discovery": sum(_item_lane(item) == "discovery" for item in all_items),
            "context": sum(_item_lane(item) == "context" for item in all_items),
            "all": len(all_items),
        },
        "view": view,
        "query": query,
        "offset": offset,
        "limit": limit,
        "sources": sorted(sources.values(), key=lambda item: item["source_name"]),
        "items": filtered[offset : offset + limit],
    }


@router.put("/read/all")
def mark_all_research_read(lane: str = "core"):
    if lane not in RESEARCH_LANE_FILTERS:
        raise HTTPException(status_code=422, detail="invalid research lane")
    feed = research_store.load_feed()
    entry_ids = [item["entry_id"] for item in feed["items"] if _matches_lane(item, lane)]
    updated = research_store.mark_all_read(entry_ids)
    return {"updated": updated, "total": len(entry_ids), "unread": 0, "lane": lane}


@router.put("/{entry_id}/read")
def set_research_read_state(entry_id: str, request: ResearchReadRequest):
    _validate_entry_id(entry_id)
    feed = research_store.load_feed()
    if not any(item.get("entry_id") == entry_id for item in feed["items"]):
        raise HTTPException(status_code=404, detail="research entry not found")
    research_store.set_read(entry_id, read=request.read)
    return {"entry_id": entry_id, "is_read": request.read}


@router.put("/{entry_id}/saved")
def set_research_saved_state(entry_id: str, request: ResearchSavedRequest):
    _validate_entry_id(entry_id)
    feed = research_store.load_feed()
    if not any(item.get("entry_id") == entry_id for item in feed["items"]):
        raise HTTPException(status_code=404, detail="research entry not found")
    research_store.set_saved(entry_id, saved=request.saved)
    return {"entry_id": entry_id, "is_saved": request.saved}
