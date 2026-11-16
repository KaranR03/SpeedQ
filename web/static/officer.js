// Officer dashboard: live priority list, the case with its score receipt, Prorio's proposal, three "whose view" lenses,
// Approve / Modify / Manual, re-rank, and the Protocol Database learning loop. Talks only to this server's API.
import { $, api, h, ISSUE_TEXT, ago, toast, tracker } from "./dom.js";

const OPEN = new Set(["QUEUED", "AWAITING_CUSTOMER_CONFIRM", "IN_REVIEW"]);
const S = {
  meta: null, queue: [], sel: null, c: null, key: "", lens: "officer", modify: false, picked: new Set(),
  seen: new Set(), first: true, tab: "queue", lastCorr: {}, lastScore: {}, auditOpen: false, busy: false,
};

const store = { get: (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode: fine */ } } };
const officer = () => ($("#officer").value.trim() || "officer").slice(0, 40);

// ---------- score receipt helpers ----------
function tag(r) {
  const sig = Object.values(S.meta?.signal_labels || {});
  if (r.startsWith("Harm:")) return ["Issue type", "info"];
  if (r.startsWith("Time to harm: money may")) return ["Verified", "ok"];
  if (r.startsWith("Time to harm")) return r.includes("customer") ? ["Said", "said"] : ["Issue type", "info"];
  if (r.startsWith("Care needs")) return ["Said", "said"];
  if (r.startsWith("Gate")) return ["Rule", "warn"];
  if (r.startsWith("Waiting")) return ["Clock", ""];
  if (sig.some((l) => r.startsWith(l)) || r.startsWith(S.meta?.first_seen_label || "~")) return ["Verified", "ok"];
  return ["Rule", "warn"];
}
const pts = (r) => (r.match(/\(\+(\d+)\)\s*$/) || [])[1];
const strip = (r) => r.replace(/\s*\(\+\d+\)\s*$/, "");
const isCap = (r) => !pts(r) && !r.startsWith("Gate") && !r.startsWith("Waiting") && !r.startsWith("Harm");

function why(c) {
  const p = c.priority;
  if (p.gates?.includes("G1_NO_VERIFIED_SIGNALS")) return p.reasons[0];
  return p.reasons.find((r) => tag(r)[0] === "Verified") || p.reasons.find((r) => r.startsWith("Gate")) || p.reasons[0];
}

// ---------- priority list ----------
function row(c) {
  const p = c.priority;
  const flags = [];
  if (c.status === "IN_REVIEW") flags.push(h("span", { class: "chip info", text: "With an officer" }));
  if (p.executor === "AI_AFTER_APPROVAL") flags.push(h("span", { class: "chip ok", text: "AI after 1 click" }));
  if (c.language && c.language !== "en") flags.push(h("span", { class: "chip", text: c.language_label || c.language }));
  if (c.clario_reported?.safeblock_activated) flags.push(h("span", { class: "chip ok", text: "SafeBlock on" }));
  if (c.clario_reported?.card_locked) flags.push(h("span", { class: "chip ok", text: "Card locked" }));
  if (c.customer_corrections?.length) flags.push(h("span", { class: "chip warn", text: "Customer corrected card" }));
  if (c.contacts > 1) flags.push(h("span", { class: "chip", text: `Contact ×${c.contacts}` }));
  if (p.gates?.includes("G1_NO_VERIFIED_SIGNALS")) flags.push(h("span", { class: "chip alert", text: "Officer to verify" }));
  const el = h("div", {
    class: `row${c.case_id === S.sel ? " sel" : ""}`, "data-id": c.case_id, role: "button", tabindex: "0",
    onclick: () => select(c.case_id), onkeydown: (e) => { if (e.key === "Enter") select(c.case_id); },
  },
  h("div", {}, h("span", { class: `band ${p.band}`, text: p.band_label?.toUpperCase() || p.band })),
  h("div", {}, h("div", { class: "name", text: c.customer_name || c.customer_id }),
    h("div", { class: "issue", text: `${ISSUE_TEXT(c.issue_type)} · ${c.case_id}` })),
  h("div", {}, h("div", { class: "score num", text: p.score }), h("div", { class: "wait", text: ago(c.created_at) })),
  h("div", { class: "why", title: why(c), text: `Why here: ${strip(why(c))}` }),
  flags.length ? h("div", { class: "flags" }, flags) : null);
  if (!S.first && !S.seen.has(c.case_id)) el.classList.add("arrived");
  S.seen.add(c.case_id);
  return el;
}

