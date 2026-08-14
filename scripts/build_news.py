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
        try:
            import anthropic

            _client = anthropic.Anthropic(api_key=key)
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
