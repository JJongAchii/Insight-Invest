import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { chromium } from "playwright";
import { fixtureFor } from "./marketExperience.fixtures.mjs";

// Run a local Next production server with the same test access hash used by
// marketExperience.smoke.mjs. Every backend request is intercepted.
const baseURL = process.env.UI_BASE_URL || "http://127.0.0.1:3137";
assert.ok(["127.0.0.1", "localhost"].includes(new URL(baseURL).hostname));
const output = process.env.UI_OUTPUT_DIR || "/tmp/insight-intraday-tab-review";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: "chrome", headless: true });
const context = await browser.newContext({ baseURL, viewport: { width: 1440, height: 1000 }, serviceWorkers: "block", reducedMotion: "reduce" });
context.setDefaultTimeout(12000);
await context.addInitScript(() => Reflect.deleteProperty(Navigator.prototype, "serviceWorker"));
await context.addCookies([{ name: "ii_access", value: "insight-local-ui-review", url: baseURL }]);
let mode = "legacy-empty", requests = 0, releaseLoading;
const loadingGate = new Promise((resolve) => { releaseLoading = resolve; });
const passed = [], errors = [], mutations = [];
const asOf = "2026-09-09 09:25";
await context.route("**/api/backend/**", async (route) => {
  const request = route.request(), url = new URL(request.url());
  const path = url.pathname.split("/api/backend/")[1];
  if (request.method() !== "GET") mutations.push(path);
  let status = 200, body = fixtureFor(path, url.searchParams, "normal");
  if (path === "intraday/market") {
    requests += 1;
    if (mode === "loading") await loadingGate;
    if (mode === "legacy-empty") body = { active: false };
    else if (mode === "error") { status = 503; body = { detail: "Synthetic network failure" }; }
    else if (mode === "server-error") body = { active: false, unavailable_reason: "error", is_open: true };
    else if (mode === "stale") body = { active: false, unavailable_reason: "stale", as_of: "2026-09-08 15:35", trade_date: "2026-09-08", is_open: true };
    else if (mode === "inconsistent") body = { active: false, unavailable_reason: "inconsistent", as_of: asOf, trade_date: "2026-09-09", is_open: true };
    else body = { ...body, is_open: mode !== "closed", as_of: asOf, trade_date: "2026-09-09" };
  }
  await route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
});
const page = await context.newPage();
page.on("pageerror", (error) => errors.push(error.message));
page.on("console", (message) => {
  if (message.type() === "error" && !message.text().includes("Failed to load resource")) errors.push(message.text());
});
const button = () => page.getByRole("button", { name: /^(장중 흐름 · 지연|최근 장중 스냅샷)$/ });
const panel = () => page.getByRole("region", { name: "장중 스냅샷", exact: true });
const selected = async () => assert.equal(await button().getAttribute("aria-pressed"), "true");
async function empty() { await panel().getByText("현재 표시할 장중 스냅샷이 없습니다", { exact: true }).waitFor(); }
async function active() { await panel().getByText(`지연 시세 · ${asOf} 기준 (~20분 지연)`, { exact: true }).waitFor(); }
async function check(name, callback) { await callback(); passed.push(name); console.log(`PASS ${name}`); }
async function capture(name) {
  await page.getByRole("button", { name: "정산 분석", exact: true }).evaluate((el) => window.scrollTo({ top: scrollY + el.getBoundingClientRect().top - 100, behavior: "instant" }));
  await page.screenshot({ path: `${output}/${name}.png` });
}
try {
  if (process.env.UI_REPRO_OLD === "1") {
    await page.goto("/insight?tab=settled");
    await button().waitFor();
    assert.equal(await button().isDisabled(), true);
    const before = page.url();
    await button().evaluate((element) => element.click());
    assert.equal(page.url(), before);
    await page.goto("/insight?tab=intraday");
    await page.getByText("장중 스냅샷이 없어 정산 데이터를 표시합니다.").waitFor();
    assert.equal(await button().getAttribute("aria-pressed"), "false");
    await capture("before-disabled");
    await writeFile(`${output}/before.json`, JSON.stringify({ reproduced: true, sourceCommit: "962292282b904fc1c95d5738d32a23b04ba5780e", inactiveButtonDisabled: true, explicitIntradayLinkFallsBackToSettled: true }, null, 2));
    console.log("REPRODUCED: unavailable data disables the button and overrides the explicit tab");
  } else {
    await check("Pending request does not disable navigation or override a later settled selection", async () => {
      mode = "loading";
      await page.goto("/insight?tab=settled", { waitUntil: "domcontentloaded" });
      await button().waitFor();
      assert.equal(await button().isEnabled(), true);
      await button().press("Enter");
      await selected();
      await panel().getByText("장중 스냅샷을 확인하고 있습니다…", { exact: true }).waitFor();
      await page.getByRole("button", { name: "정산 분석", exact: true }).click();
      mode = "normal"; releaseLoading();
      await page.waitForResponse((res) => res.url().includes("intraday/market"));
      assert.equal(new URL(page.url()).searchParams.get("tab"), "settled");
      assert.equal(await panel().count(), 0);
    });
    await check("Legacy inactive response opens an empty state and retries immediately", async () => {
      mode = "legacy-empty";
      await page.goto("/insight?tab=settled&section=flows&market=KOSDAQ");
      const before = page.url();
      await button().click();
      await selected(); await empty();
      await capture("after-empty");
      const oldRequests = requests;
      mode = "normal";
      await panel().getByRole("button", { name: "다시 조회", exact: true }).click();
      await active(); await selected();
      assert.ok(requests > oldRequests);
      await page.goBack();
      assert.equal(page.url(), before);
      assert.equal(await page.getByRole("button", { name: "투자자 수급", exact: true }).getAttribute("aria-pressed"), "true");
    });
    await check("Stale deep link and reload preserve the requested tab and last observation", async () => {
      mode = "stale";
      await page.goto("/insight?tab=intraday&market=KOSDAQ");
      await empty(); await selected();
      await panel().getByText("마지막 관측 2026-09-08 15:35", { exact: true }).waitFor();
      assert.equal(await panel().getByText("시장폭 (KR 전 종목)", { exact: true }).count(), 0);
      const before = page.url(), historyLength = await page.evaluate(() => history.length);
      await button().click(); await empty();
      assert.equal(await page.evaluate(() => history.length), historyLength);
      await page.reload(); await empty(); await selected();
      assert.equal(page.url(), before);
      await capture("after-stale");
    });
    await check("Transport errors and server assembly failures show a retryable error", async () => {
      for (const failure of ["error", "server-error"]) {
        mode = failure;
        await page.goto("/insight?tab=intraday");
        await panel().getByRole("alert").waitFor(); await selected();
        mode = "normal";
        await panel().getByRole("button", { name: "다시 시도", exact: true }).click();
        await active(); await selected();
      }
    });
    await check("Refresh to unavailable data stays on intraday; market close preserves the snapshot", async () => {
      mode = "inconsistent";
      await panel().getByRole("button", { name: "장중 스냅샷 새로고침" }).click();
      await empty(); await selected();
      await panel().getByText(/종목과 추이 자료의 기준일을 맞추는 중/).waitFor();
      mode = "closed";
      await panel().getByRole("button", { name: "다시 조회", exact: true }).click();
      await active(); await selected();
      await panel().getByText("마감 스냅샷", { exact: true }).waitFor();
      await capture("after-ready");
    });
    await check("Mobile 390/320px, keyboard selection and legacy live URL remain usable", async () => {
      await page.setViewportSize({ width: 390, height: 844 });
      mode = "stale";
      await page.goto("/insight?tab=live&market=KOSDAQ");
      await empty(); await selected();
      await page.getByRole("button", { name: "정산 분석", exact: true }).press("Enter");
      await button().press("Enter"); await empty();
      for (const width of [390, 320]) {
        await page.setViewportSize({ width, height: 844 });
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        await capture(`mobile-${width}`);
      }
    });
    assert.deepEqual(errors, []);
    assert.deepEqual(mutations, []);
    await writeFile(`${output}/results.json`, JSON.stringify({ syntheticFixtures: true, passed, browserErrors: errors, mutations }, null, 2));
    console.log(`${passed.length} checks passed.`);
  }
} finally {
  releaseLoading();
  if (errors.length) console.error(errors);
  await browser.close();
}
