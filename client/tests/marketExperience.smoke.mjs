import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { chromium } from "playwright";
import { fixtureFor } from "./marketExperience.fixtures.mjs";

// Start a local Next server with SITE_ACCESS_HASH = SHA256('insight-local-ui-review').
// All backend responses below are intercepted; no production data or user state is used.
const baseURL = process.env.UI_BASE_URL || "http://127.0.0.1:3107";
assert.ok(
  ["127.0.0.1", "localhost"].includes(new URL(baseURL).hostname),
  "Run against a local test server only",
);
const output =
  process.env.UI_OUTPUT_DIR || "/tmp/insight-market-research-review";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({
  channel: process.env.UI_BROWSER_CHANNEL || "chrome",
  headless: true,
});
const results = [];
let mode = "normal";
let newsSeen;
let seenRecords = 0;
let failNextSeenRecord = false;
const mutations = [];
const requests = [];
const errors = [];
async function contextFor(viewport) {
  const context = await browser.newContext({
    baseURL,
    viewport,
    serviceWorkers: "block",
    reducedMotion: "reduce",
  });
  // Fixture requests must bypass the PWA cache. Represent an unsupported browser
  // instead of Playwright's blocked register() resolving with no registration.
  await context.addInitScript(() => {
    Reflect.deleteProperty(Navigator.prototype, "serviceWorker");
  });
  await context.addCookies([
    { name: "ii_access", value: "insight-local-ui-review", url: baseURL },
  ]);
  await context.route("**/api/backend/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.split("/api/backend/")[1];
    requests.push(url.pathname + url.search);
    if (route.request().method() !== "GET") mutations.push(path);
    if (path === "market-desk/news/seen") {
      seenRecords += 1;
      if (failNextSeenRecord) {
        failNextSeenRecord = false;
        return route.fulfill({ status: 503, contentType: "application/json", body: '{"detail":"Synthetic failure"}' });
      }
      // "behind": a server whose clock trails the newest article keeps answering with an earlier, changing time.
      newsSeen = mode === "behind" ? `2026-09-07T10:${String(seenRecords).padStart(2, "0")}:00+09:00`
        : route.request().postDataJSON().through;
    }
    const fail =
      mode === "error" &&
      [
        "overview",
        "market-desk",
        "market-desk/news",
        "research",
        "regime/kr",
        "insight/index",
        "insight/flows/top",
      ].includes(path);
    await route.fulfill({
      status: fail ? 503 : 200,
      contentType: "application/json",
      body: JSON.stringify(
        fail
          ? { detail: "Synthetic failure" }
          : fixtureFor(path, url.searchParams, mode, newsSeen),
      ),
    });
  });
  context.on("page", (page) => {
    page.on("pageerror", (error) => errors.push(error.message));
  });
  return context;
}
async function check(name, callback) {
  await callback();
  results.push(name);
  console.log(`PASS ${name}`);
}
async function visible(page, text) {
  await page
    .getByText(text, { exact: false })
    .first()
    .waitFor({ state: "visible" });
}
async function noOverflow(page) {
  assert.ok(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
    "Page must not scroll horizontally",
  );
}
async function openMarketDetails(page) {
  const summary = page.locator("summary").filter({ hasText: "시장 지표와 수급" });
  await summary.click();
  await page.getByRole("region", { name: "주요 지수와 경제 지표" }).waitFor();
}
async function capture(page, name) {
  await page.evaluate(() => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
    window.scrollTo({ top: 0, behavior: "instant" });
  });
  await page.waitForFunction(() => window.scrollY === 0);
  await page.screenshot({ path: `${output}/${name}.png`, fullPage: true });
}
try {
  const desktop = await contextFor({ width: 1440, height: 1000 });
  const page = await desktop.newPage();
  await page.goto("/home");
  await check("Read market updates, published briefs and the latest news on the home", async () => {
    const desk = page.getByRole("region", { name: "장중 시장 해설" });
    await page.getByRole("link", { name: /공모주 신호.*매수 없음/ }).waitFor();
    await desk.getByRole("heading", { name: "코스피는 상승, 코스닥은 하락" }).waitFor();
    await desk.getByRole("link", { name: "코스피, 외국인 매도세에 장중 반락" }).waitFor();
    assert.doesNotMatch(await desk.innerText(), /단일기업|기준금리 동결|아침 브리핑|지난 거래일의 지수 배경|관측 이후 보도/);
    await desk.locator("summary").filter({ hasText: "코스피 장중 변화" }).click();
    await desk.getByText("원인 미확인").waitFor();
    const briefs = page.getByRole("region", { name: "아침·마감 브리핑" });
    await briefs.locator("summary").filter({ hasText: "아침 브리핑" }).click();
    await briefs.getByText("브리핑 전문 읽기").click();
    assert.equal(await briefs.getByRole("link", { name: "공식 발표" }).getAttribute("href"), "https://example.com/source");
    const news = page.getByRole("region", { name: "주요 뉴스" });
    await news.getByText("한은, 기준금리 연 2.50%로 동결").waitFor();
    assert.deepEqual(await news.locator("summary strong").allTextContents(),
      ["단일기업 공급계약", "한은, 기준금리 연 2.50%로 동결", "해협 통항 재개", "이전 소식"]);
    const filing = news.locator("details").filter({ hasText: "단일기업 공급계약" });
    await filing.locator("summary").click();
    await filing.getByRole("heading", { name: "기업에 미치는 영향" }).waitFor();
    await filing.getByText("기업 매출에 영향을 줍니다.").waitFor();
    assert.equal(await page.getByRole("region", { name: "기업 공시·주요 뉴스" }).count(), 0);
    assert.equal(await page.getByText("경제 뉴스 브리핑").count(), 0);
    assert.equal(await page.getByRole("region", { name: "매일 확인" }).getByLabel("새 뉴스 3개").count(), 1);
    assert.equal(mutations.includes("market-desk/news/seen"), false, "Previewing news on the home is not reading it");
  });
  await check("The news page groups a week by day, explains each article and records the visit", async () => {
    await page.getByRole("region", { name: "주요 뉴스" }).getByRole("link", { name: /새 소식 3건 · 전체 보기/ }).click();
    await page.getByRole("heading", { name: "주요 뉴스", level: 1 }).waitFor();
    const feed = page.getByRole("region", { name: "뉴스 목록" });
    await feed.getByText("최근 뉴스 4건").waitFor();
    assert.deepEqual(await feed.getByRole("heading", { level: 2 }).allTextContents(), ["9월 7일 월요일3건", "9월 6일 일요일1건"]);
    assert.deepEqual(await feed.locator("summary strong").allTextContents(),
      ["단일기업 공급계약", "한은, 기준금리 연 2.50%로 동결", "해협 통항 재개", "이전 소식"]);
    const report = feed.locator("details").filter({ hasText: "한은, 기준금리 연 2.50%로 동결" });
    // The list shows the original article's title and publisher; the editor's summary waits behind the row.
    assert.match(await report.locator("summary").innerText(), /^10:15\s+새 소식\s+경제\s+시험 기관\s+한은, 기준금리 연 2\.50%로 동결$/);
    assert.equal(await report.getByText("확인된 뉴스 본문").isVisible(), false);
    await report.locator("summary").click();
    await report.getByRole("heading", { name: "왜 중요한가" }).waitFor();
    await report.getByText("대출금리와 환율에 영향을 줍니다.").waitFor();
    assert.equal(await report.getByRole("link", { name: "시험 기관 원문" }).getAttribute("href"), "https://example.com/announcement");
    assert.equal(await report.getByRole("link", { name: "공공누리 제1유형" }).getAttribute("href"), "https://example.com/licence");
    const urgent = feed.locator("li").filter({ hasText: "해협 통항 재개" });
    assert.equal(await urgent.getAttribute("data-urgent"), "true");
    assert.match(await urgent.locator("summary").innerText(), /긴급\s+후속\s+세계정세/);
    const old = feed.locator("details").filter({ hasText: "이전 소식" });
    assert.match(await old.locator("summary").innerText(), /^18:00\s+뉴스\s+이전 소식$/);
    await old.locator("summary").click();
    assert.equal(await old.getByRole("link", { name: "공식 발표" }).getAttribute("href"), "https://example.com/source");
    await page.waitForFunction(() => !document.querySelector('[aria-label="새 뉴스 3개"]'));
    assert.equal(newsSeen, "2026-09-07T10:30:00+09:00", "The visit is recorded through the newest article shown");
    assert.equal(await feed.getByText("새 소식 3건").count(), 1, "What was new at arrival stays marked during the visit");
    await feed.getByRole("button", { name: "기업 공시 1" }).click();
    assert.deepEqual(await feed.locator("summary strong").allTextContents(), ["단일기업 공급계약"]);
    await feed.getByRole("button", { name: "전체 4" }).click();
    await page.goto("/feed?item=urgent");
    await page.waitForURL((url) => url.pathname === "/news" && url.searchParams.get("item") === "urgent");
    const linked = page.getByRole("region", { name: "뉴스 목록" }).locator("details[open]");
    await linked.getByText("봉쇄 해제가 공식 확인됐습니다.").waitFor();
    assert.match(await linked.locator("summary").innerText(), /세계정세\s+시험 통신\s+해협 통항 재개$/);
    assert.equal(await linked.count(), 1);
    assert.equal(await feed.getByText("새 소식", { exact: false }).count(), 0, "A later visit starts with nothing unseen");
    await page.goto("/home");
    await page.getByRole("region", { name: "장중 시장 해설" }).getByRole("heading", { name: "장중 시장 해설" }).waitFor();
  });
  await check("A corporate-only edition never becomes the market explanation", async () => {
    mode = "company";
    await page.reload();
    const desk = page.getByRole("region", { name: "장중 시장 해설" });
    await desk.getByText(/같은 시각에 수집한 장중 시황을 기다리고/).waitFor();
    assert.doesNotMatch(await desk.innerText(), /단일기업|아침 브리핑/);
    await page.getByRole("region", { name: "주요 뉴스" }).getByText("단일기업 공급계약").waitFor();
    mode = "explained";
    await page.reload();
    await desk.getByRole("heading", { name: "수급 보도로 확인한 코스피 반락" }).waitFor();
    await desk.getByText("해당 변동 구간의 설명").waitFor();
    mode = "lead";
    await page.reload();
    const lead = page.getByRole("region", { name: "한국 증시 마감 해설" });
    await lead.getByRole("heading", { name: "기관이 지킨 반등, 외국인은 매도 전환" }).waitFor();
    await lead.getByText("10%", { exact: true }).waitFor();
    await lead.getByText("근거 원문 1건").click();
    assert.equal(await lead.getByRole("list", { name: "시장 해설의 근거 원문" }).getByRole("link").getAttribute("href"), "https://example.org/index-report");
    assert.equal(await desk.isVisible(), false);
    await page.locator("summary").filter({ hasText: "장중 시세와 관련 보도" }).click();
    await desk.getByRole("heading", { name: "코스피는 상승, 코스닥은 하락" }).waitFor();
    mode = "normal";
    await page.reload();
  });
  await visible(page, "한은, 기준금리 연 2.50%로 동결");
  await check(
    "Daily destinations are directly accessible and market data loads on demand",
    async () => {
      const daily = page.getByRole("region", { name: "매일 확인" });
      assert.deepEqual(await daily.locator("a").evaluateAll(links => links.map(a => a.getAttribute("href"))),
        ["/home", "/ipo", "/news"]);
      assert.equal(requests.some(url => url.endsWith("/overview")), false);
      await openMarketDetails(page);
      await visible(page, "시간축별 시장 흐름");
      await visible(page, "새로 들어온 리서치");
      const personal = page
        .locator("details")
        .filter({ has: page.locator("summary", { hasText: "개인 투자 도구" }) })
        .last();
      assert.equal(await personal.getAttribute("open"), null);
      assert.equal(
        mutations.filter((path) => path.startsWith("research")).length,
        0,
      );
      await noOverflow(page);
    },
  );
  await check(
    "Observation dates and unknown health stay explicit",
    async () => {
      await visible(page, "2026-09-07 15:30 · 마감 스냅샷");
      await visible(page, "데이터 상태 · 미확인");
      await visible(page, "2026-09-02 관측 · ECOS");
      await visible(page, "2026-09-03 관측 · ECOS");
      assert.equal(await page.getByText("2026-09-04 기준 · ECOS").count(), 0);
      assert.equal(await page.getByText("함께 봐야 할 엇갈림").count(), 1);
      await page.getByText("근거 1개 더 보기").click();
      await visible(page, "추가 관측 근거");
    },
  );
  await page.getByText("근거 1개 더 보기").click();
  await capture(page, "desktop-dark");
  await page.getByRole("button", { name: "라이트 모드로 전환" }).click();
  await capture(page, "desktop-light");
  await page.getByRole("button", { name: "다크 모드로 전환" }).click();
  await check(
    "Investor, period and buy/sell controls request the selected data",
    async () => {
      await page
        .getByLabel("수급 투자자", { exact: true })
        .selectOption("inst");
      await visible(page, "기관 수급 예시 기업");
      await page.getByLabel("수급 기간", { exact: true }).selectOption("1m");
      await page.getByRole("button", { name: "순매도", exact: true }).click();
      await visible(page, "순매도 예시 기업");
      assert.ok(
        requests.some((url) => url.includes("window=1m&investor=inst")),
      );
    },
  );
  await check(
    "Home research opens the selected document and touch-readable evidence",
    async () => {
      await page
        .getByRole("link", { name: /시장 변동성의 구조와 자산 간 연결/ })
        .click();
      await page.locator("#research-fixture-0").waitFor();
      assert.ok(page.url().includes("entry=fixture-0"));
      await page.locator("#research-fixture-0 summary").click();
      await visible(page, "방법의 가정과 적용 범위를 확인하는 테스트 발췌문");
      assert.equal(
        mutations.filter((path) => /read|saved/.test(path)).length,
        0,
      );
    },
  );
  await check(
    "Intraday deep link works and keeps its full observation date",
    async () => {
      await page.goto("/insight?tab=intraday&market=KOSDAQ");
      await visible(page, "지연 시세 · 2026-09-07 15:30");
      assert.equal(
        await page
          .getByRole("button", { name: "최근 장중 스냅샷", exact: true })
          .getAttribute("aria-pressed"),
        "true",
      );
    },
  );
  await check("Market sections survive reload and browser back", async () => {
    await page.goto("/insight?tab=settled&section=flows&market=KOSDAQ");
    assert.equal(
      await page
        .getByRole("button", { name: "투자자 수급", exact: true })
        .getAttribute("aria-pressed"),
      "true",
    );
    await page
      .getByRole("button", { name: "지수 · 시장폭", exact: true })
      .click();
    await visible(page, "시장 참여 폭");
    assert.ok(page.url().includes("section=overview"));
    await page.reload();
    await visible(page, "시장 참여 폭");
    await page.goBack();
    assert.equal(
      await page
        .getByRole("button", { name: "투자자 수급", exact: true })
        .getAttribute("aria-pressed"),
      "true",
    );
  });
  await check(
    "Economy defaults to indicators and country selection is shareable",
    async () => {
      await page.goto("/regime?country=kr");
      await visible(page, "한국 금리 · 기준금리와 국고채");
      await visible(page, "2026-09-02 관측 · ECOS");
      await visible(page, "2026-08 기준월 · ECOS");
      assert.equal(
        await page
          .getByRole("button", { name: "한국 · ECOS / OECD", exact: true })
          .getAttribute("aria-pressed"),
        "true",
      );
      await page
        .getByRole("button", { name: "미국 · FRED", exact: true })
        .click();
      await visible(page, "경기 관측값 없음");
      const cpiCard = page.locator(".card").filter({
        has: page.getByRole("heading", { name: "소비자물가 상승률 (전년동월 대비, %)" }),
      });
      assert.match(await cpiCard.locator(".num").innerText(), /^2\.10/);
      assert.ok(page.url().includes("country=us"));
      await page
        .getByRole("button", { name: "경기 국면 · 위험", exact: true })
        .click();
      await visible(page, "성장·물가와 위험 압력");
      await noOverflow(page);
    },
  );
  await check(
    "Mobile primary navigation, readable evidence, and light theme",
    async () => {
      const mobile = await contextFor({ width: 390, height: 844 });
      const phone = await mobile.newPage();
      await phone.goto("/home");
      await phone.getByRole("heading", { name: "시장 브리핑", exact: true }).waitFor();
      await visible(phone, "한은, 기준금리 연 2.50%로 동결");
      const desk = phone.getByRole("region", { name: "장중 시장 해설" });
      await desk.getByRole("heading", { name: "코스피는 상승, 코스닥은 하락" }).waitFor();
      const wire = await desk.getByRole("link", { name: "코스피, 외국인 매도세에 장중 반락" }).boundingBox();
      const sector = await desk.getByRole("heading", { name: "어느 업종에서 갈렸나" }).boundingBox();
      assert.ok(wire && sector && wire.y + wire.height <= sector.y);
      const briefs = phone.getByRole("region", { name: "아침·마감 브리핑" });
      await briefs.locator("summary").filter({ hasText: "아침 브리핑" }).click();
      await briefs.getByText("아침 발행본 요약", { exact: false }).waitFor();
      const nav = phone.locator("nav.fixed");
      assert.deepEqual(
        await nav
          .locator("a")
          .allTextContents()
          .then((items) => items.map((text) => text.replace(/\d/g, "").trim())),
        ["브리핑", "공모주", "뉴스", "한국 시장", "경제"],
      );
      await nav.getByRole("link", { name: "공모주", exact: true }).click();
      await phone.getByRole("heading", { name: "공모주 신호", exact: true }).waitFor();
      await nav.getByRole("link", { name: /뉴스/ }).click();
      const feed = phone.getByRole("region", { name: "뉴스 목록" });
      const report = feed.locator("details").filter({ hasText: "한은, 기준금리 연 2.50%로 동결" });
      await report.locator("summary").press("Enter");
      await report.getByText("대출금리와 환율에 영향을 줍니다.").waitFor();
      await noOverflow(phone);
      await capture(phone, "mobile-news");
      await nav.getByRole("link", { name: "브리핑", exact: true }).click();
      await openMarketDetails(phone);
      await phone
        .getByRole("button", { name: "관측 근거 1개", exact: true })
        .press("Enter");
      await visible(phone, "지수와 시장 참여의 동반 상승");
      await phone
        .getByRole("button", { name: "관측 근거 1개", exact: true })
        .click();
      await noOverflow(phone);
      await capture(phone, "mobile-dark");
      const toggle = phone.getByRole("button", { name: /라이트|밝은|light/i });
      await toggle.click();
      await capture(phone, "mobile-light");
      await phone.setViewportSize({ width: 320, height: 740 });
      await noOverflow(phone);
      await nav.getByRole("link", { name: "경제", exact: true }).click();
      await visible(phone, "미국 경제 지표 요약");
      await noOverflow(phone);
      await mobile.close();
    },
  );
  await check(
    "Stale intraday snapshots cannot replace newer settled prices",
    async () => {
      mode = "stale";
      await page.goto("/home");
      await page.reload();
      await openMarketDetails(page);
      await visible(page, "2,626.00");
      await visible(page, "2026-09-07 · 정산 종가");
      await page.getByRole("link", { name: /공모주 신호.*산출 상태 확인/ }).waitFor();
    },
  );
  await check(
    "Empty data stays unknown, including the US recession indicator",
    async () => {
      mode = "empty";
      await page.reload();
      await openMarketDetails(page);
      await visible(page, "관측값 미확인");
      await visible(page, "시간축별 요약이 아직 없습니다");
      await visible(page, "이 분류에 등록된 자료가 없습니다");
      await page.goto("/regime");
      await visible(page, "경기 관측값 없음");
    },
  );
  await check(
    "Failed regions report their own errors",
    async () => {
      mode = "error";
      await page.goto("/home");
      await page.reload();
      await openMarketDetails(page);
      await visible(page, "시장 요약을 불러오지 못했습니다");
      await visible(page, "리서치를 불러오지 못했습니다");
      await page.getByRole("region", { name: "주요 뉴스" }).getByText("뉴스를 불러오지 못했습니다.").waitFor();
      await noOverflow(page);
      await capture(page, "error-state");
    },
  );
  await check("The news page recovers from a failure, an empty list and an expired link", async () => {
    await page.goto("/news");
    const feed = page.getByRole("region", { name: "뉴스 목록" });
    await feed.getByRole("button", { name: "다시 불러오기" }).waitFor();
    mode = "empty";
    await feed.getByRole("button", { name: "다시 불러오기" }).click();
    await feed.getByText("최근 발행된 뉴스가 없습니다.", { exact: false }).waitFor();
    mode = "normal";
    await page.goto("/news?item=expired");
    await feed.getByText("선택한 뉴스는 최근 목록에서 지나갔습니다.").waitFor();
    assert.equal(await feed.locator("details[open]").count(), 0);
    await capture(page, "desktop-news");
  });
  await check("A visit is recorded once per newest article and a failed record is tried again", async () => {
    const feed = page.getByRole("region", { name: "뉴스 목록" });
    const badge = page.getByRole("region", { name: "매일 확인" }).getByLabel(/새 뉴스 \d+개/);
    newsSeen = undefined; seenRecords = 0; mode = "behind";
    await page.goto("/news");
    await feed.getByText("최근 뉴스 4건").waitFor();
    // The answer 10:01 trails the 10:15 and 10:30 articles, so two stay unseen however often it is asked.
    await page.waitForFunction(() => document.querySelector('[aria-label="새 뉴스 2개"]'));
    await page.waitForTimeout(1200);
    assert.equal(seenRecords, 1, "An answer that falls short of the newest article is not chased in a loop");
    newsSeen = undefined; seenRecords = 0; mode = "normal"; failNextSeenRecord = true;
    await page.goto("/news");
    await feed.getByText("최근 뉴스 4건").waitFor();
    await page.waitForTimeout(600);
    assert.equal(seenRecords, 1);
    assert.equal(await badge.getAttribute("aria-label"), "새 뉴스 3개", "A failed record leaves the news unseen");
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await badge.waitFor({ state: "detached" });
    assert.equal(seenRecords, 2, "The next read of the list records the visit");
    assert.equal(newsSeen, "2026-09-07T10:30:00+09:00");
  });
  assert.deepEqual(errors, [], "No uncaught browser errors");
  await writeFile(
    `${output}/results.json`,
    JSON.stringify(
      { syntheticFixtures: true, passed: results, browserErrors: errors },
      null,
      2,
    ),
  );
  console.log(`${results.length} checks passed. Screenshots: ${output}`);
} finally {
  await browser.close();
}
