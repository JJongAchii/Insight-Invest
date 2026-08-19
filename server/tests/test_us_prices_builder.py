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


@pytest.fixture(autouse=True)
def _cutover_enabled(monkeypatch):
    """전환 게이트 기본 활성화 — 이 파일의 테스트는 빌더 로직 자체를 검증하므로,
    게이트 미통과 스킵은 test_builder_skips_without_cutover_flag에서만 별도로 확인한다."""
    monkeypatch.setenv("US_PRICES_CUTOVER", "1")


def _no_reference(**kwargs):
    raise FileNotFoundError("clean/us_ticker_events.parquet 없음 (테스트 기본값)")


def _fake_mirror(monkeypatch, bi, px_long, div_long, meta_df, events=None, details=None):
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
    # 실체 경계 로더 — 픽스처가 없으면 부재 경로(FileNotFoundError → 절단 생략)를 재현
    monkeypatch.setattr(
        bi.qdata_api,
        "load_us_ticker_events",
        (lambda tickers=None: events.copy()) if events is not None else _no_reference,
        raising=False,
    )
    monkeypatch.setattr(
        bi.qdata_api,
        "load_us_ticker_details",
        (lambda tickers=None: details.copy()) if details is not None else _no_reference,
        raising=False,
    )
    monkeypatch.setattr(bi.meta, "meta_df", lambda: meta_df)
    # _as_of()는 krx_flows(640MB 실 레이크)를 로드하는 공용 헬퍼 — 이 빌더 테스트는
    # US 가격 합성만 검증하면 되므로 고정값으로 대체해 레이크 의존·왕복 시간을 없앤다.
    monkeypatch.setattr(bi, "_as_of", lambda: "2026-08-04")


def test_builder_skips_without_cutover_flag(monkeypatch, bi, capsys):
    """US_PRICES_CUTOVER=1 이 없으면 즉시 None + [skip] 로그 — 머지가 곧 전환이
    되지 않도록 막는 게이트. 미러 접근 자체가 시도되지 않아야 한다."""
    monkeypatch.delenv("US_PRICES_CUTOVER", raising=False)

    def boom(**kwargs):
        raise AssertionError("게이트 미통과 시 미러를 읽으면 안 된다")

    monkeypatch.setattr(bi.qdata_api, "load_us_prices", boom)
    assert bi.build_us_prices() is None
    err = capsys.readouterr().err
    assert "[skip]" in err
    assert "US_PRICES_CUTOVER" in err


def test_builder_sorts_by_meta_id_not_ticker(monkeypatch, bi, capsys):
    """서빙(prices.py._us_prices)은 ("meta_id","in",...) 필터로 읽는다 — 출력은
    ticker 알파벳 순이 아니라 meta_id 순이어야 로우그룹 프루닝이 산다(F1)."""
    dates = pd.bdate_range("2026-01-05", periods=3)
    # ticker 알파벳 순(AAA < ZZZ)과 meta_id 순(20 > 1)이 반대가 되도록 구성 —
    # ticker 정렬이면 AAA가 먼저, meta_id 정렬이면 ZZZ(meta_id=1)가 먼저 와야 한다.
    px = pd.concat(
        [
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": "AAA",
                    "close": [10.0, 10.1, 10.2],
                    "adj_close": [10.0, 10.1, 10.2],
                }
            ),
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": "ZZZ",
                    "close": [20.0, 20.1, 20.2],
                    "adj_close": [20.0, 20.1, 20.2],
                }
            ),
        ]
    )
    meta_df = pd.DataFrame({"meta_id": [20, 1], "ticker": ["AAA", "ZZZ"], "iso_code": ["US", "US"]})
    _fake_mirror(
        monkeypatch, bi, px, pd.DataFrame({"ticker": [], "ex_date": [], "cash_amount": []}), meta_df
    )
    out = bi.build_us_prices()
    assert out["meta_id"].tolist() == sorted(out["meta_id"].tolist())
    assert out["meta_id"].iloc[0] == 1  # ZZZ(meta_id=1) 블록이 먼저
    assert out["ticker"].iloc[0] == "ZZZ"


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


