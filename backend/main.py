"""FastAPI app for Westpac SpeedQ: Clario's intake, Prorio's priority list and proposals, and the officer actions.

Run: uvicorn main:app --reload --port 8000
"""
import hmac
import os
from pathlib import Path


def _load_env_file(path=Path(__file__).resolve().parent / ".env"):
    """Read backend/.env (KEY=value lines, git-ignored) so a teammate can drop in the shared file and run.
    Variables already set in the environment win."""
    if path.is_file():
        for line in path.read_text().splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and key and not key.startswith("#"):
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_env_file()  # before the imports below read their settings
import asyncio
import json

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

import mock_data as md
import store
import workspace_insights
import workspace_events
import intake_drafts
import clario_live
from web_security import actor, auth_enabled, is_local, browser_security, DEMO_OFFICERS
from models import Decision, OfficerNote, OwnerDecision, Rerank, RetellPayload, DraftStart, DraftUpdate, DraftConfirm, DraftRevision
from prorio import evidence, learning, protocols
from prorio.propose import ACTIONS, ACTION_TEXT
from prorio.score import BAND_LABEL, BAND_MESSAGE, FIRST_SEEN, HANDOFF

app = FastAPI(title="Westpac SpeedQ backend (Prorio)", docs_url=None, redoc_url=None)
app.middleware("http")(browser_security)
_origins = [origin.strip() for origin in os.environ.get("NRY_CORS_ORIGINS", "").split(",")
            if origin.strip() and origin.strip() != "*"]
if _origins:
    app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["GET", "POST"],
                       allow_headers=["content-type", "x-webhook-secret", "authorization", "x-demo-officer"])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=[
    h.strip() for h in os.environ.get("NRY_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],testserver").split(",")
    if h.strip()
])
app.include_router(clario_live.router)
FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
WEB = Path(__file__).resolve().parent.parent / "web"


@app.get("/assets/{filename}", include_in_schema=False)
def frontend_asset(filename: str):
    # Do not expose tests, package manifests, reports or node_modules as web assets.
    if filename not in {"app.js", "visuals.js", "intake.js", "collaboration.css", "insights.css", "styles.css", "support-headset.svg", "docs.js"}:
        raise HTTPException(404, "asset not found")
    return FileResponse(FRONTEND / filename)


@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(FRONTEND / "index.html")


@app.get("/docs", include_in_schema=False)
def api_reference():
    return FileResponse(FRONTEND / "docs.html")


@app.get("/redoc", include_in_schema=False)
def api_reference_redirect():
    return RedirectResponse("/docs")


@app.get("/workspace/session")
def workspace_session(request: Request):
    return {"officer": request.state.staff_actor, "authenticated": auth_enabled(), "demo": not auth_enabled(),
            "available_officers": list(dict.fromkeys((request.state.staff_actor, *DEMO_OFFICERS))) if not auth_enabled() else []}


@app.get("/workspace/intake")
def workspace_intake():
    return intake_drafts.listing()


@app.get("/workspace/events")
async def workspace_event_stream(request: Request):
    async def changes():
        previous = None
        heartbeat = asyncio.get_running_loop().time()
        while not await request.is_disconnected():
            current = workspace_events.version()
            now = asyncio.get_running_loop().time()
            if current != previous:
                yield f"event: workspace\nid: {current}\ndata: {json.dumps({'revision': current})}\n\n"
                previous, heartbeat = current, now
            elif now - heartbeat >= 15:
                yield ": heartbeat\n\n"
                heartbeat = now
            await asyncio.sleep(0.5)
    return StreamingResponse(changes(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})


@app.get("/workspace/cases")
def workspace_cases():
    return store.workspace()


@app.get("/workspace/insights")
def get_workspace_insights():
    return store.insights()


@app.get("/case/{case_id}/context")
def get_customer_context(case_id: str):
    return workspace_insights.customer_context(_case(case_id))


def _errors(fn, *args):
    """Map store errors to HTTP: KeyError 404, RuntimeError 409, ValueError 422."""
    try:
        return fn(*args)
    except KeyError:
        raise HTTPException(404, "not found")
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


def _check_secret(request: Request, x_webhook_secret: str = Header(default="")):
    """Remote intake always requires a secret; local demo intake may remain open."""
    secret = os.environ.get("NRY_WEBHOOK_SECRET", "")
    local = is_local(request)
    if (auth_enabled() or not local) and not secret:
        raise HTTPException(503, "Configure NRY_WEBHOOK_SECRET before enabling remote or authenticated intake.")
    if secret and not hmac.compare_digest(x_webhook_secret.encode(), secret.encode()):
        raise HTTPException(401, "missing or wrong x-webhook-secret")


def _case(case_id):
    case = store.CASES.get(case_id)
    if not case:
        raise HTTPException(404, "case not found")
    return case


# ---- Intake from Clario -------------------------------------------------------------------------------------

@app.post("/intake/drafts", dependencies=[Depends(_check_secret)])
def start_draft(body: DraftStart):
    return _errors(intake_drafts.start, body.customer_id)