function renderQueue() {
  const rows = $("#rows");
  const before = new Map([...rows.children].map((el) => [el.dataset.id, el.getBoundingClientRect().top]));
  const els = S.queue.map(row);
  rows.replaceChildren(...(els.length ? els : [h("div", { class: "empty", text: "No open cases. New cases from Clario appear here by themselves." })]));
  for (const el of els) { // FLIP: slide rows from their old place to the new one
    const top = before.get(el.dataset.id);
    if (top === undefined) continue;
    const d = top - el.getBoundingClientRect().top;
    if (!d) continue;
    el.style.transform = `translateY(${d}px)`;
    el.style.transition = "none";
    requestAnimationFrame(() => requestAnimationFrame(() => {
      el.style.transition = "transform .7s cubic-bezier(.2,.7,.2,1)"; el.style.transform = "";
    }));
  }
  const n = { P1: 0, P2: 0, P3: 0, P4: 0 };
  S.queue.forEach((c) => { n[c.priority.band] += 1; });
  $("#counts").replaceChildren(...Object.entries(n).map(([b, k]) => h("span", { class: `band ${b}`, text: `${b} ${k}` })));
  S.first = false;
}

// ---------- case panel ----------
function select(id) {
  if (S.sel !== id) { S.modify = false; S.lens = "officer"; S.key = ""; S.auditOpen = false; }
  S.sel = id;
  [...$("#rows").children].forEach((el) => el.classList.toggle("sel", el.dataset.id === id));
  refreshCase();
}

async function refreshCase(force = false) {
  if (!S.sel || (S.modify && !force)) return;
  const seq = (S.seq = (S.seq || 0) + 1); // a slower, older request must never overwrite a newer one
  try {
    const c = await api(`/case/${encodeURIComponent(S.sel)}`);
    const status = S.lens === "customer" ? await api(`/case/${encodeURIComponent(S.sel)}/status`) : null;
    if (seq !== S.seq) return;
    const key = JSON.stringify([c, status, S.lens, S.modify]);
    if (key === S.key && !force) return;
    S.key = key;
    S.c = c;
    renderCase(c, status);
  } catch (e) {
    $("#case").replaceChildren(h("div", { class: "banner err", text: `Couldn't load ${S.sel}: ${e.message}` }));
  }
}

function section(title, ...kids) { return h("div", { class: "card" }, h("h2", { text: title }), ...kids); }

function head(c) {
  const p = c.priority;
  const proto = c.proposed_solution?.protocol || {};
  const exec = p.executor === "AI_AFTER_APPROVAL"
    ? ["AI acts after your one-click approval", "Low risk (P4): Prorio has prepared everything."]
    : p.band === "P1" ? ["Fraud specialist acts now", "Warm transfer. The AI only drafts."]
      : ["Officer acts", "P1 to P3 are done by people. The AI only drafts."];
  return h("div", { class: "case-head" },
    h("div", {}, h("div", { class: "big num" }, String(p.score), h("small", { text: "/100" })),
      h("div", { class: `band ${p.band}`, text: p.band_label?.toUpperCase() })),
    h("div", {}, h("h1", { text: c.customer_name || c.customer_id }),
      h("div", { class: "sub", text: `${proto.title || ISSUE_TEXT(c.issue_type)} · ${c.case_id}` }),
      h("div", { class: "meta" },
        h("span", { class: "chip", text: c.issue_type }),
        h("span", { class: "chip", text: `${c.language_label || c.language}` }),
        h("span", { class: "chip", text: `Status: ${c.status.replace(/_/g, " ").toLowerCase()}` }),
        h("span", { class: "chip", text: `Waiting ${ago(c.created_at)}` }),
        c.customer_confirmed ? h("span", { class: "chip ok", text: "Customer confirmed the card" }) : null)),
    h("div", { class: "exec" }, h("b", { text: exec[0] }), exec[1]));
}

