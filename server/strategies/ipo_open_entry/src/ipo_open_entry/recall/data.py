"""Recall-only input boundary; reuse the frozen, audited execution labels."""

from __future__ import annotations

import hashlib
import json

import yaml

from ipo_open_entry import evaluate
from ipo_open_entry.config import CONFIG_PATH, LINE_DIR
from ipo_open_entry.models import blocks as B
from ipo_open_entry.models.linear import CONTROL
from ipo_open_entry.signal.data import (  # noqa: F401
    FILES,
    Path,
    build_table,
    digest,
    load,
    mature_before,
)

RECALL_CONFIG = LINE_DIR / "config-recall-v1.yaml"


def spec():
    return yaml.safe_load(RECALL_CONFIG.read_text())


def config_digest(variant):
    payload = {"base": digest(CONFIG_PATH), "recall": digest(RECALL_CONFIG), "variant": variant}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def predictors(table):
    """Only keys and prelisting raw fields. No current fill, price or outcome."""
    columns = [*evaluate.KEY_COLUMNS, *B.feature_columns(B.ALL_BLOCKS), CONTROL]
    return table[columns].copy()
