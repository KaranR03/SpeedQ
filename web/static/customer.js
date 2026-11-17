// Customer app: Clario's side of Westpac SpeedQ, on a phone-sized page.
// The customer's lines are scripted so the video is repeatable. Everything else is real: Clario's look-ups read the
// customer's own data from the backend, the card goes through the same /webhook/retell the voice agent uses, Prorio
// ranks it, and "My card" polls the customer's real status. ?track=WGM-0412 shows only the live card (for Retell calls).
import { $, api, h, sleep, toast, tracker } from "./dom.js";

const S = { running: false, cid: null, ref: null, draft: null, flags: {}, t0: 0, poll: null, lang: "en", speed: 1, outcomeShown: false };
const embedded = window.parent !== window;
const tell = (msg) => { if (embedded) window.parent.postMessage(msg, location.origin); };
const chat = () => $("#chat");
const scroll = () => { chat().scrollTop = chat().scrollHeight; };
const wait = (ms) => sleep(ms / S.speed);

function add(el) { chat().append(el); scroll(); return el; }
async function clario(text, gloss) {
  const t = add(h("div", { class: "typing", text: "•••" }));
  await wait(500 + Math.min(1400, text.length * 14));
  t.remove();
  add(h("div", { class: "msgb c" }, text, gloss ? h("span", { class: "gloss", text: gloss }) : null));
  await wait(350);
}
async function customer(text, gloss) {
  await wait(300 + Math.min(1100, text.length * 18));
  add(h("div", { class: "msgb u" }, text, gloss ? h("span", { class: "gloss", text: gloss }) : null));
  await wait(300);
}
const tool = (text) => add(h("div", { class: "tool", text: `🔎 Clario checked: ${text}` }));

// Quick replies: the scripted choice is highlighted and taken automatically; tapping it goes faster.
async function choose(options, pick = 0, gloss) {
  const q = $("#quick");
  let done;
  const go = new Promise((r) => { done = r; });
  q.replaceChildren(...options.map((o, i) => h("button", { disabled: i !== pick, onclick: () => done() , text: o })));
  await wait(900);
  q.children[pick]?.classList.add("pick");
  await Promise.race([go, wait(1100)]);
  q.replaceChildren();
  add(h("div", { class: "msgb u" }, options[pick], gloss ? h("span", { class: "gloss", text: gloss }) : null));
  await wait(300);
}

async function faceId(what) {
  const ring = h("div", { class: "ring" });
  const label = h("div", { class: "small", text: `Face ID to ${what}` });
  const ov = h("div", { class: "faceid" }, h("div", {}, ring, label));
  $(".phone").append(ov);
  await wait(1300);
  ring.classList.add("ok"); label.textContent = "Confirmed";
  await wait(600);
  ov.remove();
}

async function publish(fields) {
  if (!S.draft || S.draft.status !== "DRAFT") return;
  S.draft = await api(`/intake/drafts/${S.draft.draft_id}`, {expected_revision:S.draft.revision,...fields});
}

async function readback(title, text, gloss) {
  await publish({summary_en:gloss || text,summary_customer_lang:gloss ? text : "",phase:"CONFIRMING"});
  add(h("div", { class: "readback" }, h("h2", { text: title }), text, gloss ? h("div", { class: "small muted", text: gloss }) : null));
}

const lookup = () => api(`/clario/${S.cid}/lookup`);
const money = (n) => `$${Math.abs(n).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",")}`;
const day = (iso) => new Date(iso).toLocaleDateString("en-AU", { day: "numeric", month: "short", timeZone: "UTC" });

