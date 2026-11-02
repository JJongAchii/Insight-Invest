"""공모주 t12 결정 경로 사본 — quant-lab recall-v1 t12와 같은 결정을 낸다(계약 ipo-live-ops v2 II_T12).

- 기준 파일: `tests/fixtures/ipo_t12_decisions.csv` — scripts/vendor_ipo_t01.py가 같은 quant-lab 커밋의
  t12 산출(`docs/evidence/runs/recall-v1/t12.json`)에서 만든다. 해시는 VENDOR.json의 t12 절에 있다
- 결정 재현: 개발 구간 평가 사건 616건의 매수 여부·지정가 배수가 quant-lab walk-forward 산출과 같다
- 운영 경로: 학습 표(라벨 확정 사건)·한 행 결정·개발 구간 뒤 사건의 체결 상태 라벨이 개발 표와 같은 값을 낸다
"""

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from module import ipo_t01, ipo_t12

from ipo_open_entry.operate import decision  # isort: skip
from ipo_open_entry.recall import models as recall_models  # isort: skip

FIXTURE = Path(__file__).parent / "fixtures" / "ipo_t12_decisions.csv"
VARIANT = {
    "family": "union",
    "selection": "oof",
    "institution": {"interactions": False, "shrinkage": 1000, "institutional_sign": "free"},
    "complement": {"mode": "states", "interactions": False, "shrinkage": 300},
}
LABELS = [
    "sig_filled",
    "sig_net",
    "sig_fill_type",
    "sig_growth",
    "sig_available",
    "label_available",
]


@pytest.fixture(scope="module")
def expected() -> pd.DataFrame:
    return pd.read_csv(FIXTURE).set_index("event_id")


def test_t12_record_names_the_quant_lab_trial_and_fixture():
    record = json.loads((ipo_t01.LINE_DIR / "VENDOR.json").read_text())["t12"]
    assert record["variant"] == VARIANT
    assert record["config_digest"] == "3bf9281aa50f"
    assert len(record["trial_commit"]) == 40
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == record["fixture_sha256"]
    assert ipo_t12.rule()["spec"] == ipo_t12.SPEC == "recall-v1-t12"


def test_walk_forward_reproduces_quant_lab_t12_decisions(expected):
    got, _ = recall_models.walk_forward(ipo_t12.dev_table(), VARIANT)
    got = got.set_index("event_id").loc[expected.index]
    assert got["buy"].astype(bool).tolist() == expected["buy"].astype(bool).tolist()
    assert got["additional_buy"].astype(bool).tolist() == expected["additional_buy"].tolist()
    bought = expected["buy"].astype(bool).to_numpy()
    assert got["limit_mult"].to_numpy()[bought].tolist() == pytest.approx(
        expected["limit_mult"].to_numpy()[bought].tolist()
    )
    # 점수는 BLAS 축약 순서만큼 다를 수 있다(quant-lab 재현 허용오차 1e-8)
    assert got["score"].to_numpy() == pytest.approx(expected["score"].to_numpy(), abs=1e-8)
    assert len(expected) == 616 and int(bought.sum()) == 130
    assert int(expected["additional_buy"].sum()) == 39


@pytest.mark.parametrize(
    "event_id",
    [
        "00112998_20250124000643",  # 1차 점수 매수
        "01498974_20230616000519",  # t01 패스 → 체결 상태 보완으로 매수
        "00108612_20231116000509",  # 패스
    ],
)
def test_one_listing_decision_matches_the_walk_forward(expected, event_id):
    """운영의 한 사건 결정(분기 시작 전 라벨 확정 사건으로 학습 → 그 행 결정)이 walk-forward와 같다."""
    dev = ipo_t12.dev_table()
    row = dev[dev["event_id"] == event_id]
    qs = decision.quarter_start(row["listing_date"].iloc[0])
    train = ipo_t12.training_table(dev, None, qs)
    assert (train["label_available"] < qs).all() and (train["listing_date"] < qs).all()
    made = ipo_t12.decide(train, row, qs)
    want = expected.loc[event_id]
    assert made["buy"] == bool(want["buy"])
    assert made["additional_buy"] == bool(want["additional_buy"])
    assert made["score"] == pytest.approx(want["score"], abs=1e-8)
    assert made["limit_mult"] == (1.5 if want["buy"] else None)


def test_post_dev_labels_match_the_development_table():
    """개발 구간 뒤 사건에 붙이는 체결 상태 라벨이 개발 표(quant-lab이 쓴 표)와 같은 값이다.

    개발 데이터를 2025-01-01에서 나눠 뒤쪽을 '개발 구간 뒤 사건'처럼 넣는다.
    """
    data, cfg = ipo_t01.dev_data(), ipo_t01.config()
    cut = pd.Timestamp("2025-01-01")
    late = data["events"]["listing_date"] >= cut
    ids = set(data["events"].loc[late, "event_id"])
    early = {
        "events": data["events"][~late],
        "fields": data["fields"][~data["fields"]["event_id"].isin(ids)],
        "bars": data["bars"][~data["bars"]["event_id"].isin(ids)],
        "index": data["index"],
    }
    post = {
        "events": data["events"][late].reset_index(drop=True),
        "fields": data["fields"][data["fields"]["event_id"].isin(ids)].set_index("event_id"),
        "bars": data["bars"][data["bars"]["event_id"].isin(ids)],
        "contaminated": [],
    }
    close = data["index"].set_index("date")["kosdaq"].dropna()
    table = ipo_t12.post_dev_table(early, post, close, cfg).set_index("event_id")
    dev = ipo_t12.dev_table().set_index("event_id").loc[table.index]
    assert len(table) > 100
    pd.testing.assert_frame_equal(table[LABELS], dev[LABELS], check_dtype=False)
