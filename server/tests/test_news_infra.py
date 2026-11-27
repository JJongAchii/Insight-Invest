"""뉴스 알림·확인 표식의 배포 계약 — 폴러는 발행본을 읽기만 하고, API는 표식 한 파일만 더 쓴다."""

from pathlib import Path

ROOT = Path(__file__).parents[2]
TEMPLATE = (ROOT / "infra/template.yaml").read_text(encoding="utf-8")
DEPLOY = (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")


def block(start, end):
    return TEMPLATE.split(f"  {start}:", 1)[1].split(f"  {end}:", 1)[0]


def test_news_poller_reads_the_board_and_writes_only_delivery_state():
    role = block("NewsPollerRole", "NewsPollerFunction")
    read, write = role.split("Action: [s3:PutObject]", 1)
    assert "app/market_desk/board.json" in read
    written = [line.split("/app/", 1)[1] for line in write.splitlines() if "/app/" in line]
    assert written == ["notification_subscriptions.parquet", "notification_deliveries.parquet"]
    assert "news_briefing.json" not in TEMPLATE


def test_news_poller_sends_web_push_every_two_minutes_without_a_model_key():
    function = block("NewsPollerFunction", "NewsPollerSchedule")
    assert 'ImageConfig: { Command: ["app.news_poller.handler"] }' in function
    for key in ("WEB_PUSH_PUBLIC_KEY", "WEB_PUSH_PRIVATE_KEY", "WEB_PUSH_SUBJECT"):
        assert f"{key}: !Ref" in function
    schedule = block("NewsPollerSchedule", "NewsPollerInvokePermission")
    # Odd minutes: the research poller writes the same receipt file at :02/:12/...
    assert "ScheduleExpression: cron(1/2 * * * ? *)" in schedule
    assert "Arn: !GetAtt NewsPollerFunction.Arn" in schedule
    assert "SourceArn: !GetAtt NewsPollerSchedule.Arn" in block("NewsPollerInvokePermission", "ActionPollerRole")
    assert "Anthropic" not in TEMPLATE and "ANTHROPIC" not in TEMPLATE and "Anthropic" not in DEPLOY


def test_api_can_record_the_last_news_visit_but_not_the_publication():
    writes = block("ApiRole", "ApiFunction").split("Action: [s3:PutObject, s3:DeleteObject]", 1)[1]
    assert "app/market_desk/news_seen.json" in writes
    assert "app/market_desk/board.json" not in writes and "app/market_desk/*" not in writes


def test_every_other_writer_of_the_delivery_receipts_runs_on_even_minutes():
    """영수증 파일은 읽고-고쳐-쓴다. 2분마다 홀수 분에 도는 뉴스 알림 폴러와 같은 분에 쓰면 한쪽 영수증이 사라져 같은 알림이
    다시 간다."""
    import re

    writers = [m for m in re.finditer(r"Name: (insight-invest-(?:action|research)-poll[\w-]*)\n\s+ScheduleExpression: cron\(([^ ]+) ",
                                     TEMPLATE)]
    assert len(writers) >= 5
    for match in writers:
        minutes = match[2]
        if "/" in minutes:
            start, step = minutes.split("/")
            assert int(start) % 2 == 0 and int(step) % 2 == 0, match[1]
        else:
            assert all(int(m) % 2 == 0 for m in minutes.split(",")), match[1]
