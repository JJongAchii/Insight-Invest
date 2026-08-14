# KR 뉴스 브리핑 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Google News 한국판 RSS 클러스터 + Claude Haiku 큐레이션으로 "오늘의 중요 뉴스"를 하루 2회 발행하고, 홈 카드·텔레그램에 서빙한다.

**Architecture:** EC2 배치(`build_news.py`)가 RSS 수집→규칙 랭킹→Haiku 큐레이션→`APP_DATA/news_briefing.json` 발행. Lambda가 `GET /news/briefing`으로 서빙(강등 철학), 기존 `GET /news`에 KR 리전 추가로 장중 라이브 헤드라인. 스펙: `docs/superpowers/specs/2026-08-14-kr-news-briefing-design.md`

**Tech Stack:** FastAPI, pandas 불필요(순수 파이썬 모듈), httpx, anthropic SDK, s3fs, Next.js 14 + RTK Query

## Global Constraints

- 서빙은 어떤 실패에도 500을 내지 않는다 — `{"active": false}` 200 강등 (스펙 §9-3)
- LLM 실패는 발행을 막지 않는다 — 규칙 폴백, `curated: false` (스펙 §9-4)
- 기사 본문을 수집·저장하지 않는다 — 제목·링크·언론사·시각·클러스터 메타만 (스펙 §9-5)
- 장중 폴러 Lambda·IAM·EventBridge는 변경하지 않는다 (스펙 §9-2)
- 앱 평면 뉴스 파일은 `news_briefing.json` 1개뿐 (스펙 §9-1)
- API 키는 코드·레포에 넣지 않는다 (스펙 §9-7)
- 모델 `claude-haiku-4-5-20251001`, `max_tokens=1500`, `temperature=0.2` (스펙 §4)
- 상수: 후보 60건, 섹션당 5건, Jaccard 0.6, 신선도 감쇠 24h, 서빙 스테일 72h
- 서버 테스트: `cd server && /Users/achii/opt/anaconda3/envs/insight-invest-3-11/bin/python -m pytest tests/<파일> -v` — **출력을 파이프로 넘기지 않는다** (exit code 가림)
- 클라 검증: `cd client && npm run lint && npx tsc --noEmit`
- 커밋 메시지 말미: `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

---

### Task 1: 순수 로직 모듈 `news_briefing.py`

**Files:**
- Create: `server/module/news_briefing.py`
- Test: `server/tests/test_news_briefing_module.py`

**Interfaces (Produces — 이후 태스크가 그대로 사용):**
- `KST: timezone`, `CANDIDATE_LIMIT=60`, `SECTION_SIZE=5`
- `parse_feed(xml: str, feed: str) -> list[dict]` — item dict 키: `title,url,source,published_at,cluster_count,sources,cluster_urls,feed`
- `merge_stories(items: list[dict]) -> list[dict]`
- `rank_candidates(items: list[dict], now_utc: datetime) -> list[dict]` — 정렬·상위 60·`id`(int) 부여
- `curation_prompt(candidates) -> str`, `parse_curation(text) -> dict`
- `validate_curation(out, candidates) -> list[str]` (빈 리스트 = 통과)
- `fallback_selection(candidates) -> dict`
- `build_payload(selection, candidates, curated: bool, now_kst: datetime) -> dict`

- [ ] **Step 1: 실패하는 테스트 작성** — `server/tests/test_news_briefing_module.py`

```python
"""news_briefing 순수 로직 테스트 — 클러스터 파싱·병합·랭킹·LLM 검증·페이로드."""

from datetime import datetime, timedelta, timezone

from module import news_briefing as nb

# 실측(2026-08-14) Google News KR RSS 구조 재현 — description은 HTML 이스케이프됨
GENERAL_XML = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>
<item><title>대통령 개헌 제안 - 한겨레</title>
<link>https://news.google.com/rss/articles/AAA?oc=5</link>
<guid isPermaLink="false">AAA</guid>
<pubDate>Fri, 14 Aug 2026 03:00:00 GMT</pubDate>
<description>&lt;ol&gt;&lt;li&gt;&lt;a href="https://news.google.com/rss/articles/AAA?oc=5" target="_blank"&gt;대통령 개헌 제안&lt;/a&gt;&amp;nbsp;&amp;nbsp;&lt;font color="#6f6f6f"&gt;한겨레&lt;/font&gt;&lt;/li&gt;&lt;li&gt;&lt;a href="https://news.google.com/rss/articles/BBB?oc=5" target="_blank"&gt;[속보] 개헌 전격 제안&lt;/a&gt;&amp;nbsp;&amp;nbsp;&lt;font color="#6f6f6f"&gt;경향신문&lt;/font&gt;&lt;/li&gt;&lt;li&gt;&lt;a href="https://news.google.com/rss/articles/CCC?oc=5" target="_blank"&gt;개헌 제안 파장&lt;/a&gt;&amp;nbsp;&amp;nbsp;&lt;font color="#6f6f6f"&gt;문화일보&lt;/font&gt;&lt;/li&gt;&lt;/ol&gt;</description>
<source url="https://hani.co.kr">한겨레</source></item>
<item><title>단독 소식 - 매일경제</title>
<link>https://news.google.com/rss/articles/DDD?oc=5</link>
<pubDate>Fri, 14 Aug 2026 04:00:00 GMT</pubDate>
<description>&lt;a href="https://news.google.com/rss/articles/DDD?oc=5"&gt;단독 소식&lt;/a&gt;&amp;nbsp;&lt;font color="#6f6f6f"&gt;매일경제&lt;/font&gt;</description>
<source url="https://mk.co.kr">매일경제</source></item>
</channel></rss>"""

ECONOMY_XML = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>
<item><title>[속보] 개헌 전격 제안 - 경향신문</title>
<link>https://news.google.com/rss/articles/BBB?oc=5</link>
<pubDate>Fri, 14 Aug 2026 03:10:00 GMT</pubDate>
<description>&lt;a href="https://news.google.com/rss/articles/BBB?oc=5"&gt;[속보] 개헌 전격 제안&lt;/a&gt;&amp;nbsp;&lt;font color="#6f6f6f"&gt;경향신문&lt;/font&gt;</description>
<source url="https://khan.co.kr">경향신문</source></item>
<item><title>코스피 장중 7천 회복 반도체 강세 - 한국경제</title>
<link>https://news.google.com/rss/articles/EEE?oc=5</link>
<pubDate>Fri, 14 Aug 2026 05:00:00 GMT</pubDate>
<description>&lt;a href="https://news.google.com/rss/articles/EEE?oc=5"&gt;코스피 장중 7천 회복 반도체 강세&lt;/a&gt;&amp;nbsp;&lt;font color="#6f6f6f"&gt;한국경제&lt;/font&gt;</description>
<source url="https://hankyung.com">한국경제</source></item>
</channel></rss>"""

