#!/usr/bin/env python
"""KR 뉴스 브리핑 발행 (EC2 배치 진입점) — 공용 로직은 server/module/news_publish.py.

run_pipeline.sh에서 build_insights 다음, send_briefing 전에 아침 09시·저녁 19시
실행된다. 주중 08~19시 매시 발행은 폴러 Lambda(app.news_poller)가 맡고, 이 스크립트는
폴러 장애 시의 이중화 + 텔레그램 톱3 직전 갱신 보장용으로 유지된다.
LLM 실패 시 규칙 랭킹 폴백으로 발행은 반드시 된다 (curated: false). 키가 없어도 동작한다.

사용: BRIEFING_ENV_FILE=... APP_DATA=... python scripts/build_news.py
스펙: docs/superpowers/specs/2026-08-14-kr-news-briefing-design.md
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))

from module import news_publish  # noqa: E402

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


def main() -> int:
    news_publish.run(api_key=_load_env_key())
    return 0


if __name__ == "__main__":
    sys.exit(main())
