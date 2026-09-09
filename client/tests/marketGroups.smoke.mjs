import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { chromium } from "playwright";
import { fixtureFor } from "./marketExperience.fixtures.mjs";

// UI-only replay of the API snapshots qualified on EC2. Other page regions use
// fixtures. No lake computation, production request, or user-state mutation.
const baseURL = process.env.UI_BASE_URL || "http://127.0.0.1:3127";
assert.ok(["127.0.0.1", "localhost"].includes(new URL(baseURL).hostname));
assert.ok(process.env.GROUP_API_SNAPSHOTS, "Set GROUP_API_SNAPSHOTS to the EC2 API snapshot JSON");
const snapshots = JSON.parse(await readFile(process.env.GROUP_API_SNAPSHOTS, "utf8"));
const output = process.env.UI_OUTPUT_DIR || "/tmp/insight-sector-themes-review";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: "chrome", headless: true });
const results = [], errors = [], requests = [], mutations = [];
let mode = "normal";
let olderResponses = 0;
const stockMembers = Object.values(snapshots).flatMap((s) => Object.values(s.details).flatMap((d) => d.members));
const qs = (page) => new URL(page.url()).searchParams;
const members = (page) => page.getByRole("region", { name: "구성 종목", exact: true });
const analysis = (page) => page.getByRole("region", { name: "선택 그룹 분석" });
const map = (page) => page.getByRole("region", { name: "섹터·테마 지도" });
async function visible(page, text) {
  await page.getByText(text, { exact: false }).first().waitFor({ state: "visible" });
}
async function check(name, callback) {
  await callback(); results.push(name); console.log(`PASS ${name}`);
}
async function noOverflow(page) {
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "No page horizontal overflow");
}
async function capture(page, name, target = '[data-testid="market-groups"]') {
  await page.evaluate(async () => {
    await document.fonts.ready;
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
  await page.locator(target).evaluate((element) => {
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
    window.scrollTo({ top: scrollY + element.getBoundingClientRect().top - 80, behavior: "instant" });
  });
  await page.screenshot({ path: `${output}/${name}.png` });
}
async function contextFor(viewport) {
  const context = await browser.newContext({ baseURL, viewport, serviceWorkers: "block", reducedMotion: "reduce" });
  context.setDefaultTimeout(12000);
  await context.addInitScript(() => Reflect.deleteProperty(Navigator.prototype, "serviceWorker"));
  await context.addCookies([{ name: "ii_access", value: "insight-local-ui-review", url: baseURL }]);
  await context.route("**/api/backend/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.split("/api/backend/")[1];
    requests.push(url.pathname + url.search);
    // The existing stock detail uses POST for this read-only vector query.
    if (request.method() !== "GET" && path !== "insight/factor-exposure") mutations.push(path);
    let status = 200, body;
    if (path === "insight/groups" || path === "insight/groups/detail") {
      const p = url.searchParams;
      const key = [p.get("kind"), p.get("market"), p.get("period")].join("|");
      const selected = snapshots[key];
      body = path.endsWith("/detail") ? selected?.details[p.get("group")] ?? { summary: null, members: [], history: [] } : selected?.overview ?? { as_of: null, rows: [] };
      if ((mode === "error" && path === "insight/groups") || (mode === "detail-error" && path.endsWith("/detail"))) {
        status = 503; body = { detail: "Synthetic error state" };
      } else if (mode === "empty") body = { as_of: null, rows: [] };
      else if (mode === "missing-flow" && path.endsWith("/detail")) {
        body = structuredClone(body);
        body.members[0].frgn_net = null;
        body.members[0].frgn_days = body.summary.flow_days - 1;
      } else if ((mode === "stale-detail" && path.endsWith("/detail")) || (mode === "stale-overview" && path === "insight/groups")) {
        olderResponses += 1;
        if (olderResponses === 1) {
          body = structuredClone(body);
          const oldDate = new Date(new Date(selected.overview.as_of).getTime() - 86400000).toISOString().slice(0, 10);
          if (path.endsWith("/detail")) body.summary.as_of = oldDate;
          else { body.as_of = oldDate; body.rows.forEach((row) => { row.as_of = oldDate; }); }
        }
      }
    } else if (/^stock\/\d+$/.test(path)) {
      const row = stockMembers.find((m) => m.meta_id === Number(path.split("/")[1]));
      body = {
        meta: { ...row, iso_code: "KR", security_type: "STOCK", exchange: row.market },
        summary: { latest_price: row.close, latest_date: row.price_as_of, metrics: {}, flows_recent: {} },
        in_watchlist: false, holding: null,
      };
    } else if (path.startsWith("price/")) body = { prices: [], rows: [] };
    else if (path === "watchlist") body = { items: [] };
    else if (path === "insight/factor-exposure") body = { exposures: [], note: "UI fixture" };
    else if (path.startsWith("insight/flows/ticker")) body = { rows: [] };
    else body = fixtureFor(path, url.searchParams, "normal");
    await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  });
  context.on("page", (page) => {
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error" && !message.text().includes("Failed to load resource")) errors.push(message.text());
    });
  });
  return context;
}

