/* Starts an isolated API and temp SQLite DB; never resets the developer's queue. */
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { setTimeout: delay } = require("node:timers/promises");
const { chromium } = require("playwright");
const AxeBuilder = require("@axe-core/playwright").default;

const root = path.resolve(__dirname, "../..");
const port = Number(process.env.BEACON_TEST_PORT || 8025);
const base = `http://127.0.0.1:${port}`;
const temp = fs.mkdtempSync(path.join(os.tmpdir(), "beacon-browser-"));
const output = path.join(root, "frontend/test-results");
let server, browser;
let logs = "";
let assertions = 0;
function check(condition, message) {
  assert(condition, message);
  assertions++;
}
async function api(endpoint, body) {
  const response = await fetch(base + endpoint, {
    method: body === undefined ? "GET" : "POST",
    ...(body === undefined
      ? {}
      : {
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }),
  });
  assert(response.ok, `${endpoint}: ${response.status}`);
  return response.json();
}
async function until(fn) {
  for (let i = 0; i < 80; i++) {
    try {
      if (await fn()) return;
    } catch {}
    await delay(100);
  }
  throw new Error("Readiness timed out. " + logs);
}
async function settled(page) {
  await page.waitForFunction(() =>
    document.getElementById("sync-label").textContent.startsWith("Live"),
  );
}
async function accessibility(page, label) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  fs.mkdirSync(output, { recursive: true });
  fs.writeFileSync(
    path.join(output, `accessibility-${label}.json`),
    JSON.stringify(
      {
        violations: result.violations,
        incomplete: result.incomplete,
        passedRules: result.passes.length,
      },
      null,
      2,
    ),
  );
  check(
    result.violations.length === 0,
    `${label} accessibility: ` +
      JSON.stringify(
        result.violations.map((v) => ({
          id: v.id,
          nodes: v.nodes.map((n) => ({
            target: n.target,
            summary: n.failureSummary,
          })),
        })),
      ),
  );
}
async function preview(page, name) {
  await page
    .getByRole("button", { name: new RegExp(`^Preview ${name}`) })
    .click();
  await page.locator("#overview h2").filter({ hasText: name }).waitFor();
}
async function review(page, name) {
  await preview(page, name);
  await page.getByRole("button", { name: "Review case", exact: true }).click();
  await page.locator("#detail-view h1").filter({ hasText: name }).waitFor();
}

