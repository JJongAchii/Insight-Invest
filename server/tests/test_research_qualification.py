"""Qualification must not deploy, access live user state, or reset its budget."""

import importlib.util
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "qualify_research_editorial", ROOT / "scripts/qualify_research_editorial.py"
)
qualification = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualification)


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    monkeypatch.setenv("APP_DATA", qualification.QUALIFICATION_ROOT)
    monkeypatch.setenv("RADAR_ANALYSIS_ENABLED", "true")
    monkeypatch.setenv("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "1.00")
    monkeypatch.delenv("RADAR_ANALYSIS_BUDGET_OVERRIDE_MONTH", raising=False)
    monkeypatch.delenv("RADAR_ANALYSIS_BUDGET_OVERRIDE_USD", raising=False)
    monkeypatch.setenv("RESEARCH_MAX_ITEMS", "1")
    monkeypatch.setenv("RESEARCH_SOURCES", "aqr-research")
    monkeypatch.setenv("RESEARCH_QUALIFICATION_MODEL", "gpt-5-mini")
    monkeypatch.delenv("RESEARCH_BOUNDARY_MODEL", raising=False)
    monkeypatch.delenv("RESEARCH_SAMPLE", raising=False)


def test_isolated_environment_contract(configured):
    assert qualification.validate_environment() == (1, ["aqr-research"], "gpt-5-mini")


def test_reading_quality_candidate_is_pinned_and_bounded(configured, monkeypatch):
    monkeypatch.delenv("RESEARCH_QUALIFICATION_MODEL")
    model = qualification.READING_QUALITY_MODEL
    assert qualification.validate_environment() == (1, ["aqr-research"], model)
    assert qualification.MODEL_PRICES[model] == (2500, 15000)
    assert qualification.research_selection.MODEL == model
    assert qualification.research_selection.INPUT_NANOUSD_PER_TOKEN == 2500
    assert qualification.research_boundary.MODEL == "gpt-5-mini"
    monkeypatch.setenv("RESEARCH_MAX_ITEMS", "4")
    with pytest.raises(ValueError, match="three distinct sources"):
        qualification.validate_environment()


def test_frozen_batch_preserves_multiple_originals_from_one_source(
    configured, monkeypatch
):
    sources = [
        "robeco-quant-insights",
        "cfm-research",
        "deshaw-library",
        "aqr-research",
    ]
    sample = "reading-quality-20260915-a"
    cases = qualification.fixed_cases(sample, sources)
    assert len(cases) == 7
    assert (
        sum(case["source_id"] == "robeco-quant-insights" for case in cases.values())
        == 3
    )
    assert sum(case["expected_lane"] == "context" for case in cases.values()) == 2
    monkeypatch.setenv("RESEARCH_SAMPLE", sample)
    monkeypatch.setenv("RESEARCH_SOURCES", ",".join(sources))
    monkeypatch.setenv("RESEARCH_MAX_ITEMS", "7")
    assert qualification.validate_environment() == (7, sources, "gpt-5-mini")
    monkeypatch.setenv(
        "RESEARCH_QUALIFICATION_MODEL", qualification.READING_CONTRAST_MODEL
    )
    assert qualification.validate_environment() == (
        7,
        sources,
        qualification.READING_CONTRAST_MODEL,
    )
    assert qualification.MODEL_PRICES[qualification.READING_CONTRAST_MODEL] == (
        750,
        4500,
    )
    assert qualification.research_analysis.MODEL == qualification.READING_QUALITY_MODEL
    assert qualification.research_review.MODEL == qualification.READING_QUALITY_MODEL
    for key, case in cases.items():
        assert (
            qualification.case_for(
                {"entry_id": key, "source_id": case["source_id"]}, cases
            )
            == case
        )
    monkeypatch.setenv("RESEARCH_MAX_ITEMS", "6")
    with pytest.raises(ValueError, match="exact bounded size"):
        qualification.validate_environment()
    with pytest.raises(ValueError, match="exact sources"):
        qualification.fixed_cases(sample, sources[:-1])


def test_extra_reading_cases_are_separate_from_all_development_batches():
    fixtures = ROOT / "scripts/fixtures"
    originals = qualification.json.loads(
        (fixtures / "research-quality-20260915.json").read_text()
    )["items"]
    development = set()
    for part, count in (("a", 7), ("b", 7), ("c", 7), ("d", 6)):
        sample = f"reading-quality-20260915-{part}"
        sources = sorted(
            {item["source_id"] for item in originals if item["sample"] == sample}
        )
        cases = qualification.fixed_cases(sample, sources)
        assert len(cases) == count
        development.update(cases)
    extra = qualification.fixed_cases(
        "reading-quality-20260915-e",
        ["cfm-research", "robeco-quant-insights", "verdad-research"],
    )
    assert len(development) == 27 and len(extra) == 3
    assert not development.intersection(extra)
    assert sorted(case["expected_lane"] for case in extra.values()) == [
        "context",
        "core",
        "core",
    ]


def test_legacy_library_id_maps_only_to_the_same_canonical_original():
    cases = qualification.fixed_cases(
        "reading-quality-20260915-e",
        ["cfm-research", "robeco-quant-insights", "verdad-research"],
    )
    case = next(value for value in cases.values() if "producer_entry_id" in value)
    assert qualification.batch_entry_key(case) == case["producer_entry_id"]
    assert case["producer_entry_id"] != case["entry_id"]
    for key in ("entry_id", "producer_entry_id", "consumer_document_identity", "url"):
        with pytest.raises(ValueError, match="identity mapping"):
            qualification.batch_entry_key(
                {**case, key: case["url"] + "-different" if key == "url" else "different"}
            )


def test_editorial_cache_does_not_depend_on_preserved_library_alias():
    from module import research_analysis, research_boundary, research_selection
    from test_research_analysis import TEXT, NOW
    from research_review_fixtures import selection_for

    item = {
        "entry_id": "a" * 64,
        "source_digest": "b" * 64,
        "title": "Same original",
        "parser_version": "fixed",
        "analysis_scope": "full_article",
    }
    item["editorial_selection"] = selection_for(item, TEXT, NOW)
    alias = {**item, "entry_id": "c" * 64}
    for stage in (research_selection, research_boundary, research_analysis):
        assert stage.cache_key(item) == stage.cache_key(alias)


def test_batch_completion_cannot_borrow_manual_core_or_skip_review(monkeypatch):
    for lane, reviewed, expected in [
        ("pending", True, False),
        ("core", False, False),
        ("core", True, True),
        ("held", False, True),
        ("context", False, True),
    ]:
        monkeypatch.setattr(
            qualification.research_selection, "automatic_state", lambda _: lane
        )
        monkeypatch.setattr(qualification, "current_review", lambda _: reviewed)
        assert qualification.completed_batch_item({"research_lane": "core"}) is expected


def test_boundary_qualification_preserves_frozen_sources_and_model(
    configured, monkeypatch
):
    sample = "reading-gate-products-v1"
    assert qualification.fixed_cases(
        sample, ["aqr-research"]
    ) == qualification.fixed_cases("reading-products-v1", ["aqr-research"])
    monkeypatch.setenv("RESEARCH_SAMPLE", sample)
    assert qualification.validate_environment()[2] == "gpt-5-mini"
    monkeypatch.setenv("RESEARCH_QUALIFICATION_MODEL", "gpt-5-nano")
    with pytest.raises(ValueError, match="keeps GPT-5 mini"):
        qualification.validate_environment()


def test_boundary_hold_does_not_relabel_raw_selector_failure(monkeypatch):
    from research_review_fixtures import boundary_for, selection_for
    from test_research_analysis import NOW, TEXT

    item = {
        "source_id": "synthetic",
        "source_digest": "a" * 64,
        "title": "Fixture",
        "analysis_scope": "full_article",
        "source_chars": 2000,
    }
    item["editorial_selection"] = selection_for(item, TEXT, NOW)
    item["editorial_boundary"] = boundary_for(item, TEXT, NOW, verdict="context")
    case = {"expected_content_kinds": ["practitioner"], "expected_lane": "context"}
    check = qualification.gate_check(item, case)
    assert check["matches"] and check["automatic_lane"] == "held"
    assert not check["raw_selector_matches"]
    monkeypatch.setattr(
        qualification.research_selection.research_curation,
        "original_audit",
        lambda _: {"lane": "core"},
    )
    assert qualification.gate_check(item, case) == check
    case["expected_lane"] = "core"
    assert not qualification.gate_check(item, case)[
        "matches"
    ]  # Cannot hold all positives.


def test_boundary_model_contrast_is_fixed_and_isolated(configured, monkeypatch):
    monkeypatch.setattr(
        qualification.research_selection,
        "PROMPT_VERSION",
        "reading-selection-v7-evidence-first-purpose",
    )
    monkeypatch.setenv("RESEARCH_SAMPLE", "reading-gate-products-v1")
    monkeypatch.setenv("RESEARCH_BOUNDARY_MODEL", "gpt-5.4-2026-03-05")
    assert qualification.validate_environment() == (1, ["aqr-research"], "gpt-5-mini")
    assert qualification.BOUNDARY_MODEL_PRICES["gpt-5.4-2026-03-05"] == (2500, 15000)
    assert qualification.research_boundary.MODEL == "gpt-5-mini"
    monkeypatch.setenv("RESEARCH_SAMPLE", "latest")
    with pytest.raises(ValueError, match="fixed gate samples"):
        qualification.validate_environment()
    monkeypatch.setenv("RESEARCH_SAMPLE", "reading-gate-extension-v1")
    with pytest.raises(ValueError, match="fixed gate samples"):
        qualification.validate_environment()
    monkeypatch.setenv("RESEARCH_BOUNDARY_MODEL", "gpt-5.4")
    with pytest.raises(ValueError, match="not approved"):
        qualification.validate_environment()


def test_model_only_contrast_requires_unchanged_first_selection(monkeypatch):
    from research_review_fixtures import selection_for
    from test_research_analysis import NOW, TEXT

    record = {
        "entry_id_sha256": "entry",
        "title": "Source",
        "source_digest": "a" * 64,
        "analysis_scope": "full_article",
        "source_chars": 2000,
    }
    selected = selection_for(record, TEXT, NOW)
    monkeypatch.setattr(qualification.storage, "exists", lambda _: True)
    monkeypatch.setattr(qualification.storage, "read_json", lambda _: selected)
    preserved = qualification.preserved_selections([record], {"entry": TEXT})
    assert preserved[0]["decision_digest"] == selected["decision_digest"]
    assert preserved[0]["fingerprint"] == selected["fingerprint"]
    with pytest.raises(ValueError, match="selection/input changed"):
        qualification.preserved_selections([record], {"entry": "Other input"})
    monkeypatch.setattr(qualification.storage, "exists", lambda _: False)
    with pytest.raises(ValueError, match="preserved v7"):
        qualification.preserved_selections([record], {"entry": TEXT})


def test_diagnostic_restores_model_and_prices_even_when_source_fails(
    configured, monkeypatch, tmp_path
):
    import json

    monkeypatch.setattr(
        qualification.research_selection,
        "PROMPT_VERSION",
        "reading-selection-v7-evidence-first-purpose",
    )

    from test_research_analysis import TEXT

    boundary = qualification.research_boundary
    original = (
        boundary.MODEL,
        boundary.INPUT_NANOUSD_PER_TOKEN,
        boundary.OUTPUT_NANOUSD_PER_TOKEN,
    )
    proposed = {
        "insight": [qualification.research_analysis._source_passages(TEXT)[0]["text"]],
        "method": [],
        "purpose": [],
    }
    payload = boundary.request_payload(TEXT, "Source", proposed=proposed)
    fingerprint = boundary.cache_key({"title": "Source", "source_digest": "a" * 64})
    monkeypatch.setenv("RESEARCH_SAMPLE", "reading-gate-products-v1")
    monkeypatch.setenv("RESEARCH_BOUNDARY_MODEL", "gpt-5.4-2026-03-05")
    observed = []

    def fail(*args):
        current = boundary.request_payload(TEXT, "Source", proposed=proposed)
        observed.append(current["model"])
        assert {**current, "model": payload["model"]} == payload
        assert (
            boundary.cache_key({"title": "Source", "source_digest": "a" * 64})
            != fingerprint
        )
        assert (
            boundary.INPUT_NANOUSD_PER_TOKEN,
            boundary.OUTPUT_NANOUSD_PER_TOKEN,
        ) == (2500, 15000)
        assert qualification.research_selection.MODEL == "gpt-5-mini"
        raise ValueError("source unavailable")

    monkeypatch.setattr(qualification, "fixed_publication", fail)
    path = tmp_path / "diagnostic.json"
    assert qualification.run(path) == 1
    assert observed == ["gpt-5.4-2026-03-05"]
    report = json.loads(path.read_text())
    assert report["diagnostic_only"] is True and report["analysis_runs"] == []
    assert report["boundary_request_config"][
        "system_digest"
    ] == qualification.research_review.digest(boundary.SYSTEM)
    assert (
        boundary.MODEL,
        boundary.INPUT_NANOUSD_PER_TOKEN,
        boundary.OUTPUT_NANOUSD_PER_TOKEN,
    ) == original
    assert boundary.request_payload(TEXT, "Source", proposed=proposed) == payload


def test_extension_sample_is_separate_and_does_not_replace_prior_failures():
    cases = qualification.fixed_cases(
        "reading-gate-extension-v1", ["deshaw-library", "robeco-quant-insights"]
    )
    assert cases["deshaw-library"]["expected_lane"] == "core"
    assert cases["robeco-quant-insights"]["expected_lane"] == "context"
    previous = qualification.fixed_cases(
        "reading-gate-boundaries-v1", ["syzygy-insights"]
    )
    assert previous["syzygy-insights"]["expected_lane"] == "context"
    assert previous["syzygy-insights"]["source_digest"] == (
        "168762ea8c4d9faf7d19449b2f1df4c145c6d6e0a2f2160f939f75691cedb938"
    )


def test_full_brief_requires_automatic_gate_not_only_completed_translation(monkeypatch):
    monkeypatch.setattr(qualification, "current_review", lambda _: True)
    monkeypatch.setattr(qualification.research_selection, "state", lambda _: "core")
    monkeypatch.setattr(
        qualification.research_selection, "automatic_state", lambda _: "pending"
    )
    assert not qualification.current_automatic_review({})
    monkeypatch.setattr(
        qualification.research_selection, "automatic_state", lambda _: "core"
    )
    assert qualification.current_automatic_review({})


@pytest.mark.parametrize(
    "name,value",
    [
        ("OPENAI_API_KEY", ""),
        ("APP_DATA", "s3://insight-invest-datalake/app"),
        ("RADAR_ANALYSIS_ENABLED", "false"),
        ("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "1.100001"),
        ("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "0"),
        ("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "NaN"),
        ("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "Infinity"),
        ("RESEARCH_MAX_ITEMS", "31"),
        ("RESEARCH_SOURCES", "man-systematic-insights"),
        ("RESEARCH_SOURCES", "unknown-source"),
        ("RESEARCH_QUALIFICATION_MODEL", "unapproved-model"),
        ("RESEARCH_BOUNDARY_MODEL", "unapproved-model"),
        ("RESEARCH_SAMPLE", "unapproved-sample"),
    ],
)
def test_unsafe_qualification_inputs_stop_before_io(
    configured, monkeypatch, name, value
):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        qualification.validate_environment()


def test_workflow_is_manual_serialized_non_deploy_and_within_combined_budget():
    import yaml
    from decimal import Decimal

    workflow = yaml.safe_load((ROOT / ".github/workflows/deploy.yml").read_text())
    job = workflow["jobs"]["research-qualification"]
    assert "inputs.mode == 'research-qualify'" in job["if"]
    assert job["concurrency"] == {
        "group": "research-openai-qualification",
        "cancel-in-progress": False,
    }
    steps = job["steps"]
    run = next(step for step in steps if "Qualify real" in step.get("name", ""))
    assert run["env"]["APP_DATA"] == qualification.QUALIFICATION_ROOT
    assert run["env"]["RADAR_ANALYSIS_ENABLED"] == "true"
    assert (
        run["env"]["RESEARCH_BOUNDARY_MODEL"] == "${{ inputs.research_boundary_model }}"
    )
    assert all(
        "RESEARCH_BOUNDARY_MODEL" not in step.get("env", {})
        for step in workflow["jobs"]["deploy"]["steps"]
    )
    assert Decimal(run["env"]["RADAR_ANALYSIS_MONTHLY_BUDGET_USD"]) + Decimal(
        "0.90"
    ) == Decimal("2")
    assert "lambda get-function-configuration" in run["run"]
    assert 'test "$LIVE_RESEARCH_BUDGET" = "0.90"' in run["run"]
    assert run["env"]["RADAR_ANALYSIS_BUDGET_OVERRIDE_MONTH"] == "2026-09"
    assert Decimal(run["env"]["RADAR_ANALYSIS_BUDGET_OVERRIDE_USD"]) + Decimal("1") == 5
    assert '.month == "2026-09" and .usd == "1.00"' in run["run"]
    assert (
        'RADAR_ANALYSIS_MONTHLY_BUDGET_USD: "0.90"'
        in (ROOT / "infra/template.yaml").read_text()
    )
    assert "inputs.mode != 'research-qualify'" in workflow["jobs"]["deploy"]["if"]
    assert not any(
        "cloudformation" in step.get("run", "")
        or "lambda invoke" in step.get("run", "")
        for step in steps
    )


@pytest.mark.parametrize("month,amount", [("2026-10", "4"), ("2026-09", "4.000001")])
def test_unapproved_qualification_overrides_fail(
    configured, monkeypatch, month, amount
):
    monkeypatch.setenv("RADAR_ANALYSIS_BUDGET_OVERRIDE_MONTH", month)
    monkeypatch.setenv("RADAR_ANALYSIS_BUDGET_OVERRIDE_USD", amount)
    with pytest.raises(ValueError, match="approved only"):
        qualification.validate_environment()


@pytest.mark.parametrize(
    "timestamp,expected",
    [
        ("2026-09-30T23:59:59+09:00", 4_000_000_000),
        ("2026-10-01T00:00:00+09:00", 1_100_000_000),
    ],
)
def test_qualification_uses_dated_cap_without_increasing_base(
    configured, monkeypatch, timestamp, expected
):
    monkeypatch.setenv("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "1.10")
    monkeypatch.setenv("RADAR_ANALYSIS_BUDGET_OVERRIDE_MONTH", "2026-09")
    monkeypatch.setenv("RADAR_ANALYSIS_BUDGET_OVERRIDE_USD", "4.00")
    now = datetime.fromisoformat(timestamp)
    assert qualification.validate_environment(now=now)[2] == "gpt-5-mini"
    assert qualification.research_analysis.budget_limit_nanousd(now) == expected
    monkeypatch.setenv("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "4")
    with pytest.raises(ValueError, match="at most"):
        qualification.validate_environment(now=now)


def test_mini_comparison_is_bounded_and_uses_correct_rates(configured, monkeypatch):
    monkeypatch.setenv("RESEARCH_QUALIFICATION_MODEL", "gpt-5-mini")
    monkeypatch.setenv(
        "RESEARCH_SOURCES", "aqr-research,robeco-quant-insights,cfm-research"
    )
    monkeypatch.setenv("RESEARCH_MAX_ITEMS", "3")
    assert qualification.validate_environment()[2] == "gpt-5-mini"
    assert qualification.MODEL_PRICES["gpt-5-mini"] == (250, 2000)
    assert qualification.research_analysis.MODEL == qualification.READING_QUALITY_MODEL
    monkeypatch.setenv("RESEARCH_MAX_ITEMS", "4")
    with pytest.raises(ValueError, match="three distinct sources"):
        qualification.validate_environment()
    monkeypatch.setenv("RESEARCH_MAX_ITEMS", "3")
    monkeypatch.setenv("RESEARCH_SOURCES", "aqr-research")
    with pytest.raises(ValueError, match="three distinct sources"):
        qualification.validate_environment()


def test_selection_covers_sources_before_second_article_and_deduplicates():
    def record(name):
        return {"entry_id_sha256": name, "notification_eligible": True}

    groups = [[record("a"), record("aa")], [record("b"), record("a")], [record("c")]]
    selected = qualification.select_records(groups, 3)
    assert [item["entry_id_sha256"] for item in selected] == ["a", "b", "c"]
    assert all(not item["notification_eligible"] for item in selected)
    assert len(qualification.select_records(groups, 6)) == 4
    assert groups[0][0]["notification_eligible"]  # Producer input is not rewritten.


def test_previous_ready_model_is_not_a_completed_comparison(monkeypatch):
    item = {
        "source_digest": "a" * 64,
        "title": "Same source",
        "analysis_status": "ready",
    }
    item["analysis"] = {"fingerprint": qualification.research_analysis.cache_key(item)}
    assert not qualification.current_analysis(item)  # A draft alone cannot pass.
    monkeypatch.setattr(
        qualification.research_review, "state", lambda _item: "accepted"
    )
    assert qualification.current_analysis(item)
    monkeypatch.setattr(
        qualification.research_review, "state", lambda _item: "rejected"
    )
    assert qualification.current_review(item) and not qualification.current_analysis(
        item
    )
    monkeypatch.setattr(
        qualification.research_review, "state", lambda _item: "accepted"
    )
    monkeypatch.setattr(qualification.research_analysis, "MODEL", "gpt-5-nano")
    assert not qualification.current_analysis(item)


def test_prefilter_skip_is_not_counted_as_a_model_comparison():
    records = [
        {"title": "AI introduction", "analysis_status": "not_requested"},
        {"title": "Systematic credit", "analysis_status": "pending"},
    ]
    assert qualification.analysis_candidates(records) == [records[1]]
    assert (
        len(records) == 2
    )  # Keep the exclusion in the evidence, not silently delete it.


def test_fixed_sample_never_substitutes_missing_source(configured, monkeypatch):
    cases = qualification.fixed_cases(
        "reading-value-v1", ["aqr-research", "rafi-publications"]
    )
    assert cases["aqr-research"]["title"] == "Investing in a Warming World"
    assert len(cases["aqr-research"]["source_digest"]) == 64
    assert len(cases["aqr-research"]["baseline_brief_digest"]) == 64
    monkeypatch.setenv("RESEARCH_SAMPLE", "reading-value-v1")
    monkeypatch.setenv("RESEARCH_SOURCES", "cfm-research")
    with pytest.raises(ValueError, match="does not cover"):
        qualification.validate_environment()


def test_preserved_draft_replay_keeps_its_original_parser_identity(monkeypatch):
    case = qualification.fixed_cases("v7-regression", ["aqr-research"])["aqr-research"]
    record = {
        **case,
        "parser_version": "editorial-v2-reading-text",
        "analysis_scope": "full_pdf",
    }
    replay = qualification.preserved_input(record, case)
    monkeypatch.setattr(
        qualification.research_analysis, "PROMPT_VERSION", qualification.V7_PROMPT
    )
    monkeypatch.setattr(qualification.research_analysis, "MODEL", "gpt-5-mini")
    assert (
        qualification.research_analysis.cache_key(replay)
        == case["baseline_fingerprint"]
    )
    assert record["parser_version"] == "editorial-v2-reading-text"
    for field, value in (("source_digest", "a" * 64), ("analysis_scope", "abstract")):
        with pytest.raises(ValueError, match="body or analysis scope differs"):
            qualification.preserved_input({**record, field: value}, case)


def test_subject_sample_preserves_failure_source_and_lane_expectation(monkeypatch):
    previous = qualification.fixed_cases("reading-scope-v1", ["kcmi-reports"])[
        "kcmi-reports"
    ]
    case = qualification.fixed_cases("reading-subject-v1", ["kcmi-reports"])[
        "kcmi-reports"
    ]
    for key in ("url", "source_digest", "title", "expected_lane"):
        assert case[key] == previous[key]
    assert case["expected_lane"] == "context"
    item = {
        "source_id": "kcmi-reports",
        "editorial_selection": {
            "decision": {
                "primary_subject": "institutional_policy",
                "content_kind": "research",
            }
        },
    }
    monkeypatch.setattr(
        qualification.research_selection, "model_state", lambda _: "context"
    )
    check = qualification.selection_check(item, case)
    assert check[
        "matches"
    ]  # Formal research is compatible with a non-investment subject.
    item["editorial_selection"]["decision"]["primary_subject"] = (
        "investment_methodology"
    )
    assert not qualification.selection_check(item, case)["matches"]
    item["editorial_selection"]["decision"]["primary_subject"] = "institutional_policy"
    monkeypatch.setattr(
        qualification.research_selection, "model_state", lambda _: "core"
    )
    assert not qualification.selection_check(item, case)["matches"]


def test_fixed_source_drift_stops_before_analysis(monkeypatch):
    from datetime import UTC, datetime

    case = qualification.fixed_cases("reading-value-v1", ["aqr-research"])[
        "aqr-research"
    ]
    monkeypatch.setattr(qualification, "_fetch_bytes", lambda url: b"public source")
    monkeypatch.setattr(
        qualification,
        "parse_publication",
        lambda *a, **k: {"text": "Changed document.", "title": case["title"]},
    )
    with pytest.raises(ValueError, match="fixed source changed"):
        qualification.fixed_publication(case, datetime.now(UTC))


def test_contribution_samples_are_bounded_and_frozen_before_paid_calls():
    bundles = {
        "reading-products-v1": [
            "robeco-quant-insights",
            "aqr-research",
            "cfm-research",
        ],
        "reading-commercialization-v1": [
            "robeco-quant-insights",
            "deshaw-library",
            "kcmi-reports",
        ],
        "reading-subject-v1": ["robeco-quant-insights", "aqr-research", "kcmi-reports"],
        "reading-subject-positive-v1": [
            "robeco-quant-insights",
            "deshaw-library",
            "cfm-research",
        ],
        "reading-contribution-boundaries-v1": [
            "aqr-research",
            "kcmi-capital-market-focus",
            "syzygy-insights",
        ],
        "reading-contribution-methods-v1": ["rafi-publications", "verdad-research"],
    }
    cases = {}
    for sample, sources in bundles.items():
        assert sample in qualification.SELECTION_SAMPLES
        fixed = qualification.fixed_cases(sample, sources)
        assert len(fixed) == len(sources) <= 3
        for case in fixed.values():
            previous = cases.setdefault(case["url"], case)
            assert previous == case
            assert len(case["source_digest"]) == 64
    assert len(cases) == 13
    assert sum(c["expected_lane"] == "core" for c in cases.values()) == 7
    assert sum(c["expected_lane"] == "context" for c in cases.values()) == 6


def test_selection_check_rejects_contribution_mismatch_even_when_lane_matches(
    monkeypatch,
):
    case = qualification.fixed_cases("reading-products-v1", ["robeco-quant-insights"])[
        "robeco-quant-insights"
    ]
    decision = {
        "primary_subject": "business_or_product",
        "content_kind": "practitioner",
        "contribution_type": "none",
    }
    item = {
        "source_id": case["source_id"],
        "editorial_selection": {"decision": decision},
    }
    monkeypatch.setattr(
        qualification.research_selection, "model_state", lambda _: "context"
    )
    assert qualification.selection_check(item, case)["matches"]
    decision["contribution_type"] = "rule_or_measurement"
    assert not qualification.selection_check(item, case)["matches"]


def test_full_brief_uses_the_same_frozen_positive_sources(configured, monkeypatch):
    sample = "reading-brief-evidence-v1"
    sources = ["deshaw-library", "cfm-research", "robeco-quant-insights"]
    assert qualification.fixed_cases(sample, sources) == qualification.fixed_cases(
        "reading-subject-positive-v1", sources
    )
    assert sample not in qualification.GATE_SAMPLES
    assert sample not in qualification.SELECTION_SAMPLES
    monkeypatch.setenv("RESEARCH_SAMPLE", sample)
    monkeypatch.setenv("RESEARCH_SOURCES", ",".join(sources))
    monkeypatch.setenv("RESEARCH_MAX_ITEMS", "3")
    monkeypatch.setenv("RESEARCH_QUALIFICATION_MODEL", "gpt-5-mini")
    assert qualification.validate_environment() == (3, sources, "gpt-5-mini")


def test_runner_sets_comparison_prices_and_restores_defaults_without_io(
    configured, monkeypatch, tmp_path
):
    import json

    module = qualification.research_analysis
    original = (
        module.MODEL,
        module.INPUT_NANOUSD_PER_TOKEN,
        module.OUTPUT_NANOUSD_PER_TOKEN,
    )
    reservation = module._request_reservation(
        "A complete source sentence. " * 100, "Test"
    )
    monkeypatch.setenv("RESEARCH_QUALIFICATION_MODEL", "gpt-5-nano")
    observed = []

    class EmptyProbe(list):
        health = {"readable": 0}

    def collect(*_args, **_kwargs):
        observed.append(
            (
                module.MODEL,
                module.INPUT_NANOUSD_PER_TOKEN,
                module.OUTPUT_NANOUSD_PER_TOKEN,
            )
        )
        assert (
            module._request_reservation("A complete source sentence. " * 100, "Test")
            * 5
            == reservation
        )
        return EmptyProbe()

    monkeypatch.setattr(qualification, "discover_publications", collect)
    report_path = tmp_path / "qualification.json"
    assert qualification.run(report_path) == 1  # No readable sample; no API call.
    assert observed == [("gpt-5-nano", 50, 400)]
    report = json.loads(report_path.read_text())
    assert report["model"] == "gpt-5-nano"
    assert report["pricing_nanousd_per_token"] == {"input": 50, "output": 400}
    assert report["analysis_runs"] == [] and not report["production_modified"]
    assert (
        module.MODEL,
        module.INPUT_NANOUSD_PER_TOKEN,
        module.OUTPUT_NANOUSD_PER_TOKEN,
    ) == original
