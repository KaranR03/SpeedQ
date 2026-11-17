/* Beacon Assist. No external scripts, analytics or rendering of data as HTML. */
"use strict";
import { createVisuals } from "/assets/visuals.js";
import { createIntake } from "/assets/intake.js";

const $ = (id) => document.getElementById(id);
const state = {
  cases: [],
  selected: null,
  preview: null,
  detail: null,
  view: "queue",
  returnView: "queue",
  filter: "all",
  band: "all",
  query: "",
  tab: "overview",
  session: null,
  meta: null,
  protocols: [],
  suggestions: [],
  online: false,
  loading: false,
  selectionVersion: 0,
  dialogBusy: false,
  drilldown: null,
  context: null,
  detailTabVersion: 0,
  insightVersion: 0,
  intake: { active_count: 0, drafts: [] },
  intakeFingerprint: "",
  refreshPending: false,
  openingCase: false,
  liveConnected: false,
  lastRefresh: 0,
  demoOfficer: sessionStorage.getItem("beacon-demo-officer") || "",
};
const names = {
  queue: "Priority queue",
  review: "In review",
  completed: "Completed",
  protocols: "Protocol library",
  learning: "Learning loop",
  detail: "Case workspace",
  insights: "Care insights",
  intake: "Live intake",
};
const issues = {
  SCAM_IN_PROGRESS: "Scam in progress",
  FRAUD_UNAUTHORISED: "Unrecognised charge",
  MONEY_MISSING: "Missing payment",
  CARD_DELIVERY: "Card delivery",
  ACCOUNT_ACCESS: "Account access",
  DETAILS_CHANGE: "Contact details change",
  HARDSHIP: "Financial hardship",
};
const bands = { P1: "Critical", P2: "High", P3: "Medium", P4: "Low" };
const openStatuses = new Set([
  "QUEUED",
  "AWAITING_CUSTOMER_CONFIRM",
  "IN_REVIEW",
]);
const smallScreen = window.matchMedia("(max-width: 720px)");
function setMenu(open, restoreFocus = false) {
  const visible = Boolean(open && smallScreen.matches);
  $("sidebar").classList.toggle("open", visible);
  $("sidebar").inert = smallScreen.matches && !visible;
  $("main").inert = visible;
  $("nav-backdrop").hidden = !visible;
  $("menu-toggle").setAttribute("aria-expanded", String(visible));
  if (restoreFocus) $("menu-toggle").focus();
}
const human = (s = "") =>
  String(s)
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/^./, (c) => c.toUpperCase());
const issue = (s) => issues[s] || human(s);
const active = (c) => c.stage !== "DONE";
const reviewing = (c) =>
  active(c) && (c.stage === "WITH_OFFICER" || c.status === "MANUAL");
const initials = (name = "?") =>
  name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((x) => x[0])
    .join("")
    .toUpperCase();
const casePath = (id) => `/case/${encodeURIComponent(id)}`;
const ownedByOther = (c) =>
  Boolean(c.assignment && c.assignment.officer !== state.session?.officer);