NOW = datetime(2026, 8, 14, 6, 0, 0, tzinfo=timezone.utc)


def _parsed():
    return nb.parse_feed(GENERAL_XML, "general") + nb.parse_feed(ECONOMY_XML, "economy")


def test_parse_cluster_item():
    items = nb.parse_feed(GENERAL_XML, "general")
    assert len(items) == 2
    a = items[0]
    assert a["title"] == "대통령 개헌 제안 - 한겨레"
    assert a["source"] == "한겨레"
    assert a["cluster_count"] == 3
    assert a["sources"] == ["한겨레", "경향신문", "문화일보"]
    assert "https://news.google.com/rss/articles/BBB?oc=5" in a["cluster_urls"]
    assert a["feed"] == "general"
    assert a["published_at"].startswith("2026-08-14T03:00:00")


def test_parse_single_item_cluster_is_one():
    items = nb.parse_feed(GENERAL_XML, "general")
    d = items[1]
    assert d["cluster_count"] == 1
    assert d["sources"] == ["매일경제"]


def test_merge_by_cluster_membership():
    # economy의 BBB 기사는 general AAA의 클러스터에 속함 → 병합, general 우선
    merged = nb.merge_stories(_parsed())
    urls = [m["url"] for m in merged]
    assert "https://news.google.com/rss/articles/BBB?oc=5" not in urls
    a = next(m for m in merged if m["url"].endswith("AAA?oc=5"))
    assert a["feed"] == "general"
    assert a["cluster_count"] == 3
    assert len(merged) == 3  # AAA(+BBB), DDD, EEE


def test_merge_by_title_jaccard():
    x = {"title": "삼성전자 2분기 영업이익 10조 돌파", "url": "u1", "source": "a",
         "published_at": None, "cluster_count": 1, "sources": ["a"],
         "cluster_urls": [], "feed": "economy"}
    y = {"title": "삼성전자 2분기 영업이익 10조 돌파 확정", "url": "u2", "source": "b",
         "published_at": None, "cluster_count": 2, "sources": ["b"],
         "cluster_urls": [], "feed": "economy"}
    merged = nb.merge_stories([x, y])
    assert len(merged) == 1
    assert merged[0]["cluster_count"] == 2
    assert set(merged[0]["sources"]) == {"a", "b"}


def test_rank_score_decay_and_ids():
    fresh = {"title": "새 소식", "url": "f", "source": "a", "cluster_count": 3,
             "published_at": NOW.isoformat(), "sources": [], "cluster_urls": [],
             "feed": "general"}
    old_big = {"title": "이틀 전 큰 뉴스", "url": "o", "source": "b", "cluster_count": 12,
               "published_at": (NOW - timedelta(hours=48)).isoformat(),
               "sources": [], "cluster_urls": [], "feed": "general"}
    ranked = nb.rank_candidates([old_big, fresh], NOW)
    # 12*exp(-2)=1.62 < 3*exp(0)=3 → fresh가 먼저
    assert ranked[0]["url"] == "f" and ranked[0]["id"] == 0
    assert ranked[1]["id"] == 1


def test_rank_caps_at_limit():
    items = [{"title": f"t{i}", "url": f"u{i}", "source": "s", "cluster_count": 1,
              "published_at": NOW.isoformat(), "sources": [], "cluster_urls": [],
              "feed": "general"} for i in range(80)]
    assert len(nb.rank_candidates(items, NOW)) == nb.CANDIDATE_LIMIT


def _candidates():
    return nb.rank_candidates(nb.merge_stories(_parsed()), NOW)


def test_parse_curation_accepts_code_fence():
    out = nb.parse_curation('```json\n{"general": [], "economy": []}\n```')
    assert out == {"general": [], "economy": []}


def test_validate_ok():
    c = _candidates()
    out = {"general": [{"id": c[0]["id"], "why": "중요함"}],
           "economy": [{"id": c[1]["id"], "why": "시장 영향"}]}
    assert nb.validate_curation(out, c) == []


def test_validate_catches_bad_output():
    c = _candidates()
    bad = {"general": [{"id": 999, "why": "x"}, {"id": c[0]["id"], "why": ""}],
           "economy": [{"id": c[0]["id"], "why": "dup"}]}
    errors = nb.validate_curation(bad, c)
    assert any("실존" in e for e in errors)
    assert any("why" in e for e in errors)
    assert any("중복" in e for e in errors)


def test_validate_section_missing_and_oversize():
    c = _candidates()
    errors = nb.validate_curation({"general": []}, c)
    assert any("general" in e for e in errors)
    assert any("economy" in e for e in errors)
    six = [{"id": x["id"], "why": "y"} for x in c[:3]] * 2
    errors2 = nb.validate_curation({"general": six, "economy": [
        {"id": c[0]["id"], "why": "y"}]}, c)
    assert any(">" in e or "건" in e for e in errors2)


