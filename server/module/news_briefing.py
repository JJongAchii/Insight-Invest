"""KR 뉴스 브리핑 순수 로직 — RSS 클러스터 파싱·스토리 병합·규칙 랭킹·큐레이션 검증.

Google News 한국판 RSS의 item description에는 같은 사건을 다룬 타 언론사 기사
목록이 (이스케이프된) HTML <ol>로 들어 있다. 그 크기(보도 언론사 수)를 객관적
중요도 신호로 쓴다. I/O 없음 — fetch·LLM 호출·발행은 scripts/build_news.py 소관.
스펙: docs/superpowers/specs/2026-08-14-kr-news-briefing-design.md
"""

from __future__ import annotations

import html
import json
import math
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

KST = timezone(timedelta(hours=9))
CANDIDATE_LIMIT = 60
SECTION_SIZE = 5
JACCARD_THRESHOLD = 0.6
DECAY_HOURS = 24.0

_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.DOTALL)
# description(unescape 후)의 관련기사 항목: <li><a href="URL">제목</a>…<font>언론사</font>
_LI_RE = re.compile(
    r'<li><a href="([^"]+)"[^>]*>(.*?)</a>.*?<font[^>]*>(.*?)</font>', re.DOTALL
)


def _tag(xml: str, tag: str) -> str | None:
    m = re.search(rf"<{tag}[^>]*><!\[CDATA\[(.*?)\]\]></{tag}>", xml, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xml, re.DOTALL)
    return m.group(1).strip() if m else None


