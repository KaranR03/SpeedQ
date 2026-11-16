"""Customer Service Officer dashboard. Run: streamlit run officer_app.py  (backend on :8000, or set NRY_API).

Shows Prorio's priority list and proposals. Every list it needs (actions, bands) comes from the backend.
"""
import os

import requests
import streamlit as st

API = os.environ.get("NRY_API", "http://localhost:8000")
OFFICER = os.environ.get("NRY_OFFICER", "officer")
POLL = 2  # seconds
OPEN = ("QUEUED", "AWAITING_CUSTOMER_CONFIRM", "IN_REVIEW")
BAND = {  # colour AND text, so it reads on a projector and without colour
    "P1": ("#c62828", "P1 CRITICAL"), "P2": ("#e65100", "P2 HIGH"),
    "P3": ("#1565c0", "P3 MEDIUM"), "P4": ("#546e7a", "P4 LOW"),
}
STAGES = ("RECEIVED", "RANKED", "WITH_OFFICER", "ACTION_TAKEN", "DONE")
STAGE_TEXT = ("Received", "Ranked", "With an officer", "Action taken", "Done")
st.set_page_config(page_title="Officer dashboard", layout="wide")
st.session_state.setdefault("selected", None)
st.session_state.setdefault("page", "Priority list")
st.session_state.setdefault("flash", None)


def api(path):
    r = requests.get(f"{API}{path}", timeout=2)
    r.raise_for_status()
    return r.json()


def badge(band):
    colour, text = BAND[band]  # fixed strings only: never put backend text into HTML
    return (f"<span style='background:{colour};color:#fff;padding:4px 10px;border-radius:6px;"
            f"font-weight:700;white-space:nowrap'>{text}</span>")


@st.cache_data(ttl=60)
def meta():
    return api("/meta")


def select(case_id):
    st.session_state.selected = case_id
    st.session_state.flash = None
    if case_id:  # opening a case tells the customer "With an officer"
        try:
            requests.post(f"{API}/case/{case_id}/pickup", json={"officer": OFFICER}, timeout=5)
        except requests.RequestException:
            pass


def send(path, body, label):
    """POST from a button callback and remember the outcome to show on the case."""
    try:
        r = requests.post(f"{API}{path}", json={**body, "officer": OFFICER}, timeout=5)
        if r.ok:
            st.session_state.flash = ("success", f"{label} recorded. Status: {r.json()['status']}")
        else:
            st.session_state.flash = ("error", f"{label} failed: {r.json().get('detail', r.text)}")
    except requests.RequestException as e:
        st.session_state.flash = ("error", f"Backend unreachable: {e}")


def decide(case_id, decision):
    note = st.session_state.get(f"note-{case_id}", "").strip()
    send(f"/case/{case_id}/decision", {"decision": decision, "note": note}, decision)


# Callbacks below read widget state, not args: args are captured at the previous render,
# so text typed just before the click could be missed.
def modify(case_id):
    actions = [{"action": a} for a in st.session_state[f"mod-{case_id}"]]
    send(f"/case/{case_id}/decision", {"decision": "MODIFY", "actions": actions,
                                       "suggest_update": st.session_state[f"suggest-{case_id}"],
                                       "note": st.session_state.get(f"note-{case_id}", "").strip()}, "MODIFY")


def complete(case_id):
    send(f"/case/{case_id}/complete", {"note": st.session_state[f"done-{case_id}"]}, "Completed")


def owner(sid, verb):
    try:
        r = requests.post(f"{API}/suggestions/{sid}/{verb}", json={"owner": OFFICER, "reason": "Not adopted"},
                          timeout=5)
        st.session_state.flash = ("success" if r.ok else "error",
                                  f"{sid} {verb}d" if r.ok else r.json().get("detail", r.text))
    except requests.RequestException as e:
        st.session_state.flash = ("error", f"Backend unreachable: {e}")


def rerank(case_id):
    why = st.session_state[f"rrwhy-{case_id}"].strip()
    if not why:
        st.session_state.flash = ("error", "Give a reason to re-rank.")
        return
    send(f"/case/{case_id}/rerank", {"band": st.session_state[f"rrband-{case_id}"], "reason": why}, "Re-rank")


def reset_demo():
    try:
        requests.post(f"{API}/admin/reset", timeout=5).raise_for_status()
        select(None)
    except requests.RequestException as e:
        st.session_state.flash = ("error", f"Reset failed: {e}")


def waiting(mins):
    return f"{mins} min" if mins else "just now"


