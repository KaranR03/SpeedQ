"""Live Clario: the Retell voice and chat agents, wired to this backend.

Two directions:
- Customer app -> Retell. `/clario/session/*` starts a Retell web call or chat for the signed-in demo customer. The
  customer ID goes to Retell as a dynamic variable, so Clario already knows who it is talking to (no security questions).
- Retell -> backend. Clario's custom functions call `/retell/tools/{name}`. Every request is verified with Retell's
  X-Retell-Signature, and the customer is read from the call/chat's own dynamic variables, never from the model's
  arguments, so the model cannot look up or file a card for someone else.

The live card uses the existing intake drafts: one draft per Retell conversation, revisions tracked here so the
model never has to carry them. Prorio still ranks only the confirmed card.

Settings: RETELL_API_KEY, RETELL_VOICE_AGENT_ID, RETELL_CHAT_AGENT_ID.
"""
import json
import os
import threading

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

import intake_drafts
import mock_data as md
import store
from models import DraftConfirm, DraftUpdate, RetellPayload
from prorio.score import HANDOFF

router = APIRouter()

# conversation id (Retell call_id or chat_id) -> {"customer_id", "draft_id", "case_reference"}
# ponytail: in-memory, so a backend restart mid-conversation starts a fresh draft; persist if that ever matters.
SESSIONS = {}
_lock = threading.Lock()

CARD_FIELDS = ("issue_type", "summary_en", "summary_customer_lang", "linked_transactions", "risk_signals",
               "safeblock_activated", "card_locked")


def _client():
    key = os.environ.get("RETELL_API_KEY", "")
    if not key:
        raise HTTPException(503, "Set RETELL_API_KEY to use live Clario.")
    from retell import Retell
    return Retell(api_key=key)


def _agent(kind):
    agent_id = os.environ.get(f"RETELL_{kind}_AGENT_ID", "")
    if not agent_id:
        raise HTTPException(503, f"Set RETELL_{kind}_AGENT_ID to use live Clario.")
    return agent_id


def _dynamic_vars(customer_id):
    cust = md.get_customer(customer_id)
    if not cust:
        raise HTTPException(404, "unknown customer")
    from main import clario_lookup
    # The signed-in customer's own records (the same masked, no-balance view as lookup_customer), handed over at the
    # start so Clario can answer "where's my card?" straight away, even before its tools can reach this backend.
    context = json.dumps(clario_lookup(customer_id), separators=(",", ":"), default=str)
    return {"customer_id": customer_id, "first_name": cust["name"].split()[0],
            "preferred_language": cust.get("language_label") or cust.get("language", "en"),
            "customer_context": context}


def _remember(conv_id, customer_id):
    with _lock:
        return SESSIONS.setdefault(conv_id, {"customer_id": customer_id, "draft_id": None, "case_reference": None})


# ---- Customer app -> Retell ----------------------------------------------------------------------------------

class SessionStart(BaseModel):
    customer_id: str = Field(min_length=1, max_length=80)


