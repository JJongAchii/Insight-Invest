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
    const fail =
      mode === "error" &&
      [
        "overview",
        "research",
        "news/briefing",
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
          : fixtureFor(path, url.searchParams, mode),
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
  await visible(page, "금리와 환율의 변화");
  await check(
    "Market, economy and research visible; personal tools secondary",
    async () => {
      await visible(page, "시간축별 시장 흐름");
      await visible(page, "새로 들어온 리서치");
      assert.equal(
        await page
          .getByRole("button", { name: "경제 · 시장", exact: true })
          .getAttribute("aria-pressed"),
        "true",
      );
      assert.equal(
        await page.getByText("종합 뉴스 테스트 항목").isVisible(),
        false,
      );
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
      await visible(phone, "시장 브리핑");
      await visible(phone, "금리와 환율의 변화");
      const nav = phone.locator("nav.fixed");
      assert.deepEqual(
        await nav
          .locator("a")
          .allTextContents()
          .then((items) => items.map((text) => text.replace(/\d/g, "").trim())),
        ["브리핑", "한국 시장", "경제", "리서치", "종목"],
      );
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
      await visible(page, "2,626.00");
      await visible(page, "2026-09-07 · 정산 종가");
    },
  );
  await check(
    "Empty data stays unknown, including the US recession indicator",
    async () => {
      mode = "empty";
      await page.reload();
      await visible(page, "관측값 미확인");
      await visible(page, "시간축별 요약이 아직 없습니다");
      await visible(page, "이 분류에 등록된 자료가 없습니다");
      await page.goto("/regime");
      await visible(page, "경기 관측값 없음");
    },
  );
  await check(
    "Failed regions report errors while economic RSS remains usable",
    async () => {
      mode = "error";
      await page.goto("/home");
      await page.reload();
      await visible(page, "시장 요약을 불러오지 못했습니다");
      await visible(page, "리서치를 불러오지 못했습니다");
      await visible(page, "최신 경제 헤드라인 테스트");
      assert.ok(
        requests.some(
          (url) => url.includes("/news?") && url.includes("category=economy"),
        ),
      );
      await noOverflow(page);
      await capture(page, "error-state");
    },
  );
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
