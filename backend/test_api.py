"""Checkpoint 2 check: python test_api.py (needs httpx). Acceptance tests 1, 2, 3, 4, 5 from BUILD.md."""
import os
from datetime import timedelta

os.environ["NRY_DB"] = ":memory:"  # before the app imports db: tests never touch nry.db

from fastapi.testclient import TestClient

import priority
import store
from main import app

c = TestClient(app)
SAM = dict(customer_id="CUST-002", issue_type="CARD_DELIVERY", status="TIER1_RESOLVED",
           summary_en="Card dispatched 12 Nov, due 19 Nov")
PRIYA = dict(customer_id="CUST-003", issue_type="DISPUTE_CHARGE", linked_transactions="TX-7001",
             proposed_actions="RAISE_DISPUTE", summary_en="$89 charge I don't recognise")
MINH = dict(customer_id="CUST-004", issue_type="MONEY_MISSING", linked_transactions="TX-8001",
            language="vi", language_label="Vietnamese", summary_customer_lang="Mất $650 tiền nhà",
            summary_en="Missing $650 rent")
# Retell claims a huge score and a SafeBlock: neither may influence ranking
MARIA = dict(customer_id="CUST-001", issue_type="SCAM_IN_PROGRESS", linked_transactions="TX-9001",
             risk_signals="NEW_PAYEE_24H,LARGE_TRANSFER,CUSTOMER_REPORTS_PRESSURE,VULNERABILITY_CUES",
             proposed_actions="ACTIVATE_SAFEBLOCK,DRAFT_PAYMENT_RECALL,DRAFT_SCAM_REPORT,BOOK_CALLBACK,NUKE_ACCOUNT",
             priority_score=999, priority_band="P1", safeblock_activated=True, case_reference="WGM-0412")
BARE = dict(customer_id="CUST-002", issue_type="SCAM_IN_PROGRESS", risk_signals="CUSTOMER_REPORTS_PRESSURE")

post = lambda body, url="/case": c.post(url, json=body).json()

sam = post(SAM, "/webhook/retell")
assert sam["queued"] is False and "no officer" in sam["caller_message"] and c.get("/queue").json() == []
assert store.CASES[sam["case_reference"]]["status"] == "TIER1_RESOLVED"
priya, minh = post(PRIYA), post(MINH)
assert (priya["priority"]["score"], priya["priority"]["band"]) == (40, "P3")
assert (minh["priority"]["score"], minh["priority"]["band"]) == (70, "P2")
assert [x["customer_id"] for x in c.get("/queue").json()] == ["CUST-004", "CUST-003"]

reply = post(MARIA, "/webhook/retell")
assert reply == {"case_reference": "WGM-0412", "queued": True, "priority_band": "P1",
                 "caller_message": priority.BAND_MESSAGE["P1"]}, reply
maria = c.get("/case/WGM-0412").json()
assert maria["case_id"] == "WGM-0412" and maria["priority"]["score"] == 160, maria["priority"]
assert maria["retell_estimate"]["score"] == 999
assert [a["action"] for a in maria["proposed_solution"]["actions"]] == [
    "ACTIVATE_SAFEBLOCK", "DRAFT_PAYMENT_RECALL", "DRAFT_SCAM_REPORT", "BOOK_CALLBACK"]
q = c.get("/queue").json()
assert q[0]["case_id"] == "WGM-0412" and q[0]["priority"]["band"] == "P1" and len(q) == 3

bare = post(BARE)
assert bare["priority"]["score"] == 80 and bare["priority"]["band"] == "P2"
assert "officer to verify" in bare["priority"]["reasons"][0]
assert bare["case_id"].startswith("WGM-") and bare["case_id"] != "WGM-0412"
assert c.get("/case/WGM-0412").json()["customer_name"] == "Maria R."
assert c.get("/case/NOPE").status_code == 404
assert c.post("/case", json={**BARE, "issue_type": "BOGUS"}).status_code == 422
print("Checkpoint 2 OK")

# Checkpoint 4: officer decisions
dec = lambda cid, body: c.post(f"/case/{cid}/decision", json=body)
r = dec("WGM-0412", {"decision": "APPROVE", "officer": "j.officer"})
assert r.status_code == 200 and r.json()["status"] == "APPROVED" and r.json()["officer_decision"] == "APPROVE"
assert "WGM-0412" not in [x["case_id"] for x in c.get("/queue").json()]
audit = c.get("/audit/WGM-0412").json()
assert [a["action"] for a in audit] == ["DECISION_APPROVE", "ACTIVATE_SAFEBLOCK", "DRAFT_PAYMENT_RECALL",
                                        "DRAFT_SCAM_REPORT", "BOOK_CALLBACK"], audit
