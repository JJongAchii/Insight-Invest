"""라인 설정 로더 — 설계값은 config.yaml 한 곳에만 둔다(quant-lab 불변식 4)."""

from __future__ import annotations

from pathlib import Path

import yaml

LINE_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = LINE_DIR / "config.yaml"


def load_config(path: str | Path | None = None) -> dict:
    return yaml.safe_load(Path(path or CONFIG_PATH).read_text())
