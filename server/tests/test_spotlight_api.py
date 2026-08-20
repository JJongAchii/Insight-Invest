"""GET /insight/spotlight 계약 — parquet 부재 시 빈 응답(500 금지), 존재 시
그룹이 서빙 시점 signal_study의 20일 기준선 대비 중앙값 내림차순으로 정렬된다."""

import asyncio

import pandas as pd


def _write(tmp_path, name, df):
    d = tmp_path / "insight"
    d.mkdir(exist_ok=True)
    df.to_parquet(d / name, index=False)


def test_spotlight_absent_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    import app.routers.insight as insight

    assert asyncio.run(insight.get_spotlight()) == {"as_of": None, "groups": []}


_SPOT_COLS = [
    "signal_type",
    "rank",
    "ticker",
    "name",
    "market",
    "close",
    "chg_pct",
    "mktcap",
    "streak",
    "intensity_20d",
    "ret_20d",
    "hold_days",
    "dist_pct",
    "also_in",
    "as_of",
]
_STUDY_COLS = [
    "signal_type",
    "horizon",
    "n_events",
    "mean_excess",
    "median_excess",
    "hit_rate",
    "avg_fwd_ret",
    "as_of",
    "calculation_version",
]


def test_spotlight_groups_ordered_and_marked(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    import app.routers.insight as insight

    # parquet에는 study에 없는 bull_divergence를 먼저 넣는다 — 정렬이 study 기반임과
    # study 없는 그룹이 마지막으로 가는 규칙을 증명하기 위해
    spot = pd.DataFrame(
        [
            [
                "bull_divergence",
                1,
                "000001",
                "매집A",
                "KOSPI",
                1000.0,
                -1.0,
                2e10,
                3,
                1.5,
                -6.0,
                None,
                None,
                "[]",
                "2026-07-31",
            ],
            [
                "frgn_streak10",
                1,
                "000003",
                "연속C",
                "KOSDAQ",
                500.0,
                0.5,
                3e10,
                12,
                0.8,
                2.0,
                None,
                None,
                "[]",
                "2026-07-31",
            ],
            [
                "near_52w_high_hold",
                1,
                "000006",
                "고점F",
                "KOSPI",
                900.0,
                0.1,
                5e10,
                11,
                0.2,
                8.0,
                30.0,
                -0.5,
                '["frgn_streak10"]',
                "2026-07-31",
            ],
        ],
        columns=_SPOT_COLS,
    )
    study = pd.DataFrame(
        [
            ["baseline", 20, 6_000_000, -0.5, -1.80, 41.2, 3.0, "2026-07-31", "kr_price_return_v2"],
            [
                "near_52w_high_hold",
                20,
                282_143,
                0.5,
                -1.26,
                44.2,
                4.0,
                "2026-07-31",
                "kr_price_return_v2",
            ],
            ["frgn_streak10", 20, 1_847, 0.2, -1.29, 43.0, 3.5, "2026-07-31", "kr_price_return_v2"],
        ],
        columns=_STUDY_COLS,
    )
    _write(tmp_path, "spotlight.parquet", spot)
    _write(tmp_path, "signal_study.parquet", study)

    monkeypatch.setattr(
        insight.meta_store,
        "meta_df",
        lambda: pd.DataFrame(
            {
                "meta_id": [1],
                "ticker": ["000006"],
                "iso_code": ["KR"],
                "name": ["고점F"],
                "security_type": ["stock"],
                "sector": ["기타"],
            }
        ),
    )
    monkeypatch.setattr(
        insight.holdings_store, "list_items", lambda: pd.DataFrame({"meta_id": [1]})
    )
    monkeypatch.setattr(
        insight.watchlist_store, "list_items", lambda: pd.DataFrame({"meta_id": [1]})
    )

    res = asyncio.run(insight.get_spotlight())
    # +0.54%p(near) > +0.51%p(streak) > None(bull) — parquet 순서 무시하고
    # study 기반 정렬, study 없는 그룹은 마지막
    assert [g["signal_type"] for g in res["groups"]] == [
        "near_52w_high_hold",
        "frgn_streak10",
        "bull_divergence",
    ]
    near = res["groups"][0]
    assert near["evidence"] is not None and "기준선 대비" in near["evidence"]
    item = near["items"][0]
    assert item["meta_id"] == 1
    assert item["link"] == "/stock/1"
    assert item["mine"] == "holding"
    assert item["also_in"] == ["frgn_streak10"]
    assert item["hold_days"] == 30
    # meta에 없는 종목은 링크 없이 내려간다 (500 금지)
    streak_item = res["groups"][1]["items"][0]
    assert streak_item["meta_id"] is None and streak_item["mine"] is None
    # study에 없는 그룹은 근거 없음
    bull = res["groups"][2]
    assert bull["signal_type"] == "bull_divergence"
    assert bull["evidence"] is None