@st.fragment(run_every=POLL)
def queue_view():
    st.title("Priority list")
    try:
        cases = api("/queue")
    except requests.RequestException as e:
        st.error(f"Backend unreachable at {API}: {e}")
        return
    st.caption(f"{len(cases)} waiting · refreshes every {POLL}s")
    if not cases:
        st.info("No cases waiting.")
    for c in cases:
        p = c["priority"]
        with st.container(border=True):
            cols = st.columns([1.4, 1.4, 1.8, 0.9, 0.9, 3.6, 1.1])
            cols[0].markdown(badge(p["band"]), unsafe_allow_html=True)
            cols[1].markdown(f"**{c['customer_name']}**  \n{c['case_id']}")
            cols[2].write(c["issue_type"].replace("_", " ").title())
            cols[3].metric("Score", p["score"])
            cols[4].write(waiting(p["minutes_waiting"]))
            cols[5].write(c["summary_en"])
            if cols[6].button("Open", key=f"open-{c['case_id']}"):
                select(c["case_id"])
                st.rerun()  # inside an auto-refreshing fragment: rerun the whole page to switch views
            who = "AI after your approval" if p["executor"] == "AI_AFTER_APPROVAL" else "Officer"
            st.caption(f"Who acts: {who} · " + " · ".join(p["reasons"]))


def tracker(card_status):
    done = STAGES.index(card_status["stage"])
    st.caption("Customer sees: " + "  →  ".join(f"**{t}** ✓" if i < done else (f"**[{t}]**" if i == done else t)
                                                  for i, t in enumerate(STAGE_TEXT)))


@st.fragment(run_every=POLL)
def case_view(case_id):
    if st.button("← Back to priority list"):
        select(None)
        st.rerun()  # whole page, not just this fragment
    try:
        c = api(f"/case/{case_id}")
    except requests.RequestException as e:
        st.error(f"Could not load {case_id}: {e}")
        return
    p, prop = c["priority"], c["proposed_solution"]
    st.markdown(f"## {c['customer_name']} &nbsp; {badge(p['band'])}", unsafe_allow_html=True)
    tracker(c["card_status"])
    left, right = st.columns(2)
    with left:
        st.write(f"**Case** {c['case_id']} · **Customer** {c['customer_id']} · **Status** {c['status']}")
        st.write(f"**Issue** {c['issue_type'].replace('_', ' ').title()} · **Score** {p['score']} / 100")
        st.write(f"**Linked transactions** {', '.join(c['linked_transactions']) or 'none'}")
        st.write(f"**Verified account signals** {', '.join(p['signals']) or 'none'}")
        st.write(f"**From the conversation** {', '.join(p['caller_signals']) or 'none'}")
        if c["language"] != "en":
            st.write(f"**Language** {c['language_label']} (translated)")
            if st.toggle("Show original language summary", key=f"orig-{case_id}"):
                st.info(c["summary_customer_lang"] or "No original summary recorded.")
        st.write(c["summary_en"])
        if c.get("contacts", 1) > 1:
            st.caption(f"Customer has contacted us {c['contacts']} times about this; one card, updated.")
    with right:
        st.subheader("Why it ranks here")
        for r in p["reasons"]:
            st.write(f"- {r}")
        est = c["retell_estimate"]
        if est.get("score") is not None:
            st.caption(f"Clario's estimate (not used for ranking): {est['score']:g} {est.get('band') or ''}")
        with st.expander("What Prorio did"):
            for t in c["prorio_trace"]:
                st.write(f"**{t['step']}**: {t['detail']}")

    proto = prop["protocol"]
    st.subheader("Proposed solution")
    st.write(f"Protocol **{proto['title']}** · v{proto['version']}"
             + (f" · updated by officers ({len(proto['change_log'])} change)" if proto["change_log"] else ""))
    who = ("The AI carries these out after you approve" if prop["executor"] == "AI_AFTER_APPROVAL"
           else "You (the officer) carry these out")
    st.write(f"**Actions** · {who}")
    for a in prop["actions"]:
        params = ", ".join(f"{k}: {v}" for k, v in a["params"].items())
        st.write(f"- {a['label']}" + (f" ({params})" if params else ""))
    if not prop["actions"]:
        st.write("- No automatic actions")
    for d in prop["already_done"]:
        st.write(f"- ✓ {d}")
    if prop["officer_tasks"]:
        st.write("**Officer tasks**")
        for t in prop["officer_tasks"]:
            st.write(f"- {t}")
    if prop["required_checks"]:
        st.write("**Required checks** · " + " · ".join(prop["required_checks"]))
    st.write("**Message to the customer**")
    st.info(prop["customer_message"])
    if prop["customer_message_missing"]:
        st.caption("Fill in before sending: " + ", ".join(prop["customer_message_missing"]))
    with st.expander("Protocol steps and sources"):
        for step in prop["steps"]:
            st.write(f"- **{step['who']}**: {step['step']}")
        for t in prop["timeframes"]:
            st.write(f"- ⏱ {t['what']}: {t['rule']}")
        for src in proto["sources"]:
            st.write(f"- [{src['title']}]({src['url']})")

    if st.session_state.flash:
        getattr(st, st.session_state.flash[0])(st.session_state.flash[1])
    if c["status"] in OPEN:
        st.text_input("Note (optional, shown to the protocol owner)", key=f"note-{case_id}")
        b1, b2, b3 = st.columns(3)
        approve = "Approve: AI carries it out" if prop["executor"] == "AI_AFTER_APPROVAL" else "Approve"
        b1.button(approve, type="primary", width="stretch", key=f"approve-{case_id}",
                  on_click=decide, args=(case_id, "APPROVE"))
        b3.button("Manual", width="stretch", key=f"manual-{case_id}", help="Ignore the proposal and handle it yourself",
                  on_click=decide, args=(case_id, "MANUAL"))
        with b2.popover("Modify", width="stretch"):
            acts = [a["action"] for a in meta()["actions"]]
            st.multiselect("Actions to run", acts, key=f"mod-{case_id}",
                           default=list(dict.fromkeys(a["action"] for a in prop["actions"])))
            st.checkbox("Suggest as a protocol update?", value=True, key=f"suggest-{case_id}")
            st.button("Approve edited list", key=f"modok-{case_id}", on_click=modify, args=(case_id,))
        with st.expander("Re-rank this case"):
            st.selectbox("New band", list(BAND), key=f"rrband-{case_id}")
            st.text_input("Reason (required)", key=f"rrwhy-{case_id}")
            st.button("Re-rank", key=f"rr-{case_id}", on_click=rerank, args=(case_id,))
    elif c["status"] == "MANUAL" and c["card_status"]["stage"] != "DONE":
        st.warning("You're handling this manually. Say what you did to close it and update the customer.")
        st.text_input("What was done (sent to the customer)", key=f"done-{case_id}")
        st.button("Mark done", key=f"donebtn-{case_id}", on_click=complete, args=(case_id,))
    else:
        st.success(f"Status: {c['status']} (decision: {c['officer_decision']})")
        if c.get("outcome"):
            st.caption(f"Sent to the customer: {c['outcome']['message']}")
    st.subheader("Audit log")
    try:
        log = api(f"/audit/{case_id}")
    except requests.RequestException:
        log = []
    if log:
        st.dataframe([{"time": e["ts"], "who": e["actor"], "action": e["action"], "result": e["result"],
                       "before": str(e["before"] or ""), "after": str(e["after"] or "")} for e in log],
                     hide_index=True, width="stretch")
    else:
        st.caption("No actions yet.")


