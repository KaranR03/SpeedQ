# Backend (Clario intake + Prorio)

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Checks: `python -m prorio.selftest` (Prorio's scoring, gates and proposals), `python test_api.py` (the API end to end),
`python test_db.py` (persistence across a restart). All customer data is synthetic.

## Prorio

`prorio/` is the Priority and Protocol agent. It is plain, deterministic code: no language model and no outside API,
so customer data stays in the backend. See "How Prorio works" in the top-level README. Scores are judged against a
fixed demo clock (`NRY_NOW`, default 15 Nov 2026 12:00 UTC); waiting time uses the real clock.

## Database

SQLite (`backend/nry.db`, stdlib, created on first run, git-ignored). Cases and their audit logs, the mock account
changes (SafeBlock, blocked cards, draft reference counters), protocol suggestions and approved protocol versions
survive a backend restart. It is a single connection behind a lock: fine for a demo, not for concurrent production
writers. Records saved by the earlier backend are skipped on start; press "Reset demo data" to clear them.

Wipe it for a clean rehearsal: `curl -X POST localhost:8000/admin/reset` (or "Reset demo data" in the dashboard
sidebar). That endpoint has no auth. `NRY_DB=/path/x.db` points at a different file.

## Trigger the demo without Clario

Same body works on `/case` (testing, returns the full card) and `/webhook/retell` (Clario, returns a short reply).

```
# Sam: card delivery answered by Clario. Stored, NOT in the queue
curl -s localhost:8000/case -H 'content-type: application/json' -d '{"customer_id":"CUST-002","customer_name":"Sam T.","issue_type":"CARD_DELIVERY","status":"TIER1_RESOLVED","summary_en":"Card dispatched 12 Nov, due 19 Nov"}'

# Sam, not satisfied -> 5, P4 (AI acts after one-click approval). Use CUST-005 for a second one
curl -s localhost:8000/case -H 'content-type: application/json' -d '{"customer_id":"CUST-002","customer_name":"Sam T.","issue_type":"CARD_DELIVERY","status":"QUEUED","summary_en":"Card not here yet; wants help"}'

# Priya: $89 charge she didn't make, card locked during the chat -> 55, P3
curl -s localhost:8000/case -H 'content-type: application/json' -d '{"customer_id":"CUST-003","customer_name":"Priya S.","issue_type":"FRAUD_UNAUTHORISED","linked_transactions":"TX-7001","card_locked":true,"summary_en":"$89 charge I did not make"}'

# Minh: missing $650 rent, Vietnamese -> 55, P3
curl -s localhost:8000/case -H 'content-type: application/json' -d '{"customer_id":"CUST-004","customer_name":"Minh N.","issue_type":"MONEY_MISSING","language":"vi","language_label":"Vietnamese","linked_transactions":"TX-8001","summary_en":"Missing $650 rent payment","summary_customer_lang":"Mất khoản tiền thuê nhà $650"}'

# Jordan: locked out after a password change from a new phone, can't buy groceries -> 60, P2
curl -s localhost:8000/case -H 'content-type: application/json' -d '{"customer_id":"CUST-006","customer_name":"Jordan L.","issue_type":"ACCOUNT_ACCESS","risk_signals":"ESSENTIALS_AT_RISK","summary_en":"Locked out after a password change I did not make"}'

# Maria: scam in progress -> 100, P1, jumps to the top; reply says WARM_TRANSFER_FRAUD
curl -s localhost:8000/webhook/retell -H 'content-type: application/json' -d '{"customer_id":"CUST-001","customer_name":"Maria R.","issue_type":"SCAM_IN_PROGRESS","linked_transactions":"TX-9001","risk_signals":"CUSTOMER_REPORTS_PRESSURE,VULNERABILITY_CUES","safeblock_activated":true,"summary_en":"Caller says someone claiming to be from Westpac told her to move her savings.","case_reference":"WGM-0412"}'

# Bare scam claim, nothing on the account -> 79, P2, "officer to verify" (gate G1)
curl -s localhost:8000/case -H 'content-type: application/json' -d '{"customer_id":"CUST-002","issue_type":"SCAM_IN_PROGRESS","risk_signals":"CUSTOMER_REPORTS_PRESSURE"}'

curl -s localhost:8000/queue
```

## Officer actions

```
# what Prorio proposes, and what it did
curl -s localhost:8000/case/WGM-0412/proposal
curl -s localhost:8000/case/WGM-0412/trace

# approve (APPROVE), run an edited list (MODIFY, becomes a protocol suggestion), or handle it yourself (MANUAL)
curl -s localhost:8000/case/WGM-0412/decision -H 'content-type: application/json' -d '{"decision":"APPROVE","officer":"j.officer"}'
curl -s localhost:8000/case/WGM-0900/decision -H 'content-type: application/json' -d '{"decision":"MODIFY","officer":"j.officer","note":"Customer wants a new card","actions":[{"action":"SEND_CUSTOMER_UPDATE"},{"action":"ORDER_REPLACEMENT_CARD"}]}'

# re-rank: exactly one of band / score (0-100), reason required, logged. The score is then pinned
curl -s localhost:8000/case/WGM-0901/rerank -H 'content-type: application/json' -d '{"band":"P1","reason":"Customer is vulnerable"}'

# the customer's view of their card (no score)
curl -s localhost:8000/case/WGM-0412/status
curl -s localhost:8000/audit/WGM-0412
```

## Learning loop

```
curl -s localhost:8000/suggestions
curl -s localhost:8000/suggestions/SUG-0001/approve -H 'content-type: application/json' -d '{"owner":"team lead"}'
curl -s localhost:8000/protocols/FRAUD_UNAUTHORISED
curl -s localhost:8000/protocols/FRAUD_UNAUTHORISED/rollback -H 'content-type: application/json' -d '{"owner":"team lead"}'
```

A suggestion can be approved once it has been made `NRY_SUGGEST_THRESHOLD` times (default 3; set 1 for a quick demo).