// All API content becomes text nodes. Never use innerHTML or inline event handlers.
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (
      ["checked", "required", "disabled", "hidden", "selected"].includes(key)
    )
      node[key] = Boolean(value);
    else node.setAttribute(key, String(value));
  }
  for (const child of children.flat(Infinity)) {
    if (child !== null && child !== undefined && child !== false) {
      node.append(
        child instanceof Node ? child : document.createTextNode(String(child)),
      );
    }
  }
  return node;
}
function icon(name) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "icon");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `#i-${name}`);
  svg.append(use);
  return svg;
}
function button(label, onClick, classes = "button secondary") {
  const b = el("button", { type: "button", class: classes }, label);
  b.addEventListener("click", () => run(onClick));
  return b;
}
function badge(band) {
  const safeBand = Object.hasOwn(bands, band) ? band : "P4";
  return el(
    "span",
    { class: `badge ${safeBand.toLowerCase()}` },
    `${safeBand} · ${bands[safeBand]}`,
  );
}
function avatar(name, id = "") {
  const colour =
    ["warm", "sage", "blue", ""][
      String(id).charCodeAt(String(id).length - 1) % 4
    ] || "";
  return el(
    "span",
    { class: `avatar ${colour}`, "aria-hidden": "true" },
    initials(name),
  );
}
function waiting(c) {
  const minutes = Math.max(
    0,
    Math.floor((Date.now() - new Date(c.created_at).getTime()) / 60000),
  );
  if (!Number.isFinite(minutes) || minutes < 1) return "Just now";
  if (minutes >= 60) return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
  return `${minutes} min`;
}
function time(s) {
  const d = new Date(s);
  return Number.isNaN(d.getTime())
    ? "Time unavailable"
    : new Intl.DateTimeFormat("en-AU", {
        day: "numeric",
        month: "short",
        hour: "numeric",
        minute: "2-digit",
        timeZone: "Australia/Brisbane",
      }).format(d);
}
async function api(path, body) {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    credentials: "same-origin",
    cache: "no-store",
    headers: {
      Accept: "application/json",
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...(state.demoOfficer ? { "x-demo-officer": state.demoOfficer } : {}),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    signal: AbortSignal.timeout(15000),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const detail = Array.isArray(error.detail)
      ? error.detail.map((x) => x.msg).join("; ")
      : error.detail;
    const errorObject = new Error(
      detail || `Request failed (${response.status}). Please try again.`,
    );
    errorObject.status = response.status;
    throw errorObject;
  }
  return response.json();
}
let toastTimer;
function toast(message, error = false) {
  clearTimeout(toastTimer);
  $("toast").textContent = message;
  $("toast").classList.toggle("error", error);
  $("toast").hidden = false;
  toastTimer = setTimeout(
    () => {
      $("toast").hidden = true;
    },
    error ? 9000 : 4500,
  );
}
async function run(fn) {
  try {
    await fn();
  } catch (error) {
    toast(error.message || "Something went wrong. Please try again.", true);
  }
}
function online(value) {
  state.online = value;
  $("connection-error").hidden = value;
  $("sync-dot").classList.toggle("offline", !value);
  $("sync-label").textContent = value
    ? state.liveConnected
      ? "Live · shared updates"
      : "Live · backup refresh"
    : "Updates paused";
}
function renderStats() {
  const live = state.cases.filter(active);
  $("stat-active").textContent = live.length;
  $("stat-urgent").replaceChildren(
    String(live.filter((c) => ["P1", "P2"].includes(c.priority.band)).length),
    el("span", { class: "stat-tag" }, "P1 + P2"),
  );
  $("stat-review").textContent = state.cases.filter(reviewing).length;
  $("stat-done").textContent = state.cases.filter((c) => !active(c)).length;
  $("nav-count").textContent = live.length;
  $("review-count").textContent = state.cases.filter(reviewing).length;
  $("urgent-filter-count").textContent = live.filter((c) =>
    ["P1", "P2"].includes(c.priority.band),
  ).length;
  $("next-case").disabled =
    !state.online ||
    !state.cases.some((c) => openStatuses.has(c.status) && !ownedByOther(c));
  $("intake-count").textContent = state.intake.active_count;
  $("live-intake-shortcut").hidden = !state.intake.active_count;
  $("live-intake-shortcut").textContent =
    `${state.intake.active_count} ${state.intake.active_count === 1 ? "card" : "cards"} taking shape →`;
}
function visibleCases() {
  return state.cases.filter((c) => {
    if (
      state.view === "completed"
        ? active(c)
        : state.view === "review"
          ? !reviewing(c)
          : !active(c)
    )
      return false;
    if (state.filter === "urgent" && !["P1", "P2"].includes(c.priority.band))
      return false;
    if (state.filter === "waiting" && (reviewing(c) || !active(c)))
      return false;
    if (
      state.filter === "mine" &&
      c.assignment?.officer !== state.session?.officer
    )
      return false;
    if (state.band !== "all" && c.priority.band !== state.band) return false;
    const d = state.drilldown;
    if (d?.issue && c.issue_type !== d.issue) return false;
    if (
      d?.stage &&
      (d.stage === "waiting"
        ? reviewing(c)
        : d.stage === "manual"
          ? c.status !== "MANUAL"
          : d.stage === "review"
            ? !reviewing(c) || c.status === "MANUAL"
            : active(c))
    )
      return false;
    if (d?.evidence === "with" && !c.priority.signals.length) return false;
    if (d?.evidence === "without" && c.priority.signals.length) return false;
    if (d?.language && (!c.language || c.language === "en")) return false;
    if (d?.repeat && c.contacts < 2) return false;
    if (d?.age) {
      const minutes = Math.max(
        0,
        (Date.now() - new Date(c.created_at).getTime()) / 60000,
      );
      const [start, end] = {
        under10: [0, 10],
        "10to30": [10, 30],
        "30to60": [30, 60],
        "60plus": [60, Infinity],
      }[d.age];
      if (!(minutes >= start && minutes < end)) return false;
    }
    const haystack =
      `${c.customer_name} ${c.case_id} ${c.customer_id} ${issue(c.issue_type)} ${c.summary_en}`.toLowerCase();
    return haystack.includes(state.query.toLowerCase());
  });
}
function renderRows() {
  const focused = document.activeElement?.getAttribute("data-case");
  const cases = visibleCases();
  const rows = cases.map((c) => {
    const customer = el(
      "span",
      { class: "customer-copy" },
      el(
        "strong",
        {},
        c.customer_name || "Customer",
        el("span", { class: "case-ref" }, c.case_id),
      ),
      el("p", {}, issue(c.issue_type)),
    );
    const select = button("", () => selectCase(c.case_id, true), "case-select");
    select.setAttribute("data-case", c.case_id);
    select.setAttribute(
      "aria-label",
      `Preview ${c.customer_name || "customer"}, ${c.case_id}`,
    );
    select.setAttribute("aria-pressed", String(c.case_id === state.selected));
    select.append(avatar(c.customer_name, c.customer_id), customer);
    const status = !active(c)
      ? "Completed"
      : c.status === "MANUAL"
        ? "Manual handling"
        : reviewing(c)
          ? "In review"
          : "Waiting";
    const row = el(
      "tr",
      { class: `case-row${c.case_id === state.selected ? " selected" : ""}` },
      el("td", {}, el("div", { class: "customer-cell" }, select)),
      el(
        "td",
        {},
        badge(c.priority.band),
        el(
          "span",
          { class: "score-caption" },
          `Score ${c.priority.score} / 100`,
        ),
      ),
      el(
        "td",
        {},
        el(
          "span",
          { class: "waiting-cell" },
          icon("clock"),
          !active(c) ? "—" : waiting(c),
        ),
        el(
          "span",
          { class: "row-status" },
          c.completed_by
            ? `Completed · ${c.completed_by}`
            : c.assignment
              ? `With ${c.assignment.officer}`
              : status,
        ),
      ),
      el("td", {}, icon("chevron")),
    );
    row.addEventListener("click", (e) => {
      if (!e.target.closest("button")) run(() => selectCase(c.case_id, true));
    });
    return row;
  });
  $("case-rows").replaceChildren(...rows);
  $("list-count").textContent = cases.length;
  $("results-summary").textContent =
    `${cases.length} ${cases.length === 1 ? "case" : "cases"} · Highest priority first`;
  $("empty-state").hidden = Boolean(cases.length);
  const filtered =
    state.query || state.band !== "all" || state.filter !== "all";
  $("empty-title").textContent = filtered
    ? "No matching cases"
    : state.view === "review"
      ? "No cases in review"
      : state.view === "completed"
        ? "No completed cases yet"
        : "You’re all caught up";
  $("empty-message").textContent = filtered
    ? "Try another search or clear your filters."
    : state.view === "review"
      ? "Cases appear here when you start a review or choose manual handling."
      : state.view === "completed"
        ? "Recorded customer outcomes will appear here after a case is completed."
        : "New cases will appear automatically. Load sample cases to explore the prototype.";
  if (focused)
    [...document.querySelectorAll("[data-case]")]
      .find((b) => b.dataset.case === focused)
      ?.focus({ preventScroll: true });
}
function renderOverview(c) {
  if (!c) {
    $("overview").replaceChildren(
      el(
        "div",
        { class: "overview-placeholder" },
        el("div", { class: "empty-icon" }, icon("person")),
        el("h2", {}, "One case. A clearer picture."),
        el(
          "p",
          {},
          "Select a customer to see their needs and the recommended next step.",
        ),
      ),
    );
    return;
  }
  const p = c.proposed_solution;
  const actions = p.actions
    .slice(0, 3)
    .map((a) => el("li", {}, icon("check"), a.label));
  if (p.actions.length > 3)
    actions.push(
      el(
        "li",
        { class: "more-actions" },
        `+ ${p.actions.length - 3} more in the full plan`,
      ),
    );
  if (!actions.length)
    actions.push(el("li", {}, icon("person"), "Officer-led support"));
  const review = button(
    c.card_status.stage === "DONE"
      ? "View outcome"
      : ownedByOther(c)
        ? "View case"
        : "Review case",
    () => openCase(c.case_id),
    "button primary full",
  );
  review.append(icon("arrow"));
  $("overview").replaceChildren(
    el(
      "div",
      { class: "overview-topline" },
      el("span", {}, "CASE OVERVIEW"),
      el("span", {}, c.case_id),
    ),
    el(
      "div",
      { class: "overview-content" },
      el(
        "div",
        { class: "customer-heading" },
        avatar(c.customer_name, c.customer_id),
        el(
          "div",
          {},
          el("h2", {}, c.customer_name || "Customer"),
          el("p", {}, `${c.customer_id} · ${c.language_label || "English"}`),
        ),
      ),
      el("h3", { class: "overview-issue" }, issue(c.issue_type)),
      el(
        "p",
        { class: "case-summary" },
        c.summary_en || "No summary provided.",
      ),
      el(
        "div",
        { class: "priority-strip" },
        badge(c.priority.band),
        el(
          "span",
          { class: "priority-score" },
          c.priority.score,
          el("small", {}, " / 100"),
        ),
      ),
      el("div", { class: "section-kicker" }, "Why this needs attention"),
      el(
        "p",
        { class: "reason-highlight" },
        c.priority.reasons[0] || "Ranked using the approved protocol.",
      ),
      el("div", { class: "section-kicker" }, "Recommended next steps"),
      el("ul", { class: "mini-actions" }, actions),
    ),
    el(
      "div",
      { class: "review-footer" },
      review,
      el(
        "p",
        {},
        c.card_status.stage === "DONE"
          ? "Outcome and audit trail available"
          : ownedByOther(c)
            ? `${c.assignment.officer} is handling this case`
            : "Opening a review claims the case for you",
      ),
    ),
  );
}
async function selectCase(id, interactive = false) {
  state.selected = id;
  const version = ++state.selectionVersion;
  renderRows();
  const c = await api(casePath(id));
  if (version !== state.selectionVersion) return;
  state.preview = c;
  renderOverview(c);
  if (interactive && smallScreen.matches)
    $("overview").scrollIntoView({
      block: "start",
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
    });
}
async function refresh() {
  if (state.loading) {
    state.refreshPending = true;
    return;
  }
  state.loading = true;
  try {
    const previous = new Map(state.cases.map((c) => [c.case_id, c]));
    const [cases, intake] = await Promise.all([
      api("/workspace/cases"),
      api("/workspace/intake"),
    ]);
    state.cases = cases;
    state.intake = intake;
    state.lastRefresh = Date.now();
    const completed = cases.filter(
      (c) =>
        previous.has(c.case_id) &&
        previous.get(c.case_id).stage !== "DONE" &&
        c.stage === "DONE" &&
        c.completed_by &&
        c.completed_by !== state.session?.officer,
    );
    if (completed.length)
      toast(
        completed.length === 1
          ? `${completed[0].completed_by} completed ${completed[0].customer_name}'s case. Your workspace is updated.`
          : `${completed.length} cases were completed by colleagues. Your workspace is updated.`,
      );
    online(true);
    renderStats();
    if (
      ["queue", "review", "completed"].includes(state.view) &&
      !state.openingCase
    ) {
      renderRows();
      const cases = visibleCases();
      if (!cases.some((c) => c.case_id === state.selected)) {
        state.selected = cases[0]?.case_id || null;
        state.preview = null;
        renderRows();
      }
      if (state.selected) await selectCase(state.selected);
      else renderOverview(null);
    } else if (state.view === "insights") await loadInsights();
    else if (state.view === "intake") renderIntakeView();
    else if (state.view === "detail" && state.detail && !state.openingCase) {
      const latest = await api(casePath(state.detail.case_id));
      const changed = latest.revision !== state.detail.revision;
      if ($("action-dialog").open) {
        if (changed) {
          $("dialog-stale").hidden = false;
          $("dialog-submit").disabled = true;
        }
      } else {
        let context = state.context;
        if (state.tab === "context")
          context = await api(`${casePath(latest.case_id)}/context`);
        if (
          JSON.stringify(latest) !== JSON.stringify(state.detail) ||
          JSON.stringify(context) !== JSON.stringify(state.context)
        ) {
          state.detail = latest;
          state.context = context;
          renderDetail();
        }
      }
    }
  } catch (error) {
    online(false);
    renderStats();
    $("connection-message").textContent =
      `Could not update your workspace. ${error.message} Displayed information may be out of date.`;
  } finally {
    state.loading = false;
    if (state.refreshPending) {
      state.refreshPending = false;
      queueMicrotask(() => run(refresh));
    }
  }
}
function renderIntakeView() {
  const fingerprint = JSON.stringify(state.intake);
  if (
    fingerprint !== state.intakeFingerprint ||
    !$("intake-content").children.length
  ) {
    $("intake-content").replaceChildren(intakeRenderer(state.intake));
    state.intakeFingerprint = fingerprint;
  }
}
function showView(view) {
  state.view = view;
  for (const [id, visible] of Object.entries({
    "list-view": ["queue", "review", "completed"].includes(view),
    "detail-view": view === "detail",
    "library-view": view === "protocols",
    "learning-view": view === "learning",
    "insights-view": view === "insights",
    "intake-view": view === "intake",
  })) {
    $(id).hidden = !visible;
  }
  $("breadcrumb-current").textContent = names[view];
  document.title = `${names[view]} · Beacon Assist`;
  document.querySelectorAll("[data-view]").forEach((b) => {
    const selected =
      b.dataset.view === (view === "detail" ? state.returnView : view);
    b.classList.toggle("active", selected);
    if (selected) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  setMenu(false);
}
async function navigate(view) {
  ++state.selectionVersion;
  showView(view);
  if (["queue", "review", "completed"].includes(view)) {
    state.drilldown = null;
    $("insight-filter").hidden = true;
    state.query = "";
    state.filter = "all";
    state.band = "all";
    $("search").value = "";
    $("band-filter").value = "all";
    updateFilters();
    const titles = {
      queue: [
        "Priority queue",
        "A clear view of who needs you next.",
        "Your live queue",
      ],
      review: [
        "In review",
        "Keep the next step clear for every customer.",
        "Cases with an officer",
      ],
      completed: [
        "Completed",
        "A recorded outcome. A complete trail of care.",
        "Completed cases",
      ],
    };
    $("page-title").replaceChildren(
      titles[view][0],
      el("span", { class: "heading-dot" }, "."),
    );
    $("page-description").textContent = titles[view][1];
    $("list-heading").replaceChildren(titles[view][2], $("list-count"));
    $("next-case").hidden = view === "completed";
    $("load-demo").hidden = !state.session?.demo || view !== "queue";
    renderRows();
    renderOverview(null);
    await refresh();
  } else if (view === "intake") {
    renderIntakeView();
    await refresh();
  } else if (view === "insights") await loadInsights();
  else if (view === "protocols") {
    state.protocols = await api("/protocols");
    renderProtocols();
  } else if (view === "learning") await loadSuggestions();
  $("main").focus({ preventScroll: true });
}
function updateFilters() {
  document.querySelectorAll("[data-filter]").forEach((b) => {
    const selected = b.dataset.filter === state.filter;
    b.classList.toggle("active", selected);
    b.setAttribute("aria-pressed", String(selected));
  });
}
async function refilter() {
  renderRows();
  const cases = visibleCases();
  if (!cases.some((c) => c.case_id === state.selected)) {
    state.selected = cases[0]?.case_id || null;
    if (state.selected) await selectCase(state.selected);
    else {
      ++state.selectionVersion;
      renderOverview(null);
    }
  }
}
async function openCase(id) {
  const version = ++state.selectionVersion;
  state.openingCase = true;
  try {
    let c = await api(casePath(id));
    if (version !== state.selectionVersion) return;
    if (
      (openStatuses.has(c.status) || c.status === "MANUAL") &&
      c.card_status.stage !== "DONE" &&
      !c.assignment
    ) {
      try {
        c = await api(`${casePath(id)}/pickup`, {
          officer: state.session.officer,
          expected_revision: c.revision,
        });
      } catch (error) {
        if (error.status !== 409) throw error;
        c = await api(casePath(id));
        toast(error.message, true);
      }
    }
    if (version !== state.selectionVersion) return;
    if (state.view !== "detail") state.returnView = state.view;
    state.detail = c;
    state.tab = "overview";
    state.context = null;
    ++state.detailTabVersion;
    showView("detail");
    renderDetail();
    $("main").focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: "instant" });
  } finally {
    state.openingCase = false;
  }
  await refresh();
}
function info(text) {
  return el("div", { class: "info-note" }, icon("info"), el("span", {}, text));
}
function bullets(items) {
  return el(
    "ul",
    {},
    items.map((x) => el("li", {}, x)),
  );
}
function sourceLinks(sources) {
  return el(
    "ul",
    {},
    sources.map((s) => {
      try {
        const url = new URL(s.url);
        if (url.protocol !== "https:" || url.username || url.password)
          throw new Error("Unsafe source URL");
        return el(
          "li",
          {},
          el(
            "a",
            { href: url.href, target: "_blank", rel: "noopener noreferrer" },
            s.title || url.hostname,
          ),
        );
      } catch {
        return el("li", {}, s.title || "Source unavailable");
      }
    }),
  );
}
function renderDetail() {
  const c = state.detail,
    p = c.proposed_solution,
    done = c.card_status.stage === "DONE";
  const back = button("", () => navigate(state.returnView), "back-button");
  back.append(icon("back"), `Back to ${names[state.returnView].toLowerCase()}`);
  const heading = el(
    "div",
    { class: "detail-heading" },
    el(
      "div",
      { class: "customer-heading" },
      avatar(c.customer_name, c.customer_id),
      el(
        "div",
        {},
        el("h1", {}, c.customer_name || "Customer"),
        el("p", {}, `${c.case_id} · ${issue(c.issue_type)}`),
      ),
    ),
    el(
      "div",
      { class: "detail-heading-actions" },
      badge(c.priority.band),
      button("Handoff brief", handoffDialog),
    ),
  );
  const summary = el(
    "section",
    { class: "panel" },
    el("div", { class: "section-kicker" }, "THE CUSTOMER’S NEED"),
    el(
      "p",
      { class: "detail-summary" },
      c.summary_en || "No summary provided.",
    ),
    el(
      "dl",
      { class: "metadata-grid" },
      ...[
        ["Customer", c.customer_id],
        ["Mobile on file", c.customer_mobile || "Not recorded"],
        ["Language", c.language_label || "English"],
        ["Status", c.card_status.label],
      ].map(([k, v]) => el("div", {}, el("dt", {}, k), el("dd", {}, v))),
    ),
  );
  if (c.summary_customer_lang)
    summary.append(
      el(
        "details",
        {},
        el("summary", {}, "Original language summary"),
        el("p", { class: "case-summary" }, c.summary_customer_lang),
      ),
    );
  if (c.contacts > 1)
    summary.append(
      info(
        `${c.contacts} contacts about this issue. Kept together in one case.`,
      ),
    );
  const section = el("section", { class: "panel detail-section" });
  const tabs = el("div", {
    class: "detail-tabs",
    role: "group",
    "aria-label": "Case information",
  });
  for (const [key, text] of [
    ["overview", "Overview"],
    ["evidence", "Evidence"],
    ["context", "Customer context"],
    ["activity", "Activity"],
  ]) {
    const b = button(
      text,
      async () => {
        const ticket = ++state.detailTabVersion;
        if (key === "context") {
          const context = await api(`${casePath(c.case_id)}/context`);
          if (
            ticket !== state.detailTabVersion ||
            state.detail?.case_id !== c.case_id ||
            state.view !== "detail"
          )
            return;
          state.context = context;
        }
        state.tab = key;
        renderDetail();
        [...$("detail-view").querySelectorAll("[data-detail-tab]")]
          .find((t) => t.dataset.detailTab === key)
          ?.focus({ preventScroll: true });
      },
      key === state.tab ? "active" : "",
    );
    b.setAttribute("aria-pressed", String(state.tab === key));
    b.dataset.detailTab = key;
    tabs.append(b);
  }
  section.append(tabs);
  if (state.tab === "overview") {
    section.append(
      el("h2", {}, "Why this priority"),
      el(
        "ul",
        { class: "evidence-list" },
        c.priority.reasons
          .slice(0, 3)
          .map((r) => el("li", {}, icon("shield"), r)),
      ),
    );
    if (c.priority.reasons.length > 3)
      section.append(
        el(
          "details",
          {},
          el("summary", {}, `View all ${c.priority.reasons.length} reasons`),
          bullets(c.priority.reasons),
        ),
      );
    section.append(
      el("h3", {}, "Customer message draft"),
      el(
        "div",
        { class: "message-draft" },
        c.outcome?.message || p.customer_message,
      ),
    );
    if (p.customer_message_missing.length && !done)
      section.append(
        el(
          "p",
          { class: "inline-warning" },
          `This draft has unfilled fields: ${p.customer_message_missing.join(", ")}. Use manual handling to record a complete customer outcome.`,
        ),
      );
    section.append(el("h3", {}, "What the customer sees"));
    const stages = [
      "RECEIVED",
      "RANKED",
      "WITH_OFFICER",
      "ACTION_TAKEN",
      "DONE",
    ];
    const labels = [
      "Received",
      "Ranked",
      "With officer",
      "Action taken",
      "Done",
    ];
    const index = stages.indexOf(c.card_status.stage);
    section.append(
      el(
        "div",
        { class: "customer-progress" },
        stages.map((s, i) =>
          el(
            "div",
            {
              class: `progress-step${i < index ? " done" : i === index ? " current" : ""}`,
              ...(i === index ? { "aria-current": "step" } : {}),
            },
            labels[i],
          ),
        ),
      ),
    );
  } else if (state.tab === "evidence") {
    section.append(visuals.score(c));
    section.append(
      el("h2", {}, "Account evidence"),
      info(
        "Account signals come from the synthetic account records. Customer statements are kept separate.",
      ),
    );
    section.append(
      el("h3", {}, "Verified signals"),
      el(
        "div",
        { class: "tag-list" },
        c.priority.signals.length
          ? c.priority.signals.map((s) =>
              el("span", { class: "signal-tag" }, human(s)),
            )
          : el("p", { class: "case-summary" }, "No verified account signals."),
      ),
      el("h3", {}, "Conversation cues"),
      el(
        "div",
        { class: "tag-list" },
        c.priority.caller_signals.length
          ? c.priority.caller_signals.map((s) =>
              el("span", { class: "signal-tag" }, human(s)),
            )
          : el(
              "p",
              { class: "case-summary" },
              "No conversation cues recorded.",
            ),
      ),
      el("h3", {}, "Linked transactions"),
      bullets(
        c.linked_transactions.length
          ? c.linked_transactions
          : ["No transactions linked."],
      ),
      el("h3", {}, "How Prorio reached the proposal"),
      el(
        "ol",
        {},
        c.prorio_trace.map((t) =>
          el("li", {}, el("strong", {}, t.step), t.detail),
        ),
      ),
      el(
        "details",
        {},
        el("summary", {}, "Protocol steps and sources"),
        el(
          "p",
          { class: "case-summary" },
          `${p.protocol.title} · v${p.protocol.version}`,
        ),
        el(
          "ol",
          {},
          p.steps.map((s) => el("li", {}, el("strong", {}, s.who), s.step)),
        ),
        sourceLinks(p.protocol.sources),
      ),
    );
  } else if (state.tab === "context") {
    section.append(
      state.context
        ? visuals.context(state.context)
        : info(
            "Reload the Customer context tab to fetch current account records.",
          ),
    );
  } else {
    section.append(
      el("h2", {}, "Decision & activity trail"),
      ...[...c.audit_log]
        .reverse()
        .map((a) =>
          el(
            "article",
            { class: "audit-item" },
            el("strong", {}, human(a.action)),
            el("p", {}, a.result || "Recorded"),
            el("small", {}, `${a.actor} · ${time(a.ts)}`),
          ),
        ),
    );
  }
  const actions = el(
    "aside",
    { class: "panel action-panel", "aria-label": "Recommended plan" },
    el("h2", {}, icon("spark"), "Recommended plan"),
    el(
      "p",
      { class: "action-subtitle" },
      `Prorio · ${p.protocol.title} · v${p.protocol.version}`,
    ),
  );
  if (done)
    actions.append(
      el(
        "div",
        { class: "success-note" },
        icon("check"),
        `Completed · ${human(c.officer_decision || c.status)}`,
      ),
    );
  else if (c.status === "MANUAL")
    actions.append(
      el(
        "div",
        { class: "manual-pill" },
        "Manual handling · awaiting your outcome",
      ),
    );
  actions.append(
    el(
      "div",
      { class: "section-kicker" },
      p.executor === "AI_AFTER_APPROVAL"
        ? "AI acts after your approval"
        : "Officer-led actions",
    ),
    el(
      "ol",
      { class: "action-list" },
      p.actions.map((a) =>
        el(
          "li",
          {},
          el(
            "div",
            {},
            a.label,
            Object.keys(a.params).length
              ? el("small", {}, Object.values(a.params).join(" · "))
              : null,
          ),
        ),
      ),
    ),
  );
  if (p.already_done.length)
    actions.append(el("h3", {}, "Already protected"), bullets(p.already_done));
  if (p.officer_tasks.length)
    actions.append(
      el(
        "details",
        {},
        el(
          "summary",
          { class: "text-button" },
          `${p.officer_tasks.length} officer tasks / conditions`,
        ),
        bullets(p.officer_tasks),
      ),
    );
  if (p.required_checks.length && !done)
    actions.append(
      el("h3", {}, "Before you approve"),
      bullets(p.required_checks),
    );
  const buttons = el("div", { class: "action-buttons" });
  if (!done && ownedByOther(c)) {
    buttons.append(
      el(
        "div",
        { class: "owner-readonly" },
        `${c.assignment.officer} is handling this case. You can view the evidence; only the assigned officer can record a decision or release it.`,
      ),
    );
  } else if (!done && !c.assignment) {
    buttons.append(
      button(
        "Claim this case",
        () => openCase(c.case_id),
        "button primary full",
      ),
    );
  } else if (openStatuses.has(c.status)) {
    const approve = button(
      "Review & approve",
      () => decisionDialog("APPROVE"),
      "button primary full",
    );
    const modify = button("Modify plan", () => decisionDialog("MODIFY"));
    if (p.customer_message_missing.length) {
      approve.disabled = true;
      modify.disabled = true;
      actions.append(
        el(
          "p",
          { class: "inline-warning" },
          "Complete the customer message through manual handling before closing this case.",
        ),
      );
    }
    buttons.append(
      approve,
      el(
        "div",
        { class: "action-button-row" },
        modify,
        button("Handle manually", () => decisionDialog("MANUAL")),
      ),
      button("Change priority", rerankDialog, "text-button"),
    );
  } else if (c.status === "MANUAL" && !done)
    buttons.append(
      button(
        "Record outcome & complete",
        completeDialog,
        "button primary full",
      ),
    );
  else
    buttons.append(button("Review next case", nextCase, "button primary full"));
  actions.append(
    buttons,
    el(
      "p",
      { class: "subtle-caption" },
      "Prototype: all actions are simulated. Drafts never move money. Every decision is recorded.",
    ),
  );
  const ownerBanner = el(
    "div",
    { class: `assignment-banner${ownedByOther(c) && !done ? " other" : ""}` },
    el(
      "span",
      {},
      icon("person"),
      " ",
      el(
        "strong",
        {},
        done
          ? `Completed by ${c.completed_by || "the team"}`
          : c.assignment
            ? `Assigned to ${c.assignment.officer}`
            : "Unassigned · ready for an officer",
      ),
      !done && c.assignment?.claimed_at
        ? ` · claimed ${time(c.assignment.claimed_at)}`
        : "",
    ),
  );
  if (!done && c.assignment && !ownedByOther(c))
    ownerBanner.append(button("Release case", releaseDialog));
  $("detail-view").replaceChildren(
    back,
    heading,
    ownerBanner,
    el(
      "div",
      { class: "detail-layout" },
      el("div", {}, summary, section),
      actions,
    ),
  );
}