async function submit(card) {
  const body = { customer_id: S.cid, customer_confirmed: true, ...S.flags, ...card };
  let r;
  if (S.draft) {
    await publish({issue_type:body.issue_type,summary_en:body.summary_en,
      summary_customer_lang:body.summary_customer_lang || "", phase:"CONFIRMING",
      linked_transactions:(body.linked_transactions || "").split(",").filter(Boolean),
      risk_signals:(body.risk_signals || "").split(",").filter(Boolean),
      safeblock_activated:body.safeblock_activated || false,card_locked:body.card_locked || false});
    r = await api(`/intake/drafts/${S.draft.draft_id}/confirm`, {expected_revision:S.draft.revision,
      customer_confirmed:true,case_reference:body.case_reference || ""});
    S.draft.status = "SUBMITTED";
  } else r = await api("/webhook/retell", body);
  S.ref = r.case_reference;
  tell({ type: "submitted", ref: S.ref });
  $("#cardTab").replaceChildren("My card", h("span", { class: "dot" }));
  startPolling();
  return r;
}

async function correct(card) {
  await api("/webhook/retell", { customer_id: S.cid, case_reference: S.ref, ...card });
  renderCard(true);
}

// ---------- My card: the glass-box card, live ----------
async function renderCard() {
  const v = $("#cardview");
  if (!S.ref) { v.replaceChildren(h("p", { class: "muted", text: "When Clario passes your problem to the team, your card appears here. You'll see exactly what we wrote down, and you can correct it." })); return; }
  try {
    const st = await api(`/case/${encodeURIComponent(S.ref)}/status`);
    const vi = S.lang === "vi";
    v.replaceChildren(
      h("div", { class: "ref", text: `Case ${st.case_reference}` }),
      h("h3", { text: vi ? "Những gì chúng tôi đã ghi lại" : "What we've written down" }),
      h("p", { class: "quote", text: st.summary_customer_lang || st.summary }),
      tracker(st.history),
      h("p", { class: "small", text: `${vi ? "Trạng thái" : "Status"}: ${st.status}` }),
      st.assigned_officer ? h("p", {class:"small",text:`Officer: ${st.assigned_officer}`}) : null,
      st.completed_by ? h("p", {class:"small",text:`Completed by ${st.completed_by}`}) : null,
      (st.corrections || []).map((x) => h("div", { class: "corr" }, h("b", { text: vi ? "Bạn đã thêm: " : "You added: " }), x.text)),
      st.outcome ? h("div", { class: "msg", text: st.outcome.message }) : null,
      h("button", { class: "btn", text: vi ? "Có gì sai hoặc thiếu? Nói với Clario" : "Something wrong or missing? Tell Clario", onclick: () => show("chat") }),
      h("p", { class: "small muted", text: vi ? "Bạn thấy đúng những gì nhân viên thấy về vấn đề của bạn." : "This is the same record the officer works from. Only you and the bank can see it." }));
    if (st.outcome && !S.outcomeShown) {
      S.outcomeShown = true;
      add(h("div", { class: "sys chip ok", text: `Update on ${st.case_reference}` }));
      add(h("div", { class: "msgb c", text: st.outcome.message }));
      tell({ type: "caption", text: "The loop closes: the customer gets the outcome in their own app, and the card reaches Done." });
    }
  } catch (e) { v.replaceChildren(h("p", { class: "banner err", text: `Can't load your card: ${e.message}` })); }
}
function startPolling() { clearInterval(S.poll); S.poll = setInterval(renderCard, 2000); renderCard(); }
function show(which) {
  document.querySelectorAll(".ph-tabs button").forEach((b) => b.classList.toggle("on", b.dataset.v === which));
  $("#chat")?.classList.toggle("hidden", which !== "chat");
  $("#quick")?.classList.toggle("hidden", which !== "chat");
  $("#cardview").classList.toggle("hidden", which !== "card");
  if (which === "card") { $("#cardTab")?.replaceChildren("My card"); renderCard(); }
}

// ---------- the five demo scenes ----------
const caption = (text) => tell({ type: "caption", text });
const timerStart = () => { S.t0 = performance.now(); };
const timerStop = () => {
  const s = Math.round((performance.now() - S.t0) / 1000);
  const label = `Protected in 0:${String(s).padStart(2, "0")}`;
  add(h("div", { class: "timer", text: `🛡 ${label}` }));
  caption(`${label}, before any ranking or queue. Gate G2: protect first.`);
};

