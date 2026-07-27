"""briefs 저장소 — 월 예산 집계.

month_cost는 비용 가드레일의 근거가 되는 값이라, 틀리면 상한이 조용히
무력화되거나(과소 집계) 정상 운영을 막는다(과대 집계). 경계를 테스트로 고정한다.
"""

import pandas as pd
import pytest

from datastore import briefs


@pytest.fixture
def _store(monkeypatch):
    """list_items()를 주입한 프레임으로 대체 — S3/파일 접근 없이 집계만 검증."""

    def _install(df):
        monkeypatch.setattr(briefs, "list_items", lambda: df)

    return _install


def _row(generated_at, cost_usd, ticker="005930"):
    return {"ticker": ticker, "generated_at": generated_at, "cost_usd": cost_usd}


def test_파일이_없으면_0(_store):
    _store(pd.DataFrame(columns=briefs.COLUMNS))
    assert briefs.month_cost("2026-07") == 0.0


def test_해당_월만_합산한다(_store):
    _store(
        pd.DataFrame(
            [
                _row("2026-06-30T10:00:00+00:00", 1.00),
                _row("2026-07-01T10:00:00+00:00", 2.00),
                _row("2026-07-27T10:00:00+00:00", 3.00),
                _row("2026-08-01T10:00:00+00:00", 4.00),
            ]
        )
    )
    assert briefs.month_cost("2026-07") == 5.00
    assert briefs.month_cost("2026-06") == 1.00
    assert briefs.month_cost("2026-08") == 4.00


def test_해당_월_행이_없으면_0(_store):
    _store(pd.DataFrame([_row("2026-07-01T10:00:00+00:00", 2.00)]))
    assert briefs.month_cost("2026-09") == 0.0


def test_결측_비용은_0으로_취급(_store):
    _store(
        pd.DataFrame(
            [
                _row("2026-07-01T10:00:00+00:00", 2.00),
                _row("2026-07-02T10:00:00+00:00", None),
                _row("2026-07-03T10:00:00+00:00", float("nan")),
            ]
        )
    )
    assert briefs.month_cost("2026-07") == 2.00


def test_비수치_비용도_예외없이_0으로(_store):
    _store(
        pd.DataFrame(
            [
                _row("2026-07-01T10:00:00+00:00", 2.00),
                _row("2026-07-02T10:00:00+00:00", "표기오류"),
            ]
        )
    )
    assert briefs.month_cost("2026-07") == 2.00


def test_generated_at_컬럼이_없으면_0(_store):
    _store(pd.DataFrame([{"ticker": "005930", "cost_usd": 9.99}]))
    assert briefs.month_cost("2026-07") == 0.0


def test_월_접두어가_부분일치를_오염시키지_않는다(_store):
    """ "2026-07"이 "2026-07..."에만 매칭되고 "2026-070"류에 새지 않는지."""
    _store(
        pd.DataFrame(
            [
                _row("2026-07-01T10:00:00+00:00", 1.00),
                _row("2026-12-01T10:00:00+00:00", 8.00),
                _row("2027-07-01T10:00:00+00:00", 9.00),
            ]
        )
    )
    assert briefs.month_cost("2026-07") == 1.00