let dialogSubmit = null;
function dialog(title, content, submitText, submit) {
  $("dialog-title").textContent = title;
  $("dialog-body").replaceChildren(
    ...(Array.isArray(content) ? content : [content]),
  );
  $("dialog-error").hidden = true;
  $("dialog-stale").hidden = true;
  $("dialog-submit").disabled = false;
  $("dialog-submit").hidden = !submit;
  $("dialog-submit").textContent = submitText || "Confirm";
  $("dialog-cancel").textContent = submit ? "Cancel" : "Close";
  dialogSubmit = submit;
  $("action-dialog").showModal();
}
function textField(label, id, required = false) {
  return [
    el("label", { for: id, class: "field-label" }, label),
    el("textarea", { id, class: "text-area", maxlength: "2000", required }),
  ];
}
function check(label, id, required = false, checked = false) {
  return el(
    "label",
    { class: "check-label", for: id },
    el("input", { id, type: "checkbox", required, checked }),
    el("span", {}, label),
  );
}
async function recorded(c, message) {
  state.detail = c;
  if (state.tab === "context")
    state.context = await api(`${casePath(c.case_id)}/context`).catch(
      () => null,
    );
  renderDetail();
  await refresh();
  toast(message);
}
function decisionDialog(decision) {
  const c = state.detail,
    p = c.proposed_solution;
  const contents = [
    el(
      "p",
      {},
      `${c.customer_name} · ${c.case_id}. ${decision === "MANUAL" ? "Keep this case with an officer until an outcome is recorded." : "Review the actions and required checks before recording your decision."}`,
    ),
  ];
  if (decision === "MODIFY") {
    contents.push(el("div", { class: "section-kicker" }, "Actions to include"));
    for (const a of state.meta.actions)
      contents.push(
        check(
          a.label,
          `action-${a.action}`,
          false,
          p.actions.some((x) => x.action === a.action),
        ),
      );
    contents.push(
      check(
        "Suggest these changes to the protocol owner",
        "suggest-update",
        false,
        true,
      ),
    );
  } else if (decision === "APPROVE")
    contents.push(
      el(
        "ul",
        { class: "dialog-action-list" },
        p.actions.map((a) =>
          el(
            "li",
            {},
            a.label,
            Object.keys(a.params).length
              ? ` · ${Object.values(a.params).join(", ")}`
              : "",
          ),
        ),
      ),
    );
  if (decision !== "MANUAL" && p.required_checks.length)
    contents.push(el("h3", {}, "Required checks"), bullets(p.required_checks));
  contents.push(
    ...textField(
      decision === "APPROVE"
        ? "Officer note (optional)"
        : "Reason for your decision",
      "decision-note",
      decision !== "APPROVE",
    ),
  );
  if (decision !== "MANUAL")
    contents.push(
      check(
        "I have reviewed the required checks, action parameters and customer message.",
        "confirm-checks",
        true,
      ),
    );
  dialog(
    decision === "APPROVE"
      ? "Approve this plan?"
      : decision === "MODIFY"
        ? "Modify the proposed plan"
        : "Handle this case manually",
    contents,
    decision === "MANUAL" ? "Start manual handling" : "Confirm decision",
    async () => {
      const body = {
        decision,
        officer: state.session.officer,
        expected_revision: c.revision,
        note: $("decision-note").value.trim(),
      };
      if (decision !== "APPROVE" && !body.note)
        throw new Error("Please enter a reason for this decision.");
      if (decision === "MODIFY") {
        body.actions = state.meta.actions
          .filter((a) => $(`action-${a.action}`).checked)
          .flatMap((a) => {
            const original = p.actions.filter((x) => x.action === a.action);
            return original.length
              ? original.map((x) => ({ action: x.action, params: x.params }))
              : [{ action: a.action, params: {} }];
          });
        body.suggest_update = $("suggest-update").checked;
      }
      await recorded(
        await api(`${casePath(c.case_id)}/decision`, body),
        decision === "MANUAL"
          ? "Manual handling started. Record an outcome to complete the case."
          : "Decision recorded. Customer outcome updated.",
      );
    },
  );
}
function rerankDialog() {
  const c = state.detail;
  const select = el(
    "select",
    { id: "new-band", class: "select-input" },
    Object.entries(bands).map(([band, label]) =>
      el(
        "option",
        { value: band, selected: band === c.priority.band },
        `${band} · ${label}`,
      ),
    ),
  );
  dialog(
    "Change case priority",
    [
      el(
        "p",
        {},
        "An override pins the new priority. Your name and reason will be recorded in the audit trail.",
      ),
      el("label", { for: "new-band", class: "field-label" }, "New priority"),
      select,
      ...textField(
        "Why does the priority need to change?",
        "rerank-reason",
        true,
      ),
    ],
    "Record priority change",
    async () => {
      const reason = $("rerank-reason").value.trim();
      if (!reason) throw new Error("Enter a reason for the priority change.");
      await recorded(
        await api(`${casePath(c.case_id)}/rerank`, {
          band: $("new-band").value,
          reason,
          officer: state.session.officer,
          expected_revision: c.revision,
        }),
        "Priority updated and reason recorded.",
      );
    },
  );
}
function completeDialog() {
  const c = state.detail;
  dialog(
    "Record the customer outcome",
    [
      el(
        "p",
        {},
        "This message appears on the customer’s status card. Explain what was done and what happens next.",
      ),
      ...textField("Customer outcome", "completion-note", true),
    ],
    "Complete case",
    async () => {
      const note = $("completion-note").value.trim();
      if (!note) throw new Error("Enter the customer outcome.");
      await recorded(
        await api(`${casePath(c.case_id)}/complete`, {
          note,
          officer: state.session.officer,
          expected_revision: c.revision,
        }),
        "Case completed. Customer outcome recorded.",
      );
    },
  );
}
function releaseDialog() {
  const c = state.detail;
  dialog(
    "Return this case to the team?",
    [
      el(
        "p",
        {},
        "Your claim will be released so another officer can take over. Existing evidence, notes and manual work stay on the case.",
      ),
      ...textField("Handoff note (optional)", "release-note"),
    ],
    "Release to shared queue",
    async () => {
      await recorded(
        await api(`${casePath(c.case_id)}/release`, {
          officer: state.session.officer,
          expected_revision: c.revision,
          note: $("release-note").value.trim(),
        }),
        "Case released to the shared queue.",
      );
    },
  );
}
async function nextCase() {
  await refresh();
  if (!state.online)
    throw new Error("Reconnect before starting another review.");
  const c = state.cases.find(
    (x) => openStatuses.has(x.status) && !ownedByOther(x),
  );
  if (c) await openCase(c.case_id);
  else {
    toast("No waiting cases. You’re all caught up.");
    await navigate("queue");
  }
}
function renderProtocols() {
  const query = $("protocol-search").value.toLowerCase();
  const rows = state.protocols.filter((p) =>
    `${p.title} ${p.issue_type} ${issue(p.issue_type)} ${human(p.harm_category)}`
      .toLowerCase()
      .includes(query),
  );
  $("protocol-cards").replaceChildren(
    ...rows.map((p) =>
      el(
        "article",
        { class: "protocol-card" },
        icon("book"),
        el("h2", {}, p.title),
        el("p", {}, issue(p.issue_type)),
        el(
          "div",
          { class: "protocol-meta" },
          el("span", {}, `Version ${p.version}`),
          el(
            "span",
            {},
            p.min_band ? `Minimum ${p.min_band}` : "Scored by evidence",
          ),
        ),
        button("View protocol", () => openProtocol(p.issue_type)),
      ),
    ),
  );
  if (!rows.length)
    $("protocol-cards").append(
      el("p", { class: "case-summary" }, "No protocols match your search."),
    );
}
async function openProtocol(type) {
  const p = await api(`/protocols/${encodeURIComponent(type)}`);
  const body = el(
    "div",
    { class: "protocol-detail" },
    el("p", {}, `Version ${p.version} · ${issue(p.issue_type)}`),
    el("h3", {}, "Required checks"),
    bullets(p.required_checks || []),
    el("h3", {}, "Procedure"),
    el(
      "ol",
      {},
      (p.steps || []).map((s) =>
        el("li", {}, el("strong", {}, `${s.who}: `), s.step),
      ),
    ),
    el("h3", {}, "Sources"),
    sourceLinks(p.sources || []),
  );
  if (p.change_log.length)
    body.append(
      el("h3", {}, "Approved changes"),
      bullets(p.change_log.map((x) => `v${x.version}: ${x.change} · ${x.by}`)),
      button("Roll back latest change", () => {
        $("action-dialog").close();
        dialog(
          "Roll back the latest protocol change?",
          [
            el(
              "p",
              {},
              `${p.title} · v${p.version}. This affects future proposals, not recorded case decisions.`,
            ),
            check(
              "I have reviewed the change history and intend to restore the previous version.",
              "confirm-rollback",
              true,
            ),
          ],
          "Roll back version",
          async () => {
            await api(`/protocols/${encodeURIComponent(type)}/rollback`, {
              owner: state.session.officer,
            });
            state.protocols = await api("/protocols");
            renderProtocols();
            toast("Previous protocol version restored.");
          },
        );
      }),
    );
  dialog(p.title, body, null, null);
}
async function loadSuggestions() {
  const result = await api("/suggestions");
  state.suggestions = result.suggestions;
  $("learning-threshold").textContent =
    `A change needs ${result.threshold} matching officer suggestions before a protocol owner can approve a new version.`;
  $("suggestion-dot").hidden = !result.suggestions.some(
    (s) => s.status === "READY_FOR_OWNER",
  );
  if (!result.suggestions.length) {
    $("suggestion-cards").replaceChildren(
      el(
        "div",
        { class: "panel empty-state" },
        el("div", { class: "empty-icon" }, icon("spark")),
        el("h3", {}, "Experience becomes better guidance"),
        el(
          "p",
          {},
          "When officers modify a plan or handle a case manually, their suggestions appear here for review.",
        ),
      ),
    );
    return;
  }
  $("suggestion-cards").replaceChildren(
    ...[...result.suggestions].reverse().map((s) => {
      const changes =
        s.kind === "MANUAL"
          ? "Officers recommend reviewing this procedure after manual handling."
          : `Add: ${s.change.add_actions.map(human).join(", ") || "no additions"}. Remove: ${s.change.remove_actions.map(human).join(", ") || "no removals"}.`;
      const action = el("div", { class: "suggestion-actions" });
      if (s.status === "READY_FOR_OWNER") {
        for (const verb of ["approve", "reject"])
          action.append(
            button(
              verb === "approve" ? "Review & approve" : "Reject",
              () => {
                dialog(
                  verb === "approve"
                    ? "Approve a new protocol version?"
                    : "Reject this suggestion?",
                  [
                    el(
                      "p",
                      {},
                      `${issue(s.issue_type)} · v${s.from_version} → v${s.proposed_version}`,
                    ),
                    el("p", {}, changes),
                    ...(verb === "reject"
                      ? textField(
                          "Reason for rejection",
                          "rejection-reason",
                          true,
                        )
                      : [
                          check(
                            "I have reviewed this protocol change and its effect on future proposals.",
                            "confirm-protocol",
                            true,
                          ),
                        ]),
                  ],
                  verb === "approve" ? "Approve version" : "Reject suggestion",
                  async () => {
                    const reason =
                      verb === "reject"
                        ? $("rejection-reason").value.trim()
                        : "";
                    if (verb === "reject" && !reason)
                      throw new Error("Enter a reason for the rejection.");
                    await api(
                      `/suggestions/${encodeURIComponent(s.id)}/${verb}`,
                      { owner: state.session.officer, reason },
                    );
                    await loadSuggestions();
                    toast(
                      verb === "approve"
                        ? "New protocol version approved."
                        : "Suggestion rejected.",
                    );
                  },
                );
              },
              verb === "approve" ? "button primary" : "button secondary",
            ),
          );
      }
      return el(
        "article",
        { class: "panel suggestion-card" },
        el(
          "div",
          {},
          el(
            "div",
            { class: "section-kicker" },
            `${s.id} · v${s.from_version} → v${s.proposed_version}`,
          ),
          el("h2", {}, issue(s.issue_type)),
          el("p", {}, changes),
          el(
            "div",
            { class: "suggestion-status" },
            `${s.count} / ${result.threshold} suggestions · ${human(s.status)}`,
          ),
          s.notes.length
            ? el(
                "details",
                {},
                el("summary", {}, "Officer notes"),
                bullets(s.notes),
              )
            : null,
        ),
        action,
      );
    }),
  );
}