try {
  const desktop = await contextFor({ width: 1440, height: 1100 });
  const page = await desktop.newPage();
  await page.goto("/insight?tab=settled&section=sectors&market=KOSDAQ&period=1m&group=전기·전자");
  await members(page).waitFor();
  await check("Deep link selects KOSDAQ and preserves the exact sector", async () => {
    assert.equal(await page.getByLabel("섹터·테마 시장").inputValue(), "KOSDAQ");
    assert.equal(qs(page).get("group"), "전기·전자");
    await analysis(page).getByRole("heading", { name: "전기·전자", exact: true }).waitFor();
    assert.equal(await members(page).locator("tbody tr").count(), 25);
    await noOverflow(page);
  });
  await check("Pagination, search, sorting and stock-detail back restore the URL", async () => {
    await page.getByRole("button", { name: "구성 종목 다음 페이지" }).click();
    await page.waitForURL((url) => url.searchParams.get("group_page") === "2");
    await page.getByLabel("구성 종목 검색").fill("000660");
    await visible(page, "일치하는 종목이 없습니다");
    await page.getByLabel("구성 종목 검색").fill("");
    await page.getByLabel("구성 종목 정렬 기준").selectOption("return_pct");
    await page.getByRole("button", { name: "오름차순으로 정렬" }).click();
    const link = members(page).locator("tbody a").first();
    const ticker = await link.locator("..").locator("p").first().innerText();
    await page.getByLabel("구성 종목 검색").fill(ticker.split(" · ")[0]);
    const before = page.url();
    const destination = await members(page).locator("tbody a").first().getAttribute("href");
    await members(page).locator("tbody a").first().click();
    await page.waitForURL((url) => url.pathname === destination);
    await page.getByRole("button", { name: "뒤로 가기", exact: true }).click();
    await members(page).waitFor();
    assert.equal(page.url(), before);
    await page.reload();
    await members(page).waitFor();
    assert.equal(page.url(), before);
    assert.equal(await members(page).locator("tbody tr").count(), 1);
    await page.getByLabel("구성 종목 검색").fill("");
  });
  await check("Period changes chart dates; map metrics and ranking keep selection", async () => {
    await page.getByLabel("섹터·테마 기간").selectOption("1w");
    const detail = snapshots["sector|KOSDAQ|1w"].details["전기·전자"];
    await analysis(page).getByText(new RegExp(detail.summary.start_date)).waitFor();
    assert.ok(requests.some((r) => r.includes("/groups/detail?") && r.includes("period=1w")));
    for (const metric of ["excess_pp", "advancing_pct", "frgn_net", "inst_net"]) {
      await page.getByLabel("지도 표시 지표").selectOption(metric);
      assert.equal(qs(page).get("group"), "전기·전자");
    }
    await map(page).getByRole("button", { name: "순위", exact: true }).click();
    assert.equal(qs(page).get("group_view"), "list");
    await map(page).getByRole("button", { name: "지도", exact: true }).click();
    await page.getByLabel("지도 표시 지표").selectOption("return_pct");
    await capture(page, "sector-desktop-dark");
  });
  await check("Six sourced themes open their current representatives and comparison data", async () => {
    await page.getByRole("button", { name: "대표 테마", exact: true }).click();
    await page.waitForURL((url) => url.searchParams.get("market") === "ALL");
    await map(page).getByRole("button", { name: "AI 인프라 분석 보기", exact: true }).click();
    await members(page).getByRole("heading", { name: /AI 인프라 구성 종목/ }).waitFor();
    assert.equal(await map(page).getByRole("button", { name: /분석 보기$/ }).count(), 6);
    assert.equal(await members(page).locator("tbody tr").count(), 8);
    await members(page).getByRole("button", { name: "수급", exact: true }).click();
    await members(page).getByRole("columnheader", { name: "외국인 순매수", exact: true }).waitFor();
    await members(page).getByRole("button", { name: "밸류에이션", exact: true }).click();
    await members(page).getByRole("columnheader", { name: "관측일", exact: true }).waitFor();
    await page.locator("summary", { hasText: "계산 기준 · 구성 근거와 출처" }).press("Enter");
    await visible(page, "구성표는 수동으로 검토하며");
    const source = snapshots["theme|ALL|1w"].details["ai-infrastructure"].summary.sources[0];
    assert.equal(await page.getByRole("link", { name: source.label, exact: true }).getAttribute("href"), source.url);
    await page.locator("summary", { hasText: "계산 기준 · 구성 근거와 출처" }).press("Enter");
    await members(page).getByRole("button", { name: "가격·기여도", exact: true }).click();
    await capture(page, "theme-desktop-dark");
    await page.getByRole("button", { name: "라이트 모드로 전환" }).click();
    await capture(page, "theme-desktop-light");
    await noOverflow(page);
  });
  await check("Missing investor days display unknown totals and observed-day counts", async () => {
    mode = "missing-flow";
    await page.goto("/insight?tab=settled&section=sectors&kind=theme&market=ALL&period=1w&group=ai-infrastructure&group_table=flows");
    await page.reload();
    const missing = snapshots["theme|ALL|1w"].details["ai-infrastructure"].members[0];
    const row = members(page).locator("tbody tr").filter({ has: page.getByRole("link", { name: missing.name, exact: true }) });
    await row.waitFor();
    assert.match(await row.locator("td").nth(3).innerText(), /—\s*4\/5일 확인/);
    mode = "normal";
  });
  await check("Publication between cached queries refreshes the older response in either direction", async () => {
    for (const staleMode of ["stale-detail", "stale-overview"]) {
      mode = staleMode; olderResponses = 0;
      await page.goto("/insight?section=sectors&kind=theme&market=ALL&period=1w&group=ai-infrastructure");
      await members(page).waitFor();
      await page.waitForFunction((date) => {
        const section = document.querySelector('[aria-label="선택 그룹 분석"]');
        return section?.getAttribute("aria-busy") === "false" && section.textContent.includes(`→ ${date}`);
      }, snapshots["theme|ALL|1w"].overview.as_of);
      await page.getByText(`정산 가격 ${snapshots["theme|ALL|1w"].overview.as_of}`, { exact: true }).waitFor();
      assert.equal(olderResponses, 2, "Exactly the older query is retried once");
    }
    mode = "normal";
  });
  await check("Invalid selection, empty data and failed requests have actionable states", async () => {
    await page.goto("/insight?section=sectors&group=invalid-group");
    await visible(page, "선택한 분류가 이 시장에 없습니다");
    assert.equal(await members(page).count(), 0);
    mode = "detail-error";
    await page.goto("/insight?section=sectors&kind=theme&market=ALL&group=robotics");
    await visible(page, "구성 종목과 추이를 불러오지 못했습니다");
    mode = "normal";
    await analysis(page).getByRole("button", { name: /다시/ }).click();
    await members(page).waitFor();
    mode = "error"; await page.reload();
    await visible(page, "섹터·테마 데이터를 불러오지 못했습니다");
    mode = "normal";
    await page.getByTestId("market-groups").getByRole("button", { name: /다시/ }).click();
    await members(page).waitFor();
    mode = "empty"; await page.reload();
    await visible(page, "이 시장의 분석 자료가 아직 없습니다");
    mode = "normal";
  });
  await check("Mobile 390/320 layouts, keyboard selection, source disclosure and themes", async () => {
    const mobile = await contextFor({ width: 390, height: 844 });
    const phone = await mobile.newPage();
    await phone.goto("/insight?section=sectors&kind=theme&market=ALL&group=ai-infrastructure");
    await members(phone).waitFor();
    await noOverflow(phone);
    await capture(phone, "theme-mobile-map");
    await map(phone).getByRole("button", { name: "전력 설비 분석 보기", exact: true }).press("Enter");
    await members(phone).getByRole("heading", { name: /전력 설비 구성 종목/ }).waitFor();
    await phone.waitForFunction(() => document.activeElement?.getAttribute("aria-label") === "선택 그룹 분석");
    await capture(phone, "theme-mobile-detail", '[aria-label="선택 그룹 분석"]');
    assert.equal(await members(phone).locator("article").count(), 8);
    await members(phone).getByRole("button", { name: "수급", exact: true }).click();
    await capture(phone, "theme-mobile-members", '[aria-label="구성 종목"]');
    await phone.locator("summary", { hasText: "계산 기준 · 구성 근거와 출처" }).press("Enter");
    await visible(phone, "참고자료 기준");
    await noOverflow(phone);
    await phone.getByRole("button", { name: "라이트 모드로 전환" }).click();
    await capture(phone, "theme-mobile-light");
    await phone.setViewportSize({ width: 320, height: 740 });
    await noOverflow(phone);
    await capture(phone, "theme-mobile-320");
    await mobile.close();
  });
  assert.deepEqual(errors, [], "No uncaught browser errors");
  assert.deepEqual(mutations, [], "Exploring sectors and themes cannot mutate user state");
  await writeFile(`${output}/results.json`, JSON.stringify({
    realGroupApiSnapshot: true, syntheticOtherRegions: true,
    injectedStates: ["missing-flow", "stale-detail", "stale-overview", "detail-error", "error", "empty"],
    as_of: snapshots["theme|ALL|1d"].overview.as_of, passed: results,
    browserErrors: errors, mutations,
  }, null, 2));
  console.log(`${results.length} checks passed. Screenshots: ${output}`);
} finally {
  if (errors.length) console.error("Browser errors:", errors);
  await browser.close();
}
