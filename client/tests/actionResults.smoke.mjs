import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { chromium } from "playwright";
import { fixtureFor } from "./marketExperience.fixtures.mjs";

const baseURL = process.env.UI_BASE_URL || "http://127.0.0.1:3142";
assert.ok(["127.0.0.1", "localhost"].includes(new URL(baseURL).hostname));
const output = process.env.UI_OUTPUT_DIR || "/tmp/insight-action-results-review";
await mkdir(output, { recursive: true });
const metric = (overrides = {}) => ({
  label: "소비자물가 · 전년비", unit: "%", actual: 3.1, estimate: null, previous: 2.9,
  actual_period: "2026-08-01", previous_period: "2026-07-01", frequency: "monthly",
  comparison: "previous", difference: 0.2, difference_unit: "%p", source_url: "",
  status: "released", note: null, ...overrides,
});
const summary = (metrics, overrides = {}) => ({ status: "released", source: "검증용 FRED", available_at: "2026-09-15T09:00:00+09:00", note: "화면 검증용 수치 · 예상치 미제공", metrics, ...overrides });
const items = [
  ["US CPI", "macro", summary([metric(), metric({ label: "소비자물가 · 전월비", actual: 0, previous: -0.2 })])],
  ["고용 발표 예정", "macro", summary([metric({ label: "비농업 고용", actual: null, previous: 180, unit: "천 명", difference: null, actual_period: null, status: "scheduled" })], { status: "scheduled" })],
  ["기업 실적", "earnings", summary([metric({ label: "주당순이익 (EPS)", unit: "USD/주", actual: 2.2, estimate: 2, previous: null, comparison: "estimate", difference: 10, difference_unit: "%", frequency: "fiscal", actual_period: "2026 Q3" })])],
  ["공식 실적", "earnings", summary([metric({ label: "주당순이익 (EPS)", unit: "USD/주", actual: 2.2, estimate: 2, comparison: "estimate", difference: null, note: "공식 EPS · 회계 기준이 달라 예상 대비 비교 보류" })])],
  ["GDP 반영 대기", "macro", summary([metric({ label: "실질 GDP", actual: null, actual_period: null, previous_period: "2026-04-01", frequency: "quarterly", difference: null, status: "pending" })], { status: "pending" })],
  ["PPI 수집 실패", "macro", summary([metric({ actual: null, previous: null, actual_period: null, previous_period: null, difference: null, status: "unavailable" })], { status: "unavailable" })],
  ["FOMC 정책 일정", "macro", null],
  ["투자 논거 검토", "journal", null],
].map(([title, category, result_summary], index) => ({
  event_id: String(index + 1).padStart(24, "0"), title, category, result_summary,
  kind: category === "journal" ? "review" : "event", severity: "medium", detail: "화면 검증용 항목",
  link: category === "earnings" ? "/earnings" : "/regime", meta_id: null, ticker: null, name: null,
  market: "US", scope: "market", event_status: "confirmed", occurred_at: "2026-09-11",
  scheduled_for: "2026-09-11", available_at: "2026-09-15T09:00:00+09:00", data_as_of: "2026-09-11",
  source: title.includes("FOMC") ? "federal_reserve" : "fred", actions: ["open", "snooze", "dismiss"], state: "new", snoozed_until: null,
}));
const response = () => ({ generated_at: "2026-09-15T09:00:00+09:00", data_as_of: "2026-09-11", items, calendar: items, sources: [], counts: { total: 8, actionable: 8, high: 0, new: 8, badge: 8, scheduled: 8, external: 7 } });
const browser = await chromium.launch({ channel: "chrome", headless: true });
const context = await browser.newContext({ baseURL, viewport: { width: 1440, height: 1100 }, reducedMotion: "reduce", serviceWorkers: "block" });
context.setDefaultTimeout(15000);
await context.addInitScript(() => Reflect.deleteProperty(Navigator.prototype, "serviceWorker"));
await context.addCookies([{ name: "ii_access", value: "insight-local-ui-review", url: baseURL }]);
const mutations = [], errors = [], passed = [];
let unavailable = false;
await context.route("**/api/backend/**", async (route) => {
  const url = new URL(route.request().url()), path = url.pathname.split("/api/backend/")[1];
  if (path === "actions") return unavailable ? route.fulfill({ status: 503, json: { detail: "fixture unavailable" } }) : route.fulfill({ json: response() });
  if (/^actions\/.+\/state$/.test(path)) {
    const body = route.request().postDataJSON(); mutations.push({ path, ...body });
    return route.fulfill({ json: { event_id: path.split("/")[1], ...body } });
  }
  return route.fulfill({ json: fixtureFor(path, url.searchParams, "normal") });
});
await context.route("https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js", async (route) => route.fulfill({
  contentType: "application/javascript", body: `(() => { const host = document.currentScript.parentElement;
    const frame = document.createElement('iframe'); frame.src='https://www.tradingview-widget.com/embed-widget/ticker-tape/';
    frame.style.cssText='height:46px;width:100%;border:0;display:block';host.style.height='78px';host.prepend(frame);
    host.querySelector('.tradingview-widget-copyright').style.cssText='height:32px;text-align:center;font-size:12px;line-height:32px'; })();`,
}));
await context.route("https://www.tradingview-widget.com/embed-widget/ticker-tape/", route => route.fulfill({ contentType: "text/html; charset=utf-8", body: '<html><body style="margin:0;background:#101726;color:#94a3b8;font:12px sans-serif;padding:14px">화면 검증용 시세 영역<script>parent.postMessage({name:"tv-widget-resize-iframe"},"*")</script></body></html>' }));
const page = await context.newPage(); page.on("pageerror", error => errors.push(error.message));
const card = title => page.getByRole("article").filter({ has: page.getByRole("heading", { name: title, exact: true }) });
const check = async (name, run) => { await run(); passed.push(name); console.log(`PASS ${name}`); };
try {
  await page.goto("/actions"); await card("US CPI").getByRole("region", { name: "발표 수치 요약" }).waitFor();
  await check("Numbers, periods, units and missing estimates are visible without opening details", async () => {
    const cpi = card("US CPI");
    await cpi.getByText("3.1%", { exact: true }).waitFor();
    await cpi.getByText("0%", { exact: true }).waitFor();
    assert.equal(await cpi.getByText("미제공", { exact: true }).count(), 2);
    assert.equal(await cpi.getByText("+0.2%p", { exact: true }).count(), 2);
    assert.equal(await cpi.getByText("관측 2026.08", { exact: true }).count(), 2);
    assert.equal(mutations.length, 0);
    await page.getByRole("button", { name: "발표 결과", exact: true }).click();
    await card("고용 발표 예정").waitFor({ state: "detached" });
    assert.equal(await page.getByRole("article").count(), 3);
    await cpi.getByText("0%", { exact: true }).waitFor();
    await page.screenshot({ path: `${output}/actions-desktop-dark.png` });
    await page.getByRole("button", { name: "전체", exact: true }).click();
    await card("고용 발표 예정").waitFor();
  });
  await check("Upcoming, pending and failed results remain distinct; earnings comparison is safe", async () => {
    await card("고용 발표 예정").getByText("발표 전", { exact: true }).waitFor();
    await card("고용 발표 예정").getByText("최근값", { exact: true }).waitFor();
    await card("GDP 반영 대기").getByText("반영 대기", { exact: true }).waitFor();
    await card("GDP 반영 대기").getByText("2026년 2분기", { exact: true }).waitFor();
    await card("PPI 수집 실패").getByText("확인 불가", { exact: true }).waitFor();
    await card("기업 실적").getByText("+10%", { exact: true }).waitFor();
    await card("공식 실적").getByText("비교 보류", { exact: true }).waitFor();
    assert.equal(await card("공식 실적").getByText("+10%", { exact: true }).count(), 0);
    assert.equal(await card("투자 논거 검토").getByRole("region", { name: "발표 수치 요약" }).count(), 0);
    await card("FOMC 정책 일정").getByText(/공식 성명/).waitFor();
  });
  await check("Both views, mobile widths and light theme retain inline values without overflow", async () => {
    for (const width of [390, 320]) {
      await page.setViewportSize({ width, height: 950 });
      await page.goto("/actions?tab=calendar&filter=events");
      await page.locator('button[aria-pressed="true"]').filter({ hasText: /^일정$/ }).waitFor();
      await card("US CPI").getByText("3.1%", { exact: true }).waitFor();
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await card("US CPI").scrollIntoViewIfNeeded();
      await page.screenshot({ path: `${output}/actions-mobile-${width}.png` });
      for (const cell of await card("US CPI").locator("dd").all()) {
        assert.ok(await cell.evaluate(el => el.scrollWidth <= el.clientWidth + 1));
      }
    }
    await page.setViewportSize({ width: 1440, height: 1100 });
    await page.getByRole("button", { name: "라이트 모드로 전환" }).click();
    await page.getByRole("button", { name: "다크 모드로 전환" }).waitFor();
    await card("US CPI").scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${output}/actions-desktop-light.png` });
  });
  await check("Detailed reading and snooze keep the existing explicit state actions", async () => {
    await card("기업 실적").getByRole("link", { name: "상세 보기" }).click(); await page.waitForURL("**/earnings");
    assert.equal(mutations.at(-1).state, "read");
    await page.goto("/actions");
    await Promise.all([
      page.waitForResponse(response => response.request().method() === "PUT"),
      card("US CPI").getByRole("button", { name: "내일 다시 보기" }).click(),
    ]);
    assert.equal(mutations.at(-1).state, "snoozed");
  });
  await check("API failure has a working retry and no fabricated values", async () => {
    unavailable = true; await page.reload();
    await page.getByText("검토 항목을 불러오지 못했습니다.", { exact: true }).waitFor();
    assert.equal(await page.getByRole("region", { name: "발표 수치 요약" }).count(), 0);
    unavailable = false; await page.getByRole("button", { name: "다시 시도", exact: true }).click();
    await card("US CPI").getByText("3.1%", { exact: true }).waitFor();
  });
  assert.deepEqual(errors, []);
  await writeFile(`${output}/browser-results.json`, JSON.stringify({ passed, errors, mutations, data: "All APIs and embedded ticker use synthetic fixtures; real FRED validation is recorded separately." }, null, 2));
} catch (error) { await page.screenshot({ path: `${output}/actions-failure.png` }); throw error; }
finally { await browser.close(); }
