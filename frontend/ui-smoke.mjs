// Run with a local reviewer token and Playwright installed or NWIS_PLAYWRIGHT_MODULE set.
import { mkdir } from "node:fs/promises";
const { chromium } = await import(
  process.env.NWIS_PLAYWRIGHT_MODULE || "playwright"
);
if (!process.env.NWIS_REVIEWER_TOKEN)
  throw new Error("NWIS_REVIEWER_TOKEN is required");
const browser = await chromium.launch({
  headless: true,
  ...(process.env.NWIS_CHROME_PATH
    ? { executablePath: process.env.NWIS_CHROME_PATH }
    : {}),
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } });
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
await mkdir("artifacts", { recursive: true });
try {
  await page.goto(process.env.NWIS_UI_URL || "http://127.0.0.1:13001");
  await page
    .getByLabel("Local access token")
    .fill(process.env.NWIS_REVIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await page.getByRole("button", { name: "Evidence room" }).click();
  await page.getByRole("heading", { name: "The evidence room." }).waitFor();
  await page.getByRole("button", { name: "+ Add a report" }).click();
  await page
    .getByLabel("Source report · PDF or UTF-8 text", { exact: true })
    .setInputFiles({
      name: "SYNTHETIC-field-note.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(
        `SYNTHETIC FIELD NOTE — SOFTWARE DEMONSTRATION\nReference: ${Date.now()}\nDatum: RKB\nFormation: SYN-F1\n\nMud losses at 1000 ft MD.\n\nThis fictional incident tests the review interface.\nIt must not be used for operating decisions.`,
      ),
    });
  await page.getByRole("button", { name: "Upload & extract" }).click();
  await page.getByLabel("Recorded event").waitFor({ timeout: 30000 });
  await page
    .getByLabel("Review rationale")
    .fill("Verified the exact source quote in this fictional UI test.");
  await page.getByRole("checkbox").check();
  await page.locator(".evidence-panel").evaluate((element) => {
    element.scrollTop = 0;
  });
  await page.screenshot({
    path: "artifacts/evidence-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Approve evidence" }).click();
  await page
    .getByRole("status")
    .filter({ hasText: "Review decision recorded" })
    .waitFor();
  if (!(await page.getByLabel("Recorded event").isDisabled()))
    throw new Error("Final evidence remained editable");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "artifacts/evidence-mobile.png",
    fullPage: true,
  });
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  if (overflow) throw new Error("Mobile layout has horizontal overflow");
  await page.getByRole("button", { name: "Well directory" }).click();
  await page.getByRole("heading", { name: "Nearby wells" }).waitFor();
  if (errors.length) throw new Error(errors.join("\n"));
  console.log(
    "UI smoke passed: login, upload, live extraction, approval, read-only final record, mobile width, well directory; no page errors.",
  );
} finally {
  await browser.close();
}
