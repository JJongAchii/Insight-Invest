"""브리프 출력 스키마와 결정론적 검증.

judge에게 "가짜 근거를 기각하라"고 시키는 것과 별개로, 파싱 후 코드로 검증한다.
프롬프트 규칙은 지켜지지 않을 수 있지만 이건 지켜진다.
"""

MAX_ONE_LINER = 60
MAX_SUMMARY = 200

BULL_BEAR_SCHEMA = {
    "type": "object",
    "properties": {
        "points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "strength": {"type": "string", "enum": ["strong", "moderate", "weak"]},
                    "breaks_if": {"type": "string"},
                },
                "required": ["claim", "evidence", "strength", "breaks_if"],
                "additionalProperties": False,
            },
        },
        "what_i_could_not_argue": {"type": "string"},
    },
    "required": ["points", "what_i_could_not_argue"],
    "additionalProperties": False,
}

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "one_liner": {"type": "string"},
        "summary": {"type": "string"},
        "tension": {"type": "string"},
        "decisive_question": {"type": "string"},
        "watch": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string"},
                    "threshold": {"type": "string"},
                    "meaning": {"type": "string"},
                },
                "required": ["metric", "threshold", "meaning"],
                "additionalProperties": False,
            },
        },
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "confidence_reason": {"type": "string"},
        "stance_note": {"type": "string"},
    },
    "required": [
        "one_liner",
        "summary",
        "tension",
        "decisive_question",
        "watch",
        "confidence",
        "confidence_reason",
        "stance_note",
    ],
    "additionalProperties": False,
}


def flatten_keys(obj: dict, prefix: str = "") -> set:
    """중첩 dict → 점 경로 집합. 리스트는 리프로 취급한다."""
    keys = set()
    for k, v in obj.items():
        path = f"{prefix}{k}"
        keys.add(path)
        if isinstance(v, dict):
            keys |= flatten_keys(v, f"{path}.")
    return keys


def validate_points(points: list, pack: dict) -> tuple[list, list]:
    """evidence 경로가 pack에 실재하지 않는 논거를 분리. (유효, 드롭).

    evidence가 비어 있는 논거도 드롭한다 — 근거 없는 주장이기 때문.
    """
    valid = flatten_keys(pack)
    kept, dropped = [], []
    for p in points:
        refs = p.get("evidence")
        if not isinstance(refs, list):
            refs = []
        bad = [e for e in refs if e not in valid]
        if bad or not refs:
            dropped.append({**p, "bad_refs": bad})
        else:
            kept.append(p)
    return kept, dropped


def enforce_lengths(judge: dict) -> tuple[dict, list]:
    """JSON 스키마로 강제할 수 없는 길이 제약을 파싱 후 적용.

    (결과, 절단된 필드명).
    """
    out = dict(judge)
    truncated = []
    for field, limit in (("one_liner", MAX_ONE_LINER), ("summary", MAX_SUMMARY)):
        val = out.get(field)
        if isinstance(val, str) and len(val) > limit:
            out[field] = val[:limit]
            truncated.append(field)
    return out, truncated
