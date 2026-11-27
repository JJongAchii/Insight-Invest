"""시장 지도 — 지수를 움직인 종목, 시장 폭, 거래대금 쏠림, 테마 묶음, 노트 이후 변화 (스펙 2026-11-27 §5).

기대값은 2026-11-27 11:05 운영 스냅샷 사본에서 별도 스크립트로 계산해 옮겼다.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from module import market_map

FIXTURES = Path(__file__).parent / "fixtures" / "intraday_20261127"
THEMES = json.loads((Path(__file__).parents[1] / "module" / "market_themes.json").read_text())["themes"]
INDICES = {"KOSPI": {"level": 4794.49, "chg_pct": 1.77}, "KOSDAQ": {"level": 692.99, "chg_pct": 5.69}}
OBSERVED = "2026-11-27T11:05:00+09:00"


@pytest.fixture(scope="module")
def latest():
    return pd.read_parquet(FIXTURES / "latest_1105.parquet")


def build(latest, baseline=None, **changes):
    return market_map.build_map(latest, {**INDICES, **changes}, baseline, THEMES, OBSERVED)


def test_contributions_rebuild_each_index_and_name_who_moved_it(latest):
    kospi, kosdaq = build(latest)["markets"]["KOSPI"], build(latest)["markets"]["KOSDAQ"]
    assert kospi["approx_chg_pct"] == pytest.approx(1.77, abs=0.01)
    assert kosdaq["approx_chg_pct"] == pytest.approx(5.69, abs=0.01)
    assert (kospi["top10_share"], kosdaq["top10_share"]) == (pytest.approx(0.44, abs=0.01), pytest.approx(0.29, abs=0.01))
    assert [(s["name"], s["contrib_pp"]) for s in kospi["contributors"]["up"][:2]] == [
        ("삼성전자", pytest.approx(0.36, abs=0.005)), ("SK하이닉스", pytest.approx(0.20, abs=0.005))]
    assert kospi["contributors"]["down"][0]["name"] == "신한지주"
    assert kosdaq["contributors"]["up"][0]["name"] == "레인보우로보틱스"
    assert len(kospi["contributors"]["up"]) == 5


def test_breadth_counts_every_listed_stock_like_the_exchange(latest):
    kosdaq = build(latest)["markets"]["KOSDAQ"]["breadth"]
    assert (kosdaq["up"], kosdaq["down"], kosdaq["up10"]) == (1461, 219, 93)
    assert kosdaq["median"] == pytest.approx(2.32, abs=0.01)
    assert [s["name"] for s in kosdaq["limit_up"]] == [
        "대성하이텍", "쏘닉스", "에스피시스템스", "제닉스로보틱스", "코스모로보틱스", "퀀텀레일"]
    assert build(latest)["markets"]["KOSPI"]["breadth"]["up"] == 704


def test_spacs_never_lead_a_list(latest):
    spac = latest.iloc[[0]].assign(ticker="999990", name="테스트제9호스팩", market="KOSDAQ", chg_pct=29.9,
                                   cap=9e12, value=9e11)
    built = build(pd.concat([latest, spac], ignore_index=True), pd.DataFrame({"ticker": ["999990"], "avg_value": [1e9]}))
    names = [s["name"] for s in built["markets"]["KOSDAQ"]["breadth"]["limit_up"] + built["markets"]["KOSDAQ"]["contributors"]["up"]
             + built["value_spikes"]]
    assert "테스트제9호스팩" not in names


def test_trading_value_spikes_compare_today_with_a_usual_day(latest):
    baseline = pd.DataFrame({"ticker": ["053800", "000660"], "avg_value": [3e10, 9e11]})
    spikes = build(latest, baseline)["value_spikes"]
    assert [(s["name"], s["multiple"]) for s in spikes] == [("안랩", pytest.approx(5.75, abs=0.01))]
    unavailable = build(latest)
    assert (unavailable["value_spikes"], unavailable["value_spikes_state"]) == ([], "unavailable")


def test_theme_moves_together_only_with_three_members_the_same_way(latest):
    groups = {g["name"]: g for g in build(latest)["groups"]}
    assert set(groups) == {"로봇·자동화", "2차전지", "방산·우주"}
    assert groups["로봇·자동화"]["direction"] == "up" and len(groups["로봇·자동화"]["members"]) == 6
    assert list(groups)[0] == "로봇·자동화"


def test_since_reports_what_changed_after_a_note_and_stays_quiet_otherwise(latest):
    before = market_map.series_entry(build(latest))
    quiet = market_map.series_entry(build(latest, KOSPI={"level": 4800.0, "chg_pct": 1.90}))
    assert market_map.since(before, quiet) is None
    moved = latest.copy()
    moved.loc[moved["name"].eq("레인보우로보틱스"), "chg_pct"] = 29.9
    after = market_map.series_entry(build(moved, KOSDAQ={"level": 698.0, "chg_pct": 6.40}))
    change = market_map.since(before, after)
    assert change["indices"]["KOSDAQ"] == {"from": 5.69, "to": 6.40, "delta": pytest.approx(0.71)}
    assert [s["name"] for s in change["new_limit_up"]] == ["레인보우로보틱스"]


def test_value_baseline_uses_the_twenty_sessions_before_today():
    days = pd.bdate_range("2026-10-20", "2026-11-27")
    daily = pd.DataFrame({"date": days, "ticker": "053800", "value": [float(i) for i in range(len(days))]})
    baseline = market_map.value_baseline(daily, "2026-11-27")
    before_today = [float(i) for i in range(len(days) - 1)][-20:]
    assert baseline.set_index("ticker").loc["053800", "avg_value"] == pytest.approx(sum(before_today) / 20)


def test_index_crossings_report_the_first_crossing_each_way():
    timeline = pd.read_parquet(FIXTURES / "timeline_through_1105.parquet")
    crossings = market_map.index_crossings(timeline)
    assert [(c["index"], c["direction"], c["observed_at"], c["threshold"]) for c in crossings] == [
        ("KOSDAQ", "up", "2026-11-27 09:45", 3.0), ("KOSPI", "up", "2026-11-27 10:55", 2.0)]
    assert crossings[0]["id"] == "2026-11-27/cross/KOSDAQ/up"


def test_top10_share_stays_a_share_on_a_flat_mixed_day(latest):
    """삼성전자·SK하이닉스가 빠지고 나머지가 올라 코스피가 보합이면 부호 있는 합/지수 변화는 수천 %가 된다."""
    mixed = latest.copy()
    mixed.loc[mixed["ticker"].isin(["005930", "000660"]), "chg_pct"] = -2.6
    kospi = build(mixed)["markets"]["KOSPI"]
    assert abs(kospi["approx_chg_pct"]) < 0.05
    assert 0 < kospi["top10_share"] <= 1


def test_a_new_listing_without_a_name_counts_in_breadth_but_is_never_listed(latest):
    """업종표에 아직 없는 상장 첫날 종목: 공모가 대비 +180%라도 상한가·기여 목록에 이름 없이 오르지 않는다."""
    debut = latest.iloc[[0]].assign(ticker="999999", name="", sector="기타", market="KOSDAQ", chg_pct=180.0, cap=5e12)
    kosdaq = build(pd.concat([latest, debut], ignore_index=True))["markets"]["KOSDAQ"]
    assert kosdaq["breadth"]["up"] == 1462
    assert all(s["name"] for s in kosdaq["breadth"]["limit_up"] + kosdaq["contributors"]["up"])
    assert kosdaq["approx_chg_pct"] == pytest.approx(5.69, abs=0.01)


def test_the_whole_day_crosses_each_threshold_once_and_the_last_snapshot_keeps_a_bounded_share():
    """그날 전체 시계열(09:25~15:35, 38회)과 마지막 수집본. 15:35 수집은 KRX 지연 때문에 종가 전이고(코스피 수집 +4.08%,
    종가 +4.3%), 동시호가 무렵이라 지수와 종목 시세의 시점이 어긋나 기여 합이 0.06%p 벌어진다 — 그래서 장중 수집을 15:55까지
    늘렸다. 기여 합이 지수를 재현하는지는 11:05·13:35 수집본으로 검사한다."""
    timeline = pd.read_parquet(FIXTURES / "timeline_full_day.parquet")
    assert [(c["index"], c["observed_at"]) for c in market_map.index_crossings(timeline)] == [
        ("KOSDAQ", "2026-11-27 09:45"), ("KOSPI", "2026-11-27 10:55")]
    last = build(pd.read_parquet(FIXTURES / "latest_1535.parquet"))
    assert all(0 < last["markets"][key]["top10_share"] <= 1 for key in ("KOSPI", "KOSDAQ"))


def test_contributions_rebuild_the_index_in_the_afternoon_too():
    snapshot = pd.read_parquet(FIXTURES / "latest_1335.parquet")
    timeline = pd.read_parquet(FIXTURES / "timeline_full_day.parquet")
    actual = timeline[timeline["kind"].eq("index") & timeline["as_of"].eq("2026-11-27 13:35")].set_index("key")["chg_pct"]
    markets = build(snapshot)["markets"]
    for key in ("KOSPI", "KOSDAQ"):
        assert markets[key]["approx_chg_pct"] == pytest.approx(float(actual[key]), abs=0.05)
