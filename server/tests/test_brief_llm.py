import json
from types import SimpleNamespace

import anthropic
import httpx

from module.brief.llm import PRICE_PER_TOKEN, generate_brief


class _FakeResponse:
    def __init__(self, payload, stop_reason="end_turn"):
        self.content = [SimpleNamespace(type="text", text=json.dumps(payload))]
        self.stop_reason = stop_reason
        self.usage = SimpleNamespace(
            input_tokens=1000,
            output_tokens=200,
            cache_read_input_tokens=500,
            cache_creation_input_tokens=100,
        )


class _FakeClient:
    """호출 순서대로 준비된 응답을 돌려준다 (bull, bear, judge).

    큐에 예외 인스턴스를 넣어두면 그 차례에 응답 대신 예외를 던진다 —
    anthropic.APIError 같은 통신 실패를 흉내내기 위함.
    """

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        item = self._responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


PACK = {"flows": {"frgn": {"streak": 12}}, "identity": {"ticker": "005930"}}

BULL = {
    "points": [
        {
            "claim": "수급이 붙었다",
            "evidence": ["flows.frgn.streak"],
            "strength": "moderate",
            "breaks_if": "streak 단절",
        }
    ],
    "what_i_could_not_argue": "밸류에이션 측면 근거 없음",
}
BEAR = {
    "points": [
        {
            "claim": "업황이 나쁘다",
            "evidence": ["industry.outlook"],
            "strength": "strong",
            "breaks_if": "업황 반등",
        }
    ],
    "what_i_could_not_argue": "",
}
JUDGE = {
    "one_liner": "수급 우위, 근거는 얇음",
    "summary": "외국인 수급이 유일한 강세 근거다.",
    "tension": "수급과 밸류에이션이 갈린다",
    "decisive_question": "수급이 유지되는데 가격이 안 따라오는 날이 나오는가",
    "watch": [{"metric": "intensity_20d", "threshold": "< 0.3", "meaning": "수급 소진"}],
    "confidence": "medium",
    "confidence_reason": "표본은 충분하나 우위 폭이 작다",
    "stance_note": "강세 쪽으로 약간 기울었다",
}


def test_세_콜을_순서대로_호출한다():
    client = _FakeClient([_FakeResponse(BULL), _FakeResponse(BEAR), _FakeResponse(JUDGE)])
    out = generate_brief(PACK, client, "시장 맥락")
    assert len(client.calls) == 3
    assert out["judge"]["one_liner"] == "수급 우위, 근거는 얇음"


def test_bear의_가짜_근거가_드롭된다():
    client = _FakeClient([_FakeResponse(BULL), _FakeResponse(BEAR), _FakeResponse(JUDGE)])
    out = generate_brief(PACK, client, "시장 맥락")
    assert len(out["bull_points"]) == 1
    assert out["bear_points"] == []
    assert out["dropped_refs"][0]["bad_refs"] == ["industry.outlook"]


def test_시스템_프롬프트에_캐시_제어가_걸린다():
    client = _FakeClient([_FakeResponse(BULL), _FakeResponse(BEAR), _FakeResponse(JUDGE)])
    generate_brief(PACK, client, "시장 맥락")
    system = client.calls[0]["system"]
    assert system[-1]["cache_control"] == {"type": "ephemeral"}


def test_bull과_bear는_서로의_출력을_받지_않는다():
    client = _FakeClient([_FakeResponse(BULL), _FakeResponse(BEAR), _FakeResponse(JUDGE)])
    generate_brief(PACK, client, "시장 맥락")
    bull_prompt = json.dumps(client.calls[0]["messages"], ensure_ascii=False)
    bear_prompt = json.dumps(client.calls[1]["messages"], ensure_ascii=False)
    assert "업황이 나쁘다" not in bull_prompt
    assert "수급이 붙었다" not in bear_prompt
    # judge는 둘 다 본다
    judge_prompt = json.dumps(client.calls[2]["messages"], ensure_ascii=False)
    assert "수급이 붙었다" in judge_prompt
    assert "업황이 나쁘다" in judge_prompt


def test_refusal이면_None을_반환하고_예외를_올리지_않는다():
    refused = _FakeResponse(BULL, stop_reason="refusal")
    refused.content = []  # refusal은 content가 비어 있을 수 있다
    client = _FakeClient([refused, _FakeResponse(BEAR), _FakeResponse(JUDGE)])
    assert generate_brief(PACK, client, "시장 맥락") is None


def test_bull만_실패해도_bear로_judge를_진행한다():
    boom = _FakeResponse(BULL)
    boom.content = [SimpleNamespace(type="text", text="not json{{{")]
    client = _FakeClient([boom, _FakeResponse(BEAR), _FakeResponse(JUDGE)])
    out = generate_brief(PACK, client, "시장 맥락")
    assert out is not None
    assert out["bull_points"] == []
    assert out["judge"]["one_liner"] == "수급 우위, 근거는 얇음"


def test_bull_콜에서_APIError가_나도_bear로_judge를_진행한다():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    boom = anthropic.APIConnectionError(message="일시적 통신 장애", request=request)
    client = _FakeClient([boom, _FakeResponse(BEAR), _FakeResponse(JUDGE)])
    out = generate_brief(PACK, client, "시장 맥락")
    assert out is not None
    assert out["bull_points"] == []
    assert out["judge"]["one_liner"] == "수급 우위, 근거는 얇음"
    assert len(client.calls) == 3


def test_usage와_비용이_집계된다():
    client = _FakeClient([_FakeResponse(BULL), _FakeResponse(BEAR), _FakeResponse(JUDGE)])
    out = generate_brief(PACK, client, "시장 맥락")
    u = out["usage"]
    assert u["input_tokens"] == 3000  # 1000 × 3콜
    assert u["output_tokens"] == 600  # 200 × 3콜
    assert u["cache_read_input_tokens"] == 1500
    expected = (
        3000 * PRICE_PER_TOKEN["input"]
        + 600 * PRICE_PER_TOKEN["output"]
        + 1500 * PRICE_PER_TOKEN["cache_read"]
        + 300 * PRICE_PER_TOKEN["cache_write"]
    )
    assert abs(u["cost_usd"] - expected) < 1e-9
