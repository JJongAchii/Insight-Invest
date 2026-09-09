"""Synthetic checks for offline state-machine tests, NEVER semantic acceptance."""

from module import research_review


def checks_for(brief):
    return {
        name: {
            "status": "not_applicable"
            if name in research_review.POINTS and brief[name] is None
            else "supported",
            "reason_ko": "오프라인 테스트 대조"
            if not (name in research_review.POINTS and brief[name] is None)
            else "",
            "evidence_ids": []
            if name in research_review.POINTS and brief[name] is None
            else [0],
        }
        for name in research_review.FIELDS
    }


def attach_review(item, text, now):
    analysis = item["analysis"]
    analysis["review"] = research_review.receipt(
        item, analysis, checks_for(analysis["brief"]), text, now.isoformat()
    )
