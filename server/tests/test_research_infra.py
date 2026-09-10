from pathlib import Path
import re

ROOT = Path(__file__).parents[2]
TEMPLATE = ROOT / "infra/template.yaml"
DEPLOY = ROOT / ".github/workflows/deploy.yml"


def test_image_pins_the_qualified_source_parser():
    docker = (ROOT / "server/Dockerfile").read_text()
    assert re.search(r"^ARG QDATA_REF=[a-f0-9]{40}$", docker, re.M)
    assert "quant-data.git@${QDATA_REF}" in docker


def test_research_poller_is_bounded_and_offset_from_radar():
    body = TEMPLATE.read_text()

    assert "FunctionName: insight-invest-research-poller" in body
    assert 'ImageConfig: { Command: ["app.research_poller.handler"] }' in body
    assert "ScheduleExpression: cron(2/10 * * * ? *)" in body
    poller = body.split("  ResearchPollerFunction:", 1)[1].split(
        "  ResearchPollerSchedule:", 1
    )[0]
    assert "ReservedConcurrentExecutions: 1" in poller
    assert "Timeout: 300" in poller
    assert "ResearchPollerLogGroup:" in body
    assert "RetentionInDays: 14" in body
    assert "RADAR_RECORD_PREFIX: research-radar/public/records/" in body
    assert "RADAR_PENDING_PREFIX: research-radar/realtime/pending/" in body


def test_research_poller_role_is_prefix_scoped():
    body = TEMPLATE.read_text()

    assert "research-radar/public/records/*" in body
    assert "research-radar/realtime/pending/*" in body
    assert "app/research_feed.json" in body
    assert "app/research_read_state.parquet" in body
    assert "app/research_seen_state.json" in body
    assert "app/research_analysis/*" in body
    poller = body.split("  ResearchPollerFunction:", 1)[1].split(
        "  ResearchPollerSchedule:", 1
    )[0]
    assert "OPENAI_API_KEY: !Ref OpenAIApiKey" in poller
    assert 'RADAR_ANALYSIS_MONTHLY_BUDGET_USD: "1.50"' in poller
    assert "ANTHROPIC_API_KEY" not in poller
    assert "app/notification_subscriptions.parquet" in body
    assert "app/notification_deliveries.parquet" in body
    assert "s3:*" not in body


def test_editorial_release_is_default_off_and_shared_with_read_api():
    body = TEMPLATE.read_text()
    parameter = body.split("  ResearchAnalysisEnabled:", 1)[1].split(
        "  WebPushPublicKey:", 1
    )[0]
    assert 'Default: "false"' in parameter
    assert 'AllowedValues: ["false", "true"]' in parameter
    flag = "RADAR_ANALYSIS_ENABLED: !Ref ResearchAnalysisEnabled"
    assert body.count(flag) == 2
    assert flag in body.split("  ApiFunction:", 1)[1].split("  ApiUrl:", 1)[0]
    assert (
        flag
        in body.split("  ResearchPollerFunction:", 1)[1].split(
            "  ResearchPollerSchedule:", 1
        )[0]
    )
    assert "ResearchAnalysisEnabled=true" not in DEPLOY.read_text()


def test_release_smoke_requires_projection_api_and_active_push():
    body = DEPLOY.read_text()

    assert "aws lambda invoke --function-name insight-invest-research-poller" in body
    assert ".delivery_ready == true" in body
    assert "(.projection.records > 0)" in body
    assert '"$URL/research?lane=all&limit=1"' in body
    assert '.lane == "core"' in body
    assert ".lane_counts.all > 0" in body
    assert ".notification_eligible | type" in body
    assert '"$URL/research/status"' in body
    assert '.paths["/research/seen"].put' in body
