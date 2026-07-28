"""signal_stats 순수 함수 — 기준선 대비 계산과 문장 포맷."""

import numpy as np
import pandas as pd
import pytest

from module import signal_stats
from module.signal_stats import evidence_phrase, excess_vs_baseline, format_evidence


def _study() -> pd.DataFrame:
    """설계 문서 §1.1의 20일 실측치를 축약한 테스트 픽스처."""
    return pd.DataFrame(
        [
            # signal_type, horizon, n_events, median_excess, hit_rate
            ("baseline", 20, 6000695, -1.80, 41.2),
            ("spike_1d_5", 20, 276018, -4.19, 38.1),
            ("baseline", 60, 5877263, -3.83, 39.6),
            ("near_52w_high", 60, 12000, -2.89, 42.0),
            ("broken", 20, 100, np.nan, np.nan),
        ],
        columns=["signal_type", "horizon", "n_events", "median_excess", "hit_rate"],
    )


def test_excess_vs_baseline_subtracts_the_baseline_row():
    n, med, hit = excess_vs_baseline(_study(), "spike_1d_5", 20)
    assert n == 276018
    assert med == pytest.approx(-2.39)
    assert hit == pytest.approx(-3.1)


def test_excess_vs_baseline_is_horizon_scoped():
    """60일 신호는 60일 기준선과 비교해야 한다 — 지평선을 섞으면 안 된다."""
    _, med, _ = excess_vs_baseline(_study(), "near_52w_high", 60)
    assert med == pytest.approx(0.94)


def test_excess_vs_baseline_returns_none_when_baseline_missing():
    """구 parquet에는 baseline 행이 없다 — 그 경우 값을 지어내지 않는다."""
    df = _study()
    df = df[df["signal_type"] != "baseline"]
    assert excess_vs_baseline(df, "spike_1d_5", 20) is None


def test_excess_vs_baseline_returns_none_for_unknown_signal():
    assert excess_vs_baseline(_study(), "does_not_exist", 20) is None


def test_excess_vs_baseline_returns_none_when_stats_are_nan():
    """표본이 비어 통계가 NaN인 행은 문장으로 만들지 않는다."""
    assert excess_vs_baseline(_study(), "broken", 20) is None


def test_format_evidence_abbreviates_large_counts():
    s = format_evidence(276018, -2.39, -3.1, 20)
    assert s == "과거 27.6만건 · 20일 뒤 기준선 대비 -2.4%p (승률 -3.1%p)"


def test_format_evidence_keeps_small_counts_exact():
    s = format_evidence(8500, 1.2, 0.5, 60)
    assert s == "과거 8,500건 · 60일 뒤 기준선 대비 +1.2%p (승률 +0.5%p)"


def test_evidence_phrase_composes_lookup_and_format():
    assert evidence_phrase("spike_1d_5", 20, df=_study()) == (
        "과거 27.6만건 · 20일 뒤 기준선 대비 -2.4%p (승률 -3.1%p)"
    )


def test_evidence_phrase_returns_none_when_data_is_unusable():
    assert evidence_phrase("does_not_exist", 20, df=_study()) is None


def test_evidence_phrase_explicit_none_short_circuits_without_reloading(monkeypatch):
    """df=None을 명시하면 load_study()를 다시 호출하지 않는다.

    attention.py처럼 루프 밖에서 load_study()를 한 번만 호출해 그 결과(부재
    시 None)를 매 아이템에 그대로 넘기는 호출부가 있다. None을 "인자 미지정"
    과 혼동하면 호출부의 캐싱이 무력화되고 아이템마다 재로드가 일어난다.
    """
    calls = []

    def _counting_load_study():
        calls.append(1)
        return None

    monkeypatch.setattr(signal_stats, "load_study", _counting_load_study)

    assert evidence_phrase("spike_1d_5", 20, df=None) is None
    assert len(calls) == 0


def test_evidence_phrase_omitted_df_still_loads_exactly_once(monkeypatch):
    """df를 아예 안 넘기면 여전히 load_study()로 한 번만 로드한다."""
    calls = []

    def _counting_load_study():
        calls.append(1)
        return _study()

    monkeypatch.setattr(signal_stats, "load_study", _counting_load_study)

    result = evidence_phrase("spike_1d_5", 20)
    assert result == "과거 27.6만건 · 20일 뒤 기준선 대비 -2.4%p (승률 -3.1%p)"
    assert len(calls) == 1
