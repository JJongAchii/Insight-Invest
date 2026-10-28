"""공모주 화면 API와 Action Center 이벤트 — 배치 산출(parquet·JSON)을 읽어 돌려주고 사용자 입력을 저장한다."""

from datetime import datetime

import pandas as pd
import pytest
from fastapi import HTTPException

from app.routers import actions, ipo
from datastore import storage


@pytest.fixture
def app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    storage.write_json(
        {
            "as_of": "2026-11-02",
            "next_session": "2026-11-03",
            "problems": [],
            "upcoming": [],
        },
        "ipo",
        "status.json",
    )
    storage.write_json(
        {
            "buy1": {"event_id": "buy1", "buy": True, "listing_date": "2026-11-03"},
            "pass1": {"event_id": "pass1", "buy": False, "listing_date": "2026-11-03"},
        },
        "ipo",
        "decisions.json",
    )
    storage.write_parquet(
        pd.DataFrame(
            [
                {
                    "event_id": "buy1",
                    "corp_name": "가나",
                    "market": "KOSDAQ",
                    "listing_date": "2026-11-03",
                    "buy": True,
                    "limit_price": 15_000.0,
                    "position": "signal",
                    "sell_on": "2026-11-04",
                    "as_of": "2026-11-02",
                },
                {
                    "event_id": "held",
                    "corp_name": "다라",
                    "market": "KOSPI",
                    "listing_date": "2026-10-30",
                    "buy": True,
                    "limit_price": 30_000.0,
                    "position": "holding",
                    "sell_on": "2026-11-03",
                    "rolls": 1,
                    "as_of": "2026-11-02",
                },
                {
                    "event_id": "pass1",
                    "corp_name": "마바",
                    "market": "KOSDAQ",
                    "listing_date": "2026-11-03",
                    "buy": False,
                    "as_of": "2026-11-02",
                },
            ]
        ),
        "ipo",
        "ipo_signals.parquet",
    )
    return tmp_path


def test_get_returns_open_positions_and_history(app_data):
    out = ipo.get_ipo()
    assert out["status"]["next_session"] == "2026-11-03"
    assert {r["event_id"] for r in out["open"]} == {"buy1", "held"}
    assert [r["event_id"] for r in out["history"]][0] in {"buy1", "pass1"}  # 최신 상장일 먼저
    assert len(out["history"]) == 3


def test_get_without_batch_output_says_so(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    out = ipo.get_ipo()
    assert out["open"] == [] and out["history"] == []
    assert "산출이 아직 없다" in out["status"]["problems"][0]


def test_user_fill_is_stored_validated_and_cleared(app_data):
    saved = ipo.update_position(
        "buy1", ipo.PositionRequest(filled=True, entry_price=14_800.0, quantity=10)
    )
    assert saved["user"]["entry_price"] == 14_800.0 and saved["user"]["quantity"] == 10
    row = next(r for r in ipo.get_ipo()["history"] if r["event_id"] == "buy1")
    assert row["user"]["filled"] is True
    with pytest.raises(HTTPException) as bad:
        ipo.update_position("buy1", ipo.PositionRequest(exit_price=-1))
    assert bad.value.status_code == 422
    with pytest.raises(HTTPException) as early:
        ipo.update_position("buy1", ipo.PositionRequest(exit_date="2026-11-01"))
    assert early.value.status_code == 422
    with pytest.raises(HTTPException) as passed:
        ipo.update_position("pass1", ipo.PositionRequest(filled=True))
    assert passed.value.status_code == 422
    with pytest.raises(HTTPException) as unknown:
        ipo.update_position("nope", ipo.PositionRequest(filled=True))
    assert unknown.value.status_code == 404
    cleared = ipo.update_position("buy1", ipo.PositionRequest())
    assert cleared["user"] is None


def test_action_center_raises_buy_and_sell_days(app_data):
    now = datetime(2026, 11, 2, 22, 50, tzinfo=actions.KST)
    events = actions._ipo_events(now)
    kinds = {(e["kind"], e["scheduled_for"]) for e in events}
    assert kinds == {("ipo_buy", "2026-11-03"), ("ipo_sell", "2026-11-03")}
    buy = next(e for e in events if e["kind"] == "ipo_buy")
    assert buy["severity"] == "high" and "15,000원" in buy["detail"]
    sell = next(e for e in events if e["kind"] == "ipo_sell")
    assert "하한가 이월 1회" in sell["detail"]
    later = datetime(2026, 11, 4, 8, 0, tzinfo=actions.KST)
    assert actions._ipo_events(later) == []  # 지난 매수·매도일은 다시 띄우지 않는다


def test_action_center_flags_problems(app_data):
    storage.write_json(
        {"as_of": "2026-11-02", "next_session": "2026-11-03", "problems": ["가나: 결정 대기"]},
        "ipo",
        "status.json",
    )
    now = datetime(2026, 11, 2, 22, 50, tzinfo=actions.KST)
    flagged = [e for e in actions._ipo_events(now) if e["kind"] == "data"]
    assert flagged and flagged[0]["severity"] == "medium" and "결정 대기" in flagged[0]["detail"]


def test_push_runs_after_the_evening_batch_and_before_the_pre_open_auction():
    """매수 주문은 상장일 08:30 전에 알아야 한다 — 22:50·07:40 KST 알림 실행이 있고 호출 권한이 있다."""
    from pathlib import Path

    body = (Path(__file__).parents[2] / "infra" / "template.yaml").read_text(encoding="utf-8")
    assert "cron(50 13 ? * MON-FRI *)" in body  # 22:50 KST
    assert "cron(40 22 ? * SUN-THU *)" in body  # 07:40 KST 월~금
    assert "SourceArn: !GetAtt ActionPollerScheduleNight.Arn" in body
    assert "SourceArn: !GetAtt ActionPollerScheduleEarly.Arn" in body


def test_action_center_lists_scheduled_listings_without_pushing(app_data):
    status = storage.read_json("ipo", "status.json")
    status["calendar"] = [
        {"event_id": "cal1", "corp_name": "사아", "market": "KOSDAQ",
         "planned_listing_date": "2026-11-05", "decision_night": "2026-11-04"},
        {"event_id": "cal0", "corp_name": "자차", "market": "KOSDAQ",
         "planned_listing_date": None},
    ]  # fmt: skip
    storage.write_json(status, "ipo", "status.json")
    now = datetime(2026, 11, 2, 22, 50, tzinfo=actions.KST)
    listed = [e for e in actions._ipo_events(now) if e["kind"] == "ipo_listing"]
    assert len(listed) == 1 and listed[0]["severity"] == "low"  # 낮음은 Web Push를 보내지 않는다
    assert listed[0]["scheduled_for"] == "2026-11-05" and "11-04 밤" in listed[0]["detail"]


def test_pipeline_detects_the_ipo_builder_by_its_function_name():
    """quant-data 일일 파이프라인은 build_insights.py에 'def build_ipo_signals'가 있을 때 `--only ipo_signals`를
    부른다(quant-data tests/test_pipeline_contract.py 짝 검사). 2026-10-28에는 '"ipo_signals"'를 찾아 늘
    건너뛰었다 — 이름을 바꾸면 두 쪽을 함께 바꾼다."""
    import sys
    from pathlib import Path

    scripts = Path(__file__).parents[2] / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import build_insights

    body = (scripts / "build_insights.py").read_text(encoding="utf-8")
    assert "def build_ipo_signals" in body
    names = {build_insights._builder_name(item[0]) for item in build_insights.BUILDERS}
    assert "ipo_signals" in names
