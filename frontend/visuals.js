/* Original, self-hosted visual components. Charts disclose their scope and link to cases. */
export function createVisuals({
  el,
  icon,
  button,
  badge,
  human,
  issue,
  time,
  openCase,
  filterFromInsight,
}) {
  const colours = {
    P1: "var(--p1)",
    P2: "#a96224",
    P3: "#456da0",
    P4: "#587568",
  };
  const money = (amount, currency = "AUD") =>
    new Intl.NumberFormat("en-AU", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(amount);
  const svg = (tag, attrs = {}, ...children) => {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attrs))
      node.setAttribute(key, String(value));
    for (const child of children.flat())
      node.append(
        child instanceof Node ? child : document.createTextNode(String(child)),
      );
    return node;
  };
  function bar(value, total, kind = "wine") {
    return svg(
      "svg",
      {
        viewBox: "0 0 240 8",
        class: `data-bar ${kind}`,
        "aria-hidden": "true",
        preserveAspectRatio: "none",
      },
      svg("rect", {
        x: 0,
        y: 0,
        width: 240,
        height: 8,
        rx: 4,
        class: "bar-track",
      }),
      svg("rect", {
        x: 0,
        y: 0,
        width: total ? Math.max(0, Math.min(240, (240 * value) / total)) : 0,
        height: 8,
        rx: 4,
        class: "bar-fill",
      }),
    );
  }
  function chartRow(label, count, total, filters, key, kind = "wine") {
    const row = button(
      "",
      () => filterFromInsight(filters, label),
      "chart-row",
    );
    row.dataset.insightKey = key;
    row.setAttribute(
      "aria-label",
      `Show ${label}: ${count} ${count === 1 ? "case" : "cases"}`,
    );
    row.disabled = count === 0;
    row.append(
      el(
        "span",
        { class: "chart-row-heading" },
        el("span", {}, label),
        el("strong", {}, count),
      ),
      bar(count, total, kind),
    );
    return row;
  }
  function panel(title, description, ...content) {
    return el(
      "section",
      { class: "panel insight-panel" },
      el("h2", {}, title),
      el("p", { class: "chart-description" }, description),
      ...content,
    );
  }
  function donut(data) {
    const total = data.active,
      circumference = 2 * Math.PI * 61;
    const graphic = svg(
      "svg",
      {
        viewBox: "0 0 170 170",
        class: "priority-donut",
        "aria-hidden": "true",
      },
      svg("circle", {
        cx: 85,
        cy: 85,
        r: 61,
        fill: "none",
        stroke: "var(--surface)",
        "stroke-width": 17,
      }),
    );
    let offset = 0;
    for (const item of data.priority) {
      const length = total ? (circumference * item.count) / total : 0;
      if (length)
        graphic.append(
          svg("circle", {
            cx: 85,
            cy: 85,
            r: 61,
            fill: "none",
            stroke: colours[item.band],
            "stroke-width": 17,
            "stroke-dasharray": `${length} ${circumference - length}`,
            "stroke-dashoffset": -offset,
            transform: "rotate(-90 85 85)",
          }),
        );
      offset += length;
    }
    graphic.append(
      svg(
        "text",
        { x: 85, y: 83, "text-anchor": "middle", class: "donut-value" },
        total,
      ),
      svg(
        "text",
        { x: 85, y: 104, "text-anchor": "middle", class: "donut-label" },
        "active cases",
      ),
    );
    const legend = el(
      "div",
      { class: "donut-legend" },
      data.priority.map((item) => {
        const b = button(
          "",
          () => filterFromInsight({ band: item.band }, `${item.band} priority`),
          "legend-button",
        );
        b.dataset.insightKey = `band-${item.band}`;
        b.setAttribute(
          "aria-label",
          `Show ${item.band} priority: ${item.count} cases`,
        );
        b.disabled = item.count === 0;
        b.append(
          badge(item.band),
          el("strong", {}, item.count),
          el(
            "span",
            { class: "legend-percent" },
            `${total ? Math.round((item.count / total) * 100) : 0}%`,
          ),
        );
        return b;
      }),
    );
    return el("div", { class: "donut-layout" }, graphic, legend);
  }
  function metric(label, value, description, kind = "") {
    return el(
      "article",
      { class: `insight-metric ${kind}` },
      el("span", { class: "metric-label" }, label),
      el("strong", { class: "metric-value" }, value),
      el("span", { class: "metric-description" }, description),
    );
  }
  function insights(data) {
    const linked = data.coverage;
    const root = el(
      "div",
      { class: "insight-dashboard" },
      el(
        "div",
        { class: "insights-scope" },
        el(
          "span",
          {},
          icon("chart"),
          `Current saved workspace · ${data.total} cases`,
        ),
        el("span", {}, `Updated ${time(data.generated_at)} · Brisbane`),
      ),
      !data.total
        ? el(
            "div",
            { class: "info-note" },
            icon("info"),
            el(
              "span",
              {},
              "No saved cases yet. Load sample cases from the priority queue to explore these visuals.",
            ),
          )
        : null,
      el(
        "div",
        { class: "insight-metrics" },
        metric(
          "Active care needs",
          data.active,
          "Waiting, in review or handled manually",
        ),
        metric(
          "Payments under review",
          money(linked.linked_outgoing_amount, data.currency),
          `${data.currency} · ${linked.linked_payments} unique linked outgoings · not confirmed losses`,
        ),
        metric(
          "Response watch",
          data.response_watch.count,
          "Unpicked P1 / P2 cases beyond project targets",
          "attention",
        ),
        metric(
          "Language support",
          linked.language_support,
          "Active cases with a non-English language",
        ),
      ),
    );
    const priority = panel(
      "Urgency at a glance",
      "Active cases by priority. Select a band to see the customers.",
      donut(data),
    );
    const mix = panel(
      "What customers need",
      "Issue mix across active cases. Select an issue to narrow your queue.",
      el(
        "div",
        { class: "chart-rows" },
        data.issues.length
          ? data.issues
              .slice(0, 5)
              .map((item) =>
                chartRow(
                  issue(item.issue_type),
                  item.count,
                  data.active,
                  { issue: item.issue_type },
                  `issue-${item.issue_type}`,
                ),
              )
          : el("p", { class: "chart-empty" }, "No active issues to display."),
      ),
    );
    if (data.issues.length > 5)
      mix.append(
        el(
          "p",
          { class: "chart-footnote" },
          `Showing the five most common of ${data.issues.length} issue types.`,
        ),
      );
    root.append(el("div", { class: "insight-two-column" }, priority, mix));
    const journey = panel(
      "Where the work sits",
      "Each saved case appears in one current stage. Select a stage to follow up.",
      el(
        "div",
        { class: "care-flow" },
        data.stages.map((item, index) => {
          const b = button(
            "",
            () => filterFromInsight({ stage: item.key }, item.label),
            "care-flow-step",
          );
          b.dataset.insightKey = `stage-${item.key}`;
          b.setAttribute(
            "aria-label",
            `Show ${item.label}: ${item.count} cases`,
          );
          b.disabled = item.count === 0;
          b.append(
            el(
              "span",
              { class: "flow-step-index" },
              String(index + 1).padStart(2, "0"),
            ),
            el("strong", {}, item.count),
            el("span", {}, item.label),
          );
          return b;
        }),
      ),
    );
    root.append(journey);
    const ages = panel(
      "Open case age",
      "Time since creation for all active cases, including those already in review.",
      el(
        "div",
        { class: "chart-rows" },
        data.age.map((item) =>
          chartRow(
            item.label,
            item.count,
            data.active,
            { age: item.key },
            `age-${item.key}`,
            "blue",
          ),
        ),
      ),
    );
    const decided = data.decisions.reduce((n, item) => n + item.count, 0);
    const decisions = panel(
      "How officers decide",
      `${decided} recorded decisions across all saved cases. Manual decisions include work still in progress.`,
      el(
        "div",
        { class: "decision-chart" },
        data.decisions.map((item) =>
          el(
            "div",
            { class: "decision-column" },
            el("strong", {}, item.count),
            el("meter", {
              value: item.count,
              min: 0,
              max: Math.max(1, decided),
              "aria-label": `${human(item.decision)} decisions: ${item.count} of ${decided}`,
            }),
            el(
              "span",
              {},
              { APPROVE: "Approved", MODIFY: "Modified", MANUAL: "Manual" }[
                item.decision
              ],
            ),
          ),
        ),
      ),
      el(
        "p",
        { class: "chart-footnote" },
        "A recorded decision is not a measure of recovery, accuracy or customer satisfaction.",
      ),
    );
    root.append(el("div", { class: "insight-two-column" }, ages, decisions));
    const evidence = panel(
      "A grounded starting point",
      "Account signals support a review. Their absence does not establish that a case is safe.",
      el(
        "div",
        { class: "chart-rows" },
        chartRow(
          "With verified signals",
          linked.with_signals,
          data.active,
          { evidence: "with" },
          "signals-with",
          "green",
        ),
        chartRow(
          "Without verified signals",
          linked.without_signals,
          data.active,
          { evidence: "without" },
          "signals-without",
          "neutral",
        ),
      ),
      el(
        "div",
        { class: "coverage-links" },
        chartRow(
          "Language support",
          linked.language_support,
          data.active,
          { language: true },
          "language",
          "blue",
        ),
        el(
          "p",
          { class: "chart-footnote" },
          `${linked.repeat_contacts} additional contacts across active cases. Repeated contacts stay on the same card.`,
        ),
      ),
    );
    const watch = panel(
      "Response watch",
      "Demo targets: P1 under 2 min; P2 under 30 min to first officer pickup. Uses current priority and age since creation. These are project targets, not bank SLAs.",
      data.response_watch.cases.length
        ? el(
            "div",
            { class: "watch-list" },
            data.response_watch.cases.map((c) => {
              const b = button("", () => openCase(c.case_id), "watch-case");
              b.dataset.insightKey = `watch-${c.case_id}`;
              b.append(
                el(
                  "span",
                  {},
                  badge(c.band),
                  el("strong", {}, c.customer_name || c.case_id),
                ),
                el(
                  "span",
                  {},
                  `${c.age_minutes} min · ${c.target_minutes} min target`,
                  icon("arrow"),
                ),
              );
              return b;
            }),
          )
        : el(
            "div",
            { class: "watch-clear" },
            icon("shield"),
            el("strong", {}, "No unpicked urgent cases beyond target"),
            el(
              "p",
              {},
              "Picked-up and manual cases remain visible in the review workspace.",
            ),
          ),
    );
    if (data.response_watch.count > 5)
      watch.append(
        el(
          "p",
          { class: "chart-footnote" },
          `Showing five of ${data.response_watch.count} cases. Priority takes precedence over age.`,
        ),
      );
    root.append(
      el("div", { class: "insight-two-column" }, evidence, watch),
      el(
        "p",
        { class: "insights-method" },
        icon("info"),
        `Source: saved case records, their audit state and owned linked transactions. Account evidence uses ${time(data.evidence_as_of)} (Brisbane); case age uses the live clock. No forecasts or estimated losses are shown.`,
      ),
    );
    return root;
  }
  function score(c) {
    const parts = [
      ["harm", "Harm", 60],
      ["time_to_harm", "Time to harm", 20],
      ["signals", "Account signals", 20],
      ["care", "Care needs", 10],
      ["waiting", "Waiting", 10],
    ];
    const subtotal = parts.reduce(
      (n, [key]) => n + (c.priority.parts[key] || 0),
      0,
    );
    const adjustment = c.priority.score - subtotal;
    return el(
      "section",
      { class: "score-explainer", "aria-label": "Priority score breakdown" },
      el(
        "div",
        { class: "score-heading" },
        el(
          "div",
          {},
          el(
            "span",
            { class: "section-kicker" },
            "THE POINTS BEHIND THE PRIORITY",
          ),
          el("h2", {}, "A score you can explain"),
        ),
        el(
          "strong",
          { class: "score-total" },
          c.priority.score,
          el("small", {}, " / 100"),
        ),
      ),
      el(
        "div",
        { class: "score-rows" },
        parts.map(([key, label, max]) =>
          el(
            "div",
            { class: "score-row" },
            el("span", {}, label),
            el("meter", {
              min: 0,
              max,
              value: c.priority.parts[key] || 0,
              "aria-label": `${label}: ${c.priority.parts[key] || 0} out of ${max}`,
            }),
            el("strong", {}, c.priority.parts[key] || 0),
          ),
        ),
      ),
      el(
        "p",
        { class: "chart-footnote" },
        `Component subtotal ${subtotal}. ${adjustment ? `Caps, floors or officer override: ${adjustment > 0 ? "+" : ""}${adjustment}. ` : "No net adjustment. "}Final score ${c.priority.score}.`,
      ),
      c.priority.gates.length
        ? el(
            "div",
            { class: "tag-list" },
            c.priority.gates.map((g) =>
              el("span", { class: "signal-tag" }, human(g)),
            ),
          )
        : null,
      el(
        "p",
        { class: "chart-footnote" },
        "These are rule-based points, not an AI confidence percentage. The backend applies caps, safety floors and officer overrides.",
      ),
    );
  }
  function context(data) {
    if (!data.found)
      return el(
        "div",
        { class: "context-empty" },
        icon("info"),
        el("h2", {}, "Customer records are unavailable"),
        el(
          "p",
          { class: "case-summary" },
          "This case has no matching customer in the synthetic dataset. No account state has been inferred.",
        ),
      );
    const p = data.protection;
    const root = el(
      "div",
      { class: "customer-context" },
      el("h2", {}, "The account behind the case"),
      el(
        "p",
        { class: "chart-description" },
        `Synthetic account history as of ${time(data.evidence_as_of)} (Brisbane). Mock protection state reflects current saved actions.`,
      ),
      el(
        "div",
        { class: "protection-grid" },
        el(
          "div",
          {},
          icon("shield"),
          el("span", {}, "SafeBlock · account record"),
          el("strong", {}, p.safeblock_verified ? "On" : "Off"),
        ),
        el(
          "div",
          {},
          icon("shield"),
          el("span", {}, "Card block · account record"),
          el(
            "strong",
            {},
            p.card_blocked_verified === null
              ? "No existing card"
              : p.card_blocked_verified
                ? "Blocked"
                : "Not blocked",
          ),
        ),
      ),
    );
    if (p.card_locked_reported || p.safeblock_reported)
      root.append(
        el(
          "div",
          { class: "context-reported" },
          icon("info"),
          `Customer report: ${[p.card_locked_reported ? "card locked" : null, p.safeblock_reported ? "SafeBlock activated" : null].filter(Boolean).join("; ")}. Reported state is separate from verified account state.`,
        ),
      );
    root.append(
      el("h3", {}, "Accounts on file"),
      el(
        "div",
        { class: "account-tiles" },
        data.accounts.map((a) =>
          el(
            "article",
            { class: "account-tile" },
            el("span", {}, a.type),
            el("strong", {}, money(a.balance, data.currency)),
            el("small", {}, `Account ending ${a.mask.replace(/^\.+/, "")}`),
          ),
        ),
      ),
    );
    for (const card of data.cards.filter((c) => c.kind === "replacement")) {
      const steps = [
        ["Ordered", card.ordered],
        ["Dispatched", card.dispatched],
        ["Expected", card.expected],
      ];
      root.append(
        el("h3", {}, `${card.card} · delivery`),
        el(
          "div",
          { class: "delivery-card" },
          el("p", {}, card.status),
          el(
            "div",
            { class: "delivery-track" },
            steps.map(([label, date], index) =>
              el(
                "div",
                { class: `delivery-step ${index === 2 ? "expected" : ""}` },
                icon(
                  index === 2 ||
                    !date ||
                    new Date(`${date}T00:00:00Z`) >
                      new Date(data.evidence_as_of)
                    ? "clock"
                    : "check",
                ),
                el("strong", {}, label),
                el(
                  "span",
                  {},
                  date
                    ? new Intl.DateTimeFormat("en-AU", {
                        day: "numeric",
                        month: "short",
                        timeZone: "Australia/Brisbane",
                      }).format(new Date(`${date}T12:00:00Z`))
                    : "Not recorded",
                ),
              ),
            ),
          ),
          el(
            "small",
            {},
            `${card.carrier || "Carrier not recorded"} · ${card.mask}. An expected date is not confirmation of delivery.`,
          ),
        ),
      );
    }
    root.append(
      el("h3", {}, "Transactions in context"),
      el(
        "p",
        { class: "chart-description" },
        "Linked payments appear first. Other owned transactions from the preceding 30-day evidence window are available below.",
      ),
    );
    if (data.ignored_links)
      root.append(
        el(
          "p",
          { class: "inline-warning" },
          `${data.ignored_links} unknown or out-of-scope transaction links were excluded.`,
        ),
      );
    const max = Math.max(
      1,
      ...data.transactions.map((t) => Math.abs(t.amount)),
    );
    const txRow = (t) =>
      el(
        "article",
        { class: `transaction-row ${t.linked ? "linked" : ""}` },
        el(
          "div",
          { class: "transaction-meta" },
          el("strong", {}, t.payee),
          el(
            "span",
            {},
            `${t.id} · ${time(t.date)}${t.after_evidence_clock ? " · after evidence clock" : ""}`,
          ),
          el("span", {}, t.linked ? "Linked to this case" : human(t.type)),
        ),
        el(
          "div",
          { class: "transaction-amount" },
          el("strong", {}, money(t.amount, data.currency)),
          bar(Math.abs(t.amount), max, t.amount < 0 ? "wine" : "green"),
        ),
      );
    const linked = data.transactions.filter((t) => t.linked),
      recent = data.transactions.filter((t) => !t.linked);
    root.append(
      el(
        "div",
        { class: "transaction-list" },
        linked.length
          ? linked.map(txRow)
          : el(
              "p",
              { class: "case-summary" },
              "No owned payments are linked to this case.",
            ),
      ),
    );
    if (recent.length)
      root.append(
        el(
          "details",
          { class: "recent-transactions" },
          el(
            "summary",
            {},
            `Other recent owned transactions (${recent.length})`,
          ),
          el("div", { class: "transaction-list" }, recent.map(txRow)),
        ),
      );
    root.append(
      el("h3", {}, "Security & access timeline"),
      data.security_events.length
        ? el(
            "ol",
            { class: "security-timeline" },
            data.security_events.map((e) =>
              el(
                "li",
                {},
                icon("shield"),
                el(
                  "div",
                  {},
                  el("strong", {}, human(e.type)),
                  el("p", {}, e.detail),
                  el("small", {}, time(e.at)),
                ),
              ),
            ),
          )
        : el(
            "p",
            { class: "case-summary" },
            "No security or lockout events recorded in the 30-day evidence window.",
          ),
    );
    return root;
  }
  function handoff(c) {
    const p = c.proposed_solution;
    return [
      `WESTPAC SPEEDQ · SIMULATED STAFF HANDOFF`,
      `${c.case_id} · ${c.customer_name || c.customer_id}`,
      `${issue(c.issue_type)} · ${c.priority.band} · ${c.priority.score}/100`,
      `Status: ${c.card_status.label} · Language: ${c.language_label || "English"}`,
      "",
      `Customer need: ${c.summary_en || "Not supplied"}`,
      `Verified signals: ${c.priority.signals.map(human).join("; ") || "None recorded"}`,
      `Conversation cues: ${c.priority.caller_signals.map(human).join("; ") || "None recorded"}`,
      "",
      `Plan · ${p.protocol.title} v${p.protocol.version}`,
      ...p.actions.map(
        (a) =>
          `• ${a.label}${Object.keys(a.params).length ? " · " + Object.values(a.params).join(", ") : ""}`,
      ),
      ...p.already_done.map((text) => `Already recorded/reported: ${text}`),
      ...p.required_checks.map((text) => `Check: ${text}`),
      ...p.officer_tasks.map((text) => `Officer task: ${text}`),
      ...(c.outcome ? ["", `Recorded outcome: ${c.outcome.message}`] : []),
      "",
      "Synthetic data only. Share with authorised staff. The full audit trail remains on the case.",
    ].join("\n");
  }
  return { insights, score, context, handoff };
}