def test_fallback_by_feed():
    c = _candidates()
    sel = nb.fallback_selection(c)
    gen_ids = {x["id"] for x in sel["general"]}
    eco_ids = {x["id"] for x in sel["economy"]}
    by_id = {x["id"]: x for x in c}
    assert all(by_id[i]["feed"] == "general" for i in gen_ids)
    assert all(by_id[i]["feed"] == "economy" for i in eco_ids)
    assert all(x["why"] == "" for x in sel["general"] + sel["economy"])


def test_build_payload_edition_and_why():
    c = _candidates()
    sel = {"general": [{"id": c[0]["id"], "why": "핵심"}],
           "economy": [{"id": c[1]["id"], "why": ""}, {"id": 999, "why": "없는 id"}]}
    morning = nb.build_payload(sel, c, True, datetime(2026, 8, 14, 9, 5, tzinfo=nb.KST))
    assert morning["edition"] == "morning" and morning["curated"] is True
    assert morning["sections"]["general"][0]["why"] == "핵심"
    assert "why" not in morning["sections"]["economy"][0]  # 빈 why는 생략
    assert len(morning["sections"]["economy"]) == 1  # 없는 id는 건너뜀
    row = morning["sections"]["general"][0]
    assert set(row) == {"title", "url", "source", "published_at",
                        "cluster_count", "sources", "why"}
    evening = nb.build_payload(sel, c, False, datetime(2026, 8, 14, 19, 5, tzinfo=nb.KST))
    assert evening["edition"] == "evening"
```

- [ ] **Step 2: 실패 확인**

Run: `cd server && /Users/achii/opt/anaconda3/envs/insight-invest-3-11/bin/python -m pytest tests/test_news_briefing_module.py -v`
Expected: FAIL — `No module named 'module.news_briefing'`

- [ ] **Step 3: 구현** — `server/module/news_briefing.py`

```python
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
        return parsedate_to_datetime(s)
    except (TypeError, ValueError):
        return None


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
```

- [ ] **Step 4: 통과 확인**

Run: `cd server && /Users/achii/opt/anaconda3/envs/insight-invest-3-11/bin/python -m pytest tests/test_news_briefing_module.py -v`
Expected: 12 PASS

- [ ] **Step 5: 커밋** — `feat(server): 뉴스 브리핑 순수 로직 — 클러스터 파싱·병합·랭킹·검증`

---

### Task 2: storage JSON 헬퍼 + 뉴스 KR 리전

**Files:**
- Modify: `server/datastore/storage.py` (json import + 함수 2개 추가)
- Modify: `server/module/news/config.py` (NewsRegion.KR, 국내 도메인)
- Modify: `server/module/news/service.py` (REGION_CONFIG)
- Modify: `server/app/schemas.py` (NewsRegion.KR)
- Test: `server/tests/test_news_json_storage.py`

**Interfaces:**
- Produces: `storage.read_json(*parts) -> dict`, `storage.write_json(obj, *parts) -> str` — Task 3·4가 사용
- Produces: `GET /news?region=kr` 동작 — Task 6 클라가 사용

- [ ] **Step 1: 실패하는 테스트** — `server/tests/test_news_json_storage.py`

```python
"""storage JSON 헬퍼 + 뉴스 KR 리전 설정 테스트."""

import pytest

from datastore import storage
from module.news.config import DOMAIN_TO_SOURCE, NewsRegion
from module.news.service import NewsService


@pytest.fixture
def app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    return tmp_path


def test_json_roundtrip(app_data):
    obj = {"as_of": "2026-08-14T09:00:00+09:00", "sections": {"general": [{"제목": "한글"}]}}
    target = storage.write_json(obj, "news_briefing.json")
    assert (app_data / "news_briefing.json").exists()
    assert "한글" in (app_data / "news_briefing.json").read_text()  # ensure_ascii=False
    assert storage.read_json("news_briefing.json") == obj
    assert target.endswith("news_briefing.json")


def test_kr_region_config():
    assert NewsRegion.KR.value == "kr"
    assert NewsService.REGION_CONFIG[NewsRegion.KR] == ("ko", "KR")
    assert DOMAIN_TO_SOURCE["yna.co.kr"] == "연합뉴스"
    assert DOMAIN_TO_SOURCE["hankyung.com"] == "한국경제"


def test_kr_region_schema():
    from app import schemas

    assert schemas.NewsRegion("kr") is schemas.NewsRegion.KR
```

- [ ] **Step 2: 실패 확인**

Run: `cd server && /Users/achii/opt/anaconda3/envs/insight-invest-3-11/bin/python -m pytest tests/test_news_json_storage.py -v`
Expected: FAIL — `read_json` 없음 / `KR` 없음

- [ ] **Step 3: 구현**

`storage.py` — 상단 `import json` 추가(기존 `import os` 옆), 파일 끝에:

```python
def read_json(*parts: str) -> dict:
    target = path(*parts)
    if target.startswith("s3://"):
        import s3fs

        with s3fs.S3FileSystem().open(target, "r") as f:
            return json.load(f)
    return json.loads(Path(target).read_text())


def write_json(obj: dict, *parts: str) -> str:
    target = path(*parts)
    body = json.dumps(obj, ensure_ascii=False)
    if target.startswith("s3://"):
        import s3fs

        with s3fs.S3FileSystem().open(target, "w") as f:
            f.write(body)
    else:
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_text(body)
    return target