function lensBar() {
  const notes = {
    officer: "Everything, because the officer makes the risky decisions.",
    prorio: "Only structured card fields and flags from the scoring code. Never the customer's free text.",
    customer: "What the customer sees in the app: their words and live status. No score, no fraud alarms.",
  };
  const b = (k, label) => h("button", { class: S.lens === k ? "on" : "", text: label, onclick: () => { S.lens = k; S.key = ""; refreshCase(true); } });
  return [h("div", { class: "lens", role: "tablist", "aria-label": "Whose view" }, h("button", { disabled: true, text: "View as" }),
    b("officer", "Officer"), b("prorio", "Prorio"), b("customer", "Customer")),
  h("div", { class: "lens-note", text: notes[S.lens] })];
}

function told(c) {
  const corr = c.customer_corrections || [];
  const flash = corr.length > (S.lastCorr[c.case_id] ?? corr.length);
  S.lastCorr[c.case_id] = corr.length;
  const done = c.proposed_solution?.already_done || [];
  return h("div", { class: `card${flash ? " flash" : ""}` },
    h("h2", { text: "What the customer told Clario" }),
    h("p", { class: "quote", text: c.summary_en ? `“${c.summary_en}”` : "(no summary)" }),
    c.summary_customer_lang ? h("div", { class: "orig" }, h("span", { class: "muted small", text: `Original (${c.language_label}): ` }), c.summary_customer_lang) : null,
    corr.map((x) => h("div", { class: "corr" }, h("b", { text: "Customer corrected the card: " }), x.text, h("span", { class: "muted small", text: ago(x.ts) === "just now" ? "  just now" : `  ${ago(x.ts)} ago` }))),
    done.length ? h("div", { class: "small", style: null }, h("h2", { text: "Already done in the conversation" }),
      h("ul", { class: "plain" }, done.map((d) => h("li", { text: d })))) : null,
    c.linked_transactions?.length ? h("div", { class: "small muted", text: `Linked transactions: ${c.linked_transactions.join(", ")}` }) : null);
}

function receipt(c) {
  const p = c.priority;
  const moved = S.lastScore[c.case_id] !== undefined && S.lastScore[c.case_id] !== p.score;
  S.lastScore[c.case_id] = p.score;
  const caps = p.reasons.filter(isCap);
  const lines = p.reasons.filter((r) => !isCap(r));
  return h("div", { class: `card${moved ? " flash" : ""}` },
    h("h2", { text: "Why it ranks here (computed by code, not the AI)" }),
    h("table", { class: "receipt" }, h("tbody", {},
      lines.map((r) => { const [t, k] = tag(r); return h("tr", {}, h("td", { class: "src" }, h("span", { class: `chip ${k}`, text: t })),
        h("td", { text: strip(r) }), h("td", { class: "pts", text: pts(r) ? `+${pts(r)}` : "" })); }),
      h("tr", { class: "total" }, h("td", {}), h("td", { text: `Score (capped at 100) → ${p.band_label}` }), h("td", { class: "pts", text: String(p.score) })))),
    caps.map((r) => h("div", { class: "gate", text: r })),
    h("div", { class: "small muted", text: "Verified = from account data. Said = from the customer's words, which can never lift a case to P1 on their own." }));
}

