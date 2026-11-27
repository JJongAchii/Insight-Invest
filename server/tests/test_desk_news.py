"""편집 뉴스 정규화 — 발행본의 Reporter 글을 분류·긴급도·핵심 사실로 읽는다."""

from datetime import datetime

from module import desk_news
from module.kr_intraday import KST

PUBLISHED = datetime(2026, 11, 27, 10, 2, tzinfo=KST)

REPORT = "\n".join([
    "*[주요 · 경제] 한은, 기준금리 연 2.50%로 동결*",
    "한국은행 금융통화위원회는 27일 기준금리를 연 2.50%로 유지했다.",
    "성장률 전망은 1.9%에서 2.1%로 높였다.",
    "*왜 중요한가* 대출금리와 원·달러 환율에 바로 영향을 준다.",
    "<https://www.bok.or.kr/portal/bbs/view.do?nttId=1&amp;menuNo=2|한국은행> · 발표 11-27 09:50 KST",
    "<https://www.yna.co.kr/view/AKR1|연합뉴스> · 발표 11-27 09:52 KST",
    "출처 이용: <https://www.kogl.or.kr/info/licenseType1.do|공공누리 제1유형>",
    "Reporter의 AI 한국어 요약 · 확인 11-27 10:02 KST",
])


def issue(**changes):
    base = {"id": "source-1", "kind": "news", "origin": "reporter", "status": "reported",
            "headline": "한은, 기준금리 연 2.50%로 동결", "fact": REPORT, "interpretation": "", "watch": "",
            "observation": "", "published_at": PUBLISHED.isoformat(), "observed_at": None, "sources": []}
    return {**base, **changes}


def test_report_text_becomes_category_priority_facts_and_reason():
    item = desk_news.normalize([issue()])[0]
    assert (item["category"], item["priority"], item["update"], item["attribution"]) == ("경제", "major", False, None)
    assert item["summary"] == ("한국은행 금융통화위원회는 27일 기준금리를 연 2.50%로 유지했다.\n"
                               "성장률 전망은 1.9%에서 2.1%로 높였다.")
    assert item["significance"] == "대출금리와 원·달러 환율에 바로 영향을 준다."
    assert item["change"] == "" and item["body"] is None


def test_report_sources_keep_links_publication_time_and_licence():
    item = desk_news.normalize([issue()])[0]
    assert [(s["publisher"], s["url"], s["published_at"]) for s in item["sources"]] == [
        ("한국은행", "https://www.bok.or.kr/portal/bbs/view.do?nttId=1&menuNo=2", "2026-11-27T09:50:00+09:00"),
        ("연합뉴스", "https://www.yna.co.kr/view/AKR1", "2026-11-27T09:52:00+09:00"),
    ]
    assert item["licenses"] == [{"url": "https://www.kogl.or.kr/info/licenseType1.do", "name": "공공누리 제1유형"}]


def test_board_source_supplies_the_article_title_for_the_same_link():
    known = {"title": "통화정책방향 결정문", "publisher": "한국은행", "published_at": "2026-11-27T09:50:00+09:00",
             "url": "https://www.bok.or.kr/portal/bbs/view.do?nttId=1&menuNo=2"}
    item = desk_news.normalize([issue(sources=[known])])[0]
    assert [s["title"] for s in item["sources"]] == ["통화정책방향 결정문", ""]


def test_urgent_follow_up_from_a_single_outlet_keeps_each_marker():
    text = "\n".join([
        "*[보도 · 후속 · 긴급 · 글로벌 주요사건] 해협 통항 재개 &amp; 유가 하락*",
        "연합뉴스 보도에 따르면:",
        "통항이 재개됐다.",
        "*왜 중요한가* 원유 수송 차질 우려가 줄었다.",
        "*달라진 점* 봉쇄 해제가 공식 확인됐다.",
        "<https://www.yna.co.kr/view/AKR2|연합뉴스> · 발표 11-27 09:40 KST",
        "Reporter의 AI 한국어 요약 · 확인 11-27 10:02 KST",
    ])
    item = desk_news.normalize([issue(fact=text, headline="해협 통항 재개 & 유가 하락")])[0]
    assert (item["category"], item["priority"], item["update"], item["attribution"]) == (
        "글로벌 주요사건", "urgent", True, "연합뉴스")
    assert item["summary"] == "통항이 재개됐다."
    assert item["change"] == "봉쇄 해제가 공식 확인됐다."


def test_source_published_before_new_year_keeps_the_previous_year():
    at = datetime(2027, 1, 1, 0, 20, tzinfo=KST)
    text = REPORT.replace("11-27 09:50", "12-31 23:40")
    item = desk_news.normalize([issue(fact=text, published_at=at.isoformat())])[0]
    assert item["sources"][0]["published_at"] == "2026-12-31T23:40:00+09:00"


def test_unrecognised_report_text_is_kept_whole():
    item = desk_news.normalize([issue(fact="형식을 알 수 없는 본문\n둘째 줄")])[0]
    assert item["body"] == "형식을 알 수 없는 본문\n둘째 줄"
    assert item["summary"] == "" and item["category"] is None and item["priority"] is None


