import { mkdir, readFile } from "node:fs/promises";
const { chromium } = await import(
  process.env.NWIS_PLAYWRIGHT_MODULE || "playwright"
);
if (!process.env.NWIS_REVIEWER_TOKEN)
  throw new Error("Reviewer token required");
const browser = await chromium.launch({
  headless: true,
  ...(process.env.NWIS_CHROME_PATH
    ? { executablePath: process.env.NWIS_CHROME_PATH }
    : {}),
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
try {
  await page.goto(process.env.NWIS_UI_URL || "http://127.0.0.1:13001");
  await page
    .getByLabel("Local access token")
    .fill(process.env.NWIS_REVIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await page.getByRole("button", { name: "Well intelligence" }).click();
  await page
    .getByRole("heading", { name: "Nearby is a starting point." })
    .waitFor();
  await page.getByRole("button", { name: "Evidence room" }).click();
  await page.getByRole("button", { name: "+ Add a report" }).click();
  await page
    .getByLabel("Link to wellbore")
    .selectOption({ label: "SYN-B · synthetic" });
  const report = await readFile(
    "../specs/fixtures/phase3-review-report.txt",
    "utf8",
  );
  await page
    .getByLabel("Source report · PDF or UTF-8 text", { exact: true })
    .setInputFiles({
      name: "SYNTHETIC-phase3-review.txt",
      mimeType: "text/plain",
      buffer: Buffer.from(report + `\nUI test reference: ${Date.now()}\n`),
    });
  await page.getByRole("button", { name: "Upload & extract" }).click();
  await page.getByLabel("Review rationale").waitFor({ timeout: 30000 });
  await page
    .getByLabel("Review rationale")
    .fill(
      "Verified fictional source, synthetic datum and formation for Phase 3 UI test.",
    );
  await page.getByRole("button", { name: "Approve evidence" }).click();
  await page
    .getByRole("status")
    .filter({ hasText: "Review decision recorded" })
    .waitFor();
  await page.getByRole("button", { name: "Well intelligence" }).click();
  await page
    .getByRole("cell", { name: "2130.0 m–2140.0 m", exact: true })
    .first()
    .waitFor();
  await mkdir("artifacts", { recursive: true });
  await page.screenshot({
    path: "artifacts/intelligence-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Open case →", exact: true })
    .first()
    .click();
  await page
    .getByRole("region", { name: "Historical event case file" })
    .waitFor();
  await page.locator(".citation-link").first().click();
  await page.locator(".case-source pre").waitFor();
  if (
    !(await page.locator(".case-source pre").innerText()).includes(
      "Mud losses occurred from 1930 to 1940 m MD.",
    )
  )
    throw new Error("Wrong source citation");
  await page.getByLabel("Search keywords").fill("mud losses");
  await page.getByLabel("Source MD from · m").fill("1900");
  await page.getByLabel("Source MD to · m").fill("2000");
  await page.getByRole("button", { name: "Find evidence" }).click();
  await page.locator(".search-hit").first().waitFor();
  await page.getByLabel("Search keywords").fill("nonexistentunicorn");
  await page.getByRole("button", { name: "Find evidence" }).click();
  await page
    .getByText("No approved supporting evidence matches these filters.", {
      exact: false,
    })
    .waitFor();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "artifacts/intelligence-mobile.png",
    fullPage: true,
  });
  if (
    await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
  )
    throw new Error("Mobile overflow");
  if (errors.length) throw new Error(errors.join("\n"));
  console.log(
    "Phase 3 UI passed: review, map, golden mapping, case/source citation, search/abstention, mobile width; no page errors.",
  );
} catch (error) {
  await mkdir("artifacts", { recursive: true });
  await page.screenshot({
    path: "artifacts/intelligence-failure.png",
    fullPage: true,
  });
  console.log(await page.locator("body").innerText());
  console.log("Browser errors:", errors);
  throw error;
} finally {
  await browser.close();
}