async function loadInsights() {
  const ticket = ++state.insightVersion;
  try {
    const data = await api("/workspace/insights");
    if (ticket !== state.insightVersion || state.view !== "insights") return;
    const focused = document.activeElement?.dataset.insightKey;
    $("insights-content").replaceChildren(visuals.insights(data));
    if (focused)
      [...$("insights-content").querySelectorAll("[data-insight-key]")]
        .find((b) => b.dataset.insightKey === focused)
        ?.focus({ preventScroll: true });
    online(true);
  } catch (error) {
    if (ticket !== state.insightVersion || state.view !== "insights") return;
    online(false);
    $("connection-message").textContent =
      `Could not update insights. ${error.message} Any displayed charts may be out of date.`;
    throw error;
  }
}
async function filterFromInsight(filters, label) {
  await navigate(
    filters.stage === "done"
      ? "completed"
      : ["review", "manual"].includes(filters.stage)
        ? "review"
        : "queue",
  );
  state.drilldown = { ...filters };
  if (filters.band) {
    state.band = filters.band;
    $("band-filter").value = filters.band;
  }
  $("insight-filter-label").textContent = `From insights · ${label}`;
  $("insight-filter").hidden = false;
  await refilter();
  $("main").focus({ preventScroll: true });
}
function handoffDialog() {
  const brief = visuals.handoff(state.detail);
  const field = el("textarea", {
    class: "text-area handoff-text",
    readonly: true,
    "aria-label": "Handoff brief",
  });
  field.value = brief;
  const copy = button("Copy brief", async () => {
    try {
      await navigator.clipboard.writeText(brief);
      toast(
        "Handoff brief copied. Share only through an approved staff channel.",
      );
    } catch {
      field.focus();
      field.select();
      toast(
        "Clipboard unavailable. The brief is selected for you to copy.",
        true,
      );
    }
  });
  dialog(
    "Ready for the next officer",
    [
      info("Contains customer information. Share only with authorised staff."),
      field,
      copy,
    ],
    null,
    null,
  );
}
$("refresh-insights").addEventListener("click", () => run(refresh));
$("clear-insight-filter").addEventListener("click", () =>
  run(async () => {
    state.drilldown = null;
    state.band = "all";
    $("band-filter").value = "all";
    $("insight-filter").hidden = true;
    await refilter();
  }),
);