const SCENES = {
  maria: { cid: "CUST-001", name: "Maria", label: "Maria · scam in progress", async run() {
    caption("Maria is being scammed right now. Watch how fast she is protected.");
    await clario("Hi Maria, I'm Clario, Westpac's AI assistant. You're signed in, so no security questions. What's happening?");
    timerStart();
    await customer("A man from the bank's fraud team rang. He says my savings aren't safe and I must move them to a new account. I already sent some.");
    await publish({issue_type:"SCAM_IN_PROGRESS",summary_en:"A caller claiming to be from the bank asked Maria to move savings. She reports having sent money.",risk_signals:["CUSTOMER_REPORTS_PRESSURE"],phase:"CHECKING"});
    await clario("Maria, please stop. Don't send any more money, and hang up on him. The bank will never ask you to move money to keep it safe.");
    await clario("I can turn on SafeBlock right now. It stops new payments and transfers straight away. Scheduled payments and money coming in keep working.");
    await choose(["Turn on SafeBlock", "Not now"], 0);
    await faceId("turn on SafeBlock");
    S.flags.safeblock_activated = true;
    await publish({safeblock_activated:true});
    timerStop();
    await clario("SafeBlock is on. Two quick questions so the right person helps you. Is he still on the line?");
    await choose(["Yes, he's waiting", "No"], 0);
    const d = await lookup();
    const tx = d.recent_transactions.find((t) => t.amount < -1000);
    const payee = d.payees.find((p) => p.name === tx?.payee);
    await publish({linked_transactions:[tx.id],risk_signals:["CUSTOMER_REPORTS_PRESSURE","VULNERABILITY_CUES"]});
    const hrs = tx && payee ? Math.round((Date.parse(tx.date) - Date.parse(payee.added_at)) / 3.6e6) : null;
    tool(`recent payments · ${money(tx.amount)} to ${tx.payee} on ${day(tx.date)}${hrs !== null ? ` · payee added ${hrs} h earlier` : ""}`);
    await clario(`I can see ${money(tx.amount)} to ${tx.payee} on ${day(tx.date)}. Is that the money he told you to move?`);
    await choose(["Yes, that's it"], 0);
    const summary = `Someone claiming to be from Westpac told me to move my savings. I sent ${money(tx.amount)} to ${tx.payee} and he's still on the line.`;
    await clario("Here's what I'll pass on, so you never have to repeat it. Is that right?");
    await readback("Your card", summary);
    await choose(["Yes, that's right", "Change something"], 0);
    const r = await submit({ customer_name: "Maria R.", issue_type: "SCAM_IN_PROGRESS", linked_transactions: tx.id,
      risk_signals: "CUSTOMER_REPORTS_PRESSURE,VULNERABILITY_CUES", summary_en: summary, case_reference: "WGM-0412" });
    caption("Prorio ranks the card in code. The officer's list re-orders by itself: Maria is at the top.");
    await clario(`${r.caller_message} Your reference is ${r.case_reference}. You can watch your card under "My card".`);
  } },

  priya: { cid: "CUST-003", name: "Priya", label: "Priya · charge she didn't make", async run() {
    caption("Priya sees a charge she doesn't recognise. Clario checks the facts before anything else.");
    await clario("Hi Priya, I'm Clario, Westpac's AI assistant. How can I help?");
    await customer("There's an $89 charge on my credit card I don't recognise.");
    await publish({issue_type:"FRAUD_UNAUTHORISED",summary_en:"Priya reports an unrecognised $89 card charge.",phase:"CHECKING"});
    const d = await lookup();
    const tx = d.recent_transactions.find((t) => Math.abs(t.amount) === 89);
    await publish({linked_transactions:[tx.id]});
    tool(`card transactions · ${tx.payee} ${money(tx.amount)} on ${day(tx.date)} · first time this merchant has charged you`);
    await clario(`It's from ${tx.payee}, ${money(tx.amount)} on ${day(tx.date)}, and it's the first time they've charged your card. Subscriptions sometimes show a different name. Do you recognise it?`);
    await choose(["No, that's not me", "Yes, I remember now"], 0);
    await clario("Let's protect your card first. I can lock it now, and you can unlock it yourself later in the app.");
    await choose(["Lock my card"], 0);
    await faceId("lock your card");
    S.flags.card_locked = true;
    await publish({card_locked:true});
    await clario("Your card is locked. Here's what I'll pass on. Is that right?");
    const summary = `A ${money(tx.amount)} charge from ${tx.payee} on ${day(tx.date)} that I didn't make. I've locked my card.`;
    await readback("Your card", summary);
    await choose(["Yes, that's right"], 0);
    const r = await submit({ customer_name: "Priya S.", issue_type: "FRAUD_UNAUTHORISED", linked_transactions: tx.id, summary_en: summary });
    caption("Unauthorised charge, still recoverable: P3. The officer sees the merchant was never seen before.");
    await clario(`${r.caller_message} Your reference is ${r.case_reference}.`);
  } },

  minh: { cid: "CUST-004", name: "Minh", label: "Minh · Vietnamese, adds to his card", lang: "vi", async run() {
    caption("Minh speaks Vietnamese. The officer will read the same card in English.");
    await clario("Chào Minh, tôi là Clario, trợ lý AI của Westpac. Tôi có thể giúp gì cho bạn?", "Hi Minh, I'm Clario, Westpac's AI assistant. How can I help?");
    await customer("Tôi đã chuyển 650 đô tiền thuê nhà cho chủ nhà qua Osko, nhưng chủ nhà nói chưa nhận được.", "I sent $650 rent to my landlord by Osko, but the landlord says it hasn't arrived.");
    await publish({issue_type:"MONEY_MISSING",summary_en:"Minh reports a $650 rent payment that has not reached his landlord.",phase:"CHECKING"});
    const d = await lookup();
    const tx = d.recent_transactions.find((t) => t.type === "osko");
    await publish({linked_transactions:[tx.id]});
    tool(`payments · ${money(tx.amount)} Osko to ${tx.payee} on ${day(tx.date)} · status ${tx.status || "Sent"}`);
    await clario(`Tôi thấy khoản chuyển ${money(tx.amount)} cho ${tx.payee} ngày 13/11, trạng thái: đã gửi. Tôi sẽ chuyển cho nhân viên để tra soát. Đây là nội dung tôi sẽ ghi lại, bạn xem có đúng không?`,
      `I can see ${money(tx.amount)} to ${tx.payee} on 13 Nov, status: sent. I'll pass it to an officer to trace. Here's what I'll write down. Is that right?`);
    const vi = `Khoản chuyển 650 đô tiền thuê nhà cho ${tx.payee} qua Osko ngày 13/11 vẫn chưa đến tay chủ nhà.`;
    const en = `My $650 Osko rent payment to ${tx.payee} on 13 Nov hasn't reached my landlord.`;
    await readback("Hồ sơ của bạn", vi, en);
    await choose(["Đúng rồi"], 0, "That's right");
    const r = await submit({ customer_name: "Minh N.", issue_type: "MONEY_MISSING", language: "vi", language_label: "Vietnamese",
      linked_transactions: tx.id, summary_en: en, summary_customer_lang: vi });
    await clario(`Đã xong. Mã hồ sơ của bạn là ${r.case_reference}. Bạn có thể xem trong mục "My card".`, `Done. Your reference is ${r.case_reference}. You can see it under "My card".`);
    caption("Minh checks his card, then adds something. The officer sees the change live.");
    await wait(800); show("card"); await wait(3200); show("chat");
    await customer("Tiền thuê nhà phải trả trước ngày mai, và tôi không có tiền để trả lần nữa.", "The rent is due tomorrow and I don't have the money to pay it twice.");
    await correct({ issue_type: "MONEY_MISSING", risk_signals: "ESSENTIALS_AT_RISK", correction: "Rent is due tomorrow and I can't pay it twice.",
      summary_en: `${en} Rent is due tomorrow and I can't pay it twice.`, summary_customer_lang: `${vi} Tiền thuê nhà phải trả trước ngày mai.` });
    await clario("Tôi đã cập nhật hồ sơ của bạn. Nhân viên sẽ thấy ngay.", "I've updated your card. The officer sees it straight away.");
    caption("The officer's card shows the correction. The score stays 55: care needs count once (+10), so they help without overriding emergencies.");
  } },

  sam: { cid: "CUST-002", name: "Sam", label: "Sam · card delivery (P4, one click)", async run() {
    caption("Sam asks a routine question. Clario answers from his own data.");
    await clario("Hi Sam, I'm Clario, Westpac's AI assistant. How can I help?");
    await customer("When is my new card arriving?");
    await publish({issue_type:"CARD_DELIVERY",summary_en:"Sam is asking when his replacement card will arrive.",phase:"CHECKING"});
    const c = (await lookup()).card_delivery;
    tool(`card delivery · ${c.card} ${c.mask} · ${c.status} · due ${day(c.expected)}`);
    await clario(`Your replacement ${c.card} ending ${c.mask.replace(/\D/g, "")} was sent on ${day(c.dispatched)} by ${c.carrier}. It's ${c.status.toLowerCase()} and should arrive by ${day(c.expected)}. You can use your digital card in the app until then.`);
    await clario("Did that solve it?");
    await choose(["Yes, thanks", "No, get me help"], 1);
    await customer("I fly out on the 18th. Can someone check it'll get here in time?");
    const summary = `My replacement card is due ${day(c.expected)} but I travel on 18 Nov. Please check it will arrive in time.`;
    await clario("Sure. Here's what I'll pass on. Is that right?");
    await readback("Your card", summary);
    await choose(["Yes, that's right"], 0);
    const r = await submit({ customer_name: "Sam T.", issue_type: "CARD_DELIVERY", status: "QUEUED", summary_en: summary });
    caption("Low risk, P4: Prorio has prepared the reply. One click from the officer and the AI sends it.");
    await clario(`${r.caller_message} Your reference is ${r.case_reference}.`);
  } },

  jordan: { cid: "CUST-006", name: "Jordan", label: "Jordan · \"talk to a person\"", async run() {
    caption("Jordan just wants a person. Clario never refuses: it asks one question so the right person picks up.");
    await clario("Hi Jordan, I'm Clario, Westpac's AI assistant. How can I help?");
    await customer("I just want to talk to a person.");
    await clario("Of course, I'll get you to a person. So the right person picks up, what's it about?");
    await choose(["Money I didn't send, or someone asking me to move money", "Can't get into my account or money", "Lost or stolen card",
      "A payment or charge", "Something else", "I'd rather not say"], 1);
    await clario("Thanks. Can you pay for essentials like food right now?");
    await choose(["No, I can't buy groceries", "Yes, I'm fine"], 0);
    await publish({issue_type:"ACCOUNT_ACCESS",summary_en:"Jordan cannot access the account and says essentials are at risk.",risk_signals:["ESSENTIALS_AT_RISK"],phase:"CHECKING"});
    const summary = "I can't get into my account after a password change I didn't make, and I can't buy groceries.";
    await clario("Here's what I'll pass on. Is that right?");
    await readback("Your card", summary);
    await choose(["Yes, that's right"], 0);
    const r = await submit({ customer_name: "Jordan L.", issue_type: "ACCOUNT_ACCESS", risk_signals: "ESSENTIALS_AT_RISK", summary_en: summary });
    caption("Prorio finds a password change from a new device in the account data: a verified signal. P2.");
    await clario(`${r.caller_message} Your reference is ${r.case_reference}. You'll see your place in line under "My card".`);
  } },
};

