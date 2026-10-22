"""뉴스 브리핑 발행 공용 오케스트레이션 — RSS 수집 → 규칙 랭킹 → APP_DATA 발행.

두 실행 주체가 공유한다:
- EC2 배치 `scripts/build_news.py` (09·19시)
- 시간별 폴러 Lambda `app.news_poller.handler` (주중 08~19시 KST 매시)

순수 로직(파싱·병합·랭킹·선정·페이로드)은 `module.news_briefing`에 있고,
여기는 I/O(fetch·S3 쓰기)만 엮는다. AI(LLM) 큐레이션은 쓰지 않는다 — 2026-10-23 사용자
결정으로 Anthropic API 호출을 제거했다. API 키가 환경에 남아 있어도 읽지 않으며, 발행은
늘 규칙 랭킹 `curated=False` 다.
스펙: docs/superpowers/specs/2026-08-14-kr-news-briefing-design.md
"""

from datetime import datetime, timezone

import httpx

from datastore import storage
from module import news_briefing as nb

FEEDS = [
    ("general", "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko"),
    ("economy",
     "https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=ko&gl=KR&ceid=KR:ko"),
]


def fetch_feeds() -> list:
    """두 피드 수집·파싱. KR URL은 302 정규화 리다이렉트라 follow_redirects 필수."""
    items = []
    for feed, url in FEEDS:
        r = httpx.get(url, timeout=20, follow_redirects=True)
        r.raise_for_status()
        items.extend(nb.parse_feed(r.text, feed))
    return items


def run() -> dict | None:
    """수집→규칙 선정→발행 1회. 후보 0건이면 발행 생략(None), 아니면 발행한 payload."""
    items = fetch_feeds()
    merged = nb.merge_stories(items)
    candidates = nb.rank_candidates(merged, datetime.now(timezone.utc))
    if not candidates:
        print("[warn] 후보 0건 — 발행 생략")
        return None
    selection, curated = nb.fallback_selection(candidates), False
    payload = nb.build_payload(selection, candidates, curated, datetime.now(nb.KST))
    storage.write_json(payload, "news_briefing.json")
    n = sum(len(v) for v in payload["sections"].values())
    print(f"[ok] news_briefing.json 발행 — {n}건, curated={curated}, "
          f"edition={payload['edition']}")
    return payload