def _parse_pubdate(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = parsedate_to_datetime(s)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_feed(xml: str, feed: str) -> list[dict]:
    """RSS XML → 스토리 후보 리스트. feed는 "general"|"economy"."""
    items = []
    for chunk in _ITEM_RE.findall(xml):
        title = _tag(chunk, "title")
        link = _tag(chunk, "link")
        if not title or not link:
            continue
        source = html.unescape(_tag(chunk, "source") or "")
        pub = _parse_pubdate(_tag(chunk, "pubDate"))
        desc = html.unescape(_tag(chunk, "description") or "")
        cluster = _LI_RE.findall(desc)
        cluster_urls = [u for u, _t, _s in cluster]
        sources: list[str] = [source] if source else []
        for _u, _t, s in cluster:
            s = re.sub(r"<[^>]*>", "", s).strip()
            if s and s not in sources:
                sources.append(s)
        items.append({
            "title": html.unescape(title),
            "url": link,
            "source": source,
            "published_at": pub.isoformat() if pub else None,
            "cluster_count": max(len(cluster), 1),
            "sources": sources,
            "cluster_urls": cluster_urls,
            "feed": feed,
        })
    return items


def _norm_tokens(title: str) -> set[str]:
    t = re.sub(r"[^0-9a-z가-힣 ]", " ", title.lower())
    return {w for w in t.split() if len(w) >= 2}


def _same_story(a: dict, b: dict) -> bool:
    if a["url"] == b["url"]:
        return True
    if a["url"] in b["cluster_urls"] or b["url"] in a["cluster_urls"]:
        return True
    ta, tb = _norm_tokens(a["title"]), _norm_tokens(b["title"])
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= JACCARD_THRESHOLD


def merge_stories(items: list[dict]) -> list[dict]:
    """같은 스토리 병합 — cluster_count 큰 쪽 유지, sources 합집합, general 태그 우선."""
    merged: list[dict] = []
    for it in items:
        idx = next((i for i, m in enumerate(merged) if _same_story(m, it)), None)
        if idx is None:
            merged.append(dict(it))
            continue
        hit = merged[idx]
        keep = dict(hit if hit["cluster_count"] >= it["cluster_count"] else it)
        drop = it if keep["url"] == hit["url"] else hit
        keep["sources"] = keep["sources"] + [
            s for s in drop["sources"] if s not in keep["sources"]
        ]
        keep["cluster_urls"] = sorted({*keep["cluster_urls"], *drop["cluster_urls"]})
        keep["cluster_count"] = max(hit["cluster_count"], it["cluster_count"])
        if "general" in (hit["feed"], it["feed"]):
            keep["feed"] = "general"
        merged[idx] = keep
    return merged


def rank_candidates(items: list[dict], now_utc: datetime) -> list[dict]:
    """cluster_count × exp(−age/24h) 점수 내림차순, 상위 60건에 id 부여."""

    def score(it: dict) -> float:
        age_h = 0.0
        if it["published_at"]:
            pub = datetime.fromisoformat(it["published_at"])
            age_h = max((now_utc - pub).total_seconds() / 3600.0, 0.0)
        return it["cluster_count"] * math.exp(-age_h / DECAY_HOURS)

    ranked = sorted(items, key=score, reverse=True)[:CANDIDATE_LIMIT]
    return [{**it, "id": i} for i, it in enumerate(ranked)]


def curation_prompt(candidates: list[dict]) -> str:
    slim = [
        {"id": c["id"], "title": c["title"], "source": c["source"],
         "cluster_count": c["cluster_count"], "published_at": c["published_at"],
         "feed": c["feed"]}
        for c in candidates
    ]
    return (
        "다음은 오늘의 한국 뉴스 후보 목록이다. cluster_count는 같은 사건을 보도한 "
        "언론사 수(높을수록 큰 뉴스), feed는 출처 피드(general=주요뉴스, economy=경제)다.\n"
        "오늘 꼭 알아야 할 뉴스를 종합(정치·사회·국제) 5건, 경제·금융 5건 선정하라.\n"
        "규칙:\n"
        "- 반드시 id로만 지목하고 제목을 다시 쓰지 마라.\n"
        "- 같은 사건을 두 번 뽑지 마라 (섹션 간에도).\n"
        "- 각 항목에 왜 중요한지(파급력·시장 영향·대화 소재 가치)를 한국어 80자 이내 "
        "한 줄로 why에 써라.\n"
        '- JSON만 출력하라: {"general": [{"id": 0, "why": "..."}], "economy": [...]}\n\n'
        f"후보:\n{json.dumps(slim, ensure_ascii=False)}"
    )


def parse_curation(text: str) -> dict:
    """모델 응답에서 JSON 오브젝트 추출 (코드펜스 허용). 실패 시 ValueError."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("응답에 JSON 없음")
    return json.loads(m.group(0))


def validate_curation(out: dict, candidates: list[dict]) -> list[str]:
    """큐레이션 출력 검증 — 오류 문자열 리스트 (빈 리스트 = 통과)."""
    errors: list[str] = []
    ids = {c["id"] for c in candidates}
    seen: set = set()
    for section in ("general", "economy"):
        rows = out.get(section)
        if not isinstance(rows, list) or not rows:
            errors.append(f"{section} 섹션 없음/비어있음")
            continue
        if len(rows) > SECTION_SIZE:
            errors.append(f"{section} {len(rows)}건 > {SECTION_SIZE}건")
        for r in rows:
            rid = r.get("id") if isinstance(r, dict) else None
            if rid not in ids:
                errors.append(f"실존하지 않는 id {rid}")
            elif rid in seen:
                errors.append(f"중복 id {rid}")
            seen.add(rid)
            if isinstance(r, dict) and not str(r.get("why", "")).strip():
                errors.append(f"id {rid} why 비어있음")
    return errors


def fallback_selection(candidates: list[dict]) -> dict:
    """LLM 실패 시 규칙 점수순(candidates는 이미 정렬됨) feed별 상위 5건."""
    general = [c["id"] for c in candidates if c["feed"] == "general"][:SECTION_SIZE]
    economy = [c["id"] for c in candidates if c["feed"] == "economy"][:SECTION_SIZE]
    return {
        "general": [{"id": i, "why": ""} for i in general],
        "economy": [{"id": i, "why": ""} for i in economy],
    }


def build_payload(selection: dict, candidates: list[dict], curated: bool,
                  now_kst: datetime) -> dict:
    """발행 JSON 페이로드 — 스펙 §5 스키마. 빈 why는 키 생략, 없는 id는 건너뜀."""
    by_id = {c["id"]: c for c in candidates}

    def rows(section: str) -> list[dict]:
        out = []
        for r in selection.get(section, []):
            c = by_id.get(r.get("id"))
            if c is None:
                continue
            row = {"title": c["title"], "url": c["url"], "source": c["source"],
                   "published_at": c["published_at"],
                   "cluster_count": c["cluster_count"], "sources": c["sources"]}
            why = str(r.get("why", "")).strip()
            if why:
                row["why"] = why
            out.append(row)
        return out

    return {
        "as_of": now_kst.isoformat(),
        "edition": "morning" if now_kst.hour < 12 else "evening",
        "curated": curated,
        "sections": {"general": rows("general"), "economy": rows("economy")},
    }
