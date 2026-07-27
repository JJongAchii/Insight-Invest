from module.brief.schema import (
    BULL_BEAR_SCHEMA,
    JUDGE_SCHEMA,
    enforce_lengths,
    flatten_keys,
    validate_points,
)


def test_flatten_keys가_중첩_경로를_만든다():
    pack = {"flows": {"frgn": {"streak": 12}}, "identity": {"ticker": "005930"}}
    keys = flatten_keys(pack)
    assert "flows" in keys
    assert "flows.frgn" in keys
    assert "flows.frgn.streak" in keys
    assert "identity.ticker" in keys


def test_flatten_keys는_리스트를_리프로_취급():
    keys = flatten_keys({"news": [{"title": "x"}]})
    assert keys == {"news"}


def test_실재하는_경로만_참조한_논거는_통과():
    pack = {"flows": {"frgn": {"streak": 12}}}
    points = [{"claim": "수급 강함", "evidence": ["flows.frgn.streak"]}]
    kept, dropped = validate_points(points, pack)
    assert len(kept) == 1
    assert dropped == []


def test_없는_경로를_참조한_논거는_드롭되고_사유가_남는다():
    pack = {"flows": {"frgn": {"streak": 12}}}
    points = [{"claim": "업황 회복", "evidence": ["industry.outlook"]}]
    kept, dropped = validate_points(points, pack)
    assert kept == []
    assert len(dropped) == 1
    assert dropped[0]["bad_refs"] == ["industry.outlook"]


def test_일부만_잘못된_경로여도_논거_전체를_드롭():
    pack = {"flows": {"frgn": {"streak": 12}}}
    points = [{"claim": "혼합", "evidence": ["flows.frgn.streak", "made.up"]}]
    kept, dropped = validate_points(points, pack)
    assert kept == []
    assert dropped[0]["bad_refs"] == ["made.up"]


def test_evidence가_비어있으면_드롭():
    kept, dropped = validate_points([{"claim": "근거없음", "evidence": []}], {"a": 1})
    assert kept == []
    assert dropped[0]["bad_refs"] == []


def test_길이_초과_필드를_자르고_보고한다():
    judge = {"one_liner": "가" * 80, "summary": "나" * 250, "tension": "다"}
    out, truncated = enforce_lengths(judge)
    assert len(out["one_liner"]) == 60
    assert len(out["summary"]) == 200
    assert set(truncated) == {"one_liner", "summary"}
    assert out["tension"] == "다"


def test_길이_이내면_그대로():
    judge = {"one_liner": "짧음", "summary": "짧음"}
    out, truncated = enforce_lengths(judge)
    assert out == judge
    assert truncated == []


def test_스키마가_필수필드를_강제한다():
    assert BULL_BEAR_SCHEMA["required"] == ["points", "what_i_could_not_argue"]
    point = BULL_BEAR_SCHEMA["properties"]["points"]["items"]
    assert set(point["required"]) == {"claim", "evidence", "strength", "breaks_if"}
    assert point["additionalProperties"] is False
    assert "one_liner" in JUDGE_SCHEMA["required"]
    assert "decisive_question" in JUDGE_SCHEMA["required"]
