import { mkdir } from "node:fs/promises";

const { chromium } = await import(process.env.NWIS_PLAYWRIGHT_MODULE || "playwright");
if (!process.env.NWIS_REVIEWER_TOKEN) throw new Error("Reviewer token required");
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
  await page.goto(process.env.NWIS_UI_URL || "http://127.0.0.1:13004/");
  await page.getByLabel("Local access token").fill(process.env.NWIS_REVIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await page.getByRole("button", { name: "01 Evidence room" }).click();
  await page.getByText("03 REPORTS IN VIEW").waitFor();
  await page.locator(".report-entry", { hasText: "511_25_10_2_R" }).click();
  await page.getByLabel("Source page").selectOption("7");
  await page.locator(".page-image").waitFor();
  await page.getByText("Benchmark staging · approval is locked", { exact: false }).waitFor();
  if (await page.getByRole("button", { name: "Approve evidence" }).count())
    throw new Error("Staged report unexpectedly offers approval");
  await page.getByRole("button", { name: "+ Add a report" }).click();
  await page.getByText("200 pages", { exact: false }).waitFor();
  await mkdir("artifacts", { recursive: true });
  await page.screenshot({ path: "artifacts/public-review-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "artifacts/public-review-mobile.png", fullPage: true });
  if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth))
    throw new Error("Public review mobile overflow");
  if (errors.length) throw new Error(errors.join("\n"));
  console.log("Public review UI passed: three reports, source image, locked approval, page cap, mobile width.");
} finally {
  await browser.close();
}