def test_builder_guard_cuts_before_unresolved_jump_without_deleting_ticker(
    monkeypatch, bi, capsys
):
    """오염 의심 경계 이전 이력만 버리고 현재 가격 세그먼트는 계속 제공한다."""
    dates = pd.bdate_range("2026-01-05", periods=4)
    px = pd.concat(
        [
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": "GOOD",
                    "close": [100.0, 101.0, 102.0, 103.0],
                    "adj_close": [100.0, 101.0, 102.0, 103.0],
                }
            ),
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": "BAD",
                    "close": [1.0, 1.0, 100.0, 101.0],
                    "adj_close": [1.0, 1.0, 100.0, 101.0],
                }
            ),
        ]
    )
    meta_df = pd.DataFrame({"meta_id": [1, 2], "ticker": ["GOOD", "BAD"], "iso_code": ["US", "US"]})
    _fake_mirror(
        monkeypatch, bi, px, pd.DataFrame({"ticker": [], "ex_date": [], "cash_amount": []}), meta_df
    )
    out = bi.build_us_prices()
    assert set(out.ticker) == {"GOOD", "BAD"}
    bad = out[out.ticker == "BAD"].sort_values("trade_date")
    assert bad["trade_date"].tolist() == [dates[2], dates[3]]
    assert pd.isna(bad["gross_return"].iloc[0])
    assert bad["gross_return"].iloc[1] == pytest.approx(0.01)
    assert "연속성 가드 절단" in capsys.readouterr().err


def test_builder_verified_identity_keeps_legitimate_large_jump(monkeypatch, bi, capsys):
    """상장일로 동일 실체가 확인된 종목의 실제 급등은 이력과 수익률을 보존한다."""
    dates = pd.bdate_range("2021-02-01", periods=4)
    px = pd.DataFrame(
        {
            "date": dates,
            "ticker": "CPSH",
            "close": [6.8, 6.94, 16.54, 16.8],
            "adj_close": [6.8, 6.94, 16.54, 16.8],
        }
    )
    meta_df = pd.DataFrame({"meta_id": [8919], "ticker": ["CPSH"], "iso_code": ["US"]})
    events = pd.DataFrame(columns=["ticker", "event_type", "event_date", "event_ticker"])
    details = pd.DataFrame({"ticker": ["CPSH"], "list_date": [pd.Timestamp("1997-05-09")]})
    _fake_mirror(
        monkeypatch,
        bi,
        px,
        pd.DataFrame({"ticker": [], "ex_date": [], "cash_amount": []}),
        meta_df,
        events=events,
        details=details,
    )

    out = bi.build_us_prices()

    assert out["trade_date"].tolist() == dates.tolist()
    assert out["gross_return"].iloc[2] == pytest.approx(16.54 / 6.94 - 1)
    err = capsys.readouterr().err
    assert "연속성 가드 절단" not in err
    assert "검증된 실체" in err


def test_builder_returns_none_on_mirror_failure(monkeypatch, bi, capsys):
    """미러 읽기 실패 → None (기존 파일 유지) + 경고. 예외가 새어 나가면 안 된다."""
    meta_df = pd.DataFrame({"meta_id": [1], "ticker": ["SPY"], "iso_code": ["US"]})
    monkeypatch.setattr(bi.meta, "meta_df", lambda: meta_df)  # 실 S3 접근 차단

    def boom(**kwargs):
        raise OSError("s3 down")

    monkeypatch.setattr(bi.qdata_api, "load_us_prices", boom)
    assert bi.build_us_prices() is None
    assert "기존 파일 유지" in capsys.readouterr().err