async function play(id) {
  const sc = SCENES[id];
  if (!sc) return;
  if (S.running) { toast("A conversation is already running."); return; }
  if (L.mode) liveReset();
  L.mode = null;
  Object.assign(S, { running: true, cid: sc.cid, ref: null, draft: null, flags: {}, lang: sc.lang || "en", outcomeShown: false });
  clearInterval(S.poll);
  chat().replaceChildren(); $("#quick").replaceChildren(); $("#cardTab").replaceChildren("My card");
  $("#sim").textContent = `Demo customer: ${sc.label} · customer's lines are scripted, everything else is live`;
  show("chat");
  try {
    S.draft = await api('/intake/drafts',{customer_id:S.cid});
    tell({type:'draft_started',draft_id:S.draft.draft_id});
    await sc.run();
  } catch (e) {
    add(h("div", { class: "banner err", text: `Something went wrong: ${e.message}` }));
    if (S.draft?.status === 'DRAFT') {
      await api(`/intake/drafts/${S.draft.draft_id}/cancel`,{expected_revision:S.draft.revision}).catch(()=>{});
    }
  }
  S.running = false;
  tell({ type: "done", id });
}


// ---------- Live Clario (Retell): "Get help" -> Text or Call ----------
// The backend starts the Retell chat or web call for the signed-in customer, so Clario already knows who it is
// talking to. Clario's look-ups and the card go through the backend's signed Retell tools; this page only shows the
// conversation and follows the card once Clario files it.
const LIVE_CUSTOMERS = [["CUST-001", "Maria Russo"], ["CUST-002", "Sam Taylor"], ["CUST-003", "Priya Sharma"],
  ["CUST-004", "Minh Nguyen"], ["CUST-005", "Alex"], ["CUST-006", "Jordan Lee"]];
