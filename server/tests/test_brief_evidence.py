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


from module.brief.evidence import build_evidence_pack


def _sources():
    """최소 픽스처 — 모든 소스가 존재하는 정상 케이스."""
    return {
        "meta": {"name": "테스트전자", "market": "KOSPI", "sector": "반도체"},
        "flows_signals": pd.DataFrame(
            [
                {
                    "ticker": "005930",
                    "investor": "frgn",
                    "streak": 12,
                    "net_20d": 5e11,
                    "intensity_20d": 1.4,
                    "ret_20d": -6.0,
                    "divergence": "bull",
                    "close": 70000,
                    "chg_pct": 1.2,
                    "mktcap": 4e14,
                },
                {
                    "ticker": "005930",
                    "investor": "inst",
                    "streak": -3,
                    "net_20d": -1e11,
                    "intensity_20d": -0.2,
                    "ret_20d": -6.0,
                    "divergence": None,
                    "close": 70000,
                    "chg_pct": 1.2,
                    "mktcap": 4e14,
                },
            ]
        ),
        "signal_study": pd.DataFrame(
            [
                {
                    "signal_type": "frgn_streak10",
                    "horizon": 20,
                    "n_events": 1847,
                    "median_excess": 2.1,
                    "hit_rate": 54.0,
                    "mean_excess": 2.4,
                    "avg_fwd_ret": 3.1,
                }
            ]
        ),
        "factor_pct": pd.DataFrame(
            [
                {
                    "ticker": "005930",
                    "momentum": 92.0,
                    "value": 19.0,
                    "size": 3.0,
                    "lowvol": 61.0,
                }
            ]
        ),
        "sector_perf": pd.DataFrame(
            [
                {
                    "market": "KOSPI",
                    "sector": "반도체",
                    "ret_1d": 0.8,
                    "ret_1w": 2.1,
                    "ret_1m": 5.5,
                    "ret_3m": 12.0,
                    "ret_ytd": 20.0,
                    "weight": 18.4,
                }
            ]
        ),
        "breadth": {"advancers": 480, "decliners": 420, "above_ma20_pct": 55.2},
        "valuation": {"market": "KOSPI", "per": 11.2, "pbr": 1.05, "div_yield": 2.1},
        "regime": {"phase": "회복", "risk_gauge": 42},
        "holdings": {
            "005930": {
                "shares": 10,
                "avg_cost": 65000,
                "pnl_pct": 7.7,
                "weight_pct": 12.0,
            }
        },
        "news": [{"title": "테스트 헤드라인", "source": "연합", "date": "2026-07-25"}],
        "prior_brief": {
            "as_of": "2026-07-20",
            "stance_note": "수급 우위",
            "price_change_since": 4.1,
        },
    }


def test_evidence_pack_기본_구조():
    pack = build_evidence_pack("005930", _sources())
    assert set(pack) == {
        "identity",
        "flows",
        "base_rates",
        "factors",
        "sector",
        "market",
        "holding",
        "news",
        "prior_brief",
    }
    assert pack["identity"]["ticker"] == "005930"
    assert pack["identity"]["name"] == "테스트전자"


def test_evidence_pack이_frgn_기준으로_기저율을_붙인다():
    pack = build_evidence_pack("005930", _sources())
    # streak 12 → frgn_streak10 발화, intensity 1.4 → high_intensity 발화,
    # ret_20d -6.0 & intensity 1.4 → bull_divergence 발화.
    # 단 signal_study에 행이 있는 건 frgn_streak10뿐이므로 그것만 남는다.
    assert set(pack["base_rates"]) == {"frgn_streak10"}
    assert pack["base_rates"]["frgn_streak10"]["h20"]["n_events"] == 1847


def test_evidence_pack이_투자자별_수급을_분리한다():
    pack = build_evidence_pack("005930", _sources())
    assert pack["flows"]["frgn"]["streak"] == 12
    assert pack["flows"]["inst"]["streak"] == -3


def test_미보유_종목은_holding이_None():
    src = _sources()
    src["holdings"] = {}
    pack = build_evidence_pack("005930", src)
    assert pack["holding"] is None


def test_소스_결손시_해당_섹션만_None이고_예외없음():
    src = _sources()
    src["factor_pct"] = pd.DataFrame(columns=["ticker", "momentum", "value", "size", "lowvol"])
    src["news"] = []
    src["prior_brief"] = None
    pack = build_evidence_pack("005930", src)
    assert pack["factors"] is None
    assert pack["news"] == []
    assert pack["prior_brief"] is None
    assert pack["identity"]["ticker"] == "005930"  # 나머지는 정상


def test_flows_signals에_없는_종목이면_ValueError():
    with pytest.raises(ValueError, match="flows_signals"):
        build_evidence_pack("999999", _sources())
