"""storage JSON 헬퍼 — 한글을 그대로 쓰고 같은 값을 다시 읽는다."""

from datastore import storage


def test_json_roundtrip_keeps_korean_readable(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    obj = {"checked_at": "2026-08-14T09:00:00+09:00", "issues": [{"제목": "한글"}]}
    target = storage.write_json(obj, "market_desk", "board.json")
    assert "한글" in (tmp_path / "market_desk" / "board.json").read_text()  # ensure_ascii=False
    assert storage.read_json("market_desk", "board.json") == obj
    assert target.endswith("market_desk/board.json")
