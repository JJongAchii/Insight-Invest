#!/usr/bin/env python
"""공모주 t01 결정 경로를 quant-lab에서 바이트 그대로 옮긴다(계약 ipo-live-ops II_ENGINE).

    python scripts/vendor_ipo_t01.py --quant-lab ~/Quant/quant-lab --commit <quant-lab 커밋>

`git show <commit>:<경로>`로 읽어 `server/strategies/ipo_open_entry/` 아래 같은 상대 경로에 쓰고,
파일별 sha256을 `VENDOR.json`에 남긴다. 옮긴 파일은 손으로 고치지 않는다 — 테스트
(`server/tests/test_ipo_t01_vendor.py`)가 해시를 대조한다. quant-lab 쪽 규칙이 바뀌면 이 스크립트를 새
커밋으로 다시 돌린다.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

LINE = "strategies/ipo-open-entry"
DEST = Path(__file__).resolve().parents[1] / "server" / "strategies" / "ipo_open_entry"
#: t01(op-day1-v2) 결정 경로 — 운용 규칙의 FROZEN_CODE 중 패턴 전략을 뺀 것과 거래일 달력·결정 조립
FILES = (
    "config.yaml",
    "src/ipo_open_entry/__init__.py",
    "src/ipo_open_entry/config.py",
    "src/ipo_open_entry/rules.py",
    "src/ipo_open_entry/fields.py",
    "src/ipo_open_entry/features.py",
    "src/ipo_open_entry/engine.py",
    "src/ipo_open_entry/evaluate.py",
    "src/ipo_open_entry/models/__init__.py",
    "src/ipo_open_entry/models/regression.py",
    "src/ipo_open_entry/models/linear.py",
    "src/ipo_open_entry/models/blocks.py",
    "src/ipo_open_entry/models/common.py",
    "src/ipo_open_entry/operate/__init__.py",
    "src/ipo_open_entry/operate/calendar.py",
    "src/ipo_open_entry/operate/decision.py",
    "docs/operating-rule-day1.md",
)
#: 운용 규칙의 학습 데이터셋(개발 구간 2015-06-15~2026-09-09 상장분) — data/dev-20260909-v4 → v4r
DATASET = ("events", "fields", "bars", "index")
DATASET_SRC = "data/dev-20260909-v4r"
DATASET_DEST = "data/dev-20260909-v4"


def _show(repo: Path, commit: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), "show", f"{commit}:{LINE}/{path}"], capture_output=True, check=True
    ).stdout


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quant-lab", type=Path, required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument(
        "--dataset-dir",
        type=Path,
        required=True,
        help="운용 규칙 데이터셋 폴더(git 밖, 예: <quant-lab>/strategies/ipo-open-entry/data/"
        "dev-20260909-v4r) — manifest sha256을 운용 규칙과 대조한다",
    )
    args = ap.parse_args()
    commit = subprocess.run(
        ["git", "-C", str(args.quant_lab), "rev-parse", args.commit],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()
    files = {}
    for rel in FILES:
        data = _show(args.quant_lab, commit, rel)
        out = DEST / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        files[rel] = hashlib.sha256(data).hexdigest()
    manifest = (args.dataset_dir / "manifest.json").read_bytes()
    dataset = {"manifest.json": hashlib.sha256(manifest).hexdigest()}
    dest = DEST / DATASET_DEST
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "manifest.json").write_bytes(manifest)
    for name in DATASET:
        data = (args.dataset_dir / f"{name}.parquet").read_bytes()
        (dest / f"{name}.parquet").write_bytes(data)
        dataset[f"{name}.parquet"] = hashlib.sha256(data).hexdigest()
    record = {
        "source": "JJongAchii/quant-lab",
        "line": LINE,
        "commit": commit,
        "files": files,
        "dataset": {"source": f"{LINE}/{DATASET_SRC}", "path": DATASET_DEST, "files": dataset},
    }
    (DEST / "VENDOR.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(f"옮김: {len(files)}개 파일 + 데이터셋 {len(dataset)}개 @ {commit[:12]}")


if __name__ == "__main__":
    main()
