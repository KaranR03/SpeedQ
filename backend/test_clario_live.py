"""Live Clario (Retell) checks: python test_clario_live.py. In-memory database, no network, no real Retell key.

Retell's tool requests are signed with the same HMAC scheme the SDK verifies, so these are real signed requests.
"""
import json
import os
from types import SimpleNamespace

os.environ["NRY_DB"] = ":memory:"
os.environ["NRY_STAFF_PASSWORD"] = ""
os.environ["NRY_STAFF_ACCOUNTS"] = ""
os.environ["NRY_WEBHOOK_SECRET"] = ""
os.environ["RETELL_API_KEY"] = "test-key"
os.environ["RETELL_VOICE_AGENT_ID"] = "agent_voice"
os.environ["RETELL_CHAT_AGENT_ID"] = "agent_chat"

from fastapi.testclient import TestClient  # noqa: E402
from retell.lib.webhook_auth import symmetric  # noqa: E402

import clario_live  # noqa: E402
import intake_drafts  # noqa: E402
import store  # noqa: E402
from main import app  # noqa: E402

c = TestClient(app)


def tool(name, args, conv="call_maria", customer="CUST-001", key="test-key", chat=False):
    conv_obj = {("chat_id" if chat else "call_id"): conv, "retell_llm_dynamic_variables": {"customer_id": customer}}
    raw = json.dumps({"name": name, ("chat" if chat else "call"): conv_obj, "args": args})
    return c.post(f"/retell/tools/{name}", content=raw,
                  headers={"content-type": "application/json", "x-retell-signature": symmetric["sign"](raw, key)})


# Signature: unsigned, wrongly signed and tampered requests are refused
raw = json.dumps({"call": {"call_id": "x", "retell_llm_dynamic_variables": {"customer_id": "CUST-001"}}, "args": {}})
assert c.post("/retell/tools/lookup_customer", content=raw).status_code == 401
assert tool("lookup_customer", {}, key="wrong").status_code == 401
sig = symmetric["sign"](raw, "test-key")
assert c.post("/retell/tools/lookup_customer", content=raw.replace("CUST-001", "CUST-003"),
              headers={"x-retell-signature": sig}).status_code == 401
assert tool("nope", {}).status_code == 404
print("Signature OK")

# Look-up: the customer comes from the call's dynamic variables, not the model
r = tool("lookup_customer", {"customer_id": "CUST-003"})
assert r.status_code == 200 and r.json()["customer_id"] == "CUST-001" and r.json()["first_name"] == "Maria", r.text
assert tool("lookup_customer", {}, customer="CUST-999").status_code == 422
assert tool("lookup_customer", {}, customer="CUST-002").status_code == 409   # same call, different customer
print("Look-up OK")

# Maria by voice: the card takes shape as a draft, then confirmation ranks it (100, P1, warm transfer)
r = tool("update_card", {"issue_type": "SCAM_IN_PROGRESS", "summary_en": "Caller told me to move my savings",
                         "risk_signals": "CUSTOMER_REPORTS_PRESSURE", "safeblock_activated": True})
assert r.json() == {"ok": True, "card_status": "DRAFT", "issue_type": "SCAM_IN_PROGRESS"}, r.text
draft_id = clario_live.SESSIONS["call_maria"]["draft_id"]
assert intake_drafts.DRAFTS[draft_id]["phase"] == "CHECKING" and not store.CASES      # drafts are never ranked
assert tool("update_card", {"risk_signals": ["NEW_PAYEE_24H"]}).json()["ok"] is False    # account signals refused
assert tool("update_card", {"linked_transactions": "TX-7001"}).json()["ok"] is False     # Priya's, not Maria's
r = tool("submit_card", {"linked_transactions": "TX-9001", "ready_to_confirm": True,
                         "risk_signals": ["CUSTOMER_REPORTS_PRESSURE", "VULNERABILITY_CUES"]})
res = r.json()
assert res["priority_band"] == "P1" and res["handoff"] == "WARM_TRANSFER_FRAUD", res
case = store.CASES[res["case_reference"]]
assert case["priority"]["score"] == 100 and intake_drafts.DRAFTS[draft_id]["status"] == "SUBMITTED"
assert c.get("/clario/session/call_maria").json() == {"case_reference": res["case_reference"], "draft_id": draft_id}
print("Voice card OK")

# The customer adds something after filing: it lands on the same card as a correction, still one card
r = tool("submit_card", {"correction": "He also asked for my one-time code"})
assert r.json()["case_reference"] == res["case_reference"] and r.json()["updated"] is True, r.text
assert len(store.CASES) == 1 and store.CASES[res["case_reference"]]["customer_corrections"]
print("Correction OK")

