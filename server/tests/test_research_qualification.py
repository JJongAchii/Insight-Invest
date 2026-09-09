"""Qualification must not deploy, access live user state, or reset its budget."""

import importlib.util
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
    monkeypatch.setenv("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "0.50")
    monkeypatch.setenv("RESEARCH_MAX_ITEMS", "1")
    monkeypatch.setenv("RESEARCH_SOURCES", "aqr-research")
    monkeypatch.delenv("RESEARCH_QUALIFICATION_MODEL", raising=False)


def test_isolated_environment_contract(configured):
    assert qualification.validate_environment() == (1, ["aqr-research"], "gpt-5-mini")


@pytest.mark.parametrize(
    "name,value",
    [
        ("OPENAI_API_KEY", ""),
        ("APP_DATA", "s3://insight-invest-datalake/app"),
        ("RADAR_ANALYSIS_ENABLED", "false"),
        ("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "0.51"),
        ("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "0"),
        ("RESEARCH_MAX_ITEMS", "31"),
        ("RESEARCH_SOURCES", "man-systematic-insights"),
        ("RESEARCH_SOURCES", "unknown-source"),
        ("RESEARCH_QUALIFICATION_MODEL", "unapproved-model"),
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
    assert Decimal(run["env"]["RADAR_ANALYSIS_MONTHLY_BUDGET_USD"]) + Decimal(
        "1.50"
    ) == Decimal("2")
    assert "inputs.mode != 'research-qualify'" in workflow["jobs"]["deploy"]["if"]
    assert not any(
        "cloudformation" in step.get("run", "")
        or "lambda invoke" in step.get("run", "")
        for step in steps
    )


def test_mini_comparison_is_bounded_and_uses_correct_rates(configured, monkeypatch):
    monkeypatch.setenv("RESEARCH_QUALIFICATION_MODEL", "gpt-5-mini")
    monkeypatch.setenv(
        "RESEARCH_SOURCES", "aqr-research,robeco-quant-insights,cfm-research"
    )
    monkeypatch.setenv("RESEARCH_MAX_ITEMS", "3")
    assert qualification.validate_environment()[2] == "gpt-5-mini"
    assert qualification.MODEL_PRICES["gpt-5-mini"] == (250, 2000)
    assert qualification.research_analysis.MODEL == "gpt-5-mini"
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
