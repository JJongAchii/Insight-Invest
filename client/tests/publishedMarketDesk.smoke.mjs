import assert from "node:assert/strict";
import { chromium } from "playwright";

const baseURL = "https://insight-invest-ten.vercel.app";
assert.ok(process.env.SITE_ACCESS_CODE, "A site login is required");

const browser = await chromium.launch();
try {
  const context = await browser.newContext({ baseURL });
  const login = await context.request.post("/api/auth/login", {
    data: { accessCode: process.env.SITE_ACCESS_CODE },
    maxRedirects: 0,
  });
  assert.equal(login.status(), 200, "Site login failed");
  assert.equal((await login.json()).authenticated, true);

  const page = await context.newPage();
  const [response] = await Promise.all([
    page.waitForResponse((res) => res.url() === `${baseURL}/api/backend/market-desk`, { timeout: 110_000 }),
    page.goto("/home", { waitUntil: "domcontentloaded" }),
  ]);
  assert.equal(response.status(), 200, "Home could not read its market desk");
  const { state, today, lead } = await response.json();
  assert.equal(state, "ready", "The publisher has not delivered a fresh board");
  assert.ok(lead && lead.trade_date === today, "Home has no current trading-day edition");
  assert.ok(["intraday", "close"].includes(lead.phase));

  const editionTitle = lead.phase === "close" ? "한국 증시 마감 해설" : "한국 증시 장중 해설";
  const section = page.getByRole("region", { name: editionTitle, exact: true });
  await section.getByRole("heading", { name: lead.headline, exact: true }).waitFor();
  await section.getByText(lead.watch, { exact: true }).waitFor();
  const sources = new Map();
  for (const paragraph of [lead.reading, lead.qualification]) {
    assert.ok(paragraph.sources.length, "An interpretation has no cited original");
    await section.getByText(paragraph.text, { exact: false }).first().waitFor();
    for (const source of paragraph.sources) sources.set(source.url, source.title);
  }
  await section.getByText(`근거 원문 ${sources.size}건`, { exact: true }).click();
  const originals = section.getByRole("list", { name: "시장 해설의 근거 원문" });
  await originals.waitFor();
  for (const [url, title] of sources) {
    const links = originals.getByRole("link", { name: title, exact: true });
    const targets = await links.evaluateAll((items) => items.map((item) => item.getAttribute("href")));
    assert.ok(targets.includes(url), "A cited source is missing from the rendered edition");
  }
  console.log(JSON.stringify({ trade_date: today, edition: lead.phase, published_at: lead.published_at, originals: sources.size }));
} finally {
  await browser.close();
}
