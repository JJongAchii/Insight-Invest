"""KR 장중 폴러의 운영 스케줄 계약 테스트."""

from pathlib import Path


TEMPLATE = Path(__file__).parents[2] / "infra" / "template.yaml"


def test_intraday_schedule_is_exactly_ten_minutes_during_market_window():
    body = TEMPLATE.read_text(encoding="utf-8")

    # AWS cron 하나로는 마지막 UTC 시간의 45·55분만 제외할 수 없어 두 룰이 필요하다.
    assert "cron(5,15,25,35,45,55 0-5 ? * MON-FRI *)" in body
    assert "cron(5,15,25,35 6 ? * MON-FRI *)" in body
    assert "cron(5,35 0-6 ? * MON-FRI *)" not in body


def test_both_intraday_schedules_can_invoke_the_poller():
    body = TEMPLATE.read_text(encoding="utf-8")

    assert "SourceArn: !GetAtt IntradayPollerSchedule.Arn" in body
    assert "SourceArn: !GetAtt IntradayPollerCloseSchedule.Arn" in body
    assert "Name: insight-invest-intraday-poll-close" in body
