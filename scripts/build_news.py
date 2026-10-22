#!/usr/bin/env python
"""KR 뉴스 브리핑 발행 (EC2 배치 진입점) — 공용 로직은 server/module/news_publish.py.

run_pipeline.sh에서 build_insights 다음, send_briefing 전에 아침 09시·저녁 19시
실행된다. 주중 08~19시 매시 발행은 폴러 Lambda(app.news_poller)가 맡고, 이 스크립트는
폴러 장애 시의 이중화 + 텔레그램 톱3 직전 갱신 보장용으로 유지된다.
규칙 랭킹으로만 발행한다 (curated: false) — AI 큐레이션·API 키는 쓰지 않는다 (2026-10-23).

사용: APP_DATA=... python scripts/build_news.py
스펙: docs/superpowers/specs/2026-08-14-kr-news-briefing-design.md
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))

from module import news_publish  # noqa: E402


def main() -> int:
    news_publish.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