(async () => {
  server = spawn(
    process.env.BEACON_PYTHON || path.join(root, "backend/.venv/bin/python"),
    [
      "-m",
      "uvicorn",
      "main:app",
      "--host",
      "127.0.0.1",
      "--port",
      String(port),
      "--no-access-log",
    ],
    {
      cwd: path.join(root, "backend"),
      env: {
        ...process.env,
        NRY_DB: path.join(temp, "test.db"),
        NRY_NOW: "2026-11-15T12:00:00Z",
        NRY_STAFF_PASSWORD: "",
        NRY_STAFF_ACCOUNTS: "",
        NRY_WEBHOOK_SECRET: "",
        NRY_SUGGEST_THRESHOLD: "1",
      },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  server.stdout.on("data", (b) => {
    logs += b;
  });
  server.stderr.on("data", (b) => {
    logs += b;
  });
  server.on("error", (e) => {
    logs += e.message;
  });
  await until(
    async () =>
      server.exitCode === null && (await fetch(base + "/workspace/session")).ok,
  );
  browser = await chromium.launch({
    ...(process.env.BEACON_CHROMIUM
      ? { executablePath: process.env.BEACON_CHROMIUM }
      : fs.existsSync("/usr/bin/chromium")
        ? { executablePath: "/usr/bin/chromium" }
        : {}),
    headless: true,
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1050 },
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(base);
  await settled(page);
  check(
    await page.locator("#empty-state").isVisible(),
    "Empty queue should have a clear empty state",
  );
  await page
    .getByRole("button", { name: "Care insights", exact: true })
    .click();
  await page.locator(".insight-metric").first().waitFor();
  check(
    (await page
      .locator(".insight-metric .metric-value")
      .first()
      .textContent()) === "0",
    "Empty insights show zero actual cases",
  );
  await page
    .getByRole("button", { name: /^Priority queue/ })
    .first()
    .click();
  await page
    .getByRole("button", { name: "Load sample cases", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Add sample cases", exact: true })
    .click();
  await page.locator(".case-row").nth(4).waitFor();
  check((await page.locator(".case-row").count()) === 5, "Seed five cases");
  check(
    (await page.locator(".case-row").first().innerText()).includes("Maria"),
    "Highest harm first",
  );
  check(
    (await page.locator("#stat-active").textContent()) === "5",
    "Live summary counts",
  );

  await page
    .getByRole("button", { name: "Care insights", exact: true })
    .click();
  await page.locator(".priority-donut").waitFor();
  check(
    (await page.locator(".insight-metric").count()) === 4,
    "Live insight summary cards",
  );
  // The insights panel refreshes a moment after the chart first appears (it briefly shows the
  // empty-queue "$0.00"), so wait for the amount instead of reading it the instant it renders.
  check(
    await page
      .waitForFunction(
        () =>
          document
            .getElementById("insights-content")
            .innerText.includes("$5,539.00"),
        null,
        { timeout: 5000 },
      )
      .then(
        () => true,
        () => false,
      ),
    "Owned linked outgoings reconcile with sample data",
  );
  check(
    (await page.locator(".care-flow-step").first().innerText()).includes("5"),
    "Case journey reconciles with five waiting cases",
  );
  await page.locator("#toast").waitFor({ state: "hidden" });
  await page.screenshot({
    path: path.join(output, "desktop-insights.png"),
    fullPage: true,
  });
  await accessibility(page, "desktop-insights");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForFunction(
    () => document.getElementById("sidebar").getBoundingClientRect().right <= 0,
  );
  check(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    "Insights fit a mobile viewport",
  );
  await page.screenshot({
    path: path.join(output, "mobile-insights.png"),
    fullPage: true,
    animations: "disabled",
  });
  await accessibility(page, "mobile-insights");
  await page.setViewportSize({ width: 1440, height: 1050 });
  await page
    .getByRole("button", { name: "Show P3 priority: 2 cases", exact: true })
    .click();
  await page.locator("#insight-filter").waitFor();
  check(
    (await page.locator(".case-row").count()) === 2,
    "Priority chart drills into the matching queue",
  );
  await page
    .getByRole("button", { name: "Clear insight filter", exact: true })
    .click();
  check(
    (await page.locator(".case-row").count()) === 5,
    "Insight filter can be cleared",
  );
  await page
    .getByRole("button", { name: "Care insights", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Show Card delivery: 1 case", exact: true })
    .click();
  await page.locator("#insight-filter").waitFor();
  check(
    (await page.locator("#case-rows").innerText()).includes("Sam"),
    "Issue chart selects the actual matching customer",
  );
  await page
    .getByRole("button", { name: "Clear insight filter", exact: true })
    .click();

  await page.locator("#search").fill("Minh");
  await until(async () => (await page.locator(".case-row").count()) === 1);
  check(
    (await page.locator(".case-row").innerText()).includes("Minh"),
    "Search customer",
  );
  await page.locator("#search").fill("nonexistent");
  check(
    (await page.locator("#empty-title").textContent()) === "No matching cases",
    "Filter empty state",
  );
  await page.locator("#search").fill("");
  await page.locator("#band-filter").selectOption("P1");
  check((await page.locator(".case-row").count()) === 1, "Priority dropdown");
  await page.locator("#band-filter").selectOption("all");
  await page.getByRole("button", { name: /^Urgent care/ }).click();
  check((await page.locator(".case-row").count()) === 2, "Urgent care filter");
  await page.getByRole("button", { name: "All cases", exact: true }).click();
  await page.locator("#toast").waitFor({ state: "hidden" });
  await page.locator("#main").focus();
  await page.keyboard.press("/");
  check(
    await page
      .locator("#search")
      .evaluate((node) => node === document.activeElement),
    "Search keyboard shortcut",
  );
  await page.keyboard.press("Tab");
  check(
    await page
      .locator("#band-filter")
      .evaluate((node) => node === document.activeElement),
    "Search-to-filter keyboard order",
  );
  await page.locator("#main").focus();
  fs.mkdirSync(output, { recursive: true });
  await page.screenshot({
    path: path.join(output, "desktop-queue.png"),
    fullPage: true,
  });
  await accessibility(page, "desktop-queue");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForFunction(
    () => document.getElementById("sidebar").getBoundingClientRect().right <= 0,
  );
  check(
    await page.locator("#sidebar").evaluate((node) => node.inert),
    "Closed mobile navigation is not keyboard focusable",
  );
  await page.screenshot({
    path: path.join(output, "mobile-queue.png"),
    fullPage: true,
    animations: "disabled",
  });
  await accessibility(page, "mobile-queue");
  await preview(page, "Sam");
  await page.waitForFunction(
    () =>
      document.getElementById("overview").getBoundingClientRect().bottom <=
      innerHeight,
  );
  check(true, "Mobile selection scrolls to the selected case preview");
  await page.setViewportSize({ width: 1440, height: 1050 });

  await review(page, "Maria");
  check(
    (await api("/case/DEMO-0412/status")).stage === "WITH_OFFICER",
    "Review records pickup",
  );
  await page.getByRole("button", { name: "Evidence", exact: true }).click();
  check(
    (await page.locator(".score-row").count()) === 5,
    "Score visual shows five backend components",
  );
  check(
    (await page.locator(".score-explainer").innerText()).includes(
      "Component subtotal 110.",
    ),
    "Score visual distinguishes components from the capped score",
  );
  await accessibility(page, "score-evidence");
  check(
    (await page.locator("#detail-view").innerText()).includes("Large transfer"),
    "Evidence separated from conversation",
  );
  await page
    .getByRole("button", { name: "Customer context", exact: true })
    .click();
  await page.locator(".customer-context").waitFor();
  check(
    (await page.locator(".account-tile").count()) === 2,
    "Customer context contains only Maria accounts",
  );
  check(
    (await page.locator(".transaction-list").first().innerText()).includes("TX-9001"),
    "Linked payment is shown in account history",
  );
  check(
    !(await page.locator(".transaction-list").first().innerText()).includes("TX-7001"),
    "No transaction from another customer is disclosed",
  );
  check(
    !(await page.locator(".customer-context").innerText())
      .split(/\s+/)
      .includes("null"),
    "Customer context has no placeholder text",
  );
  await page.screenshot({
    path: path.join(output, "customer-context.png"),
    fullPage: true,
  });
  await accessibility(page, "customer-context");
  await page
    .getByRole("button", { name: "Handoff brief", exact: true })
    .click();
  check(
    (
      await page
        .getByRole("textbox", { name: "Handoff brief", exact: true })
        .inputValue()
    ).includes("SIMULATED STAFF HANDOFF"),
    "Handoff clearly identifies simulated data",
  );
  check(
    (
      await page
        .getByRole("textbox", { name: "Handoff brief", exact: true })
        .inputValue()
    ).includes("Verified signals:"),
    "Handoff separates verified evidence from conversation",
  );
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page.getByRole("button", { name: "Activity", exact: true }).click();
  check(
    (await page.locator("#detail-view").innerText()).includes("Picked up"),
    "Activity trail",
  );
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await page.screenshot({
    path: path.join(output, "desktop-case.png"),
    fullPage: true,
  });
  await accessibility(page, "desktop-case");
  await page
    .getByRole("button", { name: "Review & approve", exact: true })
    .click();
  await accessibility(page, "decision-dialog");
  await page.keyboard.press("Escape");
  await page.locator("#action-dialog").waitFor({ state: "hidden" });
  check(
    (await api("/case/DEMO-0412")).status === "IN_REVIEW",
    "Cancel must not approve",
  );
  await page
    .getByRole("button", { name: "Review & approve", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm decision", exact: true })
    .click();
  check(
    await page.locator("#action-dialog").isVisible(),
    "Required checks gate submission",
  );
  await page.locator("#confirm-checks").check();
  await page
    .getByRole("button", { name: "Confirm decision", exact: true })
    .click();
  await page.locator("#action-dialog").waitFor({ state: "hidden" });
  check(
    (await api("/case/DEMO-0412/status")).stage === "DONE",
    "P1 approval updates outcome",
  );

  await page
    .getByRole("button", { name: "Priority queue", exact: false })
    .first()
    .click();
  await review(page, "Sam");
  await page
    .getByRole("button", { name: "Customer context", exact: true })
    .click();
  await page.locator(".delivery-card").waitFor();
  check(
    (await page.locator(".delivery-card").innerText()).includes("19 Nov"),
    "Card delivery track uses the expected date in the dataset",
  );
  check(
    (await page.locator(".delivery-card").innerText()).includes(
      "not confirmation of delivery",
    ),
    "Expected delivery is not shown as a completed event",
  );
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await page
    .getByRole("button", { name: "Change priority", exact: true })
    .click();
  await page.locator("#new-band").selectOption("P3");
  await page.locator("#rerank-reason").fill("Customer needs extra assistance");
  await page
    .getByRole("button", { name: "Record priority change", exact: true })
    .click();
  await page.locator("#action-dialog").waitFor({ state: "hidden" });
  check(
    (await api("/case/DEMO-0416")).priority.band === "P3",
    "Rerank recorded",
  );
  await page
    .getByRole("button", { name: "Change priority", exact: true })
    .click();
  await page.locator("#new-band").selectOption("P4");
  await page
    .locator("#rerank-reason")
    .fill("Confirmed routine delivery enquiry");
  await page
    .getByRole("button", { name: "Record priority change", exact: true })
    .click();
  await page.locator("#action-dialog").waitFor({ state: "hidden" });
  await page.getByRole("button", { name: "Modify plan", exact: true }).click();
  await page.locator("#action-SEND_GUIDE_LINK").check();
  await page.locator("#decision-note").fill("Include the delivery help guide");
  await page.locator("#confirm-checks").check();
  await page
    .getByRole("button", { name: "Confirm decision", exact: true })
    .click();
  await page.locator("#action-dialog").waitFor({ state: "hidden" });
  const modified = await api("/case/DEMO-0416");
  check(modified.status === "MODIFIED", "Modified plan executed");
  check(
    modified.audit_log.some(
      (a) =>
        a.action === "SEND_GUIDE_LINK" && a.actor.startsWith("AI (Prorio)"),
    ),
    "P4 AI actor audited",
  );

  await page
    .getByRole("button", { name: "Priority queue", exact: false })
    .first()
    .click();
  await review(page, "Priya");
  await page
    .getByRole("button", { name: "Handle manually", exact: true })
    .click();
  await page
    .locator("#decision-note")
    .fill("Officer investigating disputed merchant");
  await page
    .getByRole("button", { name: "Start manual handling", exact: true })
    .click();
  await page.locator("#action-dialog").waitFor({ state: "hidden" });
  await page
    .getByRole("button", { name: /^In review/ })
    .first()
    .click();
  check(
    (await page.locator("#case-rows").innerText()).includes("Priya"),
    "Manual case stays discoverable in review",
  );
  await review(page, "Priya");
  await page
    .getByRole("button", { name: "Record outcome & complete", exact: true })
    .click();
  await page
    .locator("#completion-note")
    .fill("Dispute recorded; customer informed of next steps.");
  await page
    .getByRole("button", { name: "Complete case", exact: true })
    .click();
  await page.locator("#action-dialog").waitFor({ state: "hidden" });
  check(
    (await api("/case/DEMO-0414/status")).outcome.message.includes(
      "Dispute recorded",
    ),
    "Manual outcome recorded",
  );
  await page.getByRole("button", { name: "Completed", exact: true }).click();
  await until(async () => (await page.locator(".case-row").count()) === 3);
  check(
    (await page.locator(".case-row").count()) === 3,
    "Completed cases remain accessible",
  );

  await page
    .getByRole("button", { name: "Learning loop", exact: true })
    .click();
  await page.locator(".suggestion-card").nth(1).waitFor();
  check(
    (await page.locator(".suggestion-card").count()) === 2,
    "Suggestions from modify and manual",
  );
  const samSuggestion = page
    .locator(".suggestion-card")
    .filter({ hasText: "Card delivery" });
  await samSuggestion.getByRole("button", { name: "Review & approve" }).click();
  await page.locator("#confirm-protocol").check();
  await page
    .getByRole("button", { name: "Approve version", exact: true })
    .click();
  await page.locator("#action-dialog").waitFor({ state: "hidden" });
  check(
    (await api("/protocols/CARD_DELIVERY")).version === "2.1",
    "Learning loop version approval",
  );
  await page
    .getByRole("button", { name: "Protocol library", exact: true })
    .click();
  await page.locator(".protocol-card").nth(30).waitFor();
  check(
    (await page.locator(".protocol-card").count()) === 31,
    "Protocol library populated",
  );
  await page.locator("#protocol-search").fill("Card delivery");
  await page
    .getByRole("button", { name: "View protocol", exact: true })
    .click();
  await page.locator("#action-dialog").waitFor();
  check(
    (await page.locator("#dialog-body").innerText()).includes("Version 2.1"),
    "Effective protocol shown",
  );
  await page.getByRole("button", { name: "Close", exact: true }).click();

  // Stored hostile customer content must be text, even inside the evidence view.
  await api("/case", {
    customer_id: "CUST-005",
    customer_name: "<img src=x onerror=alert(1)>",
    issue_type: "GENERAL_ENQUIRY",
    summary_en: "<script>window.hacked=true</script>",
    case_reference: "XSS-CHECK",
  });
  await page
    .getByRole("button", { name: "Priority queue", exact: false })
    .first()
    .click();
  await preview(page, "<img");
  check(
    (await page.locator("#overview img, #overview script").count()) === 0,
    "Stored markup stays text",
  );
  check(await page.evaluate(() => !window.hacked), "No injected code executed");
  await page.locator("#search").fill("Minh");
  await page.locator("#band-filter").selectOption("P1");
  check(
    await page.locator("#empty-state").isVisible(),
    "Combined filters reflect an empty result",
  );
  await page.locator("#search").fill("");
  await page.locator("#band-filter").selectOption("all");

  // A failed refresh preserves existing data and makes staleness visible.
  let restoring = false;
  let resumeRecovery;
  const recoveryGate = new Promise((resolve) => {
    resumeRecovery = resolve;
  });
  const offlineRoute = async (route) => {
    if (!restoring) return route.abort("failed");
    await recoveryGate;
    return route.continue();
  };
  await page.route("**/workspace/cases", offlineRoute);
  await page
    .getByRole("button", { name: "Refresh cases", exact: true })
    .click();
  await page.locator("#connection-error").waitFor();
  check(
    await page.locator("#next-case").isDisabled(),
    "No next-case handoff while offline",
  );
  // Hold successful background reads until the retry click. SSE/polling can otherwise
  // restore the connection and hide the button between unroute() and click().
  restoring = true;
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  resumeRecovery();
  await page.unroute("**/workspace/cases", offlineRoute);
  await page.locator("#connection-error").waitFor({ state: "hidden" });

  for (const width of [390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 950 });
    check(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      `No page overflow at ${width}px`,
    );
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator("#search").fill("Minh");
  await page
    .getByRole("button", { name: "Toggle navigation", exact: true })
    .click();
  check(
    (await page.locator("#menu-toggle").getAttribute("aria-expanded")) ===
      "true",
    "Mobile navigation expands",
  );
  await page
    .getByRole("button", { name: "Protocol library", exact: true })
    .click();
  check(
    (await page.locator("#menu-toggle").getAttribute("aria-expanded")) ===
      "false",
    "Mobile navigation collapses",
  );
  const demoPage = await context.newPage();
  demoPage.on("pageerror", (error) => errors.push(error.message));
  await demoPage.goto(base + "/demo");
  const officerFrame = demoPage.frameLocator("#off");
  const customerFrame = demoPage.frameLocator("#cust");
  await officerFrame.locator("#page-title").waitFor();
  await customerFrame.locator("#chat").waitFor();
  check(await officerFrame.locator("#page-title").isVisible(), "Retained demo embeds redesigned officer workspace");
  check(await customerFrame.locator("#person").isVisible(), "Retained customer app loads inside demo");
  await officerFrame.locator("#sync-label").filter({hasText:"Live"}).waitFor();
  await demoPage.evaluate(() => document.querySelector("#off").contentWindow.postMessage(
    {type:"select",id:"DEMO-0413"},location.origin));
  await officerFrame.locator("#overview h2").filter({hasText:"Jordan"}).waitFor();
  check((await api("/case/DEMO-0413")).status === "QUEUED", "Demo case preview preserves explicit officer pickup");
  await demoPage.close();
  await page.goto(base + "/docs");
  await page.locator("#endpoints details").first().waitFor();
  check(
    (await page.locator("#schemas details").count()) > 0,
    "Self-hosted API reference loads under CSP",
  );
  check(
    errors.length === 0,
    "No browser JavaScript errors: " + errors.join("; "),
  );
  console.log(
    `${assertions} browser checks passed. Desktop and mobile screenshots: frontend/test-results/`,
  );
})()
  .catch((e) => {
    console.error(e);
    process.exitCode = 1;
  })
  .finally(async () => {
    if (browser) await browser.close();
    if (server && server.exitCode === null) {
      server.kill("SIGTERM");
      await Promise.race([
        new Promise((resolve) => server.once("exit", resolve)),
        delay(3000),
      ]);
      if (server.exitCode === null) {
        server.kill("SIGKILL");
        await delay(100);
      }
    }
    fs.rmSync(temp, { recursive: true, force: true });
  });
