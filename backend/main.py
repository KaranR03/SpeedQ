"""FastAPI app. Run: uvicorn main:app --reload --port 8000"""
import hmac
import os

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import priority
import store
from models import Decision, Rerank, RetellPayload

app = FastAPI(title="Never Repeat Yourself backend")
# ponytail: wide-open CORS for the demo, restrict to the Streamlit origin if this leaves localhost
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _ingest(payload: RetellPayload):
    try:
        return store.public(store.create_case(payload))
    except ValueError as e:
        raise HTTPException(422, str(e))


def _check_secret(x_webhook_secret: str = Header(default="")):
    """Intake only. If NRY_WEBHOOK_SECRET is set, callers must send it as x-webhook-secret."""
    secret = os.environ.get("NRY_WEBHOOK_SECRET", "")
    if secret and not hmac.compare_digest(x_webhook_secret.encode(), secret.encode()):
        raise HTTPException(401, "missing or wrong x-webhook-secret")


@app.post("/webhook/retell", dependencies=[Depends(_check_secret)])
def webhook_retell(payload: RetellPayload):
    case = _ingest(payload)  # reply is short: the agent reads it aloud, it does not need the whole card
    queued = case["status"] != "TIER1_RESOLVED"
    band = case["priority"]["band"]
    return {"case_reference": case["case_id"], "queued": queued,
            "priority_band": band if queued else None,
            "caller_message": priority.BAND_MESSAGE[band] if queued else "Resolved, no officer needed."}


@app.post("/case", dependencies=[Depends(_check_secret)])
def post_case(payload: RetellPayload):  # same body as the webhook, for hand-posted test cases
    return _ingest(payload)


@app.get("/queue")
def get_queue():
    return store.queue()


@app.post("/case/{case_id}/decision")
def post_decision(case_id: str, body: Decision):
    try:
        return store.public(store.decide(case_id, body.decision, body.actions, body.officer))
    except KeyError:
        raise HTTPException(404, "case not found")
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/case/{case_id}/rerank")
def post_rerank(case_id: str, body: Rerank):
    try:
        return store.public(store.rerank(case_id, body.band, body.score, body.reason, body.officer))
    except KeyError:
        raise HTTPException(404, "case not found")
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/admin/reset")
def admin_reset():  # demo rehearsal only: wipes cases and mock account changes (no auth in the demo)
    store.reset()
    return {"ok": True}


@app.get("/audit/{case_id}")
def get_audit(case_id: str):
    case = store.CASES.get(case_id)
    if not case:
        raise HTTPException(404, "case not found")
    return case["audit_log"]


@app.get("/case/{case_id}")
def get_case(case_id: str):
    case = store.CASES.get(case_id)
    if not case:
        raise HTTPException(404, "case not found")
    store.rescore(case)
    return store.public(case)
