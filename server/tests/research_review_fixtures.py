"""Synthetic checks for offline state-machine tests, NEVER semantic acceptance."""

from module import research_review, research_selection


def selection_for(item, text, now, *, kind="research", relevant=True):
    return research_selection.receipt(
        item,
        {
            "primary_subject": "investment_methodology" if relevant else "other",
            "content_kind": kind,
            "investment_focus": relevant,
            "transferable_insight": {"evidence_ids": [0]} if relevant else None,
            "reason": "Synthetic original-selection fixture, not a semantic qualification.",
            "reading_points": {
                name: {"evidence_ids": [0]} for name in research_selection.POINT_NAMES
            },
        },
        text,
        now.isoformat(),
    )


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