class ChatMessage(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


def _agent_lines(messages):
    return [m.content for m in messages or [] if getattr(m, "role", None) == "agent" and getattr(m, "content", "")]


@router.post("/clario/session/call")
def start_call(body: SessionStart):
    dyn = _dynamic_vars(body.customer_id)
    call = _client().call.create_web_call(agent_id=_agent("VOICE"), retell_llm_dynamic_variables=dyn)
    _remember(call.call_id, body.customer_id)
    # Retell v3: the browser must connect with the transport and ICE servers it chose for this call.
    return {"conversation_id": call.call_id, "access_token": call.access_token, "transport": call.transport,
            "ice_servers": [s.model_dump(exclude_none=True) if hasattr(s, "model_dump") else s
                            for s in call.ice_servers or []]}


@router.get("/clario/session/call/{call_id}/transcript")
def call_transcript(call_id: str):
    """Server-created v3 calls don't stream the transcript to the browser; Retell saves it when the call ends."""
    if call_id not in SESSIONS:
        raise HTTPException(404, "unknown call")
    call = _client().call.retrieve(call_id)
    lines = [{"role": t.role, "content": t.content} for t in call.transcript_object or [] if t.content]
    return {"status": call.call_status, "transcript": lines}


@router.post("/clario/session/chat")
def start_chat(body: SessionStart):
    dyn = _dynamic_vars(body.customer_id)
    client = _client()
    chat = client.chat.create(agent_id=_agent("CHAT"), retell_llm_dynamic_variables=dyn)
    _remember(chat.chat_id, body.customer_id)
    messages = _agent_lines(chat.message_with_tool_calls)
    if not messages:  # a Retell chat agent speaks once the customer writes: tapping "Text Clario" is that "Hi"
        messages = _agent_lines(client.chat.create_chat_completion(chat_id=chat.chat_id, content="Hi").messages)
    return {"conversation_id": chat.chat_id, "messages": messages}


@router.post("/clario/session/chat/{chat_id}")
def send_chat(chat_id: str, body: ChatMessage):
    if chat_id not in SESSIONS:
        raise HTTPException(404, "unknown chat")
    reply = _client().chat.create_chat_completion(chat_id=chat_id, content=body.content)
    return {"messages": _agent_lines(reply.messages), **session_state(chat_id)}


@router.get("/clario/session/{conv_id}")
def session_state(conv_id: str):
    s = SESSIONS.get(conv_id)
    if not s:
        raise HTTPException(404, "unknown conversation")
    return {"case_reference": s["case_reference"], "draft_id": s["draft_id"]}


# ---- Retell -> backend (Clario's custom functions) ------------------------------------------------------------

def _conversation(body):
    """Retell sends the call (voice) or chat (text) object with each function request."""
    conv = body.get("call") or body.get("chat") or {}
    conv_id = conv.get("call_id") or conv.get("chat_id")
    customer_id = (conv.get("retell_llm_dynamic_variables") or {}).get("customer_id")
    if not conv_id or not customer_id or not md.get_customer(customer_id):
        raise HTTPException(422, "No signed-in customer on this conversation.")
    session = _remember(conv_id, customer_id)
    if session["customer_id"] != customer_id:
        raise HTTPException(409, "This conversation belongs to another customer.")
    return customer_id, session


def _listify(value):
    return [x.strip() for x in value.split(",") if x.strip()] if isinstance(value, str) else value


def _draft_update(session, args):
    """Create the conversation's draft on first use, then apply the card fields Clario sent."""
    if not session["draft_id"]:
        session["draft_id"] = intake_drafts.start(session["customer_id"])["draft_id"]
    draft = intake_drafts.DRAFTS[session["draft_id"]]
    if draft["status"] != "DRAFT":
        return draft
    fields = {k: args[k] for k in CARD_FIELDS if args.get(k) not in (None, "", [])}
    for k in ("linked_transactions", "risk_signals"):
        if k in fields:
            fields[k] = _listify(fields[k])
    if fields or args.get("ready_to_confirm"):
        fields["phase"] = "CONFIRMING" if args.get("ready_to_confirm") else "CHECKING"
        intake_drafts.update(draft["draft_id"], DraftUpdate(expected_revision=draft["revision"], **fields))
    return intake_drafts.DRAFTS[session["draft_id"]]


def lookup_customer(customer_id, _args, _session):
    from main import clario_lookup
    return clario_lookup(customer_id)


def update_card(_customer_id, args, session):
    draft = _draft_update(session, args)
    return {"ok": True, "card_status": draft["status"], "issue_type": draft["issue_type"]}


def submit_card(customer_id, args, session):
    if session["case_reference"]:  # already filed: the customer is adding to or correcting their card
        return correct_card(customer_id, args, session)
    draft = _draft_update(session, args)
    result = intake_drafts.confirm(draft["draft_id"], DraftConfirm(expected_revision=draft["revision"],
                                                                   customer_confirmed=True))
    session["case_reference"] = result["case_reference"]
    return result


def correct_card(customer_id, args, session):
    if not session["case_reference"]:
        raise ValueError("There is no submitted card to correct yet; use update_card.")
    case = store.CASES[session["case_reference"]]
    extra = {k: args[k] for k in ("summary_en", "summary_customer_lang") if isinstance(args.get(k), str) and args[k]}
    if args.get("risk_signals"):
        extra["risk_signals"] = ",".join(_listify(args["risk_signals"]))
    card = RetellPayload(customer_id=customer_id, case_reference=session["case_reference"],
                         issue_type=args.get("issue_type") or case["issue_type"],
                         correction=args.get("correction") or args.get("summary_en") or "", **extra)
    updated = store.create_case(card)
    updated.pop("_updated_existing", None)
    band = updated["priority"]["band"]
    return {"case_reference": updated["case_id"], "updated": True, "priority_band": band,
            "handoff": HANDOFF[band], "caller_message": "I've added that to your card. The officer sees it straight away."}


TOOLS = {"lookup_customer": lookup_customer, "update_card": update_card, "submit_card": submit_card,
         "correct_card": correct_card}


def _verify(raw, signature):
    key = os.environ.get("RETELL_API_KEY", "")
    if not key:
        raise HTTPException(503, "Set RETELL_API_KEY so Retell requests can be verified.")
    from retell import Retell
    if not signature or not Retell(api_key=key).verify(raw.decode("utf-8"), key, signature):
        raise HTTPException(401, "Request is not signed by Retell.")


@router.post("/retell/tools/{name}")
async def retell_tool(name: str, request: Request):
    raw = await request.body()
    _verify(raw, request.headers.get("x-retell-signature", ""))
    if name not in TOOLS:
        raise HTTPException(404, "unknown tool")
    customer_id, session = _conversation(json.loads(raw or b"{}"))
    args = json.loads(raw or b"{}").get("args") or {}
    try:
        with _lock:
            return TOOLS[name](customer_id, args, session)
    except (ValueError, RuntimeError, KeyError) as e:
        # Tell Clario what went wrong in words it can act on, instead of a bare HTTP error.
        return {"ok": False, "error": str(e)}
