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
    monkeypatch.setenv("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "0.10")
    monkeypatch.setenv("RESEARCH_MAX_ITEMS", "1")
    monkeypatch.setenv("RESEARCH_SOURCES", "aqr-research")


def test_isolated_environment_contract(configured):
    assert qualification.validate_environment() == (1, ["aqr-research"])


@pytest.mark.parametrize(
    "name,value",
    [
        ("OPENAI_API_KEY", ""),
        ("APP_DATA", "s3://insight-invest-datalake/app"),
        ("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "0.11"),
        ("RADAR_ANALYSIS_MONTHLY_BUDGET_USD", "0"),
        ("RESEARCH_MAX_ITEMS", "31"),
        ("RESEARCH_SOURCES", "man-systematic-insights"),
        ("RESEARCH_SOURCES", "unknown-source"),
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
    assert Decimal(run["env"]["RADAR_ANALYSIS_MONTHLY_BUDGET_USD"]) + Decimal(
        "1.90"
    ) == Decimal("2")
    assert "inputs.mode != 'research-qualify'" in workflow["jobs"]["deploy"]["if"]
    assert not any(
        "cloudformation" in step.get("run", "")
        or "lambda invoke" in step.get("run", "")
        for step in steps
    )