function proposal(c) {
  const s = c.proposed_solution || {};
  const proto = s.protocol || {};
  const last = (proto.change_log || []).at(-1);
  const ai = c.priority.executor === "AI_AFTER_APPROVAL";
  const actionList = S.modify
    ? (S.meta?.actions || []).map((a) => h("li", {}, h("input", {
      type: "checkbox", id: `a-${a.action}`, checked: S.picked.has(a.action),
      onchange: (e) => { e.target.checked ? S.picked.add(a.action) : S.picked.delete(a.action); },
    }), h("label", { for: `a-${a.action}`, text: a.label })))
    : (s.actions || []).map((a) => h("li", {}, h("span", { text: "▸" }),
      h("div", {}, h("div", { text: a.label }), Object.keys(a.params || {}).length
        ? h("div", { class: "small muted", text: Object.entries(a.params).map(([k, v]) => `${k}: ${v}`).join(" · ") }) : null,
      a.note ? h("div", { class: "small muted", text: a.note }) : null),
      h("span", { class: `chip ${ai ? "ok" : ""} lock`, text: a.customer_chosen ? "Customer's choice" : ai ? "AI runs after approval" : "Runs on approval" })));
  return h("div", { class: "card" },
    h("h2", { text: S.modify ? "Modify: choose the actions to run" : "Prorio's proposed solution" }),
    h("div", { class: "proto" }, h("code", { text: `${proto.issue_type} v${proto.version}` }), h("span", { text: proto.title }),
      last ? h("span", { class: "chip info", title: last.change, text: `v${last.version}: ${last.change.slice(0, 70)}${last.change.length > 70 ? "…" : ""}` }) : null),
    h("p", { class: "small", text: s.explanation }),
    h("ul", { class: "acts" }, actionList.length ? actionList : h("li", { class: "muted", text: "No automatic actions. An officer handles it." })),
    s.officer_tasks?.length ? [h("h2", { text: "Only a person may do this" }), h("ul", { class: "plain" },
      s.officer_tasks.map((t) => h("li", {}, h("span", { class: "chip alert", text: "Officer only" }), " ", t.replace(/^Officer must:\s*/, ""))))] : null,
    s.steps?.length ? [h("h2", { text: "Protocol steps: who does what" }), h("div", { class: "lanes" },
      s.steps.flatMap((st) => [h("div", { class: `w ${st.who.startsWith("AI") ? "ai" : st.who.startsWith("officer") ? "off" : ""}`, text: st.who }),
        h("div", {}, st.step, " ", h("span", { class: "chip", text: st.source === "team_design" ? "team design" : "sourced" }))]))] : null,
    s.required_checks?.length ? [h("h2", { text: "Checks before acting" }), h("ul", { class: "plain" }, s.required_checks.map((x) => h("li", { text: x })))] : null,
    s.customer_message ? [h("h2", { text: `Message Clario will send (${c.language_label || "English"})` }), h("div", { class: "msg", text: s.customer_message }),
      s.customer_message_missing?.length ? h("div", { class: "small muted", text: `Needs: ${s.customer_message_missing.join(", ")}` }) : null] : null,
    s.timeframes?.length ? [h("h2", { text: "Timeframes" }), h("ul", { class: "plain" }, s.timeframes.map((t) => h("li", { text: `${t.what}: ${t.rule}` })))] : null,
    proto.sources?.length ? h("div", { class: "srcs small" }, h("span", { class: "muted", text: "Sources: " }),
      proto.sources.map((x, i) => [i ? " · " : "", h("a", { href: x.url, target: "_blank", rel: "noopener noreferrer", text: x.title })])) : null);
}

function traceCard(c) {
  return section("What Prorio did",
    h("ol", { class: "trace" }, (c.prorio_trace || []).map((t) => h("li", {}, h("b", { text: t.step }), t.detail))));
}

function auditCard(c) {
  const d = h("details", { ontoggle: (e) => { S.auditOpen = e.target.open; } },
    h("summary", { text: `Audit log (${c.audit_log.length}): every action, who, when. Nobody can edit it.` }),
    h("table", { class: "audit" }, h("tbody", {}, c.audit_log.slice().reverse().map((a) =>
      h("tr", {}, h("td", { class: "num", text: a.ts.slice(11, 19) }), h("td", { text: a.actor }), h("td", { text: a.action }),
        h("td", { text: a.result || "" }))))));
  d.open = S.auditOpen;
  return h("div", { class: "card" }, d);
}

function prorioLens(c) {
  const p = c.priority;
  const f = (k, v) => [h("div", { class: "k", text: k }), h("div", {}, v)];
  const redact = (t) => h("span", { class: "redact", text: t });
  return [h("div", { class: "card" }, h("h2", { text: "What Prorio was allowed to read" }),
    h("div", { class: "fields" },
      f("Issue type", c.issue_type),
      f("Customer ID", c.customer_id),
      f("Customer name", redact("not needed for ranking")),
      f("Customer's words", redact("never read: free text can't steer the ranking (prompt-injection firewall)")),
      f("Linked transactions", c.linked_transactions?.join(", ") || "none"),
      f("Cues from the conversation", p.caller_signals?.length ? p.caller_signals.join(", ") : "none"),
      f("Verified account signals", p.signals?.length ? p.signals.map((s) => S.meta?.signal_labels?.[s] || s).join("; ") : "none found"),
      f("Reported by Clario", `SafeBlock ${c.clario_reported?.safeblock_activated ? "on" : "off"} · card ${c.clario_reported?.card_locked ? "locked" : "not locked"}`),
      f("Language", c.language_label || c.language),
      f("Balances, full history", redact("never seen: the scoring code passes only flags")))),
  traceCard(c)];
}