def test_builder_fails_closed_when_required_freshness_is_exceeded(
    monkeypatch, bi, capsys
):
    dates = pd.bdate_range("2026-01-05", periods=3)
    px = pd.DataFrame(
        {
            "date": dates,
            "ticker": "SPY",
            "close": [500.0, 501.0, 502.0],
            "adj_close": [500.0, 501.0, 502.0],
        }
    )
    meta_df = pd.DataFrame({"meta_id": [1], "ticker": ["SPY"], "iso_code": ["US"]})
    _fake_mirror(
        monkeypatch,
        bi,
        px,
        pd.DataFrame({"ticker": [], "ex_date": [], "cash_amount": []}),
        meta_df,
    )
    monkeypatch.setenv("US_PRICES_MAX_AGE_DAYS", "4")

    assert bi.build_us_prices() is None
    assert "필수 신선도 4일 초과" in capsys.readouterr().err


def test_builder_single_row_current_segment_is_still_priceable(monkeypatch, bi, capsys):
    """마지막 관측이 경계여도 현재가는 제공하고 수익률은 미측정으로 남긴다."""
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
    assert out is not None
    assert len(out) == 1
    assert out.iloc[0]["ticker"] == "BAD"
    assert out.iloc[0]["adj_close"] == 100.0
    assert pd.isna(out.iloc[0]["gross_return"])
    err = capsys.readouterr().err
    assert "연속성 가드 절단" in err


def test_dividend_load_floored_and_non_trading_ex_date_flagged(monkeypatch, bi, capsys):
    """load_us_dividends 는 가격과 같은 US_PRICE_FLOOR 부터 불러야 한다 — 안 그러면
    플로어 이전 정상 배당이 매일 밤 '비거래일 배당락 소실'로 오집계된다(리뷰 지적).
    같은 픽스처로 진짜 비거래일(주말) ex_date 배당은 여전히 소실 경고 + 금액 집계가
    나오는지도 함께 확인한다."""
    # 금요일→월요일 사이 주말을 포함해 "거래일 인덱스 범위 안이지만 거래일이 아닌"
    # ex_date를 만든다.
    dates = pd.bdate_range("2026-01-02", periods=4)  # Fri, Mon, Tue, Wed
    px = pd.DataFrame(
        {
            "date": dates,
            "ticker": "SPY",
            "close": [500.0, 501.0, 502.0, 503.0],
            "adj_close": [500.0, 501.0, 502.0, 503.0],
        }
    )
    weekend_ex_date = pd.Timestamp("2026-01-03")  # Saturday — dates 안에 없음
    div = pd.DataFrame({"ticker": ["SPY"], "ex_date": [weekend_ex_date], "cash_amount": [1.5]})
    meta_df = pd.DataFrame({"meta_id": [1], "ticker": ["SPY"], "iso_code": ["US"]})

    calls = []

    def fake_load_us_prices(start=None, end=None, tickers=None, columns=None):
        return px[(px.date >= start) & (px.date <= end)].copy()

    def fake_load_us_dividends(start=None, end=None, tickers=None):
        calls.append({"start": start, "end": end, "tickers": tickers})
        return div.copy()

    monkeypatch.setattr(bi.qdata_api, "load_us_prices", fake_load_us_prices)
    monkeypatch.setattr(bi.qdata_api, "load_us_dividends", fake_load_us_dividends)
    monkeypatch.setattr(bi.meta, "meta_df", lambda: meta_df)
    monkeypatch.setattr(bi, "_as_of", lambda: "2026-08-04")

    out = bi.build_us_prices()

    # (b) load_us_dividends가 가격과 같은 플로어로 호출됐는지
    assert len(calls) == 1
    assert calls[0]["start"] == bi.US_PRICE_FLOOR

    # (a) 실제 비거래일 ex_date는 여전히 소실 경고 + 금액 집계로 잡혀야 한다
    err = capsys.readouterr().err
    assert "비거래일 배당락 소실" in err
    assert "$1.50" in err

    assert set(out.ticker) == {"SPY"}