const L = { cid: "CUST-002", mode: null, conv: null, call: null, poll: null };

function liveReset() {
  if (L.call) { try { L.call.stopCall(); } catch { /* already ended */ } }
  clearInterval(L.poll); clearInterval(S.poll);
  Object.assign(L, { mode: null, conv: null, call: null });
  Object.assign(S, { ref: null, cid: L.cid, outcomeShown: false, lang: L.cid === "CUST-004" ? "vi" : "en" });
  chat().replaceChildren(); $("#quick").replaceChildren(); $("#cardTab").replaceChildren("My card");
  show("chat");
}

function getHelp() {
  liveReset();
  const name = LIVE_CUSTOMERS.find(([id]) => id === L.cid)[1].split(" ")[0];
  add(h("div", { class: "msgb c" }, `Hi ${name}. How would you like to get help?`,
    h("span", { class: "gloss", text: "You're signed in, so Clario already knows it's you. No security questions." })));
  $("#quick").replaceChildren(
    h("button", { class: "help-opt", onclick: liveText }, "💬 Text Clario"),
    h("button", { class: "help-opt", onclick: liveCall }, "📞 Call Clario"));
  $("#sim").textContent = "Live Clario (Retell) · synthetic customer data · no real money moves";
}

function followCase() {
  clearInterval(L.poll);
  L.poll = setInterval(async () => {
    if (!L.conv || S.ref) return clearInterval(L.poll);
    const st = await api(`/clario/session/${encodeURIComponent(L.conv)}`).catch(() => null);
    if (st?.case_reference) filed(st.case_reference);
  }, 2000);
}
function filed(ref) {
  if (S.ref) return;
  S.ref = ref;
  add(h("div", { class: "sys chip ok", text: `Card ${ref} sent to the team. Follow it under "My card".` }));
  $("#cardTab").replaceChildren("My card", h("span", { class: "dot" }));
  startPolling();
}

