"""Read the published board's news as articles: category, urgency, facts and why they matter.

The editorial worker publishes Reporter news either with those fields or, for editions written
for a chat channel, as one formatted text. Both become the same article here. Index and sector
moves stay with the market explanation and are not news.
"""

import re
from datetime import datetime, timedelta
from html import unescape

from module.kr_intraday import KST

_HEADER = re.compile(r"\*\[(.+?)\] (.+)\*")
# The label follows the last bar: an address may contain one, a publisher or licence name does not.
_SOURCE = re.compile(r"<(https?://[^<>\s]+)\|([^|<>]*)> · 발표 (\d{2})-(\d{2}) (\d{2}):(\d{2}) KST")
_LICENSE = re.compile(r"출처 이용: <(https?://[^<>\s]+)\|([^|<>]*)>")
_FOOTER = re.compile(r"Reporter의 AI 한국어 요약 · 확인 .+")
_ATTRIBUTION = re.compile(r"(.+) 보도에 따르면:")
_SECTIONS = {"*왜 중요한가*": "significance", "*달라진 점*": "change"}
# A roundup page ("[연합뉴스 이 시각 헤드라인]") is evidence, not the story's title.
_ROUNDUP = re.compile(r"^\[[^\]]*(?:헤드라인|이 시각|주요\s?뉴스|뉴스\s?요약)[^\]]*\]")
# "연합뉴스: …", "연합뉴스·WSJ 인용: …": the editor's credit, shown as the publisher instead.
_CREDIT = re.compile(r"^(?P<who>[^:：\n]{1,40})[:：]\s+(?=\S)")
_MARKS = {"보도", "후속", "긴급", "주요"}


def _source_time(month, day, hour, minute, published):
    """The text carries no year. A source cannot be newer than the article that cites it."""
    local = published.astimezone(KST)
    stamp = datetime(local.year, int(month), int(day), int(hour), int(minute), tzinfo=KST)
    if stamp > local + timedelta(days=1):
        stamp = stamp.replace(year=local.year - 1)
    return stamp


def parse_report(text, published):
    """Fields of a Reporter article written as chat text, or None when the text is not in that form."""
    lines = text.split("\n")
    header = _HEADER.fullmatch(lines[0])
    if not header:
        return None
    *marks, category = header[1].split(" · ")
    if not set(marks) <= _MARKS or ("긴급" in marks) == ("주요" in marks):
        return None
    parts = {"summary": [], "significance": [], "change": []}
    sources, licenses, attribution, section = [], [], None, "summary"
    for line in lines[1:]:
        if source := _SOURCE.fullmatch(line):
            try:
                stamp = _source_time(*source.groups()[2:], published)
            except ValueError:
                return None
            sources.append({"title": "", "publisher": unescape(source[2]), "url": unescape(source[1]),
                            "published_at": stamp.isoformat()})
        elif licence := _LICENSE.fullmatch(line):
            licenses.append({"url": unescape(licence[1]), "name": unescape(licence[2])})
        elif _FOOTER.fullmatch(line):
            continue
        elif "보도" in marks and not attribution and not parts["summary"] and (credit := _ATTRIBUTION.fullmatch(line)):
            attribution = unescape(credit[1])
        else:
            for prefix, name in _SECTIONS.items():
                if line.startswith(prefix):
                    section, line = name, line[len(prefix):].strip()
            parts[section].append(unescape(line))
    summary = "\n".join(parts["summary"]).strip()
    if not summary:
        return None
    return {"category": category, "priority": "urgent" if "긴급" in marks else "major", "update": "후속" in marks,
            "attribution": attribution, "summary": summary,
            "significance": "\n".join(parts["significance"]).strip(), "change": "\n".join(parts["change"]).strip(),
            "sources": sources, "licenses": licenses}


def _article(issue):
    item = {"id": issue["id"], "kind": issue["kind"], "origin": issue.get("origin") or "desk",
            "status": issue["status"], "headline": issue["headline"], "published_at": issue["published_at"],
            "category": None, "priority": None, "update": False, "attribution": None, "summary": "",
            "significance": "", "change": "", "interpretation": issue.get("interpretation") or "",
            "watch": issue.get("watch") or "", "body": None, "sources": list(issue.get("sources") or []),
            "followups": list(issue.get("followups") or []), "licenses": []}
    fact = issue.get("fact") or ""
    if issue.get("priority"):
        item.update(category=issue.get("category"), priority=issue["priority"], update=bool(issue.get("update")),
                    attribution=issue.get("attribution"), summary=fact,
                    significance=issue.get("significance") or "", change=issue.get("change") or "")
    elif item["origin"] == "reporter":
        report = parse_report(fact, datetime.fromisoformat(issue["published_at"]))
        if report is None:
            item["body"] = fact
            return item
        # The board lists an original's title only while it is recent. The text keeps every cited link.
        known = {source["url"]: source for source in item["sources"]}
        cited = [known.get(source["url"], source) for source in report["sources"]]
        urls = {source["url"] for source in cited}
        report["sources"] = cited + [source for source in item["sources"] if source["url"] not in urls]
        attached = {source.get("license_url") for source in report["sources"]}
        report["licenses"] = [licence for licence in report["licenses"] if licence["url"] not in attached]
        item.update(report)
    elif fact != issue["headline"]:
        item["summary"] = fact
    return item


def _listed_as(item):
    """The title a reader recognises: the original article's, with its publisher. Without a usable original the
    editor's own headline is used, without the outlet credit the publisher label already carries."""
    originals = [source for source in item["sources"] if source.get("title") and not _ROUNDUP.match(source["title"])]
    if originals:
        return originals[0]["title"], originals[0]["publisher"]
    publisher = item["attribution"] or (item["sources"][0]["publisher"] if item["sources"] else None)
    headline = item["headline"]
    credit = _CREDIT.match(headline)
    if credit and ("인용" in credit["who"] or "보도" in credit["who"] or (publisher and publisher in credit["who"])):
        headline = headline[credit.end():]
    return headline, publisher


def normalize(issues):
    """Board issues as news articles, newest first."""
    news = []
    for issue in issues:
        if issue["kind"] == "move":
            continue
        item = _article(issue)
        item["title"], item["publisher"] = _listed_as(item)
        news.append(item)
    return sorted(news, key=lambda item: datetime.fromisoformat(item["published_at"]), reverse=True)