function customerLens(c, st) {
  if (!st) return h("div", { class: "card", text: "Loading the customer's view…" });
  return h("div", { class: "card" }, h("h2", { text: `What ${c.customer_name || "the customer"} sees in the app` }),
    tracker(st.history),
    h("p", { class: "quote", text: st.summary_customer_lang || st.summary }),
    st.summary_customer_lang ? h("div", { class: "orig", text: st.summary }) : null,
    (st.corrections || []).map((x) => h("div", { class: "corr" }, h("b", { text: "You added: " }), x.text)),
    st.outcome ? h("div", { class: "msg", text: st.outcome.message }) : h("div", { class: "small muted", text: `Status: ${st.status}` }),
    h("div", { class: "gate", text: "Not shown to the customer: the score, the ranking reasons, which fraud alarms tripped, the protocol." }));
}

function decisionBar(c) {
  const open = OPEN.has(c.status);
  const note = h("input", { class: "note", id: "note", placeholder: "Note or reason (needed for re-rank and Manual close)", maxlength: "300" });
  if (c.status === "MANUAL" && !c.outcome) {
    return h("div", { class: "decide" }, h("b", { text: "Handled manually:" }), note,
      h("button", { class: "btn primary", text: "Mark done and tell the customer", onclick: () => act("complete", { note: $("#note").value }) }));
  }
  if (!open) return null;
  if (S.modify) {
    const sug = h("input", { type: "checkbox", id: "sug", checked: true });
    return h("div", { class: "decide" },
      h("button", { class: "btn approve", text: `Run ${S.picked.size} selected`, onclick: () => act("MODIFY", { note: $("#note").value, suggest_update: $("#sug").checked }) }),
      h("button", { class: "btn", text: "Cancel", onclick: () => { S.modify = false; S.key = ""; refreshCase(true); } }),
      h("label", { class: "small" }, sug, " Suggest as a protocol update"), note);
  }
  const ai = c.priority.executor === "AI_AFTER_APPROVAL";
  const band = h("select", { id: "band", "aria-label": "New band" }, ["P1", "P2", "P3", "P4"].map((b) => h("option", { value: b, text: b, selected: b === c.priority.band })));
  return h("div", { class: "decide" },
    c.status !== "IN_REVIEW" ? h("button", { class: "btn", text: "Pick up", onclick: () => act("pickup") }) : null,
    h("button", { class: "btn approve", text: ai ? "Approve (AI sends it)" : "Approve", onclick: () => act("APPROVE", { note: $("#note").value }) }),
    h("button", { class: "btn", text: "Modify", onclick: () => {
      S.modify = true; S.picked = new Set((c.proposed_solution?.actions || []).map((a) => a.action)); S.key = ""; refreshCase(true);
    } }),
    h("button", { class: "btn", text: "Manual", onclick: () => act("MANUAL", { note: $("#note").value }) }),
    note, band, h("button", { class: "btn small", text: "Re-rank", onclick: () => act("rerank", { band: $("#band").value, reason: $("#note").value }) }));
}

function outcomeBanner(c) {
  if (OPEN.has(c.status)) return null;
  if (c.status === "TIER1_RESOLVED") return h("div", { class: "banner done", text: "Answered by Clario. No officer needed." });
  const sug = [...c.audit_log].reverse().find((a) => a.action === "PROTOCOL_SUGGESTION");
  return h("div", { class: "banner done" },
    h("b", { text: `${c.officer_decision || c.status}` }), c.outcome ? ` · Sent to the customer: “${c.outcome.message}”` : " · Waiting for the officer to close it.",
    sug ? h("div", { class: "small", text: sug.result }) : null);
}

function renderCase(c, st) {
  const box = $("#case");
  const y = box.scrollTop;
  let body;
  if (S.lens === "prorio") body = prorioLens(c);
  else if (S.lens === "customer") body = customerLens(c, st);
  else body = [h("div", { class: "grid2" }, told(c), receipt(c)), proposal(c), h("div", { class: "grid2" }, traceCard(c), auditCard(c))];
  box.replaceChildren(head(c), outcomeBanner(c) || "", ...lensBar(), ...[body].flat(), S.lens === "officer" ? decisionBar(c) || "" : "");
  box.scrollTop = y;
}