def test_structured_report_fields_are_used_as_published():
    item = desk_news.normalize([issue(
        fact="핵심 사실 문장.", category="산업", priority="urgent", update=True, attribution="로이터",
        significance="공급망에 영향을 준다.", change="가동 중단이 확인됐다.")])[0]
    assert (item["category"], item["priority"], item["update"], item["attribution"]) == ("산업", "urgent", True, "로이터")
    assert (item["summary"], item["significance"], item["change"], item["body"]) == (
        "핵심 사실 문장.", "공급망에 영향을 준다.", "가동 중단이 확인됐다.", None)


def test_desk_filing_keeps_its_explanation_and_drops_a_repeated_title():
    source = {"title": "단일판매ㆍ공급계약체결", "publisher": "금융감독원 전자공시", "published_at": PUBLISHED.isoformat(),
              "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=1"}
    written = issue(id="firm", origin="desk", kind="filing", status="analysis", headline="A사, 매출 12% 규모 공급계약",
                    fact="계약금액은 최근 매출의 12%다.", interpretation="내년 실적에 반영된다.", watch="납품 일정",
                    sources=[source], followups=[source])
    pending = issue(id="raw", origin="desk", kind="filing", headline="B사 회사합병 결정", fact="B사 회사합병 결정")
    first, second = desk_news.normalize([written, pending])
    assert (first["kind"], first["summary"], first["interpretation"], first["watch"]) == (
        "filing", "계약금액은 최근 매출의 12%다.", "내년 실적에 반영된다.", "납품 일정")
    assert first["sources"] == [source] and first["followups"] == [source]
    assert first["category"] is None and first["priority"] is None
    assert second["summary"] == ""


def test_market_moves_are_not_news_and_newest_comes_first():
    older = issue(id="older", published_at=datetime(2026, 11, 26, 18, 0, tzinfo=KST).isoformat())
    move = issue(id="move", origin="desk", kind="move", status="unconfirmed", fact="지수 변화")
    assert [item["id"] for item in desk_news.normalize([older, move, issue()])] == ["source-1", "older"]


def test_source_link_with_a_bar_in_its_address_is_kept_whole():
    text = REPORT.replace("https://www.yna.co.kr/view/AKR1|연합뉴스", "https://www.yna.co.kr/view?id=1|2|연합뉴스")
    item = desk_news.normalize([issue(fact=text)])[0]
    assert (item["sources"][1]["url"], item["sources"][1]["publisher"]) == ("https://www.yna.co.kr/view?id=1|2", "연합뉴스")


def test_list_title_is_the_original_article_title_with_its_publisher():
    known = {"title": "통화정책방향 결정문", "publisher": "한국은행", "published_at": "2026-11-27T09:50:00+09:00",
             "url": "https://www.bok.or.kr/portal/bbs/view.do?nttId=1&menuNo=2"}
    item = desk_news.normalize([issue(headline="연합뉴스: 한은, 기준금리 동결", sources=[known])])[0]
    assert (item["title"], item["publisher"]) == ("통화정책방향 결정문", "한국은행")


def test_without_a_usable_original_title_the_editor_headline_loses_its_outlet_credit():
    roundup = {"title": "[연합뉴스 이 시각 헤드라인] - 10:30", "publisher": "연합뉴스",
               "published_at": "2026-11-27T10:30:00+09:00", "url": "https://www.yna.co.kr/view/AKR1"}
    text = REPORT.replace("*[주요 · 경제]", "*[보도 · 주요 · 경제]").replace(
        "한국은행 금융통화위원회는", "연합뉴스 보도에 따르면:\n한국은행 금융통화위원회는")
    rounded = desk_news.normalize([issue(headline="연합뉴스: 청와대, 금융당국 긴급회의", fact=text, sources=[roundup])])[0]
    assert (rounded["title"], rounded["publisher"]) == ("청와대, 금융당국 긴급회의", "연합뉴스")
    quoted = desk_news.normalize([issue(headline="연합뉴스·WSJ 인용: 미국, AI 연산력 임대에 허가제", fact="본문만 있는 판본")])[0]
    assert quoted["title"] == "미국, AI 연산력 임대에 허가제"
    speaker = desk_news.normalize([issue(headline="파월: 금리 인하 서두르지 않겠다", fact="본문만 있는 판본")])[0]
    assert speaker["title"] == "파월: 금리 인하 서두르지 않겠다"


def test_filing_title_and_registry_are_shown_as_filed():
    filed = {"title": "(코스닥)엑사이엔씨 - 단일판매ㆍ공급계약체결", "publisher": "금융감독원 DART",
             "published_at": PUBLISHED.isoformat(), "url": "https://dart.fss.or.kr/dsaf001/main.do?rcpNo=2"}
    item = desk_news.normalize([issue(origin="desk", kind="filing", headline=filed["title"], fact=filed["title"],
                                      sources=[filed])])[0]
    assert (item["title"], item["publisher"]) == (filed["title"], "금융감독원 DART")
