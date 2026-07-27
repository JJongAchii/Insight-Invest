from module.brief.select import MKTCAP_FLOOR, select_targets


def _cap(tickers, value=1e12):
    return {t: value for t in tickers}


def test_세_소스의_합집합을_반환():
    picked, dropped = select_targets(
        watchlist={"A"}, holdings={"B"}, attention_high=["C"], mktcap=_cap("ABC")
    )
    assert set(picked) == {"A", "B", "C"}
    assert dropped == []


def test_중복은_한_번만():
    picked, _ = select_targets(
        watchlist={"A"}, holdings={"A"}, attention_high=["A"], mktcap=_cap("A")
    )
    assert picked == ["A"]


def test_시총_하한_미만은_제외():
    mktcap = {"A": MKTCAP_FLOOR, "B": MKTCAP_FLOOR - 1}
    picked, dropped = select_targets(
        watchlist={"A", "B"}, holdings=set(), attention_high=[], mktcap=mktcap
    )
    assert picked == ["A"]
    assert dropped == []  # 하한 미달은 절삭이 아니라 자격 미달


def test_시총_정보_없는_종목은_제외():
    picked, _ = select_targets(
        watchlist={"A", "UNKNOWN"}, holdings=set(), attention_high=[], mktcap=_cap("A")
    )
    assert picked == ["A"]


def test_상한_초과시_보유_attention_워치리스트_순으로_남긴다():
    watch = {f"W{i}" for i in range(10)}
    hold = {f"H{i}" for i in range(3)}
    att = [f"A{i}" for i in range(5)]
    all_t = watch | hold | set(att)
    picked, dropped = select_targets(
        watchlist=watch, holdings=hold, attention_high=att, mktcap=_cap(all_t), cap=6
    )
    assert len(picked) == 6
    assert set(picked[:3]) == hold  # 보유가 최우선
    assert set(picked[3:6]) == set(att[:3])  # 그다음 attention (입력 순서 유지)
    assert len(dropped) == 12
    assert set(dropped).isdisjoint(hold)


def test_attention_입력_순서가_우선순위():
    att = ["A1", "A2", "A3"]
    picked, _ = select_targets(
        watchlist=set(), holdings=set(), attention_high=att, mktcap=_cap(att), cap=2
    )
    assert picked == ["A1", "A2"]


def test_보유가_상한을_넘으면_보유만_남는다():
    hold = {f"H{i}" for i in range(20)}
    picked, dropped = select_targets(
        watchlist={"W"}, holdings=hold, attention_high=[], mktcap=_cap(hold | {"W"}), cap=15
    )
    assert len(picked) == 15
    assert set(picked).issubset(hold)
    assert "W" in dropped
