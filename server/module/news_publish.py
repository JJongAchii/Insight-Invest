"""뉴스 브리핑 발행 공용 오케스트레이션 — RSS 수집 → Haiku 큐레이션 → APP_DATA 발행.

두 실행 주체가 공유한다:
- EC2 배치 `scripts/build_news.py` (09·19시, 키는 BRIEFING_ENV_FILE에서)
- 시간별 폴러 Lambda `app.news_poller.handler` (주중 08~19시 KST 매시, 키는 env)

순수 로직(파싱·병합·랭킹·검증·페이로드)은 `module.news_briefing`에 있고,
여기는 I/O(fetch·LLM 호출·S3 쓰기)만 엮는다.
LLM·SDK·키 어떤 실패도 발행을 막지 않는다 — 규칙 폴백 `curated=False` (스펙 §9-4).
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
MODEL = "claude-haiku-4-5-20251001"


def fetch_feeds() -> list:
    """두 피드 수집·파싱. KR URL은 302 정규화 리다이렉트라 follow_redirects 필수."""
    items = []
    for feed, url in FEEDS:
        r = httpx.get(url, timeout=20, follow_redirects=True)
        r.raise_for_status()
        items.extend(nb.parse_feed(r.text, feed))
    return items


def curate(candidates: list, api_key: str | None = None, _client=None) -> tuple:
    """(selection, curated) — LLM 큐레이션, 검증 실패 1회 재시도, 그래도 안 되면 폴백."""
    if _client is None:
        if not api_key:
            print("[warn] ANTHROPIC_API_KEY 없음 — 규칙 폴백")
            return nb.fallback_selection(candidates), False
        try:
            import anthropic

            _client = anthropic.Anthropic(api_key=api_key)
        except Exception as e:
            print(f"[warn] anthropic 클라이언트 생성 실패 — 규칙 폴백: {e}")
            return nb.fallback_selection(candidates), False
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


def run(api_key: str | None = None, _client=None) -> dict | None:
    """수집→큐레이션→발행 1회. 후보 0건이면 발행 생략(None), 아니면 발행한 payload."""
    items = fetch_feeds()
    merged = nb.merge_stories(items)
    candidates = nb.rank_candidates(merged, datetime.now(timezone.utc))
    if not candidates:
        print("[warn] 후보 0건 — 발행 생략")
        return None
    selection, curated = curate(candidates, api_key=api_key, _client=_client)
    payload = nb.build_payload(selection, candidates, curated, datetime.now(nb.KST))
    storage.write_json(payload, "news_briefing.json")
    n = sum(len(v) for v in payload["sections"].values())
    print(f"[ok] news_briefing.json 발행 — {n}건, curated={curated}, "
          f"edition={payload['edition']}")
    return payload