async function act(kind, extra = {}) {
  if (S.busy) return;
  S.busy = true;
  const id = encodeURIComponent(S.sel);
  try {
    let res;
    if (kind === "pickup") res = await api(`/case/${id}/pickup`, { officer: officer() });
    else if (kind === "complete") res = await api(`/case/${id}/complete`, { officer: officer(), note: extra.note });
    else if (kind === "rerank") {
      if (!extra.reason.trim()) { toast("Write the reason in the note box first. Re-ranks are logged and reviewed."); return; }
      res = await api(`/case/${id}/rerank`, { band: extra.band, reason: extra.reason, officer: officer() });
    } else {
      const body = { decision: kind, officer: officer(), note: extra.note || "" };
      if (kind === "MODIFY") { body.actions = [...S.picked].map((a) => ({ action: a })); body.suggest_update = extra.suggest_update; }
      res = await api(`/case/${id}/decision`, body);
      const sug = [...res.audit_log].reverse().find((a) => a.action === "PROTOCOL_SUGGESTION");
      toast(sug ? sug.result : kind === "APPROVE" ? "Approved. Actions ran and the customer was told." : `Recorded: ${kind}`);
    }
    if (kind === "pickup") toast("Picked up. The customer's card now says “With an officer”.");
    if (kind === "rerank") toast(`Re-ranked to ${res.priority.band}. Logged with your reason.`);
    S.modify = false; S.key = "";
    await tick();
    await refreshCase(true);
  } catch (e) {
    toast(`Not done: ${e.message}`);
  } finally { S.busy = false; }
}

// ---------- protocols tab ----------
async function renderProtocols() {
  const box = $("#view-protocols");
  try {
    const [sg, pr] = await Promise.all([api("/suggestions"), api("/protocols")]);
    const key = JSON.stringify([sg, pr]);
    if (key === S.pkey) return; // nothing changed: keep the page still
    S.pkey = key;
    const owner = () => `${officer()} (protocol owner)`;
    const sAct = async (sid, what) => {
      try {
        const body = { owner: owner() };
        if (what === "reject") { const r = prompt("Why reject this suggestion?"); if (r === null) return; body.reason = r; }
        const res = await api(`/suggestions/${encodeURIComponent(sid)}/${what}`, body);
        toast(what === "approve" ? `Approved: ${res.issue_type || ""} is now v${res.proposed_version || res.version || "new"}` : "Rejected and logged.");
        S.pkey = ""; renderProtocols();
      } catch (e) { toast(`Not done: ${e.message}`); }
    };
    const change = (s) => s.change?.handled_manually ? "Officers handled it manually instead"
      : [s.change?.add_actions?.length ? `add ${s.change.add_actions.join(", ")}` : "", s.change?.remove_actions?.length ? `remove ${s.change.remove_actions.join(", ")}` : ""].filter(Boolean).join("; ") || "(no change)";
    box.replaceChildren(
      h("h2", { text: "Officers teach, leads approve" }),
      h("p", { class: "small muted", text: `A Modify or Manual decision becomes a suggestion, never a rule. After ${sg.threshold} matching suggestions a protocol owner can approve it as the next version, and roll it back later.` }),
      sg.suggestions.length ? h("table", { class: "list" },
        h("thead", {}, h("tr", {}, ["Protocol", "Suggested change", "Support", "Officers' notes", "Status", ""].map((t) => h("th", { text: t })))),
        h("tbody", {}, sg.suggestions.map((s) => h("tr", {},
          h("td", {}, h("code", { text: s.issue_type }), h("div", { class: "small muted", text: `v${s.from_version} → v${s.proposed_version}` })),
          h("td", { text: change(s) }),
          h("td", {}, h("span", { class: "bar" }, h("i", { class: "fill", "data-w": "" })), `${s.count} of ${sg.threshold}`),
          h("td", { class: "small", text: (s.notes || []).filter(Boolean).join(" / ") || "—" }),
          h("td", {}, h("span", { class: `chip ${s.status === "APPROVED" ? "ok" : s.status === "REJECTED" ? "alert" : "info"}`, text: s.status.toLowerCase() })),
          h("td", {}, ["APPROVED", "REJECTED"].includes(s.status) ? "" : [
            h("button", { class: "btn small approve", text: "Approve", disabled: s.count < sg.threshold, title: s.count < sg.threshold ? "Not enough officers have suggested this yet" : "", onclick: () => sAct(s.id, "approve") }), " ",
            h("button", { class: "btn small", text: "Reject", onclick: () => sAct(s.id, "reject") })]))))) :
        h("div", { class: "card muted", text: "No suggestions yet. Modify a proposal on the priority list to create one." }),
      h("h2", { text: `Protocol Database (${pr.length} protocols)`, class: "", style: null }),
      h("table", { class: "list" },
        h("thead", {}, h("tr", {}, ["Issue type", "Title", "Version", "Harm", "Floor", "Decisions A / M / Manual", ""].map((t) => h("th", { text: t })))),
        h("tbody", {}, pr.map((p) => h("tr", {},
          h("td", {}, h("code", { text: p.issue_type })), h("td", { text: p.title }), h("td", { class: "num", text: `v${p.version}` }),
          h("td", { class: "small", text: `${p.harm_category} (${p.harm_points})` }), h("td", { text: p.min_band || "" }),
          h("td", { class: "num", text: `${p.decisions.APPROVE} / ${p.decisions.MODIFY} / ${p.decisions.MANUAL}` }),
          h("td", {}, p.approved_changes ? h("button", { class: "btn small", text: "Roll back", onclick: async () => {
            try { const r = await api(`/protocols/${encodeURIComponent(p.issue_type)}/rollback`, { owner: owner() }); toast(`Rolled back to v${r.version}`); S.pkey = ""; renderProtocols(); } catch (e) { toast(`Not done: ${e.message}`); }
          } }) : ""))))));
    box.querySelectorAll(".bar i").forEach((el, i) => {
      const s = sg.suggestions[i]; el.style.width = `${Math.min(100, (100 * s.count) / sg.threshold)}%`;
    });
  } catch (e) { box.replaceChildren(h("div", { class: "banner err", text: `Couldn't load protocols: ${e.message}` })); }
}

