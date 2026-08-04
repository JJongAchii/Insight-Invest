"""build_insights.build_us_prices (P0) — massive 미러 US 티커 총수익 계열 재생성.

server/tests/test_live_weights_builder.py 의 build_insights 임포트 관례(scripts/를
sys.path에 추가)를 따르되, 이 파일은 그 로딩을 `bi` 픽스처로 감싼다 — 브리프의
테스트 코드가 `bi.qdata_api`/`bi.meta`/`bi.build_us_prices()`를 전제하기 때문이다.
"""

import os
import sys

import pandas as pd
import pytest

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

try:
    import build_insights

    _IMPORT_ERROR = None
except Exception as e:  # 환경 문제(자격증명·의존성 부재 등)는 스킵, 에러 아님
    build_insights = None
    _IMPORT_ERROR = e


@pytest.fixture
def bi():
    if build_insights is None:
        pytest.skip(f"build_insights import 실패 (환경 문제): {_IMPORT_ERROR}")
    return build_insights


def _fake_mirror(monkeypatch, bi, px_long, div_long, meta_df):
    monkeypatch.setattr(
        bi.qdata_api,
        "load_us_prices",
        lambda start=None, end=None, tickers=None, columns=None: px_long[
            (px_long.date >= start) & (px_long.date <= end)
        ].copy(),
    )
    monkeypatch.setattr(
        bi.qdata_api,
        "load_us_dividends",
        lambda start=None, end=None, tickers=None: div_long.copy(),
    )
    monkeypatch.setattr(bi.meta, "meta_df", lambda: meta_df)
    # _as_of()는 krx_flows(640MB 실 레이크)를 로드하는 공용 헬퍼 — 이 빌더 테스트는
    # US 가격 합성만 검증하면 되므로 고정값으로 대체해 레이크 의존·왕복 시간을 없앤다.
    monkeypatch.setattr(bi, "_as_of", lambda: "2026-08-04")


def test_builder_schema_and_meta_join(monkeypatch, bi, capsys):
    dates = pd.bdate_range("2026-01-05", periods=3)
    px = pd.DataFrame(
        {
            "date": list(dates) * 1,
            "ticker": "SPY",
            "close": [500.0, 505.0, 500.0],
            "adj_close": [500.0, 505.0, 500.0],
        }
    )
    div = pd.DataFrame({"ticker": ["SPY"], "ex_date": [dates[2]], "cash_amount": [2.0]})
    meta_df = pd.DataFrame({"meta_id": [1], "ticker": ["SPY"], "iso_code": ["US"]})
    _fake_mirror(monkeypatch, bi, px, div, meta_df)
    out = bi.build_us_prices()
    assert list(out.columns) == [
        "meta_id",
        "trade_date",
        "ticker",
        "adj_close",
        "gross_return",
        "as_of",
    ]
    assert out["gross_return"].iloc[2] == pytest.approx((500.0 + 2.0) / 505.0 - 1)
    # 픽스처가 과거 날짜이므로 신선도 경고(§5)가 함께 발화해야 한다
    assert "미러 최종일" in capsys.readouterr().err


def test_builder_guard_excludes_with_warning(monkeypatch, bi, capsys):
    """40% 점프 티커는 제외 + 경고, 나머지는 살아남는다 — 조용한 소실 금지."""
    dates = pd.bdate_range("2026-01-05", periods=3)
    px = pd.concat(
        [
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": "GOOD",
                    "close": [100.0, 101.0, 102.0],
                    "adj_close": [100.0, 101.0, 102.0],
                }
            ),
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": "BAD",
                    "close": [1.0, 1.0, 100.0],
                    "adj_close": [1.0, 1.0, 100.0],
                }
            ),
        ]
    )
    meta_df = pd.DataFrame({"meta_id": [1, 2], "ticker": ["GOOD", "BAD"], "iso_code": ["US", "US"]})
    _fake_mirror(
        monkeypatch, bi, px, pd.DataFrame({"ticker": [], "ex_date": [], "cash_amount": []}), meta_df
    )
    out = bi.build_us_prices()
    assert set(out.ticker) == {"GOOD"}
    assert "연속성 가드" in capsys.readouterr().err


def test_builder_returns_none_on_mirror_failure(monkeypatch, bi, capsys):
    """미러 읽기 실패 → None (기존 파일 유지) + 경고. 예외가 새어 나가면 안 된다."""
    meta_df = pd.DataFrame({"meta_id": [1], "ticker": ["SPY"], "iso_code": ["US"]})
    monkeypatch.setattr(bi.meta, "meta_df", lambda: meta_df)  # 실 S3 접근 차단

    def boom(**kwargs):
        raise OSError("s3 down")

    monkeypatch.setattr(bi.qdata_api, "load_us_prices", boom)
    assert bi.build_us_prices() is None
    assert "기존 파일 유지" in capsys.readouterr().err


def test_builder_all_excluded_returns_none_instead_of_crashing(monkeypatch, bi, capsys):
    """전 종목이 연속성 가드에 걸리면 out이 비어 pd.concat이 ValueError로 죽는다 —
    None + 경고로 안전하게 스킵해야 한다 (기존 파일 유지, 파이프라인 비중단)."""
    dates = pd.bdate_range("2026-01-05", periods=3)
    px = pd.DataFrame(
        {
            "date": dates,
            "ticker": "BAD",
            "close": [1.0, 1.0, 100.0],
            "adj_close": [1.0, 1.0, 100.0],
        }
    )
    meta_df = pd.DataFrame({"meta_id": [1], "ticker": ["BAD"], "iso_code": ["US"]})
    _fake_mirror(
        monkeypatch, bi, px, pd.DataFrame({"ticker": [], "ex_date": [], "cash_amount": []}), meta_df
    )
    out = bi.build_us_prices()
    assert out is None
    err = capsys.readouterr().err
    assert "연속성 가드" in err
    assert "0종목" in err
