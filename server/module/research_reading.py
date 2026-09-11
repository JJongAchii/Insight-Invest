"""Read-only, field-level presentation of already reviewed reading notes.

Never edits a model draft, invents a quote, rewrites a rejection as acceptance, or
calls a provider. Original receipts remain in S3. A partial note is labelled partial.
"""

from __future__ import annotations

import re

from module import research_curation, research_review

POLICY_VERSION = "reading-display-v1-field-holds"


def display_issues(claim: str, evidence: str) -> list[str]:
    # Correct narrowly demonstrated false alarms in the old numeric guard. Strip
    # only the matching Korean unit, not arbitrary occurrences of that number.
    checked = claim
    months = (
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    )
    for number, month in enumerate(months, 1):
        if re.search(r"\b" + month + r"\b", evidence, re.I):
            checked = re.sub(rf"(?<!\d){number}월", "해당 월", checked)
    if re.search(r"\bfirst[- ]order\b", evidence, re.I):
        checked = re.sub(r"(?<!\d)1차", "일차", checked)
    issues = research_review.literal_issues(checked, evidence)
    if re.search(r"기후를?\s*고려|기후\s*투자자", claim) and not re.search(
        r"climate|carbon|기후|탄소", evidence, re.I
    ):
        issues.append("climate_modifier_absent_from_evidence")
    if re.search(r"연환산|연평균|연간\s*\d", claim) and not re.search(
        r"annual|yearly|per\s+year|연환산|연평균|연간", evidence, re.I
    ):
        issues.append("annualization_absent_from_evidence")
    if re.search(r"(?:지표|중앙값).{0,20}-?\d+\.\d+", claim) and not re.search(
        r"샤프|Sharpe|수익률|비율|상관|베타|변동성|%|bp", claim, re.I
    ):
        issues.append("unnamed_numeric_metric")
    return sorted(set(issues))


def reading_brief(item: dict) -> dict | None:
    """Only point-supported text crosses the presentation boundary.

    Topic/category checks do not invalidate unrelated translated sentences. They
    also never select an original: research_selection alone handles that decision.
    """
    if (
        not research_review.enabled()
        or item.get("editorial_selection_status") != "core"
    ):
        return None
    if research_review.state(item) not in {"accepted", "rejected"}:
        return None
    analysis = item["analysis"]
    if (
        type(analysis.get("analyzed_chars")) is not int
        or analysis["analyzed_chars"] <= 0
    ):
        return None
    brief, review = analysis["brief"], analysis["review"]
    checks = review["checks"]
    audit = research_curation.original_audit(item) or {}
    holds = (
        audit.get("field_holds", {})
        if audit.get("draft_digest") == research_review.digest(brief)
        else {}
    )
    points, held = {}, {}
    for name in research_review.POINTS:
        point = brief.get(name)
        points[name] = None
        if point is None:
            continue
        check = checks[name]
        issues = display_issues(point["text_ko"], point["evidence"])
        # Non-literal guards (e.g. citations outside the attached quote) remain.
        issues += [
            issue
            for issue in check.get("guard_issues", [])
            if not issue.startswith("numbers_absent_from_evidence:")
        ]
        if check["status"] != "supported" or issues or name in holds:
            held[name] = holds.get(name) or (
                "인용의 수치·용어·조건 확인 필요"
                if issues
                else "원문과 요약의 의미 대조 보류"
            )
        else:
            points[name] = point
    # A title or an isolated caveat is not a useful reading summary.
    if not (points["method_data"] or points["finding"]):
        return None
    title_check = checks["title_ko"]
    title = (
        brief["title_ko"]
        if title_check["status"] == "supported" and not title_check.get("guard_issues")
        else item["title"]
    )
    metadata_held = any(
        checks[name]["status"] != "supported" or checks[name].get("guard_issues")
        for name in ("title_ko", "content_kind", "quant_relevant", "substantive")
    )
    return {
        "policy_version": POLICY_VERSION,
        "source_digest": item["source_digest"],
        "draft_digest": review["draft_digest"],
        "status": "partial" if held or metadata_held else "ready",
        "title_ko": title,
        "analyzed_chars": analysis["analyzed_chars"],
        "points": points,
        "held_fields": held,
        "metadata_held": metadata_held,
    }
