/* Two independent browser sessions, a real event stream and the actual customer demo. */
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { setTimeout: delay } = require("node:timers/promises");
const { chromium } = require("playwright");
const AxeBuilder = require("@axe-core/playwright").default;
const root = path.resolve(__dirname, "../.."),
  port = Number(process.env.BEACON_COLLAB_PORT || 8026),
  base = `http://127.0.0.1:${port}`;
const temp = fs.mkdtempSync(path.join(os.tmpdir(), "beacon-collaboration-"));
const output = path.join(root, "frontend/test-results");
let server,
  browser,
  count = 0,
  logs = "";
const errors = [];
function check(value, message) {
  assert(value, message);
  count++;
}
async function api(url, body) {
  const r = await fetch(base + url, {
    method: body === undefined ? "GET" : "POST",
    ...(body === undefined
      ? {}
      : {
          headers: { "content-type": "application/json" },
          body: JSON.stringify(body),
        }),
  });
  assert(r.ok, `${url}: ${r.status} ${await r.clone().text()}`);
  return r.json();
}
async function until(fn, message, timeout = 15000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) {
    try {
      if (await fn()) return;
    } catch {}
    await delay(100);
  }
  throw new Error(message + "\n" + logs);
}
async function identity(page, name) {
  await page.goto(base);
  await page.locator("#demo-officer-control").waitFor();
  await page.locator("#demo-officer-select").selectOption(name);
  await page.waitForFunction(
    (expected) =>
      document.getElementById("officer-name").textContent === expected,
    name,
  );
  await page.waitForFunction(
    () =>
      document.getElementById("sync-label").textContent ===
      "Live · shared updates",
  );
}
async function review(page, c) {
  await page.locator(`[data-case="${c.case_id}"]`).click();
  await page
    .locator("#overview h2")
    .filter({ hasText: c.customer_name })
    .waitFor();
  await page.getByRole("button", { name: "Review case", exact: true }).click();
  await page.locator("#detail-view h1").waitFor();
}
async function approve(page) {
  await page
    .getByRole("button", { name: "Review & approve", exact: true })
    .click();
  await page.locator("#confirm-checks").check();
  await page
    .getByRole("button", { name: "Confirm decision", exact: true })
    .click();
  await page.locator("#action-dialog").waitFor({ state: "hidden" });
}
async function release(page) {
  await page.getByRole("button", { name: "Release case", exact: true }).click();
  await page
    .locator("#release-note")
    .fill("A colleague can take over with the existing context.");
  await page
    .getByRole("button", { name: "Release to shared queue", exact: true })
    .click();
  await page.locator("#action-dialog").waitFor({ state: "hidden" });
}
async function queue(page) {
  await page
    .getByRole("button", { name: /^Priority queue/ })
    .first()
    .click();
}
async function audit(page, label) {
  const r = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();
  fs.writeFileSync(
    path.join(output, `accessibility-${label}.json`),
    JSON.stringify(
      {
        violations: r.violations,
        incomplete: r.incomplete,
        passedRules: r.passes.length,
      },
      null,
      2,
    ),
  );
  check(
    !r.violations.length,
    label +
      ": " +
      JSON.stringify(
        r.violations.map((v) => ({
          id: v.id,
          nodes: v.nodes.map((n) => n.target),
        })),
      ),
  );
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
        NRY_STAFF_PASSWORD: "",
        NRY_STAFF_ACCOUNTS: "",
        NRY_WEBHOOK_SECRET: "",
        NRY_NOW: "2026-11-15T12:00:00Z",
      },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );
  server.stdout.on("data", (b) => (logs += b));
  server.stderr.on("data", (b) => (logs += b));
  server.on("error", (e) => (logs += e.message));
  await until(
    async () => (await fetch(base + "/workspace/session")).ok,
    "Server did not start",
  );
  browser = await chromium.launch({
    ...(process.env.BEACON_CHROMIUM
      ? { executablePath: process.env.BEACON_CHROMIUM }
      : fs.existsSync("/usr/bin/chromium")
        ? { executablePath: "/usr/bin/chromium" }
        : {}),
    headless: true,
  });
  const alexContext = await browser.newContext({
    viewport: { width: 1440, height: 1050 },
  });
  const taylorContext = await browser.newContext({
    viewport: { width: 1440, height: 1050 },
  });
  const alex = await alexContext.newPage(),
    taylor = await taylorContext.newPage();
  for (const p of [alex, taylor])
    p.on("pageerror", (e) => errors.push(e.message));
  await identity(alex, "Alex Morgan");
  await identity(taylor, "Taylor Lee");
  const one = await api("/case", {
    customer_id: "CUST-002",
    issue_type: "CARD_DELIVERY",
    summary_en: "My card has not arrived.",
  });
  const two = await api("/case", {
    customer_id: "CUST-005",
    issue_type: "CARD_DELIVERY",
    summary_en: "Please check my replacement card.",
  });
  await until(
    async () =>
      (await alex.locator(".case-row").count()) === 2 &&
      (await taylor.locator(".case-row").count()) === 2,
    "Both officers did not receive shared cases",
  );
  check(true, "Both officers receive new cases without reloading");
  await review(alex, one);
  await taylor
    .locator(`[data-case="${one.case_id}"]`)
    .filter({ hasText: "Sam" })
    .waitFor();
  await until(
    async () =>
      (
        await taylor
          .locator(".case-row")
          .filter({ hasText: one.case_id })
          .innerText()
      ).includes("Alex Morgan"),
    "Claim did not reach the other officer",
  );
  check(true, "Claim ownership updates the other queue");
  await taylor.locator(`[data-case="${one.case_id}"]`).click();
  await taylor.getByRole("button", { name: "View case", exact: true }).click();
  await taylor.locator(".owner-readonly").waitFor();
  check(
    (await taylor
      .getByRole("button", { name: "Review & approve", exact: true })
      .count()) === 0,
    "Another officer cannot act on the claimed case",
  );
  check(
    (await taylor
      .getByRole("button", { name: "Release case", exact: true })
      .count()) === 0,
    "Another officer cannot release the claim",
  );
  await alex
    .getByRole("button", { name: "Review & approve", exact: true })
    .click();
  await api("/webhook/retell", {
    customer_id: "CUST-002",
    issue_type: "CARD_DELIVERY",
    case_reference: one.case_id,
    summary_en: "I need the card before my flight.",
    correction: "I fly out tomorrow.",
  });
  await alex.locator("#dialog-stale").waitFor();
  check(
    await alex.locator("#dialog-submit").isDisabled(),
    "A changed case invalidates an open decision",
  );
  await alex.getByRole("button", { name: "Cancel", exact: true }).click();
  await until(
    async () =>
      (await alex.locator(".detail-summary").innerText()).includes(
        "before my flight",
      ),
    "Latest customer correction not shown",
  );
  await approve(alex);
  await until(
    async () =>
      (await taylor.locator(".assignment-banner").innerText()).includes(
        "Completed by Alex Morgan",
      ),
    "Completion was not reflected for the other officer",
  );
  check(
    (await taylor.locator("#stat-done").textContent()) === "1",
    "Completion count updates across sessions",
  );
  check(
    (await api("/case/" + one.case_id)).completed_by === "Alex Morgan",
    "Responsible officer recorded on the case",
  );
  fs.mkdirSync(output, { recursive: true });
  await taylor.screenshot({
    path: path.join(output, "shared-completion.png"),
    fullPage: true,
    animations: "disabled",
  });
  await queue(taylor);
  await review(taylor, two);
  await release(taylor);
  await queue(alex);
  await until(
    async () =>
      !(
        await alex
          .locator(".case-row")
          .filter({ hasText: two.case_id })
          .innerText()
      ).includes("Taylor Lee"),
    "Release not reflected in shared queue",
  );
  await review(alex, two);
  check(
    (await api("/case/" + two.case_id)).assignment.officer === "Alex Morgan",
    "Released work can be claimed by another officer",
  );
  await release(alex);
  await queue(taylor);
  await review(taylor, two);
  await approve(taylor);
  await until(
    async () => (await alex.locator("#stat-done").textContent()) === "2",
    "Independent completion counts did not reconcile",
  );
  check(
    (await api("/case/" + two.case_id)).completed_by === "Taylor Lee",
    "Second officer can complete independent work",
  );
  await queue(alex);
  await alex.getByRole("button", { name: "Mine", exact: true }).click();
  check(
    (await alex.locator(".case-row").count()) === 0,
    "Mine filter excludes completed cases",
  );

  await alex.getByRole("button", { name: /^Live intake/ }).click();
  await taylor.getByRole("button", { name: /^Live intake/ }).click();
  let draft = await api("/intake/drafts", { customer_id: "CUST-001" });
  const draftUrl = "/intake/drafts/" + draft.draft_id;
  await alex.locator(`[data-draft-id="${draft.draft_id}"]`).waitFor();
  await taylor.locator(`[data-draft-id="${draft.draft_id}"]`).waitFor();
  check(
    (await api("/workspace/insights")).active === 0,
    "Unfinished drafts stay outside active metrics",
  );
  draft = await api(draftUrl, {
    expected_revision: draft.revision,
    issue_type: "SCAM_IN_PROGRESS",
    phase: "CHECKING",
    summary_en: "A caller asked me to move savings. I already sent money.",
    risk_signals: ["CUSTOMER_REPORTS_PRESSURE"],
    linked_transactions: ["TX-9001"],
  });
  await until(
    async () =>
      (await alex.locator(".draft-summary").innerText()).includes(
        "already sent",
      ),
    "Draft facts did not arrive live",
  );
  await until(
    async () =>
      (await taylor.locator(".draft-facts").innerText()).includes("4,800"),
    "Verified payment did not arrive in the other session",
  );
  check(
    (await alex.locator(".score-total,.priority-score").count()) === 0,
    "Draft view invents no priority score",
  );
  check(
    (await taylor.locator(".draft-status").innerText()).includes("not queued"),
    "Draft status is explicit",
  );
  await alex.locator("#toast").waitFor({ state: "hidden" });
  await alex.screenshot({
    path: path.join(output, "live-intake.png"),
    fullPage: true,
    animations: "disabled",
  });
  await audit(alex, "live-intake");
  await alex.setViewportSize({ width: 390, height: 844 });
  await alex.waitForFunction(
    () => document.getElementById("sidebar").getBoundingClientRect().right <= 0,
  );
  check(
    await alex.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    "Live intake fits a mobile viewport",
  );
  await alex.screenshot({
    path: path.join(output, "mobile-live-intake.png"),
    fullPage: true,
    animations: "disabled",
  });
  await audit(alex, "mobile-live-intake");
  await alex.setViewportSize({ width: 1440, height: 1050 });
  const submitted = await api(draftUrl + "/confirm", {
    expected_revision: draft.revision,
    customer_confirmed: true,
  });
  await alex.locator(".draft-status.confirmed").waitFor();
  await until(
    async () => (await taylor.locator("#intake-count").textContent()) === "0",
    "Confirmation did not update other intake counters",
  );
  check(
    (await api("/queue")).length === 1,
    "Confirmed draft enters the queue once",
  );
  const retried = await api(draftUrl + "/confirm", {
    expected_revision: draft.revision,
    customer_confirmed: true,
  });
  check(
    retried.case_reference === submitted.case_reference &&
      (await api("/queue")).length === 1,
    "Retried confirmation is idempotent",
  );

  // Reset only this isolated test DB, then exercise the actual scripted conversation and demo handoff.
  await api("/admin/reset", {});
  const demo = await alexContext.newPage();
  demo.on("pageerror", (e) => errors.push(e.message));
  await demo.goto(base + "/demo");
  await demo.locator('#scenes button[data-id="sam"]').waitFor();
  await demo.locator("#speed").selectOption("2");
  await demo.locator('#scenes button[data-id="sam"]').click();
  const officer = demo.frameLocator("#off");
  await officer.locator("#intake-title").waitFor();
  await officer
    .locator(".draft-need h3")
    .filter({ hasText: "Card delivery" })
    .waitFor();
  check(
    (await api("/queue")).length === 0,
    "Actual customer script shows the forming card before submission",
  );
  await demo.screenshot({
    path: path.join(output, "live-conversation-demo.png"),
    fullPage: true,
    animations: "disabled",
  });
  await until(
    async () => (await api("/queue")).length === 1,
    "Script did not confirm and queue its draft",
    60000,
  );
  await officer
    .locator("#overview h2")
    .filter({ hasText: "Sam" })
    .waitFor({ timeout: 15000 });
  check(
    (await api("/workspace/intake")).active_count === 0,
    "Scripted conversation completes its draft handoff",
  );
  await demo.close();
  check(errors.length === 0, "No browser errors: " + errors.join("; "));
  console.log(
    `${count} collaboration browser checks passed. Two sessions and the customer demo verified.`,
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
        new Promise((r) => server.once("exit", r)),
        delay(3000),
      ]);
      if (server.exitCode === null) server.kill("SIGKILL");
    }
    fs.rmSync(temp, { recursive: true, force: true });
  });
