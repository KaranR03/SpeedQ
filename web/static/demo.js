// Officer-first demo. The customer conversation is an optional preview opened from Live intake.
import { $, api, h } from "./dom.js";

const cust = () => $("#cust").contentWindow;
const off = () => $("#off").contentWindow;
const send = (win, msg) => win.postMessage(msg, location.origin);
const preview = $("#customer-preview");
let busy = false;

window.addEventListener("message", (e) => {
  if (e.origin !== location.origin) return;
  const m = e.data || {};
  if (e.source === off() && m.type === "customer_preview") {
    if (!preview.open) preview.showModal();
    return;
  }
  if (e.source !== cust()) return;
  if (m.type === "ready") {
    $("#scenes").replaceChildren(...Object.entries(m.scenes).map(([id, label]) =>
      h("button", { class: "btn small", "data-id": id, text: label, onclick: () => start(id) }), " "));
  }
  if (m.type === "caption") $("#caption").textContent = m.text;
  if (m.type === "draft_started") send(off(), {type:"intake"});
  if (m.type === "submitted") setTimeout(() => send(off(), { type: "select", id: m.ref }), 2600);
  if (m.type === "done") { busy = false; document.querySelectorAll("#scenes .btn").forEach((b) => b.classList.remove("on")); }
});

$("#close-customer-preview").addEventListener("click", () => preview.close());
preview.addEventListener("close", () => send(off(), { type: "customer_preview_closed" }));

function start(id) {
  if (busy) return;
  busy = true;
  document.querySelectorAll("#scenes .btn").forEach((b) => b.classList.toggle("on", b.dataset.id === id));
  send(cust(), { type: "speed", speed: $("#speed").value });
  send(cust(), { type: "play", id });
}

$("#speed").addEventListener("change", (e) => send(cust(), { type: "speed", speed: e.target.value }));
$("#reset").addEventListener("click", async () => {
  if (!confirm("Reset the demo? This clears every case.")) return;
  await api("/admin/reset", {});
  if (preview.open) preview.close();
  busy = false;
  $("#caption").textContent = "Demo reset. Pick a customer to start.";
  $("#cust").src = "/customer?embed=1";
  $("#off").src = "/officer";
});
