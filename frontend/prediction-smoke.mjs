import { mkdir } from "node:fs/promises";
const { chromium } = await import(process.env.NWIS_PLAYWRIGHT_MODULE || "playwright");
if (!process.env.NWIS_VIEWER_TOKEN) throw new Error("Viewer token required");
const browser = await chromium.launch({ headless: true, ...(process.env.NWIS_CHROME_PATH ? { executablePath: process.env.NWIS_CHROME_PATH } : {}) });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on("pageerror", e => errors.push(e.message));
  await page.goto(process.env.NWIS_UI_URL || "http://127.0.0.1:13001");
  await page.getByLabel("Local access token").fill(process.env.NWIS_VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await page.getByRole("button", { name: "04 Model readiness" }).click();
  await page.getByRole("heading", { name: "Awaiting qualified data" }).waitFor();
  await page.getByText("NO TRAINED MODEL", { exact: true }).waitFor();
  await mkdir("artifacts", { recursive: true });
  await page.screenshot({ path: "artifacts/prediction-desktop.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error("Mobile overflow");
  if (errors.length) throw new Error(errors.join("\n"));
  console.log("Model readiness: viewer access, honest unavailable state and mobile width passed.");
} finally { await browser.close(); }