document
  .querySelectorAll("[data-view]")
  .forEach((b) =>
    b.addEventListener("click", () => run(() => navigate(b.dataset.view))),
  );
document.querySelectorAll("[data-filter]").forEach((b) =>
  b.addEventListener("click", () => {
    state.filter = b.dataset.filter;
    updateFilters();
    run(refilter);
  }),
);
$("search").addEventListener("input", () => {
  state.query = $("search").value;
  run(refilter);
});
$("band-filter").addEventListener("change", () => {
  state.band = $("band-filter").value;
  if (state.drilldown?.band) {
    state.drilldown = null;
    $("insight-filter").hidden = true;
  }
  run(refilter);
});
$("protocol-search").addEventListener("input", renderProtocols);
$("refresh").addEventListener("click", () => run(refresh));
$("retry").addEventListener("click", () => run(init));
$("next-case").addEventListener("click", () => run(nextCase));
$("load-demo").addEventListener("click", () =>
  dialog(
    "Add synthetic sample cases?",
    [
      el(
        "p",
        {},
        "Add five example customers to explore the queue and review flow. Existing cases and decisions are preserved. Each example is only added once.",
      ),
      info(
        "All accounts, transactions and actions in this prototype are simulated.",
      ),
    ],
    "Add sample cases",
    async () => {
      const result = await api("/demo/seed", {});
      await refresh();
      toast(`${result.added} sample cases added. Existing work preserved.`);
    },
  ),
);
function closeDialog() {
  if (!state.dialogBusy) $("action-dialog").close();
}
$("action-dialog").addEventListener("close", () => run(refresh));
$("dialog-close").addEventListener("click", closeDialog);
$("dialog-cancel").addEventListener("click", closeDialog);
$("action-dialog").addEventListener("cancel", (e) => {
  if (state.dialogBusy) e.preventDefault();
});
$("action-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (
    state.dialogBusy ||
    !dialogSubmit ||
    !$("dialog-stale").hidden ||
    !$("action-form").reportValidity()
  )
    return;
  state.dialogBusy = true;
  $("dialog-submit").disabled = true;
  $("dialog-close").disabled = true;
  $("dialog-cancel").disabled = true;
  $("dialog-error").hidden = true;
  try {
    await dialogSubmit();
    $("action-dialog").close();
  } catch (error) {
    $("dialog-error").textContent = error.message;
    $("dialog-error").hidden = false;
  } finally {
    state.dialogBusy = false;
    $("dialog-submit").disabled = !$("dialog-stale").hidden;
    $("dialog-close").disabled = false;
    $("dialog-cancel").disabled = false;
  }
});
$("menu-toggle").addEventListener("click", () => {
  const opened = !$("sidebar").classList.contains("open");
  setMenu(opened);
  if (opened) $("sidebar").querySelector(".nav-item").focus();
});
$("nav-backdrop").addEventListener("click", () => setMenu(false, true));
smallScreen.addEventListener("change", () => setMenu(false));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && $("sidebar").classList.contains("open"))
    setMenu(false, true);
  if (
    e.key === "/" &&
    !e.ctrlKey &&
    !e.metaKey &&
    !e.altKey &&
    !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName) &&
    !$("action-dialog").open &&
    !$("list-view").hidden
  ) {
    e.preventDefault();
    $("search").focus();
  }
});
document.addEventListener("click", (e) => {
  if (
    !$("sidebar").contains(e.target) &&
    !$("menu-toggle").contains(e.target)
  ) {
    setMenu(false);
  }
});
async function init() {
  try {
    [state.session, state.meta] = await Promise.all([
      api("/workspace/session"),
      api("/meta"),
    ]);
    $("officer-name").textContent = state.session.officer;
    $("demo-officer-control").hidden = !state.session.demo;
    $("demo-officer-select").replaceChildren(
      ...state.session.available_officers.map((name) =>
        el(
          "option",
          { value: name, selected: name === state.session.officer },
          `Demo: ${name}`,
        ),
      ),
    );
    $("officer-avatar").textContent = initials(state.session.officer);
    $("access-label").textContent = state.session.authenticated
      ? "Authenticated staff session"
      : "Local demo session";
    $("load-demo").hidden = !state.session.demo || state.view !== "queue";
    $("load-demo").disabled = false;
    await refresh();
    connectWorkspaceEvents();
  } catch (error) {
    online(false);
    $("connection-message").textContent =
      `Could not start your workspace. ${error.message}`;
    $("load-demo").disabled = true;
    $("next-case").disabled = true;
  }
}
$("today").textContent = new Intl.DateTimeFormat("en-AU", {
  weekday: "long",
  day: "numeric",
  month: "long",
  timeZone: "Australia/Brisbane",
})
  .format(new Date())
  .toUpperCase();
