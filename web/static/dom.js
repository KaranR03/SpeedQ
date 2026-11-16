// Tiny DOM and API helpers shared by every page.
// Security: text is only ever set with textContent, never innerHTML, so customer words can't run as code.

export function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "href") { if (/^https:\/\//i.test(v) || v.startsWith("/")) el.setAttribute("href", v); }
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

export const $ = (sel, root = document) => root.querySelector(sel);

export async function api(path, body) {
  const opt = body === undefined ? {} : {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
  };
  const r = await fetch(path, opt);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : `HTTP ${r.status}`);
  return data;
}

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let toastTimer;
export function toast(text) {
  let t = $(".toast");
  if (!t) { t = h("div", { class: "toast", role: "status" }); document.body.append(t); }
  t.textContent = text;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 3200);
}

export const ISSUE_TEXT = (s) => (s || "").toLowerCase().replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

export function ago(iso, now = Date.now()) {
  const m = Math.max(0, Math.round((now - Date.parse(iso)) / 60000));
  return m < 1 ? "just now" : m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`;
}

export const STAGES = [["RECEIVED", "Received"], ["RANKED", "Ranked"], ["WITH_OFFICER", "With an officer"],
  ["ACTION_TAKEN", "Action taken"], ["DONE", "Done"]];

export function tracker(history) {
  const reached = new Set((history || []).map((x) => x.stage));
  const last = (history || []).at(-1)?.stage;
  return h("div", { class: "tracker", "aria-label": "Case progress" },
    STAGES.map(([k, label]) => h("div", { class: `st${reached.has(k) ? " on" : ""}${k === last ? " now" : ""}`, text: label })));
}