```

`module/news/config.py` — `NewsRegion`에 `KR = "kr"` 추가, `REGION_QUERIES`에 `NewsRegion.KR: "한국 경제 시장"` 추가, `DOMAIN_TO_SOURCE`에 추가:

```python
    # 국내 언론사 (KR 라이브 헤드라인용)
    "yna.co.kr": "연합뉴스",
    "hankyung.com": "한국경제",
    "mk.co.kr": "매일경제",
    "chosun.com": "조선일보",
    "joongang.co.kr": "중앙일보",
    "donga.com": "동아일보",
    "hani.co.kr": "한겨레",
    "khan.co.kr": "경향신문",
    "kbs.co.kr": "KBS",
    "imbc.com": "MBC",
    "sbs.co.kr": "SBS",
    "ytn.co.kr": "YTN",
    "mt.co.kr": "머니투데이",
    "sedaily.com": "서울경제",
    "einfomax.co.kr": "연합인포맥스",
```

`module/news/service.py` — `REGION_CONFIG`에 `NewsRegion.KR: ("ko", "KR"),` 추가.

`app/schemas.py` — `NewsRegion`(class, line ~23)에 `KR = "kr"` 추가.

- [ ] **Step 4: 통과 확인**

Run: `cd server && /Users/achii/opt/anaconda3/envs/insight-invest-3-11/bin/python -m pytest tests/test_news_json_storage.py -v`
Expected: 3 PASS

- [ ] **Step 5: 커밋** — `feat(server): storage JSON 헬퍼 + 뉴스 KR 리전`

---

### Task 3: `GET /news/briefing` 라우터

**Files:**
- Modify: `server/app/routers/news.py`
- Test: `server/tests/test_news_briefing_api.py`

**Interfaces:**
- Consumes: `storage.read_json` (Task 2)
- Produces: `GET /news/briefing` → `{active, as_of, edition, curated, sections}` 또는 `{"active": false}` — Task 6 클라가 사용

- [ ] **Step 1: 실패하는 테스트** — `server/tests/test_news_briefing_api.py`

```python
"""GET /news/briefing 테스트 — 서빙·스테일 강등·500 금지."""

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from datastore import storage
from module.news_briefing import KST

client = TestClient(app)


@pytest.fixture
def app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    monkeypatch.delenv("API_TOKEN", raising=False)
    return tmp_path


def _payload(as_of=None):
    return {
        "as_of": (as_of or datetime.now(KST)).isoformat(),
        "edition": "morning",
        "curated": True,
        "sections": {
            "general": [{"title": "t", "url": "u", "source": "s",
                         "published_at": None, "cluster_count": 3,
                         "sources": ["s"], "why": "w"}],
            "economy": [],
        },
    }


def test_briefing_active(app_data):
    storage.write_json(_payload(), "news_briefing.json")
    r = client.get("/news/briefing")
    assert r.status_code == 200
    body = r.json()
    assert body["active"] is True
    assert body["edition"] == "morning"
    assert body["sections"]["general"][0]["why"] == "w"


def test_briefing_stale_72h_inactive(app_data):
    storage.write_json(_payload(datetime.now(KST) - timedelta(hours=80)),
                       "news_briefing.json")
    r = client.get("/news/briefing")
    assert r.status_code == 200
    assert r.json() == {"active": False}


def test_briefing_weekend_kept(app_data):
    # 금 19시 발행 → 월 09시(62h)까지 유지되어야 한다 (스펙 §6)
    storage.write_json(_payload(datetime.now(KST) - timedelta(hours=62)),
                       "news_briefing.json")
    assert client.get("/news/briefing").json()["active"] is True


def test_briefing_missing_file_inactive(app_data):
    r = client.get("/news/briefing")
    assert r.status_code == 200
    assert r.json() == {"active": False}


def test_briefing_corrupt_file_no_500(app_data):
    (app_data / "news_briefing.json").write_text("{망가진 json")
    r = client.get("/news/briefing")
    assert r.status_code == 200
    assert r.json() == {"active": False}
```

- [ ] **Step 2: 실패 확인**

Run: `cd server && /Users/achii/opt/anaconda3/envs/insight-invest-3-11/bin/python -m pytest tests/test_news_briefing_api.py -v`
Expected: FAIL — 404 (라우트 없음)

- [ ] **Step 3: 구현** — `routers/news.py`

임포트 추가: `from datetime import datetime, timedelta` 는 이미 있음 — `timezone` 추가, 그리고 `from datastore import storage`. 파일 끝(기존 `/cache` 라우트 뒤)에:

```python
STALE_HOURS = 72  # 금 19시 발행분이 월 09시(62h)까지 주말 내내 유지되도록


@router.get("/briefing")
async def get_news_briefing() -> dict:
    """오늘의 중요 뉴스 (EC2 배치 발행분) — 실패·스테일은 {"active": False} 200 강등."""
    try:
        data = storage.read_json("news_briefing.json")
        as_of = datetime.fromisoformat(data["as_of"])
        now = datetime.now(as_of.tzinfo or timezone.utc)
        if now - as_of > timedelta(hours=STALE_HOURS):
            return {"active": False}
        return {"active": True, **data}
    except Exception as e:
        logger.warning(f"news briefing 강등: {e}")
        return {"active": False}
