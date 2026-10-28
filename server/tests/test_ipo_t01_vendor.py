"""공모주 t01 결정 경로 사본 — 옮긴 파일이 quant-lab 원본과 바이트까지 같고 과거 결정을 그대로 낸다.

- 사본 해시: `server/strategies/ipo_open_entry/VENDOR.json`(scripts/vendor_ipo_t01.py가 quant-lab 커밋에서 기록)
- 데이터셋: 운용 규칙(op-day1-v2) 머리말의 dataset_manifest_sha256과 같은 manifest
- 결정 재현: 개발 구간 평가 사건 616건의 매수 여부·지정가 배수가 quant-lab walk-forward 산출
  (`tests/fixtures/ipo_t01_decisions.csv`, 같은 커밋)과 같다
"""

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from module import ipo_t01

LINE = ipo_t01.LINE_DIR
FIXTURE = Path(__file__).parent / "fixtures" / "ipo_t01_decisions.csv"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_vendored_files_match_the_recorded_quant_lab_bytes():
    record = json.loads((LINE / "VENDOR.json").read_text())
    assert len(record["commit"]) == 40
    for rel, digest in record["files"].items():
        assert _sha(LINE / rel) == digest, rel
    data = LINE / record["dataset"]["path"]
    for name, digest in record["dataset"]["files"].items():
        assert _sha(data / name) == digest, name
    # 사본에 원본에 없는 파이썬 파일이 끼지 않았다(손으로 고친 모듈을 막는다)
    shipped = {p.relative_to(LINE).as_posix() for p in (LINE / "src").rglob("*.py")}
    assert shipped == {r for r in record["files"] if r.endswith(".py")}


def test_dataset_is_the_operating_rule_dataset():
    rule = ipo_t01.rule()
    assert rule["spec"] == "op-day1-v2"
    assert _sha(ipo_t01.DATASET / "manifest.json") == rule["dataset_manifest_sha256"]
    assert rule["strategy_args"]["entry_cap"] == 1.5


def test_walk_forward_reproduces_quant_lab_decisions():
    expected = pd.read_csv(FIXTURE)
    cfg = ipo_t01.config()
    got = ipo_t01.evaluate.walk_forward(ipo_t01.make_strategy, ipo_t01.dev_table(), cfg)
    got = got.set_index("event_id").loc[expected["event_id"]]
    assert got["buy"].astype(bool).tolist() == expected["buy"].astype(bool).tolist()
    bought = expected["buy"].astype(bool).to_numpy()
    assert got["limit_mult"].to_numpy()[bought].tolist() == pytest.approx(
        expected["limit_mult"].to_numpy()[bought].tolist()
    )
    assert int(bought.sum()) == 62 and len(expected) == 616
