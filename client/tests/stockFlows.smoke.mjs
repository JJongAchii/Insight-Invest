import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { chromium } from "playwright";
import { fixtureFor } from "./marketExperience.fixtures.mjs";

const baseURL = process.env.UI_BASE_URL || "http://127.0.0.1:3143";
assert.ok(["localhost", "127.0.0.1"].includes(new URL(baseURL).hostname));
const output = process.env.UI_OUTPUT_DIR || "/tmp/insight-stock-flow-review";
await mkdir(output, { recursive: true });
const dates = Array.from({ length: 30 }, (_, i) => new Date(Date.UTC(2026, 7, 16 + i)).toISOString().slice(0, 10));
let priceSnapshot = {
  meta: { meta_id: 3969, ticker: "000660", name: "수급 검증 종목", iso_code: "KR", security_type: "STOCK", marketcap: 1e12 },
  prices: dates.map((date, i) => ({ trade_date: `${date}T00:00:00`, value: 100000 + i * 1000, adj_close: 100000 + i * 1000, gross_return: 0.01 })),
};
let flowSnapshot = { ticker: "000660", as_of: "2026-09-14", rows: dates.map((date, i) => ({ date, frgn_net: (i % 2 ? -1 : 1) * (i + 1) * 1e8, inst_net: (i % 3 ? 1 : -1) * (i + 2) * 1e8, indiv_net: 0 })) };
if (process.env.STOCK_FLOW_SNAPSHOTS) {
  priceSnapshot = JSON.parse(await readFile(`${process.env.STOCK_FLOW_SNAPSHOTS}/prices-000660.json`, "utf8"));
  flowSnapshot = JSON.parse(await readFile(`${process.env.STOCK_FLOW_SNAPSHOTS}/flows-000660.json`, "utf8"));
}
const browser = await chromium.launch({ channel: "chrome", headless: true });
const context = await browser.newContext({ baseURL, viewport: { width: 1440, height: 1100 }, serviceWorkers: "block", reducedMotion: "reduce", timezoneId: "America/Los_Angeles" });
context.setDefaultTimeout(15000);
await context.addInitScript(() => Reflect.deleteProperty(Navigator.prototype, "serviceWorker"));
await context.addCookies([{ name: "ii_access", value: "insight-local-ui-review", url: baseURL }]);
let mode = "normal", releaseFlow;
const errors = [], requests = [], mutations = [], passed = [];
await context.route("**/api/backend/**", async route => {
  const request = route.request(), url = new URL(request.url()), path = url.pathname.split("/api/backend/")[1];
  requests.push(path + url.search);
  if (request.method() !== "GET" && path !== "insight/factor-exposure") mutations.push(path);
  let body;
  const isUS = path.includes("/9001");
  const meta = isUS ? { ...priceSnapshot.meta, meta_id: 9001, ticker: "TEST", name: "US 검증 종목", iso_code: "US", security_type: "STOCK" } : { ...priceSnapshot.meta, security_type: "STOCK" };
  if (/^stock\/\d+$/.test(path)) body = { meta, summary: { latest_price: priceSnapshot.prices.at(-1).value, latest_date: "2026-09-14", metrics: {}, flows_recent: null }, in_watchlist: false, holding: null };
  else if (/^price\/\d+$/.test(path)) body = { ...priceSnapshot, meta, prices: priceSnapshot.prices.filter(p => p.trade_date.slice(0, 10) >= url.searchParams.get("start_date")) };
  else if (path.startsWith("insight/flows/ticker/")) {
    if (mode === "error") return route.fulfill({ status: 500, json: { detail: "Synthetic flow request failure" } });
    if (mode === "loading") await new Promise(resolve => { releaseFlow = resolve; });
    body = structuredClone(flowSnapshot);
    if (mode === "empty") body.rows = [];
    if (mode === "outside") body.rows = body.rows.map(row => ({ ...row, date: "2000-01-03" }));
    if (mode === "partial") body.rows.forEach(row => { row.frgn_net = null; });
    if (mode === "zero") body.rows.forEach((row, i) => { row.frgn_net = i === body.rows.length - 1 ? 0 : null; row.inst_net = null; });
  } else if (path === "insight/factor-exposure") body = { exposures: [], note: "UI fixture" };
  else if (path.endsWith("/fundamentals")) body = { available: false, note: "UI fixture" };
  else body = fixtureFor(path, url.searchParams, "normal");
  await route.fulfill({ json: body });
});
await context.route("https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js", route => route.fulfill({ contentType: "application/javascript", body: `(() => { const host=document.currentScript.parentElement; const frame=document.createElement('iframe'); frame.src='https://www.tradingview-widget.com/embed-widget/ticker-tape/'; frame.style.cssText='height:46px;width:100%;border:0;display:block';host.style.height='78px';host.prepend(frame);host.querySelector('.tradingview-widget-copyright').style.cssText='height:32px;text-align:center;font-size:12px;line-height:32px'; })();` }));
await context.route("https://www.tradingview-widget.com/embed-widget/ticker-tape/", route => route.fulfill({ contentType: "text/html; charset=utf-8", body: '<html><body style="margin:0;background:#101726;color:#94a3b8;font:12px sans-serif;padding:14px">화면 검증용 시세 영역<script>parent.postMessage({name:"tv-widget-resize-iframe"},"*")</script></body></html>' }));
const page = await context.newPage();
await page.clock.setFixedTime(new Date("2026-09-15T00:00:00Z"));
page.on("pageerror", error => errors.push(error.message));
const info = () => page.getByRole("region", { name: "투자자 수급 정보" });
const bars = () => page.locator(".recharts-bar-rectangle path");
const check = async (name, run) => { await run(); passed.push(name); console.log(`PASS ${name}`); };
const ready = async () => { await info().getByText(/최근 수급/).waitFor(); await bars().first().waitFor(); };
const capture = async name => {
  await page.getByRole("heading", { name: "가격 · 투자자 수급", exact: true }).evaluate(element => window.scrollTo({ top: scrollY + element.getBoundingClientRect().top - 110, behavior: "instant" }));
  await page.evaluate(async () => { await document.fonts.ready; });
  await page.screenshot({ path: `${output}/${name}.png` });
};
try {
  await page.goto("/stock/3969"); await ready();
  await check("Timestamped prices join day-only flows; foreign, institution and both render real bars", async () => {
    const count = await bars().count();
    assert.ok(count > 0);
    await page.getByRole("button", { name: "기관", exact: true }).click(); await ready();
    assert.equal(await bars().count(), count);
    await page.getByRole("button", { name: "함께", exact: true }).click(); await ready();
    assert.equal(await bars().count(), count * 2);
    const last = flowSnapshot.rows.at(-1);
    for (const value of [last.frgn_net, last.inst_net]) {
      assert.ok((await info().innerText()).includes((value / 1e8).toLocaleString("ko-KR", { maximumFractionDigits: 1 })));
    }
    await bars().last().hover({ force: true });
    await page.getByText("기관 순매수", { exact: true }).waitFor();
    assert.ok((await info().innerText()).includes("2026. 09. 14."));
    await page.mouse.move(10, 10);
    await capture("stock-flows-desktop-dark");
  });
  await check("Period changes refetch flows and disclose the actual displayed coverage", async () => {
    for (const [label, months] of [["3M",3],["6M",6],["1Y",12],["3Y",36],["ALL",120]]) {
      await page.getByRole("button", { name: label, exact: true }).click(); await ready();
      assert.ok(requests.some(r => r.endsWith(`flows/ticker/000660?months=${months}`)));
      await info().getByText(/수급 표시 구간/).waitFor();
    }
    await page.getByRole("button", { name: "1Y", exact: true }).click(); await ready();
  });
  await check("Loading and request failures keep the price visible, with a working retry", async () => {
    mode = "loading"; await page.reload();
    await info().getByText("수급 데이터를 불러오는 중…", { exact: true }).waitFor();
    await page.locator(".recharts-line-curve").waitFor();
    assert.equal(await bars().count(), 0);
    mode = "normal"; releaseFlow(); await ready();
    mode = "error"; await page.reload();
    await info().getByRole("alert").waitFor();
    await page.locator(".recharts-line-curve").waitFor();
    mode = "normal"; await info().getByRole("button", { name: "수급 다시 시도", exact: true }).click(); await ready();
  });
  await check("Empty, unmatched and null flows stay missing; genuine zero remains visible", async () => {
    for (mode of ["empty", "outside"]) {
      await page.reload(); await info().getByText(/수급 데이터가 없습니다/).waitFor();
      assert.equal(await bars().count(), 0);
    }
    mode = "partial"; await page.reload();
    await info().getByText(/외국인 수급 데이터가 없습니다/).waitFor();
    await page.getByRole("button", { name: "함께", exact: true }).click(); await ready();
    await info().getByText("미제공", { exact: true }).waitFor();
    mode = "zero"; await page.reload();
    await info().getByText("0억", { exact: true }).waitFor();
    assert.equal(await info().getByText(/수급 데이터가 없습니다/).count(), 0);
  });
  await check("Desktop, 320/390px, both themes and US price-only views remain usable", async () => {
    mode = "normal"; await page.reload(); await ready();
    await page.getByRole("button", { name: "함께", exact: true }).click();
    await page.getByRole("button", { name: "라이트 모드로 전환" }).click();
    await capture("stock-flows-desktop-light");
    for (const width of [390,320]) {
      await page.setViewportSize({ width, height: 950 }); await ready();
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await capture(`stock-flows-mobile-${width}`);
    }
    const before = requests.filter(r => r.startsWith("insight/flows/ticker")).length;
    await page.goto("/stock/9001");
    await page.getByRole("heading", { name: "가격 흐름", exact: true }).waitFor();
    await page.locator(".recharts-line-curve").waitFor();
    assert.equal(await info().count(),0);
    assert.equal(requests.filter(r => r.startsWith("insight/flows/ticker")).length,before);
  });
  assert.deepEqual(errors, []); assert.deepEqual(mutations, []);
  await writeFile(`${output}/browser-results.json`, JSON.stringify({ passed, errors, mutations, source: process.env.STOCK_FLOW_SNAPSHOTS ? "Real local API payloads from S3 for KR price/flow charts; other regions and failure cases are fixtures. No authenticated production page was used." : "Synthetic API fixtures", snapshotRows: { prices: priceSnapshot.prices.length, flows: flowSnapshot.rows.length } }, null, 2));
} catch(error) { await page.screenshot({ path: `${output}/stock-flows-failure.png` }); throw error; }
finally { releaseFlow?.(); await browser.close(); }