def test_builder_applies_entity_windows(monkeypatch, bi, capsys):
    """실체 경계 절단 엔드투엔드 — 개명 체인으로 이전 티커 병합 + 상장 전 남의 행 절단."""
    d1, d2, d3, d4 = pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"])
    px = pd.concat(
        [
            pd.DataFrame({"date": [d1, d2], "ticker": "NEWT",
                          "close": [1.0, 1.1], "adj_close": [1.0, 1.1]}),  # 남의 회사 (개명 전)
            pd.DataFrame({"date": [d1, d2], "ticker": "OLDT",
                          "close": [50.0, 51.0], "adj_close": [50.0, 51.0]}),
            pd.DataFrame({"date": [d3, d4], "ticker": "NEWT",
                          "close": [51.5, 52.0], "adj_close": [51.5, 52.0]}),  # 진짜 (개명 후)
        ]
    )
    events = pd.DataFrame({
        "ticker": ["NEWT", "NEWT"],
        "event_type": ["ticker_change", "ticker_change"],
        "event_date": [d1, d3],
        "event_ticker": ["OLDT", "NEWT"],
    })
    details = pd.DataFrame({"ticker": ["NEWT"], "list_date": [d1]})
    meta_df = pd.DataFrame({"meta_id": [7], "ticker": ["NEWT"], "iso_code": ["US"]})
    div = pd.DataFrame({"ticker": [], "ex_date": [], "cash_amount": []})
    _fake_mirror(monkeypatch, bi, px, div, meta_df, events=events, details=details)
    monkeypatch.setattr(bi.meta, "meta_df", lambda: meta_df)

    out = bi.build_us_prices()
    newt = out[out.ticker == "NEWT"].sort_values("trade_date")
    # OLDT 2행 + NEWT 2행 병합, 남의 회사(개명 전 NEWT) 2행 절단 → 4행 연속 시계열
    assert len(newt) == 4
    # 경계에서 가짜 점프가 없어야 한다 (병합 전이라면 50→1 급락·1→51 급등): 최대 ~2%
    assert newt["gross_return"].abs().max() < 0.03
    # TR 앵커: 최신값 = 원 adj_close 최신값
    assert newt["adj_close"].iloc[-1] == pytest.approx(52.0)


def test_builder_proceeds_without_reference_loaders(monkeypatch, bi, capsys):
    """events/details 미러 부재 → 절단 생략 + 경고, 빌드는 계속 (하위호환)."""
    dates = pd.bdate_range("2026-01-05", periods=3)
    px = pd.DataFrame({"date": dates, "ticker": "SPY",
                       "close": [500.0, 505.0, 500.0], "adj_close": [500.0, 505.0, 500.0]})
    div = pd.DataFrame({"ticker": [], "ex_date": [], "cash_amount": []})
    meta_df = pd.DataFrame({"meta_id": [1], "ticker": ["SPY"], "iso_code": ["US"]})
    _fake_mirror(monkeypatch, bi, px, div, meta_df)  # events/details 기본값 = 부재
    monkeypatch.setattr(bi.meta, "meta_df", lambda: meta_df)

    out = bi.build_us_prices()
    assert set(out.ticker) == {"SPY"}
    assert "실체 경계 절단 생략" in capsys.readouterr().err


def test_builder_old_qdata_without_loaders(monkeypatch, bi, capsys):
    """구버전 qdata(로더 부재) → hasattr 분기로 절단 생략 + 경고, 빌드는 계속."""
    dates = pd.bdate_range("2026-01-05", periods=3)
    px = pd.DataFrame({"date": dates, "ticker": "SPY",
                       "close": [500.0, 505.0, 500.0], "adj_close": [500.0, 505.0, 500.0]})
    div = pd.DataFrame({"ticker": [], "ex_date": [], "cash_amount": []})
    meta_df = pd.DataFrame({"meta_id": [1], "ticker": ["SPY"], "iso_code": ["US"]})
    _fake_mirror(monkeypatch, bi, px, div, meta_df)
    monkeypatch.setattr(bi.meta, "meta_df", lambda: meta_df)
    monkeypatch.delattr(bi.qdata_api, "load_us_ticker_events", raising=False)
    monkeypatch.delattr(bi.qdata_api, "load_us_ticker_details", raising=False)

    out = bi.build_us_prices()
    assert set(out.ticker) == {"SPY"}
    assert "구버전" in capsys.readouterr().err
