"""signal_stats 순수 함수 — 기준선 대비 계산과 문장 포맷."""

import numpy as np
import pandas as pd
import pytest

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
