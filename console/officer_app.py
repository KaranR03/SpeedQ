"""Officer console. Run: streamlit run officer_app.py  (backend on :8000, or set NRY_API)."""
import os

import requests
import streamlit as st

API = os.environ.get("NRY_API", "http://localhost:8000")
OFFICER = os.environ.get("NRY_OFFICER", "officer")
POLL = 2  # seconds
OPEN = ("QUEUED", "AWAITING_CUSTOMER_CONFIRM", "IN_REVIEW")
ACTIONS = ("ACTIVATE_SAFEBLOCK", "BLOCK_CARD", "RAISE_DISPUTE", "DRAFT_PAYMENT_RECALL",
           "DRAFT_SCAM_REPORT", "BOOK_CALLBACK", "SEND_CUSTOMER_UPDATE")  # backend whitelist
BAND = {  # colour AND text, so it reads on a projector and without colour
    "P1": ("#c62828", "P1 URGENT"), "P2": ("#e65100", "P2 HIGH"),
    "P3": ("#1565c0", "P3 MEDIUM"), "P4": ("#546e7a", "P4 LOW"),
}
st.set_page_config(page_title="Officer console", layout="wide")
st.session_state.setdefault("selected", None)
st.session_state.setdefault("flash", None)


def api(path):
    r = requests.get(f"{API}{path}", timeout=2)
    r.raise_for_status()
    return r.json()


def badge(band):
    colour, text = BAND[band]  # fixed strings only: never put backend text into HTML
    return (f"<span style='background:{colour};color:#fff;padding:4px 10px;border-radius:6px;"
            f"font-weight:700;white-space:nowrap'>{text}</span>")


def select(case_id):
    st.session_state.selected = case_id
    st.session_state.flash = None


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
    send(f"/case/{case_id}/decision", {"decision": decision}, decision)


# Callbacks below read widget state, not args: args are captured at the previous render,
# so text typed just before the click could be missed.
def modify(case_id):
    actions = [{"action": a} for a in st.session_state[f"mod-{case_id}"]]
    send(f"/case/{case_id}/decision", {"decision": "MODIFY", "actions": actions}, "MODIFY")


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
    st.title("Priority queue")
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
            cols = st.columns([1.3, 1.6, 2, 0.8, 0.9, 4, 0.9])
            cols[0].markdown(badge(p["band"]), unsafe_allow_html=True)
            cols[1].markdown(f"**{c['customer_name']}**  \n{c['case_id']}")
            cols[2].write(c["issue_type"].replace("_", " ").title())
            cols[3].metric("Score", p["score"])
            cols[4].write(waiting(p["minutes_waiting"]))
            cols[5].write(c["summary_en"])
            cols[6].button("Open", key=f"open-{c['case_id']}", on_click=select, args=(c["case_id"],))
            st.caption(" · ".join(p["reasons"]))


@st.fragment(run_every=POLL)
def case_view(case_id):
    st.button("← Back to queue", on_click=select, args=(None,))
    try:
        c = api(f"/case/{case_id}")
    except requests.RequestException as e:
        st.error(f"Could not load {case_id}: {e}")
        return
    p = c["priority"]
    st.markdown(f"## {c['customer_name']} &nbsp; {badge(p['band'])}", unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        st.write(f"**Case** {c['case_id']} · **Customer** {c['customer_id']} · **Status** {c['status']}")
        st.write(f"**Issue** {c['issue_type'].replace('_', ' ').title()} · **Score** {p['score']}")
        st.write(f"**Linked transactions** {', '.join(c['linked_transactions']) or 'none'}")
        st.write(f"**Risk signals** {', '.join(c['risk_signals']) or 'none'}")
        if c["language"] != "en":
            st.write(f"**Language** {c['language_label']} (translated)")
            if st.toggle("Show original language summary", key=f"orig-{case_id}"):
                st.info(c["summary_customer_lang"] or "No original summary recorded.")
        st.write(c["summary_en"])
    with right:
        st.subheader("Why it ranks here")
        for r in p["reasons"]:
            st.write(f"- {r}")
        est = c["retell_estimate"]
        if est.get("score") is not None:
            st.caption(f"Voice agent estimate (not used for ranking): {est['score']:g} {est.get('band') or ''}")
    st.subheader("Proposed solution")
    st.write(c["proposed_solution"]["explanation"])
    for a in c["proposed_solution"]["actions"]:
        draft = " (DRAFT, no money moved)" if a["action"].startswith("DRAFT_") else ""
        st.write(f"- `{a['action']}` {a['params'] or ''}{draft}")
    if st.session_state.flash:
        getattr(st, st.session_state.flash[0])(st.session_state.flash[1])
    if c["status"] in OPEN:
        b1, b2, b3 = st.columns(3)
        b1.button("Approve", type="primary", width="stretch", key=f"approve-{case_id}",
                  on_click=decide, args=(case_id, "APPROVE"))
        b3.button("Do it myself", width="stretch", key=f"manual-{case_id}",
                  on_click=decide, args=(case_id, "MANUAL"))
        with b2.popover("Modify", width="stretch"):
            st.multiselect("Actions to run", ACTIONS, key=f"mod-{case_id}",
                           default=[a["action"] for a in c["proposed_solution"]["actions"]])
            st.button("Approve edited list", key=f"modok-{case_id}", on_click=modify, args=(case_id,))
        with st.expander("Re-rank this case"):
            st.selectbox("New band", list(BAND), key=f"rrband-{case_id}")
            st.text_input("Reason (required)", key=f"rrwhy-{case_id}")
            st.button("Re-rank", key=f"rr-{case_id}", on_click=rerank, args=(case_id,))
    else:
        st.success(f"Status: {c['status']} (decision: {c['officer_decision']})")
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


st.sidebar.button("Reset demo data", on_click=reset_demo)
if st.session_state.selected:
    case_view(st.session_state.selected)
else:
    queue_view()
