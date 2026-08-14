"""news_briefing 순수 로직 테스트 — 클러스터 파싱·병합·랭킹·LLM 검증·페이로드."""

from datetime import datetime, timedelta, timezone

from module import news_briefing as nb

# 실측(2026-08-14) Google News KR RSS 구조 재현 — description은 HTML 이스케이프됨
GENERAL_XML = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>
<item><title>대통령 개헌 제안 - 한겨레</title>
<link>https://news.google.com/rss/articles/AAA?oc=5</link>
<guid isPermaLink="false">AAA</guid>
<pubDate>Fri, 14 Aug 2026 03:00:00 GMT</pubDate>
<description>&lt;ol&gt;&lt;li&gt;&lt;a href="https://news.google.com/rss/articles/AAA?oc=5" target="_blank"&gt;대통령 개헌 제안&lt;/a&gt;&amp;nbsp;&amp;nbsp;&lt;font color="#6f6f6f"&gt;한겨레&lt;/font&gt;&lt;/li&gt;&lt;li&gt;&lt;a href="https://news.google.com/rss/articles/BBB?oc=5" target="_blank"&gt;[속보] 개헌 전격 제안&lt;/a&gt;&amp;nbsp;&amp;nbsp;&lt;font color="#6f6f6f"&gt;경향신문&lt;/font&gt;&lt;/li&gt;&lt;li&gt;&lt;a href="https://news.google.com/rss/articles/CCC?oc=5" target="_blank"&gt;개헌 제안 파장&lt;/a&gt;&amp;nbsp;&amp;nbsp;&lt;font color="#6f6f6f"&gt;문화일보&lt;/font&gt;&lt;/li&gt;&lt;/ol&gt;</description>
<source url="https://hani.co.kr">한겨레</source></item>
<item><title>단독 소식 - 매일경제</title>
<link>https://news.google.com/rss/articles/DDD?oc=5</link>
<pubDate>Fri, 14 Aug 2026 04:00:00 GMT</pubDate>
<description>&lt;a href="https://news.google.com/rss/articles/DDD?oc=5"&gt;단독 소식&lt;/a&gt;&amp;nbsp;&lt;font color="#6f6f6f"&gt;매일경제&lt;/font&gt;</description>
<source url="https://mk.co.kr">매일경제</source></item>
</channel></rss>"""

ECONOMY_XML = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>
<item><title>[속보] 개헌 전격 제안 - 경향신문</title>
<link>https://news.google.com/rss/articles/BBB?oc=5</link>
<pubDate>Fri, 14 Aug 2026 03:10:00 GMT</pubDate>
<description>&lt;a href="https://news.google.com/rss/articles/BBB?oc=5"&gt;[속보] 개헌 전격 제안&lt;/a&gt;&amp;nbsp;&lt;font color="#6f6f6f"&gt;경향신문&lt;/font&gt;</description>
<source url="https://khan.co.kr">경향신문</source></item>
<item><title>코스피 장중 7천 회복 반도체 강세 - 한국경제</title>
<link>https://news.google.com/rss/articles/EEE?oc=5</link>
<pubDate>Fri, 14 Aug 2026 05:00:00 GMT</pubDate>
<description>&lt;a href="https://news.google.com/rss/articles/EEE?oc=5"&gt;코스피 장중 7천 회복 반도체 강세&lt;/a&gt;&amp;nbsp;&lt;font color="#6f6f6f"&gt;한국경제&lt;/font&gt;</description>
<source url="https://hankyung.com">한국경제</source></item>
</channel></rss>"""

NOW = datetime(2026, 8, 14, 6, 0, 0, tzinfo=timezone.utc)


def _parsed():
    return nb.parse_feed(GENERAL_XML, "general") + nb.parse_feed(ECONOMY_XML, "economy")


def test_parse_cluster_item():
    items = nb.parse_feed(GENERAL_XML, "general")
    assert len(items) == 2
    a = items[0]
    assert a["title"] == "대통령 개헌 제안 - 한겨레"
    assert a["source"] == "한겨레"
    assert a["cluster_count"] == 3
    assert a["sources"] == ["한겨레", "경향신문", "문화일보"]
    assert "https://news.google.com/rss/articles/BBB?oc=5" in a["cluster_urls"]
    assert a["feed"] == "general"
    assert a["published_at"].startswith("2026-08-14T03:00:00")


def test_parse_single_item_cluster_is_one():
    items = nb.parse_feed(GENERAL_XML, "general")
    d = items[1]
    assert d["cluster_count"] == 1
    assert d["sources"] == ["매일경제"]


def test_parse_pubdate_naive_gets_utc():
    xml = GENERAL_XML.replace("Fri, 14 Aug 2026 03:00:00 GMT", "Fri, 14 Aug 2026 03:00:00 -0000")
    items = nb.parse_feed(xml, "general")
    # -0000은 naive로 파싱될 수 있다 — 랭킹(aware now와의 뺄셈)이 죽지 않아야 한다
    ranked = nb.rank_candidates(items, NOW)
    assert ranked and ranked[0]["published_at"] is not None


