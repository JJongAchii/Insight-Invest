import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { chromium } from "playwright";
import { fixtureFor } from "./marketExperience.fixtures.mjs";

const baseURL = process.env.UI_BASE_URL || "http://127.0.0.1:3141";
assert.ok(["127.0.0.1", "localhost"].includes(new URL(baseURL).hostname));
const output = process.env.UI_OUTPUT_DIR || "/tmp/insight-global-ticker-review";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: "chrome", headless: true });
const passed = [], errors = [], mutations = [];
let mode = "normal", scriptRequests = 0, release;
const scriptURL = "https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js";
const mockScript = `(() => {
  const script = document.currentScript, host = script.parentElement;
  const config = JSON.parse(script.textContent), frame = document.createElement('iframe');
  frame.src = 'https://www.tradingview-widget.com/embed-widget/ticker-tape/?theme=' + config.colorTheme;
  frame.style.cssText = 'display:block;width:100%;height:46px;border:0';
  host.style.height = '78px';
  host.querySelector('.tradingview-widget-container__widget').replaceWith(frame);
  host.querySelector('.tradingview-widget-copyright').style.cssText = 'height:32px;line-height:32px;text-align:center;font-size:12px;white-space:nowrap';
})();`;
async function contextFor(real = false) {
  const context = await browser.newContext({ baseURL, viewport: { width: 1440, height: 1000 }, serviceWorkers: "block", reducedMotion: "reduce" });
  context.setDefaultTimeout(20000);
  await context.addInitScript(() => Reflect.deleteProperty(Navigator.prototype, "serviceWorker"));
  await context.addCookies([{ name: "ii_access", value: "insight-local-ui-review", url: baseURL }]);
  await context.route("**/api/backend/**", async (route) => {
    const url = new URL(route.request().url()), path = url.pathname.split("/api/backend/")[1];
    if (route.request().method() !== "GET") mutations.push(path);
    await route.fulfill({ json: fixtureFor(path, url.searchParams, "normal") });
  });
  if (!real) {
    await context.route(scriptURL, async (route) => {
      scriptRequests++;
      if (mode === "script-error") return route.abort("failed");
      if (mode === "loading") await new Promise((resolve) => { release = resolve; });
      await route.fulfill({ contentType: "application/javascript", body: mockScript });
    });
    await context.route("https://www.tradingview-widget.com/embed-widget/ticker-tape/**", async (route) => {
      const dark = new URL(route.request().url()).searchParams.get("theme") === "dark";
      const notify = mode === "iframe-error" ? "" : '<script>parent.postMessage({name:"tv-widget-resize-iframe",data:{height:46}},"*")</script>';
      await route.fulfill({ contentType: "text/html; charset=utf-8", body: `<html><body style="margin:0;background:${dark ? "#0f0f0f" : "#fff"};color:${dark ? "#ddd" : "#333"};font:14px sans-serif;line-height:46px">UI 검증용 시세${notify}</body></html>` });
    });
  }
  context.on("page", (page) => page.on("pageerror", (error) => errors.push(error.message)));
  return context;
}
const bar = (page) => page.getByRole("complementary", { name: "글로벌 시장 시세", exact: true });
const ready = (page) => bar(page).locator('[data-status="ready"]').waitFor();
async function check(name, callback) { await callback(); passed.push(name); console.log(`PASS ${name}`); }
async function geometry(page, mobile) {
  // Even reduced-motion transitions settle on the next rendered frame.
  await page.waitForFunction((isMobile) => {
    const rect = document.querySelector('aside[aria-label="글로벌 시장 시세"]').getBoundingClientRect();
    const bottom = isMobile ? document.querySelector('nav[aria-label="주요 탐색"]').getBoundingClientRect().top : innerHeight;
    return Math.round(rect.height) === 79 && Math.abs(rect.bottom - bottom) <= 1;
  }, mobile);
  const rect = await bar(page).boundingBox(), viewport = page.viewportSize();
  assert.ok(rect.x >= 0 && rect.x + rect.width <= viewport.width + 1);
  assert.equal(Math.round(rect.height), 79);
  if (mobile) {
    const nav = await page.getByRole("navigation", { name: "주요 탐색" }).boundingBox();
    assert.ok(Math.abs(rect.y + rect.height - nav.y) <= 1);
  } else assert.ok(Math.abs(rect.y + rect.height - viewport.height) <= 1);
  const credit = await bar(page).locator(".tradingview-widget-copyright").boundingBox();
  assert.ok(credit.y >= rect.y && credit.y + credit.height <= rect.y + rect.height + 1);
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  return rect;
}
async function capture(page, name) { await page.screenshot({ path: `${output}/${name}.png` }); }
let page;
try {
  const context = await contextFor(); page = await context.newPage();
  await check("Persistent ticker survives Next page navigation with one iframe and script", async () => {
    await page.goto("/home"); await ready(page);
    const frame = await bar(page).locator("iframe").elementHandle(), before = scriptRequests;
    assert.equal(await page.locator(".tradingview-widget-container").count(), 1);
    for (const path of ["/insight", "/regime", "/research", "/stocksearch", "/earnings", "/data-trust", "/home"]) {
      await page.locator(`a[href="${path}"]:visible`).first().click();
      await page.waitForURL((url) => url.pathname === path);
      assert.equal(await frame.evaluate((el) => el.isConnected), true);
      await geometry(page, false);
    }
    assert.equal(scriptRequests, before);
    await page.evaluate(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "instant" }));
    const rect = await geometry(page, false), last = await page.locator("main details").last().boundingBox();
    assert.ok(last.y + last.height < rect.y, "Last content must clear the fixed tape");
  });
  await check("Theme changes replace only the widget; sidebar collapse adjusts its boundary", async () => {
    const original = await bar(page).locator("iframe").elementHandle();
    await page.getByRole("button", { name: "라이트 모드로 전환" }).click();
    await page.getByRole("button", { name: "다크 모드로 전환" }).waitFor(); await ready(page);
    assert.equal(await original.evaluate((el) => el.isConnected), false);
    assert.match(await bar(page).locator("iframe").getAttribute("src"), /theme=light/);
    assert.equal(await bar(page).locator("iframe").count(), 1);
    await page.getByRole("button", { name: "사이드바 접기 또는 메뉴 열기" }).click();
    await page.getByRole("button", { name: "사이드바 펼치기", exact: true }).waitFor();
    await page.waitForFunction(() => document.querySelector('aside[aria-label="글로벌 시장 시세"]').getBoundingClientRect().x === 72);
    assert.equal(Math.round((await bar(page).boundingBox()).x), 72);
    await page.getByRole("button", { name: "다크 모드로 전환" }).click(); await ready(page);
  });
  await check("Mobile and tablet preserve menu access, content clearance and install prompts", async () => {
    for (const width of [768, 390, 320]) {
      await page.setViewportSize({ width, height: 844 });
      await page.goto("/home"); await ready(page); await geometry(page, width < 768);
      await page.evaluate(() => window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "instant" }));
      const rect = await geometry(page, width < 768), last = await page.locator("main details").last().boundingBox();
      assert.ok(last.y + last.height < rect.y);
      if (width < 768) {
        const frame = await bar(page).locator("iframe").elementHandle();
        await page.getByRole("navigation", { name: "주요 탐색" }).getByRole("link", { name: "경제", exact: true }).click();
        await page.waitForURL("**/regime");
        assert.equal(await frame.evaluate((el) => el.isConnected), true);
        await page.getByRole("button", { name: /사이드바 펼치기|사이드바 접기 또는 메뉴 열기/ }).click();
        await page.locator('button.fixed[aria-label="메뉴 닫기"]').waitFor();
        await page.keyboard.press("Escape");
        await page.locator('button.fixed[aria-label="메뉴 닫기"]').waitFor({ state: "detached" });
      }
    }
    await page.evaluate(() => {
      const event = new Event("beforeinstallprompt");
      event.prompt = async () => {}; event.userChoice = Promise.resolve({ outcome: "dismissed" });
      dispatchEvent(event);
    });
    const prompt = page.getByRole("region", { name: "앱 설치 안내" }); await prompt.waitFor();
    const promptRect = await prompt.boundingBox(), tickerRect = await bar(page).boundingBox();
    assert.ok(promptRect.y + promptRect.height < tickerRect.y);
    await page.getByRole("button", { name: "설치 안내 닫기" }).click();
  });
  await check("Loading reserves space; blocked script and iframe both offer recovery", async () => {
    mode = "loading"; await page.goto("/home", { waitUntil: "domcontentloaded" });
    await bar(page).getByText("글로벌 시세를 연결하고 있습니다…").waitFor();
    const before = await bar(page).boundingBox();
    mode = "normal"; release(); await ready(page);
    assert.deepEqual(await bar(page).boundingBox(), before);
    for (const failure of ["script-error", "iframe-error"]) {
      mode = failure; await page.reload({ waitUntil: "domcontentloaded" });
      if (failure === "iframe-error") {
        await page.evaluate(() => dispatchEvent(new MessageEvent("message", { data: { name: "tv-widget-resize-iframe" }, origin: "https://www.tradingview-widget.com", source: window })));
        assert.equal(await bar(page).locator('[data-status="ready"]').count(), 0);
      }
      await bar(page).getByText("글로벌 시세에 연결하지 못했습니다", { exact: true }).waitFor();
      await capture(page, `failure-${failure}`);
      mode = "normal"; await bar(page).getByRole("button", { name: "다시 시도" }).click(); await ready(page);
    }
  });
  await check("Login and offline screens do not load the ticker", async () => {
    for (const path of ["/login", "/offline"]) { await page.goto(path); assert.equal(await bar(page).count(), 0); }
  });
  await context.close();
  const liveContext = await contextFor(true); page = await liveContext.newPage();
  let liveScripts = 0;
  page.on("request", (request) => { if (request.url() === scriptURL) liveScripts++; });
  await check("Official TradingView quotes, source attribution and both themes render correctly", async () => {
    await page.goto("/home"); await ready(page);
    const frame = page.frameLocator('iframe[title="글로벌 시장 시세 — TradingView"]');
    await frame.getByText("NASDAQ 100 CFD", { exact: true }).first().waitFor();
    await frame.locator(".tv-ticker-item-tape").filter({ hasText: "NASDAQ 100 CFD" }).first().getByText(/%/).first().waitFor();
    assert.equal(await frame.locator('.js-exclamationed-symbol[title="이 심볼은 트레이딩뷰에서만 볼 수 있습니다"]').count(), 0);
    await geometry(page, false); await capture(page, "real-desktop-dark");
    const retained = await bar(page).locator("iframe").elementHandle(), before = liveScripts;
    await page.locator('a[href="/regime"]:visible').first().click(); await page.waitForURL("**/regime");
    assert.equal(await retained.evaluate((el) => el.isConnected), true); assert.equal(liveScripts, before);
    await page.getByRole("button", { name: "라이트 모드로 전환" }).click(); await ready(page);
    await page.frameLocator('iframe').getByText("NASDAQ 100 CFD", { exact: true }).first().waitFor();
    const config = JSON.parse(decodeURIComponent(new URL(await bar(page).locator("iframe").getAttribute("src")).hash.slice(1)));
    assert.equal(config.colorTheme, "light"); await capture(page, "real-desktop-light");
    await page.getByRole("button", { name: "다크 모드로 전환" }).click(); await ready(page);
    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 844 }); await geometry(page, true);
      await page.getByRole("navigation", { name: "주요 탐색" }).getByRole("link", { name: "한국 시장", exact: true }).click();
      await page.waitForURL("**/insight");
      await page.frameLocator('iframe').getByText("NASDAQ 100 CFD", { exact: true }).first().waitFor({ state: "attached" });
      await capture(page, `real-mobile-${width}`);
    }
  });
  await liveContext.close();
  assert.deepEqual(errors, []);
  assert.ok(mutations.every((path) => path === "research/seen"), "Only the existing, mocked research acknowledgement is allowed");
  await writeFile(`${output}/results.json`, JSON.stringify({ passed, browserErrors: errors, mockedMutations: mutations, fixtures: "All app APIs and failure scenarios are synthetic; final TradingView scenario uses the real official widget", liveScriptRequests: liveScripts }, null, 2));
  console.log(`${passed.length} checks passed.`);
} catch (error) { if (page && !page.isClosed()) await capture(page, "failure"); console.error(errors); throw error; }
finally { release?.(); await browser.close(); }
