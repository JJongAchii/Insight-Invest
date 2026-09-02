"""Research Radar feed and single-user read state API."""

import re

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from datastore import research as research_store

router = APIRouter(prefix="/research", tags=["Research"])
ENTRY_ID = re.compile(r"^[0-9a-f]{64}$")


class ResearchReadRequest(BaseModel):
    read: bool = True


def _validate_entry_id(entry_id: str) -> None:
    if not ENTRY_ID.fullmatch(entry_id):
        raise HTTPException(status_code=422, detail="invalid research entry id")


@router.get("")
def get_research_feed(
    source_id: str | None = None,
    unread_only: bool = False,
    entry_id: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
):
    if entry_id:
        _validate_entry_id(entry_id)
    feed = research_store.load_feed()
    read_ids = research_store.read_entry_ids()
    all_items = [{**item, "is_read": item["entry_id"] in read_ids} for item in feed["items"]]
    sources: dict[str, dict] = {}
    for item in all_items:
        source = sources.setdefault(
            item["source_id"],
            {"source_id": item["source_id"], "source_name": item["source_name"], "count": 0},
        )
        source["count"] += 1
    filtered = all_items
    if source_id:
        filtered = [item for item in filtered if item["source_id"] == source_id]
    if unread_only:
        filtered = [item for item in filtered if not item["is_read"]]
    if entry_id:
        filtered = [item for item in filtered if item["entry_id"] == entry_id]
    return {
        "schema_version": 1,
        "generated_at": feed["generated_at"],
        "total": len(filtered),
        "unread": sum(not item["is_read"] for item in all_items),
        "offset": offset,
        "limit": limit,
        "sources": sorted(sources.values(), key=lambda item: item["source_name"]),
        "items": filtered[offset : offset + limit],
    }


@router.put("/{entry_id}/read")
def set_research_read_state(entry_id: str, request: ResearchReadRequest):
    _validate_entry_id(entry_id)
    feed = research_store.load_feed()
    if not any(item.get("entry_id") == entry_id for item in feed["items"]):
        raise HTTPException(status_code=404, detail="research entry not found")
    research_store.set_read(entry_id, read=request.read)
    return {"entry_id": entry_id, "is_read": request.read}
