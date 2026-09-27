import { mkdir } from "node:fs/promises";
const { chromium } = await import(process.env.NWIS_PLAYWRIGHT_MODULE || "playwright");
if (!process.env.NWIS_VIEWER_TOKEN) throw new Error("Viewer token required");
const browser = await chromium.launch({
  headless: true,
  ...(process.env.NWIS_CHROME_PATH
    ? { executablePath: process.env.NWIS_CHROME_PATH }
    : {}),
});
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(process.env.NWIS_UI_URL || "http://127.0.0.1:13001");
  await page.getByLabel("Local access token").fill(process.env.NWIS_VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await page.getByRole("button", { name: "Well intelligence" }).click();
  await page.getByRole("button", { name: "Related meaning" }).click();
  await page.getByLabel("Search approved evidence").fill("drilling fluid vanished into rock");
  await page.getByRole("button", { name: "Find evidence" }).click();
  await page.getByText("Related-meaning candidates", { exact: false }).waitFor();
  await page.locator(".search-hit").first().waitFor();
  if (process.env.NWIS_EXPECT_ONE_SOURCE === "1" &&
      (await page.locator(".search-hit").count()) !== 1)
    throw new Error("Clean demo did not show exactly one cited source");
  const first = page.locator(".search-hit").first();
  if (!(await first.locator("small").innerText()).includes("page"))
    throw new Error("Semantic result has no source-page citation");
  await mkdir("artifacts", { recursive: true });
  await page.screenshot({ path: "artifacts/semantic-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "artifacts/semantic-mobile.png", fullPage: true });
  if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth))
    throw new Error("Semantic search mobile overflow");
  if (process.env.NWIS_EXPECT_ONE_SOURCE === "1") {
    await page.getByLabel("Search approved evidence").fill("cementing failure");
    await page.getByRole("button", { name: "Find evidence" }).click();
    await page.getByText("No approved supporting evidence matches these filters.", {
      exact: false,
    }).waitFor();
  }
  await page.getByRole("button", { name: "Exact terms" }).click();
  await page.getByRole("button", { name: "Find evidence" }).click();
  await page.getByText("Exact-term matches", { exact: false }).waitFor();
  if (errors.length) throw new Error(errors.join("\n"));
  console.log("Semantic UI passed: local model, cited result, exact-term mode, mobile width.");
} finally {
  await browser.close();
}