def test_merge_by_cluster_membership():
    # economy의 BBB 기사는 general AAA의 클러스터에 속함 → 병합, general 우선
    merged = nb.merge_stories(_parsed())
    urls = [m["url"] for m in merged]
    assert "https://news.google.com/rss/articles/BBB?oc=5" not in urls
    a = next(m for m in merged if m["url"].endswith("AAA?oc=5"))
    assert a["feed"] == "general"
    assert a["cluster_count"] == 3
    assert len(merged) == 3  # AAA(+BBB), DDD, EEE


def test_merge_by_title_jaccard():
    x = {"title": "삼성전자 2분기 영업이익 10조 돌파", "url": "u1", "source": "a",
         "published_at": None, "cluster_count": 1, "sources": ["a"],
         "cluster_urls": [], "feed": "economy"}
    y = {"title": "삼성전자 2분기 영업이익 10조 돌파 확정", "url": "u2", "source": "b",
         "published_at": None, "cluster_count": 2, "sources": ["b"],
         "cluster_urls": [], "feed": "economy"}
    merged = nb.merge_stories([x, y])
    assert len(merged) == 1
    assert merged[0]["cluster_count"] == 2
    assert set(merged[0]["sources"]) == {"a", "b"}


def test_rank_score_decay_and_ids():
    fresh = {"title": "새 소식", "url": "f", "source": "a", "cluster_count": 3,
             "published_at": NOW.isoformat(), "sources": [], "cluster_urls": [],
             "feed": "general"}
    old_big = {"title": "이틀 전 큰 뉴스", "url": "o", "source": "b", "cluster_count": 12,
               "published_at": (NOW - timedelta(hours=48)).isoformat(),
               "sources": [], "cluster_urls": [], "feed": "general"}
    ranked = nb.rank_candidates([old_big, fresh], NOW)
    # 12*exp(-2)=1.62 < 3*exp(0)=3 → fresh가 먼저
    assert ranked[0]["url"] == "f" and ranked[0]["id"] == 0
    assert ranked[1]["id"] == 1


def test_rank_caps_at_limit():
    items = [{"title": f"t{i}", "url": f"u{i}", "source": "s", "cluster_count": 1,
              "published_at": NOW.isoformat(), "sources": [], "cluster_urls": [],
              "feed": "general"} for i in range(80)]
    assert len(nb.rank_candidates(items, NOW)) == nb.CANDIDATE_LIMIT


def _candidates():
    return nb.rank_candidates(nb.merge_stories(_parsed()), NOW)


def test_parse_curation_accepts_code_fence():
    out = nb.parse_curation('```json\n{"general": [], "economy": []}\n```')
    assert out == {"general": [], "economy": []}


def test_validate_ok():
    c = _candidates()
    out = {"general": [{"id": c[0]["id"], "why": "중요함"}],
           "economy": [{"id": c[1]["id"], "why": "시장 영향"}]}
    assert nb.validate_curation(out, c) == []


def test_validate_catches_bad_output():
    c = _candidates()
    bad = {"general": [{"id": 999, "why": "x"}, {"id": c[0]["id"], "why": ""}],
           "economy": [{"id": c[0]["id"], "why": "dup"}]}
    errors = nb.validate_curation(bad, c)
    assert any("실존" in e for e in errors)
    assert any("why" in e for e in errors)
    assert any("중복" in e for e in errors)


def test_validate_section_missing_and_oversize():
    c = _candidates()
    errors = nb.validate_curation({"general": []}, c)
    assert any("general" in e for e in errors)
    assert any("economy" in e for e in errors)
    six = [{"id": x["id"], "why": "y"} for x in c[:3]] * 2
    errors2 = nb.validate_curation({"general": six, "economy": [
        {"id": c[0]["id"], "why": "y"}]}, c)
    assert any(">" in e or "건" in e for e in errors2)


def test_fallback_by_feed():
    c = _candidates()
    sel = nb.fallback_selection(c)
    gen_ids = {x["id"] for x in sel["general"]}
    eco_ids = {x["id"] for x in sel["economy"]}
    by_id = {x["id"]: x for x in c}
    assert all(by_id[i]["feed"] == "general" for i in gen_ids)
    assert all(by_id[i]["feed"] == "economy" for i in eco_ids)
    assert all(x["why"] == "" for x in sel["general"] + sel["economy"])


def test_build_payload_edition_and_why():
    c = _candidates()
    sel = {"general": [{"id": c[0]["id"], "why": "핵심"}],
           "economy": [{"id": c[1]["id"], "why": ""}, {"id": 999, "why": "없는 id"}]}
    morning = nb.build_payload(sel, c, True, datetime(2026, 8, 14, 9, 5, tzinfo=nb.KST))
    assert morning["edition"] == "morning" and morning["curated"] is True
    assert morning["sections"]["general"][0]["why"] == "핵심"
    assert "why" not in morning["sections"]["economy"][0]  # 빈 why는 생략
    assert len(morning["sections"]["economy"]) == 1  # 없는 id는 건너뜀
    row = morning["sections"]["general"][0]
    assert set(row) == {"title", "url", "source", "published_at",
                        "cluster_count", "sources", "why"}
    evening = nb.build_payload(sel, c, False, datetime(2026, 8, 14, 19, 5, tzinfo=nb.KST))
    assert evening["edition"] == "evening"
