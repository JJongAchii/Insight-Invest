"""시간별 뉴스 브리핑 폴러 Lambda — 주중 08~19시 KST 매시 정각 (EventBridge cron 2룰).

EC2 배치(09·19시)와 같은 파일(`APP_DATA/news_briefing.json`)을 같은 공용 로직
(`module.news_publish`)으로 발행한다 — EC2 발행은 폴러 장애 시의 이중화로 유지.
API 키는 Lambda env `ANTHROPIC_API_KEY` (CFN NoEcho 파라미터 ← GitHub secret).
키·LLM 실패는 규칙 폴백으로 강등되고(curated=false), 그 외 예외는 전파한다 —
강등 서빙은 라우터 몫이고, 폴러 실패 시 직전 발행분이 72h까지 유지된다.
"""

import logging
import os

from module import news_publish

logging.basicConfig(level=logging.INFO)


def handler(event, context):
    payload = news_publish.run(api_key=os.environ.get("ANTHROPIC_API_KEY") or None)
    if payload is None:
        return {"status": "no-candidates"}
    return {
        "status": "ok",
        "curated": payload["curated"],
        "edition": payload["edition"],
        "as_of": payload["as_of"],
        "items": sum(len(v) for v in payload["sections"].values()),
    }
