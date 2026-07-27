"""Claude Opus 5 3콜 오케스트레이션 — bull ∥ bear → judge.

bull과 bear는 서로의 출력을 보지 못한다. 한 컨텍스트에서 양쪽을 쓰게 하면
모델이 균형을 맞춰버려 "강세 3개, 약세 3개, 결론은 중립" 같은 무해하고
쓸모없는 출력이 나온다. 대립은 구조로 만들어야 한다.
"""

import json
import logging

from module.brief.schema import BULL_BEAR_SCHEMA, JUDGE_SCHEMA, enforce_lengths, validate_points

logger = logging.getLogger(__name__)

MODEL = "claude-opus-5"
MAX_TOKENS = 8000

# Claude Opus 5: $5 in / $25 out per MTok. 캐시 쓰기 1.25×, 캐시 읽기 0.1×.
PRICE_PER_TOKEN = {
    "input": 5.0 / 1_000_000,
    "output": 25.0 / 1_000_000,
    "cache_write": 6.25 / 1_000_000,
    "cache_read": 0.5 / 1_000_000,
}

SYSTEM_RULES = """너는 한국 주식 시장의 리서치 애널리스트다.

절대 규칙:
1. 주어진 evidence pack 안의 사실만 사용한다. 종목·산업에 대해 네가 따로 알고 있는
   지식은 인용하지 않는다. 학습 시점의 정보는 낡았고 사용자가 검증할 수 없다.
2. 숫자를 다시 말하지 않는다. 사용자는 대시보드에서 숫자를 이미 봤다.
   숫자는 그것이 무엇을 함의하는지 말할 때 근거로만 인용한다.
3. base_rates가 있으면 반드시 인용한다 — 표본 수, 승률, 중앙값을 함께.
   표본이 없으면 "표본 없음"이라고 명시한다.
4. 모든 주장에 evidence 경로를 단다. evidence pack의 실제 키 경로여야 한다
   (예: "flows.frgn.streak", "base_rates.frgn_streak10.h20").
   근거를 댈 수 없는 주장은 출력하지 않는다.
5. 모든 논거에 breaks_if를 단다 — 무엇이 관찰되면 이 논거가 무효가 되는가.
   관찰 가능한 조건이어야 한다.
6. 없으면 없다고 한다. 억지 논거를 만들지 말고 what_i_could_not_argue에 적는다.
   빈칸도 정보다."""

BULL_ROLE = """이 종목을 매수하거나 계속 보유해야 할 이유만 찾아라.
균형을 잡는 것은 네 일이 아니다 — 반대편은 다른 분석가가 독립적으로 맡는다.
네 임무는 강세 논거의 최선 버전을 만드는 것이다."""

BEAR_ROLE = """이 종목을 매도하거나 회피해야 할 이유만 찾아라.
균형을 잡는 것은 네 일이 아니다 — 반대편은 다른 분석가가 독립적으로 맡는다.
네 임무는 약세 논거의 최선 버전을 만드는 것이다."""

JUDGE_ROLE = """강세·약세 분석가의 논거를 모두 받았다.

점수를 매기지 마라. 매수/매도 판정을 내리지 마라.
두 논거가 어디서 갈리는지 짚어라. 같은 사실을 양쪽이 다르게 읽고 있다면 그게 핵심이다.
그리고 무엇이 관찰되면 결판나는지를, 다음 며칠 안에 확인 가능한 형태로 적어라.

evidence 경로가 evidence pack에 실제로 없는 논거는 기각하고 근거에서 제외하라.
base_rates의 표본이 30 미만이면 그 논거의 신뢰도를 낮춰 다뤄라.

one_liner는 60자 이내, summary는 200자 이내로 쓴다."""


def _system_blocks(market_context: str) -> list:
    """규칙 + 시장 공통 맥락을 캐시 접두부로 묶는다. 종목별 내용은 여기 넣지 않는다."""
    return [
        {"type": "text", "text": SYSTEM_RULES},
        {
            "type": "text",
            "text": f"오늘의 시장 맥락:\n{market_context}",
            "cache_control": {"type": "ephemeral"},
        },
    ]


