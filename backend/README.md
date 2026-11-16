# Backend

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Checks: `python priority.py` (scoring), `python test_api.py` (API, acceptance tests 1-6), `python test_db.py` (persistence).
All customer data is synthetic.

## Database

SQLite (`backend/nry.db`, stdlib, created on first run, git-ignored). Cases and their audit logs, plus the
mock account changes (SafeBlock, blocked cards, draft reference counters), survive a backend restart.
The BUILD.md spec said no database; this was added on request. It is a single connection behind a lock:
fine for a demo, not for concurrent production writers.

Wipe it for a clean rehearsal: `curl -X POST localhost:8000/admin/reset` (or "Reset demo data" in the console
sidebar). That endpoint has no auth. `NRY_DB=/path/x.db` points at a different file.

## Officer actions

```
# approve the proposed actions (APPROVE), run an edited list (MODIFY), or take it yourself (MANUAL)
curl -s localhost:8000/case/WGM-0412/decision -H 'content-type: application/json' -d '{"decision":"APPROVE","officer":"j.officer"}'
curl -s localhost:8000/case/WGM-0900/decision -H 'content-type: application/json' -d '{"decision":"MODIFY","actions":[{"action":"BLOCK_CARD"}]}'

# re-rank: exactly one of band / score, reason required, logged. The score is then pinned (no more ageing)
curl -s localhost:8000/case/WGM-0900/rerank -H 'content-type: application/json' -d '{"band":"P1","reason":"Customer is vulnerable"}'

curl -s localhost:8000/audit/WGM-0412
```

## Trigger the demo without a phone

Same body works on `/case` (testing) and `/webhook/retell` (Retell).

```
# Sam: card delivery, Tier 1. Stored, but NOT in the queue
curl -s localhost:8000/case -H 'content-type: application/json' -d '{"customer_id":"CUST-002","customer_name":"Sam T.","issue_type":"CARD_DELIVERY","status":"TIER1_RESOLVED","summary_en":"Card dispatched 12 Nov, due 19 Nov"}'

# Priya: disputed $89 charge -> 40, P3
curl -s localhost:8000/case -H 'content-type: application/json' -d '{"customer_id":"CUST-003","customer_name":"Priya S.","issue_type":"DISPUTE_CHARGE","linked_transactions":"TX-7001","proposed_actions":"RAISE_DISPUTE","summary_en":"$89 charge I do not recognise"}'

# Minh: missing $650 rent, Vietnamese -> 70, P2
curl -s localhost:8000/case -H 'content-type: application/json' -d '{"customer_id":"CUST-004","customer_name":"Minh N.","issue_type":"MONEY_MISSING","language":"vi","language_label":"Vietnamese","linked_transactions":"TX-8001","summary_en":"Missing $650 rent payment","summary_customer_lang":"Mất khoản tiền thuê nhà $650"}'

# Maria: scam in progress -> 160, P1, jumps to the top of the queue
curl -s localhost:8000/case -H 'content-type: application/json' -d '{"customer_id":"CUST-001","customer_name":"Maria R.","issue_type":"SCAM_IN_PROGRESS","linked_transactions":"TX-9001","risk_signals":"CUSTOMER_REPORTS_PRESSURE,VULNERABILITY_CUES","proposed_actions":"ACTIVATE_SAFEBLOCK,DRAFT_PAYMENT_RECALL,DRAFT_SCAM_REPORT,BOOK_CALLBACK","proposed_explanation":"Likely bank impersonation scam. Protect the account and attempt recovery.","summary_en":"Caller says someone claiming to be from Westpac told her to move her savings.","case_reference":"WGM-0412"}'

# Bare scam claim, no account signals -> capped, 80, P2, flagged for officer
curl -s localhost:8000/case -H 'content-type: application/json' -d '{"customer_id":"CUST-002","issue_type":"SCAM_IN_PROGRESS","risk_signals":"CUSTOMER_REPORTS_PRESSURE"}'

curl -s localhost:8000/queue
```

## Ranking rules

- Retell's `priority_score` / `priority_band` are kept only as `retell_estimate`. The backend always recomputes.
- Account signals (new payee, large transfer, lockout, SafeBlock) come from the mock data, using the case's linked transactions that belong to that customer.
- `NEW_PAYEE_24H` is measured from payee-added time to transfer time, not the wall clock, so scores are stable across demo runs.
- Retell's `safeblock_activated` is recorded in `retell_estimate`, not scored. SafeBlock counts once the mock account shows it on.

## Future work (deliberately not built)

Websockets, a database, `/chat` and `/voice`, PII redaction, prompt-injection shields, real auth.
