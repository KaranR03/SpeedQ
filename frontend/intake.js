/* A read-only view of durable intake drafts; no score is invented for an unfinished card. */
export function createIntake({
  el,
  icon,
  button,
  avatar,
  human,
  issue,
  time,
  openCase,
}) {
  let previous = new Map();
  const money = (n) =>
    new Intl.NumberFormat("en-AU", {
      style: "currency",
      currency: "AUD",
    }).format(Math.abs(n));
  return function render(result) {
    const next = new Map();
    const root = el(
      "div",
      { class: "live-intake" },
      el(
        "div",
        { class: "intake-summary" },
        el(
          "strong",
          {},
          `${result.active_count} ${result.active_count === 1 ? "card is" : "cards are"} taking shape`,
        ),
        el(
          "span",
          {},
          "Active drafts and the five most recent confirmed handoffs",
        ),
      ),
    );
    if (!result.drafts.length)
      root.append(
        el(
          "div",
          { class: "panel intake-empty" },
          el("div", { class: "empty-icon" }, icon("spark")),
          el("h2", {}, "The next story starts here"),
          el(
            "p",
            {},
            "Start a customer conversation in the side-by-side demo. The card will appear here as facts are collected, before it is confirmed or ranked.",
          ),
        ),
      );
    const cards = result.drafts.map((d) => {
      next.set(d.draft_id, d);
      const old = previous.get(d.draft_id),
        confirmed = d.status === "SUBMITTED";
      const phases = {
        LISTENING: "Listening to the customer",
        CHECKING: "Checking the records",
        CONFIRMING: "Waiting for customer confirmation",
        CONFIRMED: "Customer confirmed",
      };
      const index = confirmed
        ? 3
        : ({ LISTENING: 0, CHECKING: 1, CONFIRMING: 2 }[d.phase] ?? 0);
      const card = el(
        "article",
        {
          class: `intake-card ${confirmed ? "confirmed" : ""}`,
          "data-draft-id": d.draft_id,
          "aria-label": `Incoming card for ${d.customer_name}`,
        },
        el(
          "div",
          { class: "intake-card-heading" },
          el(
            "div",
            { class: "customer-heading" },
            avatar(d.customer_name, d.customer_id),
            el(
              "div",
              {},
              el("h2", {}, d.customer_name),
              el("p", {}, `${d.customer_id} · ${d.language_label}`),
            ),
          ),
          el(
            "span",
            { class: `draft-status ${confirmed ? "confirmed" : ""}` },
            confirmed ? "Confirmed" : "Draft · not queued",
          ),
        ),
        el(
          "div",
          { class: "draft-phase" },
          icon(confirmed ? "check" : "spark"),
          el("strong", {}, phases[d.phase] || "Gathering details"),
        ),
        el(
          "ol",
          { class: "draft-steps", "aria-label": "Card creation progress" },
          ["Listening", "Record checks", "Confirmation"].map((label, i) =>
            el(
              "li",
              {
                class: i < index ? "done" : i === index ? "current" : "",
                ...(i === index ? { "aria-current": "step" } : {}),
              },
              el("span", {}, i < index ? "✓" : i + 1),
              label,
            ),
          ),
        ),
        el(
          "div",
          { class: "draft-need" },
          el("span", { class: "section-kicker" }, "The customer’s need"),
          el(
            "h3",
            {},
            d.issue_type ? issue(d.issue_type) : "Issue still being understood",
          ),
          el(
            "p",
            {
              class: `draft-summary ${old && old.summary_en !== d.summary_en ? "field-fresh" : ""}`,
            },
            d.summary_en ||
              "Waiting for the customer to describe what happened…",
          ),
        ),
      );
      if (d.summary_customer_lang)
        card.append(
          el(
            "details",
            {},
            el("summary", {}, "Original language summary"),
            el("p", { class: "case-summary" }, d.summary_customer_lang),
          ),
        );
      card.append(
        el(
          "div",
          { class: "draft-facts" },
          el("h3", {}, "Matched account records"),
          d.linked_payments.length
            ? el(
                "ul",
                {},
                d.linked_payments.map((tx) =>
                  el(
                    "li",
                    {},
                    icon("check"),
                    el(
                      "span",
                      {},
                      el("strong", {}, `${money(tx.amount)} · ${tx.payee}`),
                      el("small", {}, `${tx.id} · ${time(tx.date)}`),
                    ),
                  ),
                ),
              )
            : el(
                "p",
                { class: "draft-muted" },
                "No payment record linked yet.",
              ),
          Object.keys(d.verified_signals).length
            ? el(
                "div",
                { class: "draft-signals" },
                Object.entries(d.verified_signals).map(([key, text]) =>
                  el(
                    "div",
                    {},
                    icon("shield"),
                    el(
                      "span",
                      {},
                      el("strong", {}, human(key)),
                      el("small", {}, text),
                    ),
                  ),
                ),
              )
            : el(
                "p",
                { class: "draft-muted" },
                "No verified account signals recorded. This is not a safety assessment.",
              ),
        ),
      );
      const reported = [
        ...(d.risk_signals || []).map(human),
        ...(d.card_locked ? ["Card lock reported"] : []),
        ...(d.safeblock_activated ? ["SafeBlock activation reported"] : []),
      ];
      if (reported.length)
        card.append(
          el(
            "div",
            { class: "draft-reported" },
            el("h3", {}, "Reported in the conversation"),
            el(
              "div",
              { class: "tag-list" },
              reported.map((text) => el("span", { class: "signal-tag" }, text)),
            ),
            el(
              "small",
              {},
              "Reported actions and cues remain separate from verified account state.",
            ),
          ),
        );
      if (confirmed)
        card.append(
          el(
            "div",
            { class: "draft-handoff" },
            icon("check"),
            el(
              "span",
              {},
              `${d.case_reference} · ${d.completed_by ? `Completed by ${d.completed_by}` : d.assigned_officer ? `With ${d.assigned_officer}` : "Ranked · shared queue"}`,
            ),
            button(
              d.case_stage === "DONE"
                ? "View outcome"
                : "Review confirmed case",
              () => openCase(d.case_reference),
              "button primary",
            ),
          ),
        );
      else
        card.append(
          el(
            "div",
            { class: "draft-wait" },
            icon("person"),
            el(
              "span",
              {},
              "Waiting for the customer. Officers cannot approve an unfinished card.",
            ),
          ),
        );
      card.append(
        el(
          "div",
          { class: "draft-updated" },
          `Updated ${time(d.updated_at)} · revision ${d.revision}`,
        ),
      );
      return card;
    });
    root.append(el("div", { class: "intake-grid" }, cards));
    if (result.truncated)
      root.append(
        el(
          "p",
          { class: "chart-footnote" },
          "Showing the 20 most recently updated active drafts.",
        ),
      );
    previous = next;
    return root;
  };
}