def _call(client, system, user_text, schema):
    """단일 호출. 실패·거부·파싱 불가 시 (None, usage, refused).

    refused는 stop_reason == "refusal"이었는지만 별도로 알려준다 — 거부는
    "이 콜만 못 씀"이 아니라 "이 브리프 전체를 포기"로 이어지는 신호라서,
    한쪽만 파싱 실패한 경우(다른 쪽으로 진행)와 구분해야 한다.
    """
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": schema},
        },
        system=system,
        messages=[{"role": "user", "content": user_text}],
    )
    usage = _usage_of(resp)

    if resp.stop_reason == "refusal":
        logger.warning("브리프 콜 거부됨 (stop_reason=refusal)")
        return None, usage, True
    if resp.stop_reason == "max_tokens":
        logger.warning("브리프 콜이 max_tokens에 도달 — 출력이 잘렸을 수 있음")

    text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), None)
    if not text:
        return None, usage, False
    try:
        return json.loads(text), usage, False
    except json.JSONDecodeError:
        logger.warning("브리프 콜 응답 JSON 파싱 실패")
        return None, usage, False


def _usage_of(resp) -> dict:
    u = resp.usage
    return {
        "input_tokens": getattr(u, "input_tokens", 0) or 0,
        "output_tokens": getattr(u, "output_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
        "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
    }


def _accumulate(total: dict, one: dict) -> dict:
    for k, v in one.items():
        total[k] = total.get(k, 0) + v
    return total


def _cost(usage: dict) -> float:
    return (
        usage["input_tokens"] * PRICE_PER_TOKEN["input"]
        + usage["output_tokens"] * PRICE_PER_TOKEN["output"]
        + usage["cache_read_input_tokens"] * PRICE_PER_TOKEN["cache_read"]
        + usage["cache_creation_input_tokens"] * PRICE_PER_TOKEN["cache_write"]
    )


def generate_brief(pack: dict, client, market_context: str) -> dict | None:
    """3콜을 돌려 브리프 한 건을 만든다. judge가 실패하면 None."""
    system = _system_blocks(market_context)
    pack_json = json.dumps(pack, ensure_ascii=False, indent=1, default=str)
    usage: dict = {}

    bull, u, bull_refused = _call(
        client, system, f"{BULL_ROLE}\n\nevidence pack:\n{pack_json}", BULL_BEAR_SCHEMA
    )
    _accumulate(usage, u)
    bear, u, bear_refused = _call(
        client, system, f"{BEAR_ROLE}\n\nevidence pack:\n{pack_json}", BULL_BEAR_SCHEMA
    )
    _accumulate(usage, u)

    if bull_refused or bear_refused:
        logger.warning("bull 또는 bear 콜이 거부됨 — 브리프 생성 포기")
        return None

    if bull is None and bear is None:
        logger.warning("bull·bear 모두 실패 — 브리프 생성 포기")
        return None

    bull_kept, bull_dropped = validate_points((bull or {}).get("points", []), pack)
    bear_kept, bear_dropped = validate_points((bear or {}).get("points", []), pack)

    # judge에게는 코드가 거른 kept가 아니라 원본 points를 그대로 준다 — 근거가
    # pack에 실재하는지 판단하는 것 자체가 JUDGE_ROLE이 맡은 일이다.
    judge_input = (
        f"{JUDGE_ROLE}\n\n"
        f"evidence pack:\n{pack_json}\n\n"
        f"강세 논거:\n"
        f"{json.dumps({'points': (bull or {}).get('points', [])}, ensure_ascii=False, indent=1)}\n"
        f"강세가 주장하지 못한 것: {(bull or {}).get('what_i_could_not_argue', '(강세 논거 확보 실패)')}\n\n"
        f"약세 논거:\n"
        f"{json.dumps({'points': (bear or {}).get('points', [])}, ensure_ascii=False, indent=1)}\n"
        f"약세가 주장하지 못한 것: {(bear or {}).get('what_i_could_not_argue', '(약세 논거 확보 실패)')}"
    )
    judge, u, _ = _call(client, system, judge_input, JUDGE_SCHEMA)
    _accumulate(usage, u)

    if judge is None:
        logger.warning("judge 실패 — 브리프 생성 포기")
        return None

    judge, truncated = enforce_lengths(judge)
    if truncated:
        logger.warning("길이 초과로 절단된 필드: %s", truncated)

    usage["cost_usd"] = _cost(usage)
    return {
        "bull_points": bull_kept,
        "bear_points": bear_kept,
        "bull_could_not_argue": (bull or {}).get("what_i_could_not_argue", ""),
        "bear_could_not_argue": (bear or {}).get("what_i_could_not_argue", ""),
        "dropped_refs": bull_dropped + bear_dropped,
        "judge": judge,
        "usage": usage,
    }
