"""FastAPI app for Beacon Assist: Clario's intake, Prorio's priority list and proposals, and the officer actions.

Run: uvicorn main:app --reload --port 8000
"""
import hmac
import os

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import mock_data as md
import store
from models import Decision, OfficerNote, OwnerDecision, Rerank, RetellPayload
from prorio import learning, protocols
from prorio.propose import ACTIONS, ACTION_TEXT
from prorio.score import BAND_LABEL, BAND_MESSAGE, HANDOFF

app = FastAPI(title="Beacon Assist backend (Prorio)")
# ponytail: wide-open CORS for the demo, restrict to the dashboard's origin if this leaves localhost
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


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


def _check_secret(x_webhook_secret: str = Header(default="")):
    """Intake only. If NRY_WEBHOOK_SECRET is set, callers must send it as x-webhook-secret."""
    secret = os.environ.get("NRY_WEBHOOK_SECRET", "")
    if secret and not hmac.compare_digest(x_webhook_secret.encode(), secret.encode()):
        raise HTTPException(401, "missing or wrong x-webhook-secret")


def _case(case_id):
    case = store.CASES.get(case_id)
    if not case:
        raise HTTPException(404, "case not found")
    return case


# ---- Intake from Clario -------------------------------------------------------------------------------------

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
def post_pickup(case_id: str, body: OfficerNote):
    return store.public(_errors(store.pick_up, case_id, body.officer))


@app.post("/case/{case_id}/decision")
def post_decision(case_id: str, body: Decision):
    return store.public(_errors(store.decide, case_id, body.decision, body.actions, body.officer, body.note,
                                body.suggest_update))


@app.post("/case/{case_id}/complete")
def post_complete(case_id: str, body: OfficerNote):
    return store.public(_errors(store.complete, case_id, body.officer, body.note))


@app.post("/case/{case_id}/rerank")
def post_rerank(case_id: str, body: Rerank):
    return store.public(_errors(store.rerank, case_id, body.band, body.score, body.reason, body.officer))


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
def post_rollback(issue_type: str, body: OwnerDecision):
    if issue_type not in protocols.BASE:
        raise HTTPException(404, "unknown issue type")
    version = _errors(protocols.rollback, issue_type)
    return {"issue_type": issue_type, "version": version, "rolled_back_by": body.owner}


@app.get("/suggestions")
def get_suggestions():
    return {"threshold": learning.THRESHOLD, "suggestions": learning.listing()}


@app.post("/suggestions/{sid}/approve")
def post_approve(sid: str, body: OwnerDecision):
    return _errors(learning.approve, sid, body.owner, store._now_str())


@app.post("/suggestions/{sid}/reject")
def post_reject(sid: str, body: OwnerDecision):
    return _errors(learning.reject, sid, body.owner, body.reason, store._now_str())


# ---- Reference and admin --------------------------------------------------------------------------------------

@app.get("/meta")
def get_meta():
    """Fixed lists the dashboard needs, so it never hard-codes them."""
    return {"actions": [{"action": a, "label": ACTION_TEXT[a]} for a in ACTIONS], "bands": BAND_LABEL,
            "issue_types": list(protocols.ISSUE_TYPES), "demo_now": md.demo_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "suggestion_threshold": learning.THRESHOLD}


@app.post("/admin/reset")
def admin_reset():  # demo rehearsal only: wipes cases, mock account changes and the learning loop (no auth)
    store.reset()
    return {"ok": True}