@app.get("/intake/drafts/{draft_id}")
def get_draft(draft_id: str):
    with store._lock:
        return intake_drafts.public(_errors(intake_drafts._get, draft_id))


@app.post("/intake/drafts/{draft_id}", dependencies=[Depends(_check_secret)])
def update_draft(draft_id: str, body: DraftUpdate):
    return _errors(intake_drafts.update, draft_id, body)


@app.post("/intake/drafts/{draft_id}/confirm", dependencies=[Depends(_check_secret)])
def confirm_draft(draft_id: str, body: DraftConfirm):
    return _errors(intake_drafts.confirm, draft_id, body)


@app.post("/intake/drafts/{draft_id}/cancel", dependencies=[Depends(_check_secret)])
def cancel_draft(draft_id: str, body: DraftRevision):
    return _errors(intake_drafts.cancel, draft_id, body.expected_revision)

@app.post("/webhook/retell", dependencies=[Depends(_check_secret)])
def webhook_retell(payload: RetellPayload):
    """Short reply for Clario to act on during the call: never the score."""
    case = _errors(store.create_case, payload)
    updated = case.pop("_updated_existing", False)
    queued = case["status"] != "TIER1_RESOLVED"
    band = case["priority"]["band"]
    return {"case_reference": case["case_id"], "queued": queued,
            "priority_band": band if queued else None,
            "handoff": HANDOFF[band] if queued else "NONE",
            "caller_message": BAND_MESSAGE[band] if queued else "Resolved, no officer needed.",
            "updated_existing_case": updated}


@app.post("/case", dependencies=[Depends(_check_secret)])
def post_case(payload: RetellPayload):  # same body as the webhook, for hand-posted test cases
    case = _errors(store.create_case, payload)
    case.pop("_updated_existing", None)
    return store.public(case)


# ---- Priority list and cases (officer dashboard) --------------------------------------------------------------

@app.get("/queue")
def get_queue():
    return store.queue()


@app.get("/case/{case_id}")
def get_case(case_id: str):
    case = _case(case_id)
    store.rescore(case)
    return store.public(case)


@app.get("/case/{case_id}/proposal")
def get_proposal(case_id: str):
    return _case(case_id)["proposed_solution"]


@app.get("/case/{case_id}/trace")
def get_trace(case_id: str):
    """What Prorio did, step by step."""
    return _case(case_id)["prorio_trace"]


@app.get("/case/{case_id}/status")
def get_status(case_id: str):
    """The customer's view of their card: status tracker and outcome, no score or internal notes."""
    return store.customer_view(_case(case_id))


@app.post("/case/{case_id}/pickup")
def post_pickup(case_id: str, body: OfficerNote, request: Request):
    return store.public(_errors(store.pick_up, case_id, actor(request, body.officer), body.expected_revision))


@app.post("/case/{case_id}/release")
def release_case(case_id: str, body: OfficerNote, request: Request):
    return store.public(_errors(store.release, case_id, actor(request, body.officer), body.note, body.expected_revision))


@app.post("/case/{case_id}/decision")
def post_decision(case_id: str, body: Decision, request: Request):
    return store.public(_errors(store.decide, case_id, body.decision, body.actions, actor(request, body.officer), body.note,
                                body.suggest_update, body.expected_revision))


@app.post("/case/{case_id}/complete")
def post_complete(case_id: str, body: OfficerNote, request: Request):
    return store.public(_errors(store.complete, case_id, actor(request, body.officer), body.note, body.expected_revision))


@app.post("/case/{case_id}/rerank")
def post_rerank(case_id: str, body: Rerank, request: Request):
    return store.public(_errors(store.rerank, case_id, body.band, body.score, body.reason, actor(request, body.officer), body.expected_revision))


@app.get("/audit/{case_id}")
def get_audit(case_id: str):
    return _case(case_id)["audit_log"]


# ---- Protocol Database and the learning loop ------------------------------------------------------------------

@app.get("/protocols")
def get_protocols():
    rows = protocols.summary()
    for r in rows:
        r["decisions"] = learning.STATS.get(r["issue_type"], {"APPROVE": 0, "MODIFY": 0, "MANUAL": 0})
    return rows


@app.get("/protocols/{issue_type}")
def get_protocol(issue_type: str):
    p = protocols.get(issue_type)
    if not p:
        raise HTTPException(404, "unknown issue type")
    return {**p, "sources": protocols.sources_for(p)}


@app.post("/protocols/{issue_type}/rollback")
def post_rollback(issue_type: str, body: OwnerDecision, request: Request):
    if issue_type not in protocols.BASE:
        raise HTTPException(404, "unknown issue type")
    version = _errors(protocols.rollback, issue_type)
    return {"issue_type": issue_type, "version": version, "rolled_back_by": actor(request, body.owner)}


@app.get("/suggestions")
def get_suggestions():
    return {"threshold": learning.THRESHOLD, "suggestions": learning.listing()}


@app.post("/suggestions/{sid}/approve")
def post_approve(sid: str, body: OwnerDecision, request: Request):
    return _errors(learning.approve, sid, actor(request, body.owner), store._now_str())


