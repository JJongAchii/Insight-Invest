import json

from app.routers import journal


def test_journal_captures_evidence_and_appends_review(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    monkeypatch.setattr(
        journal.overview,
        "get_overview",
        lambda: {
            "generated_at": "2026-08-18T12:00:00+09:00",
            "tone_label": "시간축별 혼조",
            "horizons": [{"key": "tactical"}],
            "conflicts": ["엇갈림"],
            "data_status": [],
            "method": "분리",
        },
    )
    request = journal.JournalCreateRequest(
        observation="시장폭 하락",
        interpretation="참여 위축",
        decision="신규 매수 보류",
        horizon="tactical",
        confidence=3,
        counter_evidence="외국인 순매수",
        invalidation="시장폭 55% 회복",
        review_date="2026-09-01",
    )

    created = journal.create_journal_entry(request)
    rows = journal.get_journal()["items"]

    assert len(rows) == 1
    assert rows[0]["entry_id"] == created["entry_id"]
    assert rows[0]["evidence_snapshot"]["tone_label"] == "시간축별 혼조"
    assert json.dumps(rows[0]["evidence_snapshot"], ensure_ascii=False)

    journal.review_journal_entry(
        created["entry_id"], journal.JournalReviewRequest(outcome="보류 판단 유지", lesson="시장폭 확인 유효")
    )
    reviewed = journal.get_journal()["items"][0]
    assert reviewed["outcome"] == "보류 판단 유지"
