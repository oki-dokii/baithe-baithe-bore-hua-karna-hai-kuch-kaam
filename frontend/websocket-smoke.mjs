const { chromium } = await import(process.env.NWIS_PLAYWRIGHT_MODULE || "playwright");
if (!process.env.NWIS_VIEWER_TOKEN) throw new Error("Viewer token required");
const browser = await chromium.launch({
  headless: true,
  ...(process.env.NWIS_CHROME_PATH
    ? { executablePath: process.env.NWIS_CHROME_PATH }
    : {}),
});
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(process.env.NWIS_UI_URL || "http://127.0.0.1:13001");
  await page.getByLabel("Local access token").fill(process.env.NWIS_VIEWER_TOKEN);
  await page.getByRole("button", { name: "Connect", exact: true }).click();
  await page.getByRole("button", { name: "00 Operations" }).click();
  try {
    await page.getByText("Transport: WebSocket snapshots").waitFor({ timeout: 15000 });
  } catch (error) {
    const visible = await page.locator("body").innerText();
    throw new Error(
      `${error.message}\nTransport: ${visible.match(/Transport: [^\n]*/)?.[0] ?? "none"}` +
        `\nAlerts: ${visible.match(/Evidence-backed alerts[^\n]*/)?.[0] ?? "none"}` +
        `\nPage errors: ${errors.join("; ")}`,
    );
  }
  if (errors.length) throw new Error(errors.join("\n"));
  const fallback = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await fallback.addInitScript(() => {
    Object.defineProperty(window, "WebSocket", {
      value: class {
        constructor() {
          throw new Error("Synthetic transport outage");
        }
      },
    });
  });
  await fallback.goto(process.env.NWIS_UI_URL || "http://127.0.0.1:13001");
  await fallback.getByLabel("Local access token").fill(process.env.NWIS_VIEWER_TOKEN);
  await fallback.getByRole("button", { name: "Connect", exact: true }).click();
  await fallback.getByText("Transport: HTTP reconnect fallback").waitFor({ timeout: 15000 });
  console.log("Viewer replay snapshots: authenticated WebSocket and HTTP fallback passed.");
} finally {
  await browser.close();
}
