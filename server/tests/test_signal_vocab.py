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


# 빌더가 만드는 최종 어휘 — 13종(baseline 포함).
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
        "near_52w_high_hold",
        "spike_1d_5",
        "spike_1d_5_10",
        "spike_1d_10",
        "drop_1d_5",
    }
)

# attention.py 가격 급변 분기가 signal_stats.evidence_phrase에 넘기는 literal 3개.
# 아래 테스트는 이 상수를 attention.py 소스에서 추출한 실제 값과 대조한다 —
# 손으로 적은 목록끼리만 비교하면 "+5~10% 구간이 상위집합(spike_1d_5) 통계를
# 인용"하던 원래 버그로 되돌아가도 통과해버린다(둘 다 빌더 어휘의 원소라서).
ATTENTION_SIGNAL_TYPES = frozenset({"spike_1d_10", "spike_1d_5_10", "drop_1d_5"})

_ATTENTION_PY = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "app", "routers", "attention.py")
)


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


def _attention_vocabulary() -> set[str]:
    """attention.py의 `sig, sev, word = "<signal>", ...` 분기에서 signal_type 추출.

    빌더처럼 임포트해서 읽지 않고 소스를 파싱한다 — attention.py를 임포트하면
    datastore·qdata 체인이 통째로 딸려와 유닛 테스트로는 무겁다.
    """
    with open(_ATTENTION_PY, encoding="utf-8") as f:
        tree = ast.parse(f.read())

    found = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        target, value = node.targets[0], node.value
        if not (isinstance(target, ast.Tuple) and isinstance(value, ast.Tuple)):
            continue
        names = [n.id for n in target.elts if isinstance(n, ast.Name)]
        if names[:1] != ["sig"] or not value.elts:
            continue
        first = value.elts[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            found.add(first.value)
    return found


def test_attention_signal_literals_match_source_and_builder():
    """attention.py가 실제로 쓰는 literal이 기대값과 같고, 빌더 어휘 안에 있어야 한다.

    앞 assert가 핵심이다 — 부분집합만 확인하면 +5~10% 구간을 spike_1d_5(=상위집합)로
    되돌려도 통과한다. 소스에서 뽑은 집합과 정확히 일치시켜야 그 회귀가 잡힌다.
    """
    _skip_if_import_failed()
    assert _attention_vocabulary() == ATTENTION_SIGNAL_TYPES
    assert ATTENTION_SIGNAL_TYPES <= _emitted_vocabulary()
