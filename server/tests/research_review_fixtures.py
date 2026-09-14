"""Synthetic checks for offline state-machine tests, NEVER semantic acceptance."""

from module import research_boundary, research_review, research_selection


def boundary_value(*, verdict="substantive"):
    return {
        "checks": {
            name: {
                "source_meaning": "Synthetic check, not semantic evidence.",
                "disclosed_or_missing": "Synthetic disclosure check.",
                "role": {
                    "substantive": "operational_detail",
                    "context": "objective_or_profile",
                    "uncertain": "unclear",
                }[verdict],
            }
            for name in research_boundary.EVIDENCE_FIELDS
        },
        "analysis_object": "investment_rule_or_measurement",
        "object_evidence_id": 0,
    }


def boundary_for(item, text, now, *, verdict="substantive"):
    if "editorial_selection" not in item:
        item["editorial_selection"] = selection_for(item, text, now)
    value = boundary_value(verdict=verdict)
    plan = research_boundary.evidence_plan(item)
    for name in value["checks"]:
        if not plan[name]:
            value["checks"][name] = None
    return research_boundary.receipt(
        item,
        value,
        text,
        now.isoformat(),
    )


def selection_for(item, text, now, *, kind="research", relevant=True):
    return research_selection.receipt(
        item,
        {
            "main_purpose": {
                "category": "investment_analysis"
                if relevant
                else "adoption_or_outlook",
                "evidence": {"evidence_ids": [0]},
            },
            "primary_subject": "investment_methodology" if relevant else "other",
            "content_kind": kind,
            "contribution_type": "investment_mechanism" if relevant else "none",
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