async function liveText() {
  liveReset(); L.mode = "text";
  const typing = add(h("div", { class: "typing", text: "•••" }));
  try {
    const r = await api("/clario/session/chat", { customer_id: L.cid });
    L.conv = r.conversation_id;
    typing.remove();
    r.messages.forEach((m) => add(h("div", { class: "msgb c", text: m })));
    if (!r.messages.length) add(h("div", { class: "msgb c", text: "Hi, I'm Clario, Westpac's AI assistant. What can I help with?" }));
  } catch (e) { typing.remove(); return add(h("div", { class: "banner err", text: `Can't reach Clario: ${e.message}` })); }
  const input = h("input", { class: "composer-in", placeholder: "Message Clario", "aria-label": "Message Clario", maxlength: "2000" });
  const send = async (text) => {
    text = (text ?? input.value).trim();
    if (!text || L.mode !== "text") return;
    input.value = "";
    add(h("div", { class: "msgb u", text }));
    const t = add(h("div", { class: "typing", text: "•••" }));
    try {
      const r = await api(`/clario/session/chat/${encodeURIComponent(L.conv)}`, { content: text });
      t.remove();
      r.messages.forEach((m) => add(h("div", { class: "msgb c", text: m })));
      if (r.case_reference) filed(r.case_reference);
    } catch (e) { t.remove(); add(h("div", { class: "banner err", text: `Message not sent: ${e.message}` })); }
  };
  L.send = send;
  $("#quick").replaceChildren(h("form", { class: "composer", onsubmit: (e) => { e.preventDefault(); send(); } },
    input, h("button", { class: "btn primary", type: "submit", text: "Send" })));
  input.focus();
}