```

주의: `datastore` 임포트는 파일 상단의 기존 `sys.path.insert` **다음**에 둔다 (다른 라우터와 동일 관례).

- [ ] **Step 4: 통과 확인 + 전체 스위트**

Run: `cd server && /Users/achii/opt/anaconda3/envs/insight-invest-3-11/bin/python -m pytest tests/ -v`
Expected: 신규 5 PASS 포함 전체 PASS

- [ ] **Step 5: 커밋** — `feat(server): GET /news/briefing — 72h 신선도, 강등 서빙`

---

### Task 4: 발행 스크립트 `build_news.py` + anthropic 의존성

**Files:**
- Create: `scripts/build_news.py`
- Modify: `server/requirements.txt`
- Test: `server/tests/test_build_news_script.py`

**Interfaces:**
- Consumes: `news_briefing` 모듈 전부(Task 1), `storage.write_json`(Task 2)
- Produces: `APP_DATA/news_briefing.json` — Task 3 라우터·Task 5 텔레그램이 읽음
- `_curate(candidates, _client=None) -> tuple[dict, bool]` — 테스트가 fake client 주입

- [ ] **Step 1: 실패하는 테스트** — `server/tests/test_build_news_script.py`

```python
"""build_news.py 스크립트 테스트 — 폴백 발행·fake LLM 큐레이션·재시도."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from datastore import storage

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_news.py"
spec = importlib.util.spec_from_file_location("build_news", SCRIPT)
bn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bn)


@pytest.fixture
def app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # 로컬 ~/Quant/quant-data/.env에 실키가 있어도 절대 읽지 않도록
    # 존재하지 않는 경로로 고정 — 없으면 no-key 폴백 경로가 결정적으로 탄다.
    monkeypatch.setenv("BRIEFING_ENV_FILE", str(tmp_path / "no-such.env"))
    return tmp_path


def _items(n_general=6, n_economy=6):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    out = []
    for i in range(n_general):
        out.append({"title": f"종합 {i}", "url": f"g{i}", "source": "한겨레",
                    "published_at": now, "cluster_count": 5 - (i % 5),
                    "sources": ["한겨레"], "cluster_urls": [], "feed": "general"})
    for i in range(n_economy):
        out.append({"title": f"경제 {i}", "url": f"e{i}", "source": "한국경제",
                    "published_at": now, "cluster_count": 5 - (i % 5),
                    "sources": ["한국경제"], "cluster_urls": [], "feed": "economy"})
    return out


class FakeClient:
    def __init__(self, texts):
        self.calls = 0
        outer = self

        class _Messages:
            def create(self, **kwargs):
                outer.calls += 1
                text = texts[min(outer.calls - 1, len(texts) - 1)]
                return SimpleNamespace(content=[SimpleNamespace(text=text)])

        self.messages = _Messages()


def test_no_key_falls_back(app_data, monkeypatch):
    monkeypatch.setattr(bn, "_fetch_feeds", lambda: _items())
    assert bn.main() == 0
    data = storage.read_json("news_briefing.json")
    assert data["curated"] is False
    assert len(data["sections"]["general"]) == 5
    assert len(data["sections"]["economy"]) == 5
    assert all("why" not in r for r in data["sections"]["general"])


def test_fake_llm_curates(app_data):
    items = _items()
    from datetime import datetime, timezone
    from module import news_briefing as nb
    cand = nb.rank_candidates(nb.merge_stories(items), datetime.now(timezone.utc))
    gen = [c["id"] for c in cand if c["feed"] == "general"][:5]
    eco = [c["id"] for c in cand if c["feed"] == "economy"][:5]
    good = json.dumps({
        "general": [{"id": i, "why": f"이유 {i}"} for i in gen],
        "economy": [{"id": i, "why": f"이유 {i}"} for i in eco],
    })
    sel, curated = bn._curate(cand, _client=FakeClient([good]))
    assert curated is True
    assert len(sel["general"]) == 5


def test_bad_then_good_retries_once(app_data):
    items = _items()
    from datetime import datetime, timezone
    from module import news_briefing as nb
    cand = nb.rank_candidates(nb.merge_stories(items), datetime.now(timezone.utc))
    gen = [c["id"] for c in cand if c["feed"] == "general"][:5]
    eco = [c["id"] for c in cand if c["feed"] == "economy"][:5]
    bad = json.dumps({"general": [{"id": 9999, "why": "x"}], "economy": []})
    good = json.dumps({
        "general": [{"id": i, "why": "이유"} for i in gen],
        "economy": [{"id": i, "why": "이유"} for i in eco],
    })
    fake = FakeClient([bad, good])
    sel, curated = bn._curate(cand, _client=fake)
    assert curated is True and fake.calls == 2


def test_bad_twice_falls_back(app_data):
    items = _items()
    from datetime import datetime, timezone
    from module import news_briefing as nb
    cand = nb.rank_candidates(nb.merge_stories(items), datetime.now(timezone.utc))
    bad = json.dumps({"general": [{"id": 9999, "why": "x"}], "economy": []})
    fake = FakeClient([bad, bad])
    sel, curated = bn._curate(cand, _client=fake)
    assert curated is False and fake.calls == 2


def test_empty_feeds_skip_publish(app_data, monkeypatch):
    monkeypatch.setattr(bn, "_fetch_feeds", lambda: [])
    assert bn.main() == 0
    assert not (app_data / "news_briefing.json").exists()
```

- [ ] **Step 2: 실패 확인**

Run: `cd server && /Users/achii/opt/anaconda3/envs/insight-invest-3-11/bin/python -m pytest tests/test_build_news_script.py -v`
Expected: FAIL — 스크립트 없음

- [ ] **Step 3: 구현** — `scripts/build_news.py`

```python
#!/usr/bin/env python
"""KR 뉴스 브리핑 발행 — Google News RSS 수집 → Haiku 큐레이션 → APP_DATA JSON.

EC2 파이프라인(run_pipeline.sh)에서 build_insights 다음, send_briefing 전에
아침 09시·저녁 19시 실행된다. LLM 실패 시 규칙 랭킹 폴백으로 발행은 반드시
된다 (curated: false). 키가 없어도 동작한다.

사용: BRIEFING_ENV_FILE=... APP_DATA=... python scripts/build_news.py
스펙: docs/superpowers/specs/2026-08-14-kr-news-briefing-design.md
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))

from datastore import storage  # noqa: E402
from module import news_briefing as nb  # noqa: E402