def suggestions_view():
    st.title("Protocol suggestions")
    st.caption("Officers teach, leads approve. A suggestion is offered to the protocol owner once it has been made "
               "enough times.")
    if st.session_state.flash:
        getattr(st, st.session_state.flash[0])(st.session_state.flash[1])
    try:
        data = api("/suggestions")
    except requests.RequestException as e:
        st.error(f"Backend unreachable at {API}: {e}")
        return
    if not data["suggestions"]:
        st.info("No suggestions yet. They appear when an officer modifies a proposal or handles a case manually.")
    for sg in reversed(data["suggestions"]):
        with st.container(border=True):
            ch = sg["change"]
            what = ("handled manually" if sg["kind"] == "MANUAL" else
                    f"add {', '.join(ch['add_actions']) or 'nothing'}; remove {', '.join(ch['remove_actions']) or 'nothing'}")
            st.write(f"**{sg['id']}** · {sg['issue_type']} v{sg['from_version']} → v{sg['proposed_version']} · {what}")
            st.caption(f"Suggested {sg['count']} of {data['threshold']} times by {', '.join(sg['officers'])} · "
                       f"cases {', '.join(sg['cases'])} · status {sg['status']}")
            for n in sg["notes"][-3:]:
                st.write(f"> {n}")
            if sg["status"] == "READY_FOR_OWNER":
                a, b = st.columns(2)
                a.button("Approve as new version", key=f"sa-{sg['id']}", on_click=owner, args=(sg["id"], "approve"))
                b.button("Reject", key=f"sr-{sg['id']}", on_click=owner, args=(sg["id"], "reject"))


st.sidebar.radio("View", ["Priority list", "Protocol suggestions"], key="page")
st.sidebar.button("Reset demo data", on_click=reset_demo)
if st.session_state.page == "Protocol suggestions":
    suggestions_view()
elif st.session_state.selected:
    case_view(st.session_state.selected)
else:
    queue_view()