async function liveCall() {
  liveReset(); L.mode = "call";
  const status = add(h("div", { class: "sys chip", text: "Calling Clario…" }));
  const lines = h("div", { class: "transcript" });
  add(lines);
  try {
    const [{ RetellWebClient }, r] = await Promise.all([import("./retell-web.js"), api("/clario/session/call", { customer_id: L.cid })]);
    L.conv = r.conversation_id;
    const call = new RetellWebClient();
    L.call = call;
    call.on("call_started", () => { status.textContent = "Connected · Clario is listening"; });
    call.on("update", (u) => {
      lines.replaceChildren(...(u.transcript || []).map((m) =>
        h("div", { class: `msgb ${m.role === "agent" ? "c" : "u"}`, text: m.content })));
      scroll();
    });
    call.on("call_ended", () => { status.textContent = "Call ended"; L.call = null; $("#quick").replaceChildren(); });
    call.on("error", (err) => { status.textContent = `Call problem: ${err?.message || err}`; L.call = null; });
    await call.startCall({ accessToken: r.access_token });
    followCase();
    $("#quick").replaceChildren(h("button", { class: "help-opt end", onclick: () => call.stopCall() }, "End call"));
  } catch (e) { status.textContent = `Can't start the call: ${e.message}`; L.call = null; }
}

function liveBar() {
  const sel = h("select", { "aria-label": "Signed-in demo customer", onchange: (e) => { L.cid = e.target.value; getHelp(); } },
    LIVE_CUSTOMERS.map(([id, n]) => h("option", { value: id, selected: id === L.cid, text: `${n} (${id})` })));
  return h("div", { class: "livebar" }, h("span", { class: "small", text: "Live · signed in as" }), sel,
    h("button", { class: "btn small primary", text: "Get help", onclick: getHelp }));
}

function trackOnly(ref) {
  S.ref = ref;
  $("#picker").remove();
  document.querySelector(".ph-tabs").remove();
  $("#chat").remove(); $("#quick").remove();
  $("#sim").textContent = "Live case from Clario (voice). Updates every 2 s.";
  show("card");
  startPolling();
}

function init() {
  if (embedded) document.body.classList.add("embed");
  const p = new URLSearchParams(location.search);
  S.speed = Math.min(3, Math.max(0.5, Number(p.get("speed")) || 1));
  document.querySelectorAll(".ph-tabs button").forEach((b) => b.addEventListener("click", () => show(b.dataset.v)));
  $("#person").addEventListener("click", () => {
    if (L.mode === "text") return L.send("I want to talk to a person.");
    if (!S.running && !L.mode) play("jordan");
  });
  if (p.get("track")) return trackOnly(p.get("track"));
  $("#picker").replaceChildren(liveBar(), h("div", { class: "scripted" }, h("span", { class: "small muted", text: "Scripted scenes:" }),
    ...Object.entries(SCENES).map(([k, s]) => h("button", { class: "btn small", text: s.label, onclick: () => play(k) }))));
  if (embedded) add(h("p", { class: "muted small", text: "Pick a customer in the bar above to start." }));
  else getHelp();
  renderCard();
  window.addEventListener("message", (e) => {
    if (e.origin !== location.origin) return;
    if (e.data?.type === "play") play(String(e.data.id));
    if (e.data?.type === "speed") S.speed = Number(e.data.speed) || 1;
  });
  tell({ type: "ready", scenes: Object.fromEntries(Object.entries(SCENES).map(([k, s]) => [k, s.label])) });
}
init();
