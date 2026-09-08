// Render actual qualification briefs against a local Next build. Library changes
// are browser-test fixtures only; every backend request is intercepted.
import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { chromium } from "playwright";
import { fixtureFor } from "./marketExperience.fixtures.mjs";

const reportPath = process.argv[2];
assert.ok(reportPath, "Pass a local qualification-report.json, never credentials");
const report = JSON.parse(await readFile(reportPath, "utf8"));
assert.equal(report.production_modified, false);
assert.equal(report.status, "api_contract_qualified");
const originalItems = report.items.filter((item) =>
  item.analysis_status === "ready" && item.analysis?.prompt_version === report.prompt_version,
);
assert.equal(originalItems.length, 3, "This smoke test covers the bounded three-card sample");
const baseURL = process.env.UI_BASE_URL || "http://127.0.0.1:3118";
assert.ok(["127.0.0.1", "localhost"].includes(new URL(baseURL).hostname));
const output = process.env.UI_OUTPUT_DIR || "/tmp/insight-research-reading-review";
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ channel: "chrome", headless: true });
const errors = [];
const checks = [];

try {
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    const items = structuredClone(originalItems).map((item) => ({ ...item, is_read: false, is_saved: false }));
    const context = await browser.newContext({ baseURL, viewport, serviceWorkers: "block", reducedMotion: "reduce" });
    await context.addInitScript(() => Reflect.deleteProperty(Navigator.prototype, "serviceWorker"));
    await context.addCookies([{ name: "ii_access", value: "insight-local-ui-review", url: baseURL }]);
    await context.route("**/*", async (route) => {
      const url = new URL(route.request().url());
      if (url.origin !== new URL(baseURL).origin) return route.abort();
      if (!url.pathname.startsWith("/api/backend/")) return route.continue();
      const path = url.pathname.slice("/api/backend/".length);
      const params = url.searchParams;
      const lane = params.get("lane") || "core";
      const inLane = items.filter((item) => lane === "all" || item.research_lane === lane);
      let payload;
      if (path === "research") {
        const view = params.get("view") || "all";
        const query = params.get("q") || "";
        const selected = inLane.filter((item) =>
          (view !== "saved" || item.is_saved) && (view !== "read" || item.is_read)
          && (view !== "unread" || !item.is_read)
          && (!query || JSON.stringify(item).includes(query)),
        );
        payload = {
          schema_version: 1, generated_at: report.checked_at, total: selected.length,
          unread: inLane.filter((item) => !item.is_read).length,
          read: inLane.filter((item) => item.is_read).length,
          saved: inLane.filter((item) => item.is_saved).length,
          lane, view, query, offset: 0, limit: 500,
          lane_counts: Object.fromEntries(["core", "discovery", "context", "updates", "all"].map((value) =>
            [value, items.filter((item) => value === "all" || item.research_lane === value).length])),
          sources: inLane.map((item) => ({ source_id: item.source_id, source_name: item.source_name, count: 1 })),
          items: selected,
        };
      } else if (path === "research/read/all") {
        const updated = inLane.filter((item) => !item.is_read).length;
        inLane.forEach((item) => { item.is_read = true; });
        payload = { updated, total: inLane.length, unread: 0, lane };
      } else if (/^research\/[a-f0-9]+\/(saved|read)$/.test(path)) {
        const [, id, action] = path.split("/");
        const item = items.find((value) => value.entry_id === id);
        const body = route.request().postDataJSON();
        item[`is_${action}`] = body[action];
        payload = { entry_id: id, [`is_${action}`]: item[`is_${action}`] };
      } else {
        payload = fixtureFor(path, params, "normal");
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(payload) });
    });
    const page = await context.newPage();
    page.setDefaultTimeout(10000);
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("dialog", (dialog) => dialog.accept());
    await page.goto("/research");
    for (const item of items.filter((value) => value.research_lane === "core")) {
      const card = page.locator(`#research-${item.entry_id}`);
      await card.waitFor();
      assert.equal(await card.getByRole("link", { name: "원문 열기" }).getAttribute("href"), item.url);
      const points = card.locator("dl > div");
      for (const [index, point] of Object.values(item.analysis.brief).filter((value) => value?.evidence).entries()) {
        const row = points.nth(index);
        await row.locator("summary").click();
        const expected = point.evidence_excerpts || [point.evidence];
        assert.deepEqual(await row.locator("blockquote").allTextContents(), expected);
        if (expected.length > 1) assert.ok(await row.getByText("중간 원문 생략 · 다음 근거").count());
      }
    }
    assert.ok(await page.getByText("방법·실증 연구", { exact: true }).count());
    assert.ok(await page.getByText("운용 아이디어·실무", { exact: true }).count());
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await page.screenshot({ path: `${output}/core-${viewport.width}.png`, fullPage: true });
    await page.getByRole("button", { name: /^시장·배경/ }).click();
    const commentary = items.find((item) => item.analysis.brief.content_kind === "market_commentary");
    assert.ok(commentary, "The sample must retain a market-commentary card");
    const card = page.locator(`#research-${commentary.entry_id}`);
    await card.waitFor();
    assert.ok(await card.getByText("저자의 전망·해석", { exact: true }).count());
    await card.getByRole("button", { name: "보관", exact: true }).click();
    await card.getByRole("button", { name: "보관 해제", exact: true }).waitFor();
    await page.getByRole("button", { name: /^보관함/ }).click();
    await card.waitFor();
    await page.getByRole("searchbox", { name: "리서치 검색" }).fill(commentary.analysis.brief.title_ko.slice(0, 6));
    await page.waitForURL((url) => Boolean(url.searchParams.get("q")));
    await card.waitFor();
    await page.getByRole("button", { name: "모두 읽음", exact: true }).click();
    await card.getByRole("button", { name: "안 읽음으로", exact: true }).waitFor();
    assert.ok(await card.getByRole("button", { name: "보관 해제", exact: true }).isVisible());
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await page.screenshot({ path: `${output}/commentary-${viewport.width}.png`, fullPage: true });
    checks.push({ width: viewport.width, status: "passed", cards: items.length });
    console.log(`PASS ${viewport.width}px: actual briefs, separated quotes, lane, search, save, mark-all-read`);
    await context.close();
  }
  assert.deepEqual(errors, []);
} finally {
  await browser.close();
  await writeFile(`${output}/result.json`, JSON.stringify({ report: reportPath, production_modified: false, checks, errors }, null, 2) + "\n");
}