@app.post("/suggestions/{sid}/reject")
def post_reject(sid: str, body: OwnerDecision, request: Request):
    return _errors(learning.reject, sid, actor(request, body.owner), body.reason, store._now_str())


@app.post("/demo/seed")
def seed_demo():
    """Add a small synthetic queue, preserving all existing cases and decisions."""
    if auth_enabled():
        raise HTTPException(403, "Sample loading is available only in local demo mode.")
    samples = [
        {"customer_id": "CUST-001", "customer_name": "Maria R.", "issue_type": "SCAM_IN_PROGRESS",
         "linked_transactions": "TX-9001", "risk_signals": "CUSTOMER_REPORTS_PRESSURE,VULNERABILITY_CUES",
         "summary_en": "A caller claiming to be from the bank asked Maria to move $4,800 to a new account.",
         "case_reference": "DEMO-0412"},
        {"customer_id": "CUST-006", "customer_name": "Jordan L.", "issue_type": "ACCOUNT_ACCESS",
         "risk_signals": "ESSENTIALS_AT_RISK", "summary_en": "Locked out after an unfamiliar password change. Needs access to buy groceries.",
         "case_reference": "DEMO-0413"},
        {"customer_id": "CUST-003", "customer_name": "Priya S.", "issue_type": "FRAUD_UNAUTHORISED",
         "linked_transactions": "TX-7001", "card_locked": True,
         "summary_en": "An unrecognised $89 subscription charge. Priya has already locked her card.",
         "case_reference": "DEMO-0414"},
        {"customer_id": "CUST-004", "customer_name": "Minh N.", "issue_type": "MONEY_MISSING",
         "linked_transactions": "TX-8001", "language": "vi", "language_label": "Vietnamese",
         "summary_en": "A $650 rent payment has not reached the landlord. Vietnamese language support requested.",
         "summary_customer_lang": "Mất khoản tiền thuê nhà $650", "case_reference": "DEMO-0415"},
        {"customer_id": "CUST-002", "customer_name": "Sam T.", "issue_type": "CARD_DELIVERY",
         "summary_en": "Replacement card has not arrived. Would like an update on the delivery date.",
         "case_reference": "DEMO-0416"},
    ]
    added = 0
    for sample in samples:
        if sample["case_reference"] not in store.CASES and not any(
            c["customer_id"] == sample["customer_id"] and c["issue_type"] == sample["issue_type"]
            and c["status"] in store.QUEUE_STATUSES for c in store.CASES.values()
        ):
            store.create_case(RetellPayload(**sample))
            added += 1
    return {"added": added}


# ---- Reference and admin --------------------------------------------------------------------------------------

@app.get("/meta")
def get_meta():
    """Fixed lists the dashboard needs, so it never hard-codes them."""
    return {"actions": [{"action": a, "label": ACTION_TEXT[a]} for a in ACTIONS], "bands": BAND_LABEL,
            "signal_labels": evidence.SIGNALS, "first_seen_label": FIRST_SEEN,
            "issue_types": list(protocols.ISSUE_TYPES), "demo_now": md.demo_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "suggestion_threshold": learning.THRESHOLD}


@app.post("/admin/reset")
def admin_reset():  # demo rehearsal only: wipes cases, mock account changes and the learning loop (no auth)
    store.reset()
    return {"ok": True}


# ---- Clario's read-only look-ups (the signed-in customer's own data) ---------------------------------------------

@app.get("/clario/{customer_id}/lookup")
def clario_lookup(customer_id: str):
    """What Clario may read for the signed-in customer: name, card delivery, account status, recent transactions.
    Read-only, one customer, account numbers masked. In the demo the "signed-in" customer is picked by the page."""
    cust = md.get_customer(customer_id)
    if not cust:
        raise HTTPException(404, "unknown customer")
    txs = md.get_recent_transactions(customer_id, days=30, now=md.demo_now())
    return {"customer_id": customer_id, "first_name": cust["name"].split()[0], "language": cust["language"],
            "accounts": [{"type": a["type"], "mask": a["mask"]} for a in cust["accounts"]],
            "safeblock": cust.get("safeblock", False), "card_delivery": md.get_card_delivery_status(customer_id),
            "payees": cust.get("payees", []), "recent_transactions": txs[:10]}


# ---- Web pages: officer dashboard, customer app, side-by-side demo -------------------------------------------------

@app.get("/static/{filename}", include_in_schema=False)
def demo_asset(filename: str):
    if filename not in {"app.css", "officer.js", "customer.js", "demo.js", "dom.js", "retell-web.js"}:
        raise HTTPException(404, "asset not found")
    return FileResponse(WEB / "static" / filename)


@app.get("/officer", include_in_schema=False)
def page_officer():
    return FileResponse(FRONTEND / "index.html")


@app.get("/customer", include_in_schema=False)
def page_customer():
    return FileResponse(WEB / "customer.html")


@app.get("/demo", include_in_schema=False)
def page_demo():
    return FileResponse(WEB / "demo.html")