setMenu(false);
function connectWorkspaceEvents() {
  if (state.eventSource) state.eventSource.close();
  const source = new EventSource("/workspace/events");
  state.eventSource = source;
  source.onopen = () => {
    state.liveConnected = true;
    online(state.online);
  };
  source.onerror = () => {
    state.liveConnected = false;
    online(state.online);
  };
  source.addEventListener("workspace", () => {
    if (!document.hidden && state.session) run(refresh);
  });
}
$("demo-officer-select").addEventListener("change", () =>
  run(async () => {
    state.demoOfficer = $("demo-officer-select").value;
    sessionStorage.setItem("beacon-demo-officer", state.demoOfficer);
    ++state.selectionVersion;
    await init();
    if (state.view === "detail" && state.detail) renderDetail();
  }),
);
$("refresh-intake").addEventListener("click", () => run(refresh));
$("live-intake-shortcut").addEventListener("click", () =>
  run(() => navigate("intake")),
);
window.addEventListener("pagehide", () => state.eventSource?.close());
window.addEventListener("pageshow", (event) => {
  if (event.persisted && state.session) connectWorkspaceEvents();
});
setInterval(() => {
  if (
    !document.hidden &&
    state.session &&
    Date.now() - state.lastRefresh >= (state.liveConnected ? 10000 : 2000)
  )
    run(refresh);
}, 2000);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && state.session) run(refresh);
});
const visuals = createVisuals({
  el,
  icon,
  button,
  badge,
  human,
  issue,
  time,
  openCase,
  filterFromInsight,
});
const intakeRenderer = createIntake({
  el,
  icon,
  button,
  avatar,
  human,
  issue,
  time,
  openCase,
});
window.addEventListener("message", (event) => {
  if (
    window.parent === window ||
    event.source !== window.parent ||
    event.origin !== location.origin
  )
    return;
  if (event.data?.type === "intake") {
    run(() => navigate("intake"));
    return;
  }
  if (
    event.data?.type !== "select" ||
    typeof event.data.id !== "string" ||
    event.data.id.length > 200
  )
    return;
  run(async () => {
    await navigate("queue");
    await selectCase(event.data.id, true);
  });
});
run(init);
