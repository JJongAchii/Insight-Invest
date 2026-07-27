"""브리프 대상 종목 선정.

워치리스트 ∪ 보유 ∪ attention(high)에서 시총 하한을 넘는 종목을 고르고
상한을 적용한다. 절삭된 종목은 반드시 호출자가 로깅해야 한다 —
조용한 절삭은 "전부 커버했다"는 착각을 만든다.
"""

MKTCAP_FLOOR = 1e10  # build_insights.MKTCAP_FLOOR와 동일 — signal_study 유니버스 기준
DEFAULT_CAP = 15


def select_targets(
    watchlist: set,
    holdings: set,
    attention_high: list,
    mktcap: dict,
    cap: int = DEFAULT_CAP,
) -> tuple[list, list]:
    """(선정 티커, 절삭 티커).

    우선순위: 보유 > attention high > 워치리스트.
    attention_high는 입력 순서(=attention 점수순)를 우선순위로 그대로 쓴다.
    시총 하한 미달·시총 정보 없음은 자격 미달이라 절삭 목록에 넣지 않는다.
    """

    def eligible(t):
        return mktcap.get(t) is not None and mktcap[t] >= MKTCAP_FLOOR

    ordered, seen = [], set()
    for tier in (sorted(holdings), [t for t in attention_high], sorted(watchlist)):
        for t in tier:
            if t in seen or not eligible(t):
                continue
            seen.add(t)
            ordered.append(t)

    return ordered[:cap], ordered[cap:]