FEEDS = [
    ("general", "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko"),
    ("economy",
     "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko"),
]
MODEL = "claude-haiku-4-5-20251001"
DEFAULT_ENV_FILE = str(Path.home() / "Quant" / "quant-data" / ".env")


def _load_env_key() -> str | None:
    """ANTHROPIC_API_KEY — 환경변수 우선, 없으면 BRIEFING_ENV_FILE에서."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    envf = os.environ.get("BRIEFING_ENV_FILE", DEFAULT_ENV_FILE)
    p = Path(envf)
    if not p.exists():
        return None
    for line in p.read_text().splitlines():
        line = line.strip()
        if line.startswith("ANTHROPIC_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None


def _fetch_feeds() -> list:
    items = []
    for feed, url in FEEDS:
        r = httpx.get(url, timeout=20, follow_redirects=True)
        r.raise_for_status()
        items.extend(nb.parse_feed(r.text, feed))
    return items


def _curate(candidates: list, _client=None) -> tuple:
    """(selection, curated) — LLM 큐레이션, 검증 실패 1회 재시도, 그래도 안 되면 폴백."""
    if _client is None:
        key = _load_env_key()
        if not key:
            print("[warn] ANTHROPIC_API_KEY 없음 — 규칙 폴백")
            return nb.fallback_selection(candidates), False
        import anthropic

        _client = anthropic.Anthropic(api_key=key)
    prompt = nb.curation_prompt(candidates)
    for attempt in (1, 2):
        try:
            msg = _client.messages.create(
                model=MODEL, max_tokens=1500, temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            out = nb.parse_curation(msg.content[0].text)
            errors = nb.validate_curation(out, candidates)
            if not errors:
                return out, True
            print(f"[warn] 큐레이션 검증 실패(시도 {attempt}): {errors}")
            prompt = prompt + "\n\n직전 응답은 검증에 실패했다. 오류를 고쳐 다시 JSON만 출력하라: " + "; ".join(errors)
        except Exception as e:
            print(f"[warn] LLM 호출 실패(시도 {attempt}): {e}")
    return nb.fallback_selection(candidates), False


def main() -> int:
    items = _fetch_feeds()
    merged = nb.merge_stories(items)
    candidates = nb.rank_candidates(merged, datetime.now(timezone.utc))
    if not candidates:
        print("[warn] 후보 0건 — 발행 생략")
        return 0
    selection, curated = _curate(candidates)
    payload = nb.build_payload(selection, candidates, curated, datetime.now(nb.KST))
    storage.write_json(payload, "news_briefing.json")
    n = sum(len(v) for v in payload["sections"].values())
    print(f"[ok] news_briefing.json 발행 — {n}건, curated={curated}, "
          f"edition={payload['edition']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`server/requirements.txt` — `httpx>=0.27` 줄 아래에 추가:

```
anthropic>=0.40          # news briefing 큐레이션 (EC2 배치 — scripts/build_news.py)
```

- [ ] **Step 4: 통과 확인**

Run: `cd server && /Users/achii/opt/anaconda3/envs/insight-invest-3-11/bin/python -m pytest tests/test_build_news_script.py -v`
Expected: 5 PASS (anthropic 미설치 환경에서도 통과해야 함 — no-key/fake-client 경로만 탄다)

- [ ] **Step 5: 커밋** — `feat(scripts): build_news 발행 스크립트 + anthropic 의존성`

---

### Task 5: 텔레그램 브리핑에 뉴스 톱3

**Files:**
- Modify: `scripts/send_briefing.py`

**Interfaces:**
- Consumes: `storage.read_json`(Task 2), `news_briefing.json` 스키마(Task 1 `build_payload`)

- [ ] **Step 1: 구현** — `_section_strategies`와 `_section_summary` 사이에 추가:

```python
def _section_news() -> str | None:
    """오늘의 뉴스 톱3 — build_news가 직전에 발행한 news_briefing.json 재사용."""
    data = storage.read_json("news_briefing.json")
    rows = (data.get("sections") or {}).get("general") or []
    lines = [f"· {_esc(r['title'])}" for r in rows[:3] if r.get("title")]
    if not lines:
        return None
    return "<b>📰 오늘의 뉴스</b>\n" + "\n".join(lines)
```

`compose_message()`의 섹션 리스트에서 `("strategies", _section_strategies),`와 `("summary", _section_summary),` 사이에 한 줄 추가:

```python
        ("news", _section_news),
```

(섹션 실패는 기존 try/except가 흡수 — 파일 없으면 자동 생략)

- [ ] **Step 2: 전체 스위트 확인**

Run: `cd server && /Users/achii/opt/anaconda3/envs/insight-invest-3-11/bin/python -m pytest tests/ -v`
Expected: 전체 PASS (send_briefing 전용 테스트는 없음 — compose는 EC2 실행으로 검증)

- [ ] **Step 3: 커밋** — `feat(scripts): 텔레그램 브리핑에 오늘의 뉴스 톱3`

---

### Task 6: 클라이언트 — NewsBriefingCard

**Files:**
- Modify: `client/src/state/api.ts`
- Create: `client/src/app/home/NewsBriefingCard.tsx`
- Modify: `client/src/app/home/page.tsx`
- Delete: `client/src/app/home/NewsCompactList.tsx`

**Interfaces:**
- Consumes: `GET /news/briefing`(Task 3), `GET /news?region=kr`(Task 2)

- [ ] **Step 1: api.ts 타입·엔드포인트**

`NewsRegion` 타입(line ~12)에 `"kr"` 추가:

```typescript
export type NewsRegion = "us" | "asia" | "europe" | "global" | "all" | "kr";
```

`NewsQueryParams` 인터페이스 아래에 추가:

```typescript
export interface NewsBriefingItem {
  title: string;
  url: string;
  source: string;
  published_at: string | null;
  cluster_count: number;
  sources: string[];
  why?: string;
}

export interface NewsBriefingResponse {
  active: boolean;
  as_of?: string;
  edition?: "morning" | "evening";
  curated?: boolean;
  sections?: { general: NewsBriefingItem[]; economy: NewsBriefingItem[] };
}
```

`fetchNews` 엔드포인트 아래에 추가:

```typescript
    fetchNewsBriefing: builder.query<NewsBriefingResponse, void>({
      query: () => "/news/briefing",
      providesTags: ["News"],
    }),
```

하단 훅 export 목록(`useFetchNewsQuery` 옆)에 `useFetchNewsBriefingQuery` 추가.

- [ ] **Step 2: NewsBriefingCard 컴포넌트** — `client/src/app/home/NewsBriefingCard.tsx`

```tsx
"use client";

import React, { useState } from "react";
import { IoChevronDown, IoOpenOutline, IoNewspaperOutline } from "react-icons/io5";

import {
  useFetchNewsBriefingQuery,
  useFetchNewsQuery,
  NewsBriefingItem,
} from "@/state/api";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import LoadingState from "@/components/ui/LoadingState";

// 언론사 칩 색 (theme-aware tint — NewsCompactList 관례 계승, 국내 언론사판)
const SOURCE_COLORS: Record<string, { bg: string; text: string }> = {
  연합뉴스: { bg: "bg-blue-500/10", text: "text-blue-400" },
  한국경제: { bg: "bg-sky-500/10", text: "text-sky-400" },
  매일경제: { bg: "bg-amber-500/10", text: "text-amber-400" },
  조선일보: { bg: "bg-slate-500/10", text: "text-slate-400" },
  중앙일보: { bg: "bg-indigo-500/10", text: "text-indigo-400" },
  동아일보: { bg: "bg-teal-500/10", text: "text-teal-400" },
  한겨레: { bg: "bg-emerald-500/10", text: "text-emerald-400" },
  경향신문: { bg: "bg-lime-500/10", text: "text-lime-400" },
  KBS: { bg: "bg-red-500/10", text: "text-red-400" },
  MBC: { bg: "bg-rose-500/10", text: "text-rose-400" },
  SBS: { bg: "bg-orange-500/10", text: "text-orange-400" },
  YTN: { bg: "bg-cyan-500/10", text: "text-cyan-400" },
  머니투데이: { bg: "bg-violet-500/10", text: "text-violet-400" },
  서울경제: { bg: "bg-fuchsia-500/10", text: "text-fuchsia-400" },
  default: { bg: "bg-raised", text: "text-ink-secondary" },
};

const getSourceColors = (source: string) => {
  for (const [name, colors] of Object.entries(SOURCE_COLORS)) {
    if (name !== "default" && source.includes(name)) return colors;
  }
  return SOURCE_COLORS.default;
};

const EDITION_LABEL: Record<string, string> = {
  morning: "아침판",
  evening: "저녁판",
};

const formatAsOf = (iso?: string): string => {
  if (!iso) return "";
  const d = new Date(iso);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  return `${mm}/${dd} ${hh}:${mi}`;
};

const BriefingRow: React.FC<{ item: NewsBriefingItem }> = ({ item }) => {
  const colors = getSourceColors(item.source);
  return (
    <li>
      <a
        href={item.url}
        target="_blank"
        rel="noopener noreferrer"
        className="group flex flex-col gap-1 py-3 px-1 rounded-lg hover:bg-raised transition-colors"
      >
        <div className="flex items-center gap-2">
          <span
            className={`shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-md ${colors.bg} ${colors.text}`}
          >
            {item.source || "뉴스"}
          </span>
          <span className="flex-1 min-w-0 text-sm text-ink truncate group-hover:text-primary-400 transition-colors">
            {item.title}
          </span>
          {item.cluster_count >= 3 && (
            <span className="shrink-0 flex items-center gap-1 text-[10px] text-ink-muted">
              <IoNewspaperOutline className="w-3 h-3" aria-hidden />
              {item.cluster_count}개 언론사
            </span>
          )}
          <IoOpenOutline
            className="shrink-0 w-4 h-4 text-ink-muted group-hover:text-primary-400 transition-colors"
            aria-hidden
          />
        </div>
        {item.why && (
          <p className="text-xs text-ink-muted pl-1 line-clamp-2">{item.why}</p>
        )}
      </a>
    </li>
  );
};

/** 라이브 최신 헤드라인 (기존 /news 라우트, KR) — 접었을 땐 fetch 안 함 */
const LiveHeadlines: React.FC<{ open: boolean }> = ({ open }) => {
  const { data, isLoading } = useFetchNewsQuery(
    { category: "topnews", region: "kr", limit: 5 },
    { skip: !open },
  );
  if (!open) return null;
  if (isLoading || !data) return <LoadingState label="헤드라인을 불러오는 중..." />;
  const articles = data.articles.slice(0, 5);
  if (articles.length === 0) return <EmptyState title="헤드라인 없음" />;
  return (
    <ul className="flex flex-col divide-y divide-edge">
      {articles.map((a) => {
        const colors = getSourceColors(a.source);
        return (
          <li key={a.id}>
            <a
              href={a.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-center gap-2 py-2 px-1 rounded-lg hover:bg-raised transition-colors"
            >
              <span
                className={`shrink-0 text-[10px] font-bold px-2 py-0.5 rounded-md ${colors.bg} ${colors.text}`}
              >
                {a.source}
              </span>
              <span className="flex-1 min-w-0 text-sm text-ink truncate group-hover:text-primary-400 transition-colors">
                {a.title}
              </span>
            </a>
          </li>
        );
      })}
    </ul>
  );
};

/** 홈 카드: 큐레이션된 오늘의 중요 뉴스 + 접이식 라이브 헤드라인. */
const NewsBriefingCard: React.FC = () => {
  const { data, isLoading } = useFetchNewsBriefingQuery();
  const [tab, setTab] = useState<"general" | "economy">("general");
  const [showLive, setShowLive] = useState(false);

  const sections = data?.active ? data.sections : undefined;
  const active = Boolean(sections);
  const rows = sections ? sections[tab] : [];

  return (
    <Card title="오늘의 중요 뉴스">
      {isLoading ? (
        <LoadingState label="뉴스를 불러오는 중..." />
      ) : (
        <div className="flex flex-col gap-2">
          {active ? (
            <>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-ink-muted">
                  {EDITION_LABEL[data?.edition ?? ""] ?? ""} {formatAsOf(data?.as_of)}
                </span>
                <div className="ml-auto flex gap-1">
                  {(["general", "economy"] as const).map((s) => (
                    <button
                      key={s}
                      onClick={() => setTab(s)}
                      className={`text-xs px-2.5 py-1 rounded-md transition-colors ${
                        tab === s
                          ? "bg-primary-500/15 text-primary-400 font-semibold"
                          : "text-ink-muted hover:bg-raised"
                      }`}
                    >
                      {s === "general" ? "종합" : "경제"}
                    </button>
                  ))}
                </div>
              </div>
              {rows.length === 0 ? (
                <EmptyState title="선정된 뉴스 없음" />
              ) : (
                <ul className="flex flex-col divide-y divide-edge">
                  {rows.map((item) => (
                    <BriefingRow key={item.url} item={item} />
                  ))}
                </ul>
              )}
            </>
          ) : (
            <p className="text-xs text-ink-muted px-1">
              아직 오늘의 브리핑이 없습니다 — 최신 헤드라인을 확인하세요.
            </p>
          )}
          <button
            onClick={() => setShowLive((v) => !v)}
            className="flex items-center gap-1 text-xs text-ink-muted hover:text-ink transition-colors pt-1"
          >
            <IoChevronDown
              className={`w-3.5 h-3.5 transition-transform ${showLive ? "rotate-180" : ""}`}
              aria-hidden
            />
            최신 헤드라인
          </button>
          <LiveHeadlines open={showLive || !active} />
        </div>
      )}
    </Card>
  );
};

export default NewsBriefingCard;
```

주의: briefing이 비활성일 때는 라이브 헤드라인을 **자동으로 펼친다**(`open={showLive || !active}`) — 카드가 빈 껍데기가 되지 않게.

- [ ] **Step 3: page.tsx 교체 + 구파일 삭제**

`client/src/app/home/page.tsx`에서 `import NewsCompactList from "./NewsCompactList";` → `import NewsBriefingCard from "./NewsBriefingCard";`, `<NewsCompactList />` → `<NewsBriefingCard />`. 그 뒤 `git rm client/src/app/home/NewsCompactList.tsx` (다른 참조가 없는지 grep으로 확인 후).

- [ ] **Step 4: 검증**

Run: `cd client && npm run lint && npx tsc --noEmit`
Expected: 오류 0

- [ ] **Step 5: 커밋** — `feat(client): 오늘의 중요 뉴스 카드 — 종합/경제 탭 + 라이브 헤드라인`

---

### Task 7: EC2 파이프라인 훅 (quant-data 레포)

**Files:**
- Modify: `/Users/achii/Quant/quant-data/scripts/server/run_pipeline.sh` (별도 레포 — worktree 밖)

**주의:** 이 태스크는 Insight-Invest worktree가 아니라 **quant-data 레포 main**에 직접 커밋한다. **push는 하지 않는다** — Insight-Invest가 main에 머지·push된 뒤에 컨트롤러가 함께 push한다 (EC2가 스크립트 없는 상태에서 훅만 먼저 받으면 매일 warn이 나므로; 순서가 어긋나도 `|| echo` 덕에 파이프라인은 안 죽는다).

- [ ] **Step 1: 훅 추가** — `build_insights.py` 줄(152행 부근)과 `send_briefing.py` 줄 사이에:

```bash
  BRIEFING_ENV_FILE=$ENVF $IIPY $BASE/Insight-Invest/scripts/build_news.py || echo "[warn] build_news 실패"
```

(`QDATA_LAKE` 불필요 — 뉴스는 레이크를 읽지 않는다. `APP_DATA`는 storage.py 기본값 사용. **send_briefing보다 먼저** 와야 텔레그램 톱3가 최신 발행분을 읽는다.)

- [ ] **Step 2: 문법 확인**

Run: `bash -n /Users/achii/Quant/quant-data/scripts/server/run_pipeline.sh`
Expected: 출력 없음 (문법 OK)

- [ ] **Step 3: 커밋 (push 금지)** — quant-data에서 `chore(server): 파이프라인에 build_news 스텝 — 뉴스 브리핑 발행`

---

## 머지 후 검증 체크리스트 (태스크 아님 — 컨트롤러 수행)

1. Insight-Invest main 머지 → push (deploy-api + Vercel 자동) → quant-data push
2. `GET /news/briefing` → 첫 배치 전이므로 `{"active": false}` 확인 (강등 정상)
3. 오늘 19:00 EC2 사이클 후: `active: true`, `curated: true`, 섹션 5+5, why 존재 확인
4. 텔레그램 브리핑에 `📰 오늘의 뉴스` 섹션 확인
5. 홈 카드: 저녁판 배지·탭·클러스터 배지·라이브 헤드라인 확인
6. (선택) EC2 수동 1회 실행으로 즉시 검증: `ssh` 후 `BRIEFING_ENV_FILE=~/Quant/quant-data/.env python scripts/build_news.py` — 실 API 과금 1회