assert audit[1]["before"] == {"safeblock": False} and audit[1]["after"] == {"safeblock": True}
assert "DRAFT ONLY" in audit[2]["result"] and all(a["actor"] == "j.officer" and a["ts"] for a in audit)
assert c.get("/case/WGM-0412").json()["priority"]["score"] == 160  # frozen, SafeBlock did not rewrite it
assert dec("WGM-0412", {"decision": "APPROVE"}).status_code == 409  # no double decisions
assert dec("NOPE", {"decision": "APPROVE"}).status_code == 404
assert dec(priya["case_id"], {"decision": "MODIFY"}).status_code == 422
assert dec(priya["case_id"], {"decision": "MODIFY", "actions": [{"action": "WIPE_ACCOUNT"}]}).status_code == 422
r = dec(priya["case_id"], {"decision": "MODIFY", "actions": [{"action": "BLOCK_CARD"}, {"action": "RAISE_DISPUTE", "params": {"transaction_id": "TX-7001"}}]})
assert r.json()["status"] == "MODIFIED"
assert [a["action"] for a in r.json()["audit_log"]] == ["DECISION_MODIFY", "BLOCK_CARD", "RAISE_DISPUTE"]
r = dec(minh["case_id"], {"decision": "MANUAL"})
assert r.json()["status"] == "MANUAL" and len(r.json()["audit_log"]) == 1
assert [x["case_id"] for x in c.get("/queue").json()] == [bare["case_id"]]
assert c.get("/audit/NOPE").status_code == 404
print("Checkpoint 4 OK")

# Checkpoint 5: ageing (acceptance test 6) and re-rank
low = post(dict(customer_id="CUST-003", issue_type="DISPUTE_CHARGE"))                 # 40 now
old = post(dict(customer_id="CUST-002", issue_type="GENERAL_ENQUIRY"))                # 10 now
ids = lambda: [x["case_id"] for x in c.get("/queue").json()]
assert ids().index(low["case_id"]) < ids().index(old["case_id"])
store.CASES[old["case_id"]]["created_at"] -= timedelta(minutes=35)                    # waited 35 min
assert ids().index(old["case_id"]) < ids().index(low["case_id"])
o = next(x for x in c.get("/queue").json() if x["case_id"] == old["case_id"])
assert o["priority"]["score"] == 45 and "Waiting 35 min (+35)" in o["priority"]["reasons"]

rr = lambda cid, body: c.post(f"/case/{cid}/rerank", json=body)
assert rr(old["case_id"], {"band": "P1"}).status_code == 422                          # reason required
assert rr(old["case_id"], {"band": "P1", "reason": "  "}).status_code == 422
assert rr(old["case_id"], {"band": "P1", "score": 5, "reason": "x"}).status_code == 422
assert rr(old["case_id"], {"band": "P9", "reason": "x"}).status_code == 422
assert rr("NOPE", {"band": "P1", "reason": "x"}).status_code == 404
assert rr("WGM-0412", {"band": "P1", "reason": "x"}).status_code == 409              # already decided
r = rr(old["case_id"], {"band": "P1", "reason": "Customer is elderly and alone", "officer": "j.officer"})
assert r.status_code == 200 and r.json()["priority"]["band"] == "P1" and r.json()["priority"]["score"] == 120
assert ids()[0] == old["case_id"] and c.get("/case/" + old["case_id"]).json()["priority"]["score"] == 120
assert "Customer is elderly and alone" in c.get("/case/" + old["case_id"]).json()["priority"]["reasons"][-1]
last = c.get("/audit/" + old["case_id"]).json()[-1]
assert last["action"] == "RERANK" and last["before"]["score"] == 45 and last["after"]["score"] == 120
assert rr(low["case_id"], {"score": 200, "reason": "manual escalation"}).json()["priority"]["score"] == 200
print("Checkpoint 5 OK")

# Hardening: messy agent input, and the optional shared secret on intake
messy = dict(customer_id="CUST-003", issue_type="DISPUTE_CHARGE", language_label=None, summary_customer_lang=None,
             customer_confirmed=None, risk_signals=None, priority_score=None, status=None,
             linked_transactions=["TX-7001"], proposed_actions=["RAISE_DISPUTE"])
r = c.post("/webhook/retell", json=messy)
assert r.status_code == 200 and r.json()["priority_band"] == "P3", r.text
got = store.CASES[r.json()["case_reference"]]
assert got["priority"]["score"] == 40 and got["linked_transactions"] == ["TX-7001"] and got["status"] == "QUEUED"
os.environ["NRY_WEBHOOK_SECRET"] = "s3cret"
try:
    for url in ("/webhook/retell", "/case"):
        assert c.post(url, json=messy).status_code == 401
        assert c.post(url, json=messy, headers={"x-webhook-secret": "wrong"}).status_code == 401
        assert c.post(url, json=messy, headers={"x-webhook-secret": "s3cret"}).status_code == 200
    assert c.get("/queue").status_code == 200  # the console is not locked out
finally:
    del os.environ["NRY_WEBHOOK_SECRET"]
assert c.post("/case", json=messy).status_code == 200  # no secret set: open again
print("Hardening OK")
