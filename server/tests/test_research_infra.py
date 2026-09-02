from pathlib import Path

ROOT = Path(__file__).parents[2]
TEMPLATE = ROOT / "infra/template.yaml"
DEPLOY = ROOT / ".github/workflows/deploy.yml"


def test_research_poller_is_bounded_and_offset_from_radar():
    body = TEMPLATE.read_text()

    assert "FunctionName: insight-invest-research-poller" in body
    assert 'ImageConfig: { Command: ["app.research_poller.handler"] }' in body
    assert "ScheduleExpression: cron(2/10 * * * ? *)" in body
    assert "ReservedConcurrentExecutions: 1" in body
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
    assert "app/notification_subscriptions.parquet" in body
    assert "app/notification_deliveries.parquet" in body
    assert "s3:*" not in body


def test_release_smoke_requires_projection_api_and_active_push():
    body = DEPLOY.read_text()

    assert "aws lambda invoke --function-name insight-invest-research-poller" in body
    assert ".delivery_ready == true" in body
    assert "(.projection.records > 0)" in body
    assert '"$URL/research?limit=1"' in body