// ---------- loop ----------
async function tick() {
  const seq = (S.qseq = (S.qseq || 0) + 1);
  try {
    const q = await api("/queue");
    if (seq !== S.qseq) return;
    S.queue = q;
    renderQueue();
    const sg = await api("/suggestions");
    const open = sg.suggestions.filter((s) => !["APPROVED", "REJECTED"].includes(s.status)).length;
    $("#sugCount").textContent = open; $("#sugCount").classList.toggle("hidden", !open);
    $("#live").classList.remove("down"); $("#live").lastChild.textContent = "Live";
  } catch {
    $("#live").classList.add("down"); $("#live").lastChild.textContent = "Backend not reachable";
  }
}

async function init() {
  $("#officer").value = store.get("officer", "officer");
  $("#officer").addEventListener("change", (e) => store.set("officer", e.target.value.trim()));
  document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => {
    S.tab = b.dataset.tab;
    document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("on", x === b));
    $("#view-queue").classList.toggle("hidden", S.tab !== "queue");
    $("#view-protocols").classList.toggle("hidden", S.tab !== "protocols");
    if (S.tab === "protocols") { S.pkey = ""; renderProtocols(); }
  }));
  $("#reset").addEventListener("click", async () => {
    if (!confirm("Reset the demo? This clears every case, the learning loop and mock account changes.")) return;
    await api("/admin/reset", {}); S.sel = null; S.seen.clear(); S.first = true;
    $("#case").replaceChildren(h("div", { class: "empty", text: "Demo reset." }));
    tick();
  });
  window.addEventListener("message", (e) => { // the side-by-side demo page can open a case
    if (e.origin !== location.origin || e.data?.type !== "select") return;
    if (S.tab !== "queue") document.querySelector('.tab[data-tab="queue"]').click();
    select(String(e.data.id));
  });
  S.meta = await api("/meta").catch(() => null);
  const q = new URLSearchParams(location.search).get("case");
  await tick();
  if (q) select(q);
  setInterval(() => { tick(); refreshCase(); if (S.tab === "protocols") renderProtocols(); }, 2000);
}
init();
