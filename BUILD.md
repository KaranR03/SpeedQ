# Never Repeat Yourself: Backend and Officer Console Build Spec

**For:** a Claude Code session building workstreams D and E for the Westpac hackathon.
**Deadline:** Tuesday 4 PM. Build fast, keep it working at every checkpoint.
**How to use this file:** open Claude Code in an empty folder, drop this file in, and say "read BUILD.md and build it in order, stopping at each checkpoint so I can test." All customer data is synthetic.

---

## 1. Mission

Build the part of "Never Repeat Yourself" that the judges actually watch. A Retell voice agent (already built) talks to a customer and, at the end of each call, sends a case card to a webhook. This backend receives that card, **recalculates the priority score from account data**, and drops it into a queue. An officer console shows the queue sorted by priority, updating live, so judges see a scam case jump to the top of the queue in real time while the officer approves the fix.

The single most important moment: Maria's scam case lands and the queue reorders to put her at Priority 1, with the reasons visible, and the officer clicks Approve.

Two things make or break this:
1. The queue reorders **live** (poll every 2 seconds, no manual refresh).
2. The score is **recomputed server side** from account data, not trusted from the voice agent, so the anti gaming rule is real and the numbers are stable across runs.

---

## 2. Stack (locked)

| Layer | Choice | Why |
|---|---|---|
| Backend | Python, FastAPI | Team knows Python, fast to build |
| Store | In memory (a dict), seeded from JSON files | No database needed for a demo |
| Officer console | Streamlit | Fastest path to a live polling queue in a day |
| Data | Synthetic JSON files | No real banking data, ever |
| Polling | Frontend calls `GET /queue` every 2 seconds | Simple and reliable, no websockets |

Do not add a database, auth server, message broker, or websockets. They cost time and buy nothing for the demo.

---

## 3. Repo layout

```
never-repeat-yourself/
├── BUILD.md                 ← this file
├── backend/
│   ├── main.py              ← FastAPI app and endpoints
│   ├── models.py            ← pydantic models (case card, enums)
│   ├── priority.py          ← scoring, ageing, anti gaming, bands
│   ├── store.py             ← in memory case store + seed loader
│   ├── mock_data.py         ← read-only tools over the JSON data
│   ├── requirements.txt
│   └── data/
│       ├── customers.json
│       ├── transactions.json
│       └── cards.json
└── console/
    ├── officer_app.py       ← Streamlit officer console
    └── requirements.txt
```

---

## 4. Build order and checkpoints

Build in this order. Do not move on until the current checkpoint passes.

**Checkpoint 1: data and scoring.** `priority.py` and `mock_data.py` work. A script can load the 4 customers and score a hand built Maria card to exactly 160, P1. A plain scam card with no account signals caps at 60.

**Checkpoint 2: backend receives a case.** `POST /webhook/retell` accepts the Retell payload (section 6), recalculates the score, stores the case, and `GET /queue` returns cases sorted by score with reasons.

**Checkpoint 3: officer console live.** Streamlit console polls `/queue` every 2 seconds and shows cases sorted, band shown by colour and text, reasons visible. Posting a new case makes the queue reorder on screen within 2 seconds.

**Checkpoint 4: officer actions.** Open a case, see proposed actions, click Approve / Modify / Do it myself, status and audit log update, queue reflects it.

**Checkpoint 5: fairness and polish.** Ageing raises older cases over time, re rank works with a logged reason, and the four demo scenarios in section 11 all pass. Freeze and rehearse.

---

## 5. Internal case card (the model the backend stores)

```json
{
  "case_id": "WGM-0412",
  "customer_id": "CUST-001",
  "customer_name": "Maria R.",
  "language": "en",
  "language_label": "English",
  "channel": "voice",
  "created_at": "2026-11-16T05:12:00Z",
  "issue_type": "SCAM_IN_PROGRESS",
  "summary_en": "Caller says someone claiming to be from Westpac told her to move her savings. She paid $4,800 to a new payee yesterday.",
  "summary_customer_lang": "",
  "linked_transactions": ["TX-9001"],
  "risk_signals": ["NEW_PAYEE_24H", "LARGE_TRANSFER", "CUSTOMER_REPORTS_PRESSURE", "VULNERABILITY_CUES"],
  "customer_confirmed": true,
  "customer_sentiment": "distressed",
  "priority": {
    "score": 160,
    "band": "P1",
    "reasons": [
      "Issue type: scam in progress (+100)",
      "New payee added in last 24h (+15)",
      "Transfer over $1,000 (+15)",
      "Customer reports pressure from a caller (+20)",
      "Vulnerability cues in the call (+10)",
      "Waiting 0 min (+0)"
    ]
  },
  "proposed_solution": {
    "explanation": "Likely bank impersonation scam. Protect the account and attempt recovery.",
    "actions": [
      {"action": "ACTIVATE_SAFEBLOCK", "params": {}},
      {"action": "DRAFT_PAYMENT_RECALL", "params": {"transaction_id": "TX-9001"}},
      {"action": "DRAFT_SCAM_REPORT", "params": {}},
      {"action": "BOOK_CALLBACK", "params": {"when": "tomorrow 10:00"}}
    ]
  },
  "status": "QUEUED",
  "officer_decision": null,
  "audit_log": []
}
```