# Priya by chat: unauthorised charge, card locked, 55 P3, queued (no transfer)
tool("update_card", {"issue_type": "FRAUD_UNAUTHORISED", "summary_en": "$89 charge I didn't make",
                     "linked_transactions": ["TX-7001"], "card_locked": True}, conv="chat_priya", customer="CUST-003", chat=True)
r = tool("submit_card", {}, conv="chat_priya", customer="CUST-003", chat=True).json()
assert r["priority_band"] == "P3" and r["handoff"] == "QUEUE" and store.CASES[r["case_reference"]]["priority"]["score"] == 55, r
print("Chat card OK")

# Customer app starts sessions with the customer as a dynamic variable (Retell client faked)
seen = {}
class FakeRetell:
    call = SimpleNamespace(
        create_web_call=lambda **kw: seen.update(call=kw) or SimpleNamespace(
            call_id="call_1", access_token="tok", transport="gateway", ice_servers=[{"urls": ["stun:stun.example"]}]),
        retrieve=lambda call_id: SimpleNamespace(call_status="ongoing", transcript_object=[
            SimpleNamespace(role="agent", content="Hi Sam, I'm Clario."), SimpleNamespace(role="user", content="")]))
    chat = SimpleNamespace(
        create=lambda **kw: seen.update(chat=kw) or SimpleNamespace(chat_id="chat_1", message_with_tool_calls=[
            SimpleNamespace(role="agent", content="Hi Sam, I'm Clario.")]),
        create_chat_completion=lambda **kw: SimpleNamespace(messages=[
            SimpleNamespace(role="tool_call_invocation", content=""), SimpleNamespace(role="agent", content="It's due 19 Nov.")]))
clario_live._client = lambda: FakeRetell
r = c.post("/clario/session/call", json={"customer_id": "CUST-002"})
assert r.json() == {"conversation_id": "call_1", "access_token": "tok", "transport": "gateway",
                    "ice_servers": [{"urls": ["stun:stun.example"]}]}
assert c.get("/clario/session/call/call_1/transcript").json() == {
    "status": "ongoing", "transcript": [{"role": "agent", "content": "Hi Sam, I'm Clario."}]}
assert c.get("/clario/session/call/nope/transcript").status_code == 404
assert seen["call"]["agent_id"] == "agent_voice" and seen["call"]["retell_llm_dynamic_variables"]["customer_id"] == "CUST-002"
r = c.post("/clario/session/chat", json={"customer_id": "CUST-002"}).json()
assert r == {"conversation_id": "chat_1", "messages": ["Hi Sam, I'm Clario."]} and seen["chat"]["agent_id"] == "agent_chat"
r = c.post("/clario/session/chat/chat_1", json={"content": "When is my card arriving?"}).json()
assert r["messages"] == ["It's due 19 Nov."] and r["case_reference"] is None
assert c.post("/clario/session/chat/unknown", json={"content": "hi"}).status_code == 404
assert c.post("/clario/session/call", json={"customer_id": "CUST-999"}).status_code == 404
print("Customer sessions OK")

# Without a key, live Clario says so instead of failing open
os.environ["RETELL_API_KEY"] = ""
assert tool("lookup_customer", {}, key="").status_code == 503
print("Clario live OK")

# A tunnel (ngrok) connects from loopback but forwards someone else: never treated as the local demo
os.environ["RETELL_API_KEY"] = "test-key"
fwd = {"x-forwarded-for": "203.0.113.9"}
assert c.get("/queue").status_code == 200
assert c.get("/queue", headers=fwd).status_code == 403
assert c.get("/customer", headers=fwd).status_code == 403
assert c.post("/clario/session/chat", json={"customer_id": "CUST-002"}, headers=fwd).status_code == 403
r = tool("lookup_customer", {})  # signed Retell tools still work through the tunnel
assert c.post("/retell/tools/lookup_customer", content=r.request.content,
              headers={**fwd, "x-retell-signature": r.request.headers["x-retell-signature"]}).status_code == 200
assert c.post("/webhook/retell", json={"customer_id": "CUST-002", "issue_type": "GENERAL_ENQUIRY"},
              headers=fwd).status_code == 503   # remote intake needs NRY_WEBHOOK_SECRET
print("Tunnel OK")

# backend/.env: shared settings load at startup, but anything already in the environment wins
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402
from main import _load_env_file  # noqa: E402
with tempfile.TemporaryDirectory() as d:
    f = Path(d) / ".env"
    f.write_text("# comment\nCLARIO_TEST_A='from file'\nRETELL_VOICE_AGENT_ID=agent_from_file\nnot a setting\n")
    _load_env_file(f)
assert os.environ.pop("CLARIO_TEST_A") == "from file" and os.environ["RETELL_VOICE_AGENT_ID"] == "agent_voice"
print(".env OK")
