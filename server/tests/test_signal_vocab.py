"""signal_type 어휘 가드 — 빌더와 소비자가 손으로 맞춘 문자열 목록이 어긋나지
않는지 확인한다.

signal_study.parquet는 untyped이라, `scripts/build_insights.py`에서
signal_type 문자열을 하나 rename하면 `server/app/routers/attention.py`·
`scripts/send_briefing.py`·`client/src/state/api.ts`는 아무 에러 없이
그냥 그 신호를 못 찾는다(조용한 no-op). per-signal 리뷰는 이 드리프트를
구조적으로 볼 수 없다 — 이 테스트가 빌더의 실제 어휘를 얼린(frozen) 기대값과
비교해 렌더링 대신 CI에서 잡아낸다.

빌더 함수 소스를 AST로 파싱해 state_conds/daily_conds 딕셔너리의 키를
추출한다 — build_signal_study()를 직접 실행하려면 qdata 레이크 전체가
필요해 유닛 테스트로는 너무 무겁다.
"""

import ast
import inspect
import os
import sys

import pytest

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

try:
    import build_insights

    _IMPORT_ERROR = None
except Exception as e:  # 환경 문제(자격증명·의존성 부재 등)는 스킵, 에러 아님
    build_insights = None
    _IMPORT_ERROR = e


# 이 branch(feat/signal-baseline)가 만드는 최종 어휘 — 12종(baseline 포함).
EXPECTED_SIGNAL_TYPES = frozenset(
    {
        "baseline",
        "bull_divergence",
        "frgn_streak10",
        "high_intensity",
        "spike_5d_15",
        "spike_20d_20",
        "spike_20d_50",
        "near_52w_high_entry",
        "spike_1d_5",
        "spike_1d_5_10",
        "spike_1d_10",
        "drop_1d_5",
    }
)

# attention.py가 signal_stats.evidence_phrase에 넘기는 literal 3개
# (server/app/routers/attention.py의 가격 급변 분기).
ATTENTION_SIGNAL_TYPES = frozenset({"spike_1d_10", "spike_1d_5_10", "drop_1d_5"})


def _skip_if_import_failed():
    if build_insights is None:
        pytest.skip(f"build_insights import 실패 (환경 문제): {_IMPORT_ERROR}")


def _emitted_vocabulary() -> set[str]:
    """build_signal_study 소스에서 state_conds/daily_conds 딕셔너리 키 + baseline."""
    source = inspect.getsource(build_insights.build_signal_study)
    tree = ast.parse(source)

    keys: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Dict)
        ):
            continue
        name = node.targets[0].id
        if name in ("state_conds", "daily_conds"):
            keys[name] = {
                k.value
                for k in node.value.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            }

    assert "state_conds" in keys, "state_conds 딕셔너리를 찾지 못함 — 변수명이 바뀌었나?"
    assert "daily_conds" in keys, "daily_conds 딕셔너리를 찾지 못함 — 변수명이 바뀌었나?"
    return keys["state_conds"] | keys["daily_conds"] | {"baseline"}


def test_builder_signal_vocabulary_matches_frozen_set():
    """빌더가 정의하는 signal_type 전체가 이 테스트의 frozen 목록과 정확히 같아야 한다.

    빌더에서 신호를 추가/삭제/rename하면 이 assert가 깨진다 — 그때 네 소비자
    (attention.py, send_briefing.py, api.ts, 이 파일)를 함께 검토하라는 신호다.
    """
    _skip_if_import_failed()
    assert _emitted_vocabulary() == EXPECTED_SIGNAL_TYPES


def test_attention_signal_literals_are_in_builder_vocabulary():
    """attention.py가 쓰는 literal 3개는 항상 빌더 어휘의 부분집합이어야 한다."""
    _skip_if_import_failed()
    assert ATTENTION_SIGNAL_TYPES <= _emitted_vocabulary()