### Allowed values

| Field | Values |
|---|---|
| `issue_type` | `SCAM_IN_PROGRESS`, `FRAUD_UNAUTHORISED`, `MONEY_MISSING`, `HARDSHIP`, `DISPUTE_CHARGE`, `CARD_LOST_STOLEN`, `CARD_DELIVERY`, `GENERAL_ENQUIRY` |
| `band` | `P1`, `P2`, `P3`, `P4` |
| `status` | `TIER1_RESOLVED`, `AWAITING_CUSTOMER_CONFIRM`, `QUEUED`, `IN_REVIEW`, `APPROVED`, `MODIFIED`, `MANUAL`, `DONE` |
| `officer_decision` | `null`, `APPROVE`, `MODIFY`, `MANUAL` |

`case_id` and `case_reference` are the same WGM reference. If Retell already sent one, keep it. If not, generate `WGM-####` with a 4 digit counter.

---

## 6. Retell webhook payload (what arrives)

`POST /webhook/retell` receives a flat object from the voice agent after each call. Field names come straight from the Retell agent, so match them exactly.

| Incoming field | Type | Maps to |
|---|---|---|
| `customer_id` | string | `customer_id` |
| `customer_name` | string | `customer_name` |
| `language` | string (ISO, e.g. `vi`) | `language` |
| `language_label` | string | `language_label` |
| `issue_type` | string | `issue_type` |
| `summary_en` | string | `summary_en` |
| `summary_customer_lang` | string | `summary_customer_lang` |
| `linked_transactions` | comma string, e.g. `TX-9001` | split to list |
| `risk_signals` | comma string | split to list |
| `customer_confirmed` | bool | `customer_confirmed` |
| `priority_score` | number | **ignore for ranking, keep as `retell_estimate`** |
| `priority_band` | string | ignore for ranking |
| `priority_reasons` | string | ignore, backend writes its own |
| `proposed_explanation` | string | `proposed_solution.explanation` |
| `proposed_actions` | comma string of action names | build `proposed_solution.actions` |
| `status` | `TIER1_RESOLVED` or `QUEUED` | `status` |
| `safeblock_activated` | bool | add `SAFEBLOCK_ACTIVATED` to signals if true |
| `case_reference` | string, `WGM-####` | `case_id` |
| `customer_sentiment` | string | `customer_sentiment` |

Rules on receipt:
- If `status` is `TIER1_RESOLVED`, store it but keep it out of the live queue (it needs no officer).
- Otherwise set status to `QUEUED`, recalculate priority (section 7), and add to the queue.
- Also expose `POST /case` with the same body, so the team can post test cases by hand without Retell. Put a few curl examples in the backend README.

---

## 7. Priority engine (`priority.py`)

```
score = issue_weight + sum(signal_weights) + ageing
ageing = 1 point per minute since created, capped at +40
```

Recompute on every `GET /queue` call so ageing is always current.

### Issue weights

| Issue type | Weight |
|---|---|
| SCAM_IN_PROGRESS | 100 |
| FRAUD_UNAUTHORISED | 80 |
| MONEY_MISSING | 70 |
| CARD_LOST_STOLEN | 60 |
| HARDSHIP | 60 |
| DISPUTE_CHARGE | 40 |
| CARD_DELIVERY | 10 |
| GENERAL_ENQUIRY | 10 |

### Signal weights

Account signals are recomputed from the mock data. Caller word signals are taken from the Retell payload, since they come from the conversation and cannot be derived from account data.

| Signal | Source | Weight |
|---|---|---|
| NEW_PAYEE_24H | account data | +15 |
| LARGE_TRANSFER (over $1,000) | account data | +15 |
| RECENT_LOCKOUT | account data | +10 |
| SAFEBLOCK_ACTIVATED | account data | +10 |
| CUSTOMER_REPORTS_PRESSURE | caller's words | +20 |
| VULNERABILITY_CUES | caller's words | +10 |

