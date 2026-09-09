import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { chromium } from "playwright";
import { fixtureFor } from "./marketExperience.fixtures.mjs";

const baseURL = process.env.UI_BASE_URL || "http://127.0.0.1:3138";
assert.ok(["127.0.0.1", "localhost"].includes(new URL(baseURL).hostname));
const output = process.env.UI_OUTPUT_DIR || "/tmp/insight-intraday-members-review";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: "chrome", headless: true });
const context = await browser.newContext({ baseURL, viewport: { width: 1440, height: 1000 }, serviceWorkers: "block", reducedMotion: "reduce" });
context.setDefaultTimeout(12000);
await context.addInitScript(() => Reflect.deleteProperty(Navigator.prototype, "serviceWorker"));
await context.addCookies([{ name: "ii_access", value: "insight-local-ui-review", url: baseURL }]);
const members = Array.from({ length: 28 }, (_, i) => ({
  ticker: String(100000 + i), name: `전기전자 예시 ${String(i + 1).padStart(2, "0")}`,
  market: i % 2 === 0 ? "KOSPI" : "KOSDAQ", close: 2000 + i * 100,
  chg_pct: i === 27 ? null : i - 12, value: (28 - i) * 1e8,
}));
const game = [{ ticker: "900001", name: "게임 예시 기업", market: "KOSDAQ", close: 12000, chg_pct: -2, value: 7e8 }];
const unclassified = [{ ticker: "900002", name: "", market: "KOSPI", close: 3000, chg_pct: null, value: 0 }];
const groups = { "전기전자": members, "게임": game, "기타": unclassified };
const sectors = Object.entries(groups).map(([name, rows]) => ({ name, n: rows.length,
  chg_pct: name === "기타" ? null : 2.3, value_krw: rows.reduce((sum, r) => sum + r.value, 0), flow: [] }));
