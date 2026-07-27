import pandas as pd
import pytest

from module.brief.evidence import attach_base_rates, match_base_rate_signals


def test_streak_경계_10은_발화_9는_미발화():
    assert "frgn_streak10" in match_base_rate_signals(
        {"streak": 10, "intensity_20d": 0.0, "ret_20d": 0.0}
    )
    assert "frgn_streak10" not in match_base_rate_signals(
        {"streak": 9, "intensity_20d": 0.0, "ret_20d": 0.0}
    )


def test_intensity_경계_1_0은_발화_0_99는_미발화():
    assert "high_intensity" in match_base_rate_signals(
        {"streak": 0, "intensity_20d": 1.0, "ret_20d": 0.0}
    )
    assert "high_intensity" not in match_base_rate_signals(
        {"streak": 0, "intensity_20d": 0.99, "ret_20d": 0.0}
    )


def test_bull_divergence는_ret_20d가_정확히_마이너스5면_미발화():
    # signal_study 조건은 ret_20d < -5 (이하가 아니라 미만)
    assert "bull_divergence" not in match_base_rate_signals(
        {"streak": 0, "intensity_20d": 0.31, "ret_20d": -5.0}
    )
    assert "bull_divergence" in match_base_rate_signals(
        {"streak": 0, "intensity_20d": 0.31, "ret_20d": -5.01}
    )


def test_flows_signals_divergence_라벨과_갈리는_구간():
    """★ 회귀 방지의 핵심.

    ret_20d=-3, intensity=0.5는 flows_signals에서 divergence="bull"로 라벨링되지만
    signal_study의 bull_divergence(ret_20d < -5)에는 해당하지 않는다.
    divergence 라벨을 조회 키로 쓰면 -5 기준 통계가 잘못 딸려온다.
    """
    row = {"streak": 0, "intensity_20d": 0.5, "ret_20d": -3.0}
    assert "bull_divergence" not in match_base_rate_signals(row)


def test_결측치는_예외없이_미발화():
    assert match_base_rate_signals({"streak": None, "intensity_20d": None, "ret_20d": None}) == []
    assert match_base_rate_signals({}) == []


def test_복수_신호_동시_발화():
    row = {"streak": 12, "intensity_20d": 1.5, "ret_20d": -8.0}
    matched = match_base_rate_signals(row)
    assert set(matched) == {"frgn_streak10", "high_intensity", "bull_divergence"}


def test_attach_base_rates가_지평선별로_묶는다():
    study = pd.DataFrame(
        [
            {
                "signal_type": "frgn_streak10",
                "horizon": 5,
                "n_events": 1800,
                "median_excess": 0.4,
                "hit_rate": 51.2,
                "mean_excess": 0.5,
                "avg_fwd_ret": 0.9,
            },
            {
                "signal_type": "frgn_streak10",
                "horizon": 20,
                "n_events": 1847,
                "median_excess": 2.1,
                "hit_rate": 54.0,
                "mean_excess": 2.4,
                "avg_fwd_ret": 3.1,
            },
            {
                "signal_type": "high_intensity",
                "horizon": 20,
                "n_events": 900,
                "median_excess": 1.0,
                "hit_rate": 52.0,
                "mean_excess": 1.2,
                "avg_fwd_ret": 2.0,
            },
        ]
    )
    out = attach_base_rates(["frgn_streak10"], study)
    assert set(out) == {"frgn_streak10"}
    assert out["frgn_streak10"]["h20"] == {"n_events": 1847, "median_excess": 2.1, "hit_rate": 54.0}
    assert "h5" in out["frgn_streak10"]


def test_attach_base_rates는_결측_통계를_None으로():
    study = pd.DataFrame(
        [
            {
                "signal_type": "high_intensity",
                "horizon": 20,
                "n_events": 0,
                "median_excess": float("nan"),
                "hit_rate": float("nan"),
                "mean_excess": float("nan"),
                "avg_fwd_ret": float("nan"),
            }
        ]
    )
    out = attach_base_rates(["high_intensity"], study)
    assert out["high_intensity"]["h20"]["median_excess"] is None
    assert out["high_intensity"]["h20"]["n_events"] == 0