**Recompute the account signals yourself.** Look at the customer's transactions and account state in the mock data and decide NEW_PAYEE_24H, LARGE_TRANSFER, RECENT_LOCKOUT, SAFEBLOCK_ACTIVATED from the facts, not from what Retell claimed. This is what makes the anti gaming rule real.

### Anti gaming

If `issue_type` is `SCAM_IN_PROGRESS` but **no account signals** are present after recomputation, cap the issue weight at 60 and add the reason `"Customer reports scam, no account signals yet: officer to verify"`. Caller word signals still count, but the issue weight is capped.

### Bands

| Band | Score | Caller is told |
|---|---|---|
| P1 | 120 or more | Next available specialist, warm transfer to fraud team |
| P2 | 70 to 119 | About 5 minutes |
| P3 | 30 to 69 | About 20 minutes, WGM reference, callback offered |
| P4 | under 30 | Callback within one business day |

### Reasons

Every scored case carries a list of plain reason strings, one per contribution, each ending in the points, for example `"New payee added in last 24h (+15)"`. The ageing line updates as the case waits.

### Worked examples (use as tests)

| Customer | Calculation | Score | Band |
|---|---|---|---|
| Maria (CUST-001) | 100 + 15 + 15 + 20 + 10 | 160 | P1 |
| Priya (CUST-003) | 40 | 40 | P3 |
| Minh (CUST-004) | 70 | 70 | P2 |
| Bare scam, no account signals | 60 (capped) + 20 pressure | 80 | P2, flagged for officer |

---

## 8. Mock data (locked, must match the Retell agent)

Four customers. These IDs and facts match the voice agent, so do not renumber them.

| customer_id | Name | Language | Accounts and key transaction | Scenario |
|---|---|---|---|---|
| CUST-001 | Maria Russo ("Maria R.") | English | Everyday ...3302 $1,210.40; Savings ...3310 $6,950.00; TX-9001 on 15 Nov 2026, $4,800.00 to new payee "J. Bennett", payee added 2 hours before the transfer. No locks, SafeBlock off, no open cases. | Scam in progress |
| CUST-002 | Sam Taylor | English | Replacement Debit Mastercard ...4821, ordered 10 Nov, dispatched 12 Nov 2026 via Australia Post, "In transit, at Brisbane mail centre", expected 19 Nov 2026; Everyday ...7731 $2,431.56 | Card delivery, Tier 1 |
| CUST-003 | Priya Sharma | English | Credit card ...5560; TX-7001 on 14 Nov 2026, $89.00 "SP DIGITALHUB SUBS" (never seen before); Woolworths $54.10 and Opal $4.20 on 13 Nov | Disputed charge |
| CUST-004 | Minh Nguyen | Vietnamese | Everyday ...6120 $980.75; TX-8001 on 13 Nov 2026, $650.00 Osko to landlord "T. Pham", status Sent, landlord says not received | Missing payment, multilingual |

For Maria, TX-9001 must make NEW_PAYEE_24H and LARGE_TRANSFER both true when recomputed, so her live jump to P1 is genuine. Split this into `customers.json`, `transactions.json`, and `cards.json`. Give each customer roughly 5 to 10 transactions so the data looks real on screen.

---

## 9. API endpoints (`main.py`)

| Method | Endpoint | Used by | Purpose |
|---|---|---|---|
| POST | `/webhook/retell` | Retell | Receive a post-call case card, recalc, queue it |
| POST | `/case` | Testing | Same body as the webhook, for manual test cases |
| GET | `/queue` | Console | All queued cases sorted by score, highest first, with reasons and current ageing |
| GET | `/case/{id}` | Console | Full case card |
| POST | `/case/{id}/decision` | Console | Body `{decision: APPROVE / MODIFY / MANUAL, actions?: [...]}`. Runs whitelisted actions (mocked), updates status, appends to audit log |
| POST | `/case/{id}/rerank` | Console | Body `{band or score, reason}`. Manual re rank, logged |
| GET | `/audit/{id}` | Console | Audit log for a case |
| GET | `/case/{id}/status` | Customer view | Queue position, estimated wait, status |
| GET | `/case/{id}/confirm` | Customer view | Mark customer_confirmed, optional corrections (optional, build if time) |
| GET | `/case/{id}/summary` | Customer view | Final summary in the caller's language (optional) |

