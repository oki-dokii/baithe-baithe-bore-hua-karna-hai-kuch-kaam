import { mkdir } from "node:fs/promises";
const { chromium } = await import(
  process.env.NWIS_PLAYWRIGHT_MODULE || "playwright"
);
if (!process.env.NWIS_ENGINEER_TOKEN)
  throw new Error("Engineer token required");
const browser = await chromium.launch({
  headless: true,
  ...(process.env.NWIS_CHROME_PATH
    ? { executablePath: process.env.NWIS_CHROME_PATH }
    : {}),
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
async function step(sequence) {
  await page
    .getByRole("button", { name: "Next depth sample", exact: true })
    .click();
  await page
    .getByText(`State: paused · step ${sequence}/5`, { exact: true })
    .waitFor();
}
try {
  await page.goto(process.env.NWIS_UI_URL || "http://127.0.0.1:13001");
  await page
    .getByLabel("Local access token")
    .fill(process.env.NWIS_ENGINEER_TOKEN);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await page
    .getByRole("heading", { name: "Before the next interval." })
    .waitFor();
  await page
    .getByRole("button", { name: "New synthetic replay", exact: true })
    .click();
  await page.getByText("State: paused · step 0/5", { exact: true }).waitFor();
  await step(1);
  if (await page.locator(".operation-alert").count())
    throw new Error("Premature alert at 2029 m");
  await step(2);
  await page.locator(".operation-alert").waitFor();
  if ((await page.locator(".operation-alert").count()) !== 1)
    throw new Error("Duplicate episode");
  await page
    .getByLabel("Decision / feedback rationale")
    .fill(
      "Verified the synthetic source and acknowledged the alert without resolving it.",
    );
  await page.getByRole("button", { name: "acknowledge", exact: true }).click();
  await page.getByText("ACKNOWLEDGED", { exact: true }).waitFor();
  await page.getByText(/Why this alert exists/).click();
  await mkdir("artifacts", { recursive: true });
  await page.screenshot({
    path: "artifacts/operations-desktop.png",
    fullPage: true,
  });
  await step(3);
  await step(4);
  await page
    .getByRole("button", { name: "Next depth sample", exact: true })
    .click();
  await page
    .getByText("State: completed · step 5/5", { exact: true })
    .waitFor();
  await page.getByText("passed", { exact: true }).waitFor();
  if ((await page.locator(".operation-alert").count()) !== 1)
    throw new Error("Repeated samples duplicated alerts");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "artifacts/operations-mobile.png",
    fullPage: true,
  });
  if (
    await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
  )
    throw new Error("Mobile overflow");
  await page.getByRole("button", { name: "Reset into new session" }).click();
  await page.getByText("State: paused · step 0/5", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Play replay", exact: true }).click();
  await page
    .getByText("State: completed · step 5/5", { exact: true })
    .waitFor({ timeout: 30000 });
  if ((await page.locator(".operation-alert").count()) !== 1)
    throw new Error("Autoplay episode mismatch");
  if (errors.length) throw new Error(errors.join("\n"));
  console.log(
    "Operations UI passed: manual boundaries, one episode, acknowledgment, passed relevance, reset, server autoplay and mobile width.",
  );
} catch (e) {
  console.log(await page.locator("body").innerText());
  console.log(errors);
  throw e;
} finally {
  await browser.close();
}