const passed = [], errors = [], mutations = [], requests = [];
let mode = "normal", asOf = "2026-09-09 10:25", release;
let slowSector = null;
await context.route("**/api/backend/**", async (route) => {
  const req = route.request(), url = new URL(req.url());
  const path = url.pathname.split("/api/backend/")[1];
  if (req.method() !== "GET") mutations.push(path);
  let body = fixtureFor(path, url.searchParams, "normal"), status = 200;
  if (path === "meta") body = [{ ticker: members[0].ticker, meta_id: 111, iso_code: "KR" }, { ticker: game[0].ticker, meta_id: 222, iso_code: "US" }];
  if (path === "intraday/market") {
    const sector = url.searchParams.get("sector"); requests.push(sector);
    body = { ...body, active: true, is_open: true, as_of: asOf, trade_date: "2026-09-09", sectors };
    if (sector) body.sector_detail = { name: sector, members: groups[sector] ?? [] };
    if (mode === "missing-detail") delete body.sector_detail;
    if (mode === "error") { body = { detail: "Synthetic failure" }; status = 503; }
    if (mode === "stale") body = { active: false, is_open: true, unavailable_reason: "stale", as_of: asOf, trade_date: "2026-09-09" };
    if (slowSector && sector === slowSector) await new Promise((resolve) => { release = resolve; });
  }
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
});
const page = await context.newPage();
page.on("pageerror", (error) => errors.push(error.message));
page.on("console", (message) => { if (message.type() === "error" && !message.text().includes("Failed to load resource")) errors.push(message.text()); });
const detail = () => page.getByRole("region", { name: "장중 구성 종목", exact: true });
const tile = (name) => page.getByRole("button", { name: `${name} 구성 종목 보기`, exact: true });
async function ready(name, count) {
  await detail().getByRole("heading", { name: `${name} 구성 종목`, exact: true }).waitFor();
  await detail().getByText(`검색 결과 ${count}종목`, { exact: false }).waitFor();
  assert.equal(await tile(name).getAttribute("aria-pressed"), "true");
}
async function check(name, callback) { await callback(); passed.push(name); console.log(`PASS ${name}`); }
async function capture(name, target = detail()) {
  await target.evaluate((el) => window.scrollTo({ top: scrollY + el.getBoundingClientRect().top - 100, behavior: "instant" }));
  await page.screenshot({ path: `${output}/${name}.png` });
}
try {
  await check("Sector click opens full membership, preserves URL context and links registered stocks", async () => {
    await page.goto("/insight?tab=intraday&market=KOSDAQ&section=sectors");
    await tile("전기전자").click(); await ready("전기전자", 28);
    assert.equal(new URL(page.url()).searchParams.get("live_sector"), "전기전자");
    assert.equal(new URL(page.url()).searchParams.get("market"), "KOSDAQ");
    assert.equal(await detail().locator("tbody tr").count(), 25);
    assert.equal(await detail().getByRole("link", { name: members[0].name, exact: true }).first().getAttribute("href"), "/stock/111");
    assert.equal(await detail().getByRole("link", { name: members[1].name, exact: true }).first().getAttribute("href"), `/stocksearch?q=${encodeURIComponent(members[1].name)}`);
    assert.equal(await page.evaluate(() => document.activeElement?.textContent), "전기전자 구성 종목");
    await capture("desktop-members");
    await capture("desktop-heatmap", page.getByRole("region", { name: "장중 섹터 현황" }));
  });
  await check("Pagination, search, sort direction and null-last ordering work on all constituents", async () => {
    await detail().getByRole("button", { name: "장중 구성 종목 다음 페이지" }).click();
    assert.equal(await detail().locator("tbody tr").count(), 3);
    assert.match(await detail().locator("tbody tr").last().innerText(), /—/);
    await detail().getByRole("searchbox").fill("100003 KOSDAQ");
    assert.equal(await detail().locator("tbody tr").count(), 1);
    await detail().getByRole("searchbox").fill("no-match");
    await detail().getByText("일치하는 종목이 없습니다. 검색어를 바꿔보세요.").waitFor();
    await detail().getByRole("searchbox").fill("");
    await detail().getByRole("combobox").selectOption("chg_pct");
    assert.match(await detail().locator("tbody tr").first().innerText(), /전기전자 예시 27/);
    await detail().getByRole("button", { name: "오름차순으로 정렬" }).click();
    assert.match(await detail().locator("tbody tr").first().innerText(), /전기전자 예시 01/);
    await detail().getByRole("button", { name: "장중 구성 종목 다음 페이지" }).click();
    assert.match(await detail().locator("tbody tr").last().innerText(), /전기전자 예시 28/);
  });
  await check("Keyboard selection, browser history, reload and unknown-sector deep links remain usable", async () => {
    await tile("게임").press("Enter"); await ready("게임", 1);
    assert.ok((await detail().getByRole("link", { name: "게임 예시 기업" }).first().getAttribute("href")).startsWith("/stocksearch?"));
    await page.goBack(); await ready("전기전자", 28);
    await page.reload(); await ready("전기전자", 28);
    await page.goto("/insight?tab=intraday&live_sector=없는업종");
    await detail().getByText(/이 스냅샷에서 선택한 섹터의 종목을 찾지 못했습니다/).waitFor();
  });
  await check("Slow earlier selection never replaces a later sector or mixes its constituents", async () => {
    await page.goto("/insight?tab=intraday&live_sector=전기전자"); await ready("전기전자", 28);
    slowSector = "게임";
    await tile("게임").click();
    await detail().getByText("구성 종목을 확인하고 있습니다…", { exact: true }).waitFor();
    assert.equal(await detail().getByRole("link").count(), 0);
    await tile("기타").click(); await ready("기타", 1);
    const delayed = page.waitForResponse((r) => new URL(r.url()).searchParams.get("sector") === "게임");
    slowSector = null; release(); await delayed;
    assert.equal(new URL(page.url()).searchParams.get("live_sector"), "기타");
    assert.equal(await detail().getByRole("link", { name: "게임 예시 기업" }).count(), 0);
    await detail().getByRole("link", { name: "900002", exact: true }).first().waitFor();
  });
  await check("Missing detail and network failure retry; stale refresh hides constituents", async () => {
    mode = "missing-detail";
    await page.goto("/insight?tab=intraday&live_sector=전기전자");
    await detail().getByRole("alert").waitFor();
    mode = "normal";
    await detail().getByRole("button", { name: "다시 시도", exact: true }).click(); await ready("전기전자", 28);
    mode = "error";
    await page.getByRole("button", { name: "장중 스냅샷 새로고침" }).click();
    await page.getByRole("region", { name: "장중 스냅샷", exact: true }).getByRole("alert").waitFor();
    assert.equal(await detail().count(), 0);
    mode = "normal"; asOf = "2026-09-09 10:35";
    await page.getByRole("button", { name: "다시 시도", exact: true }).click(); await ready("전기전자", 28);
    await detail().getByText(/2026-09-09 10:35 기준/).waitFor();
    mode = "stale";
    await page.getByRole("button", { name: "장중 스냅샷 새로고침" }).click();
    await page.getByText("현재 표시할 장중 스냅샷이 없습니다", { exact: true }).waitFor();
    assert.equal(await detail().count(), 0);
  });
  await check("320/390px selection scrolls to mobile cards with no horizontal overflow; light mode stays legible", async () => {
    mode = "normal";
    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 844 });
      await page.goto("/insight?tab=intraday");
      await tile("전기전자").click(); await ready("전기전자", 28);
      await page.waitForFunction(() => {
        const y = document.querySelector("#intraday-sector-members h3")?.getBoundingClientRect().y;
        return y >= 50 && y < 250;
      });
      const heading = await detail().getByRole("heading").boundingBox();
      assert.ok(heading.y >= 50 && heading.y < 250, JSON.stringify(heading));
      assert.equal(await detail().locator("article:visible").count(), 25);
      // Scope this feature's overflow: the pre-existing three RankTables are separate.
      const bounds = await detail().boundingBox();
      assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= width);
      assert.ok(await detail().evaluate((el) => el.scrollWidth <= el.clientWidth));
      await capture(`mobile-${width}`);
      await detail().getByRole("button", { name: "섹터 다시 선택 ↑", exact: true }).click();
      assert.equal(await tile("전기전자").evaluate((el) => el === document.activeElement), true);
      await tile("게임").click(); await ready("게임", 1);
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.evaluate(() => document.documentElement.classList.add("light"));
    await capture("desktop-light");
  });
  assert.deepEqual(errors, []); assert.deepEqual(mutations, []);
  await writeFile(`${output}/results.json`, JSON.stringify({ syntheticFixtures: true, passed, requests, browserErrors: errors, mutations }, null, 2));
  console.log(`${passed.length} checks passed.`);
} catch (error) {
  await page.screenshot({ path: `${output}/failure.png` });
  console.error(errors);
  throw error;
} finally { release?.(); await browser.close(); }