Enable CORS for the Streamlit origin. The plan's `/chat` and `/voice` endpoints are not needed, Retell is the voice channel. Skip them.

---

## 10. Actions and audit

Officer decisions run actions from this whitelist only. Effects are mocked, just record that they ran. The AI and the backend never move money.

| Action | Who | Effect (mocked) |
|---|---|---|
| ACTIVATE_SAFEBLOCK | customer step-up or officer | set account SafeBlock on |
| BLOCK_CARD | officer | mark card blocked |
| RAISE_DISPUTE | officer | create dispute ref |
| DRAFT_PAYMENT_RECALL | officer, draft only | create a recall draft, money never moved |
| DRAFT_SCAM_REPORT | officer, draft only | create a report draft |
| BOOK_CALLBACK | officer | record a callback time |
| SEND_CUSTOMER_UPDATE | officer | record a message sent |

Every action appends an audit entry: who approved, timestamp, action, before and after. `DRAFT_PAYMENT_RECALL` must stay a draft and say so on screen.

Read-only tools over the mock data, for Tier 1 answers and the officer view: `get_card_delivery_status(customer_id)`, `get_recent_transactions(customer_id, days)`, `get_account_status(customer_id)`, `get_open_cases(customer_id)`.

---

## 11. Officer console (`officer_app.py`)

Two views, in one Streamlit app.

**Queue view**
- Cases sorted by score, highest first, refreshing every 2 seconds.
- Each row: customer name, issue type, band as a coloured tag **and** the text P1 to P4 (colour alone is not enough), score, short summary, time waiting.
- P1 stands out. Click a row to open the case.

**Case view**
- Full case card: name, customer ID, issue type, language label, linked transactions, risk signals.
- The reasons list, so the officer sees why it ranks where it does.
- For a non English caller, show the "Vietnamese (translated)" label and a toggle for the original language summary.
- Proposed solution with three buttons: **Approve**, **Modify** (edit the action list, then approve), **Do it myself** (manual).
- A re rank control with a required reason box.
- An audit log panel that updates after each action.

Use colour and text for bands so it reads on a projector. Keep the layout clean, it will be on screen the whole pitch.

---

## 12. What to mock and what to skip

Mock: login, Face ID step-up, telephony, SafeBlock, payment recall, core banking. Hard coding is fine.

Skip entirely for now: websockets, a database, the plan's `/chat` and `/voice`, PII redaction, prompt injection shields. Note them as future work in the README, do not build them before the demo works end to end.

---

## 13. Acceptance tests (the demo must pass these)

Post each case to `/case` (or drive it from Retell) and watch the console.

| # | Input | Pass condition |
|---|---|---|
| 1 | Sam, "when is my card arriving" | Returns dispatched 12 Nov, due 19 Nov, TIER1_RESOLVED, does **not** appear in the queue |
| 2 | Priya, "$89 charge I don't recognise" | DISPUTE_CHARGE, score 40, P3, proposes RAISE_DISPUTE, shows in queue |
| 3 | Maria, "someone from the bank told me to move my savings" | Score 160, P1, jumps to top of the queue within 2 seconds, proposes SafeBlock plus recall draft, Approve updates status and audit |
| 4 | Minh, Vietnamese, missing $650 rent | MONEY_MISSING, score 70, P2, card shows "Vietnamese (translated)" with original summary available |
| 5 | A bare scam claim with no account signals | Issue weight capped at 60, reason says officer to verify, does not reach P1 on words alone |
| 6 | Two cases waiting, leave one for a few minutes | Its score rises from ageing and it climbs the queue |

---

## 14. Setup and run

```
# backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # fastapi, uvicorn, pydantic
uvicorn main:app --reload --port 8000

# console (second terminal)
cd console
pip install -r requirements.txt   # streamlit, requests
streamlit run officer_app.py
```

Backend README should include curl commands that post Maria, Priya, Sam and Minh, so anyone can trigger the demo without a phone.

---

## 15. Notes carried from the voice agent

- The Retell agent follows the scenario table, so Maria is English and Minh is Vietnamese. The old case card example that showed Maria as Vietnamese is out of date. This spec is the current truth.
- Retell's own `priority_score` is an estimate from the model and can drift. The backend is the source of truth for ranking. Keep Retell's number only as a labelled estimate if you want to show both.
- The placeholder transfer number in Retell (+61400000000) always fails. For a live handoff demo, swap in a teammate's mobile. Not needed for the console demo.
