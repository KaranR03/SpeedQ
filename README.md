# Never Repeat Yourself

**Team Astars · Westpac hackathon**

When a customer rings the bank about something urgent, like a scam in progress, they often explain it once to a phone
assistant, then again to a person, then again to a specialist. Meanwhile the cases that need help *right now* sit in
the same line as a question about where a card is.

**Never Repeat Yourself** fixes both problems:

1. The customer explains their problem **once**, to a voice assistant. It writes the problem up as a short **case card**
   and passes it on, so nobody has to ask again.
2. This system takes that case card, **works out for itself how urgent it is**, and puts it in the right place in a
   queue that a bank officer watches live. The officer sees *why* each case ranks where it does, then approves, changes
   or takes over the fix.

This repository is the part after the phone call: the **backend** that receives and ranks cases, and the **officer
console** (a web page) that the officer works from.

> All customer data in this project is made up. No real banking data is used anywhere. No money is ever moved.

---

## Contents

- [What happens, step by step](#what-happens-step-by-step)
- [How urgency is worked out](#how-urgency-is-worked-out)
- [The officer console](#the-officer-console)
- [The demo customers](#the-demo-customers)
- [Run it](#run-it)
- [Connecting the voice assistant](#connecting-the-voice-assistant)
- [What the officer can do](#what-the-officer-can-do)
- [Reference: backend endpoints](#reference-backend-endpoints)
- [Where data is kept](#where-data-is-kept)
- [Settings](#settings)
- [Tests](#tests)
- [Project layout](#project-layout)
- [What is real and what is pretend](#what-is-real-and-what-is-pretend)
- [Known limits and future work](#known-limits-and-future-work)

---

## What happens, step by step

```
 Customer rings          Voice assistant            This backend                 Officer console
 ───────────────        ─────────────────         ────────────────────         ─────────────────────
 explains the     ──▶   listens, writes up   ──▶  checks the customer's   ──▶  queue, most urgent
 problem once           a case card and           account, works out the        first, refreshing
                        sends it                  urgency score itself          every 2 seconds
                                                  and adds it to the queue
                                                                                      │
                                                                                      ▼
                                                                         officer reads the reasons,
                                                                         approves / edits / takes over
                                                                         and every step is logged
```

1. **The call.** A customer talks to the voice assistant (built separately, on a service called Retell). When the call
   ends, the assistant sends a **case card** to this backend: who the customer is, what went wrong, which transactions
   are involved, what it suggests doing, and its own guess at how urgent it is.
2. **Checking the facts.** The backend does **not** take the assistant's word for how urgent the case is. It looks the
   customer up in the account data (new payees, large transfers, lockouts) and **calculates the urgency itself**. Two
   customers with the same story always get the same result.
3. **The queue.** The case goes into a queue sorted by urgency. Simple questions that the assistant already
   answered (for example "when does my card arrive?") are saved but **kept out of the queue**, because no officer is
   needed.
4. **The officer acts.** The console shows the queue. The officer opens a case, reads the reasons for its ranking,
   and chooses one of: **Approve** the suggested fix, **Modify** it, or **Do it myself**.
5. **The record.** Every decision and every action is written to an **audit log** that says who did what, when, and
   what changed.

The moment the demo is built around: a scam case arrives, the queue **reorders on screen by itself** to put it first,
the reasons are visible, and the officer clicks Approve.

---

## How urgency is worked out

Every case gets a **score**. A higher score means more urgent.

```
score = issue weight  +  signals  +  waiting time
```

### 1. Issue weight (what kind of problem it is)

| Issue | Points |
|---|---:|
| Scam in progress | 100 |
| Unauthorised fraud | 80 |
| Money missing | 70 |
| Card lost or stolen | 60 |
| Financial hardship | 60 |
| Disputed charge | 40 |
| Card delivery | 10 |
| General enquiry | 10 |

### 2. Signals (extra warning signs)

| Signal | Points | Where it comes from |
|---|---:|---|
| New payee added within 24 hours of the transfer | +15 | **Checked in the account data** |
| Transfer over $1,000 | +15 | **Checked in the account data** |
| Recent account lockout | +10 | **Checked in the account data** |
| SafeBlock already on the account | +10 | **Checked in the account data** |
| Customer says someone is pressuring them | +20 | What the customer said on the call |
| Signs the customer may be vulnerable | +10 | What the customer said on the call |

The first four are worked out by the backend from the customer's real (demo) account records, using only the
transactions linked to the case **that belong to that customer**. The last two can only be known from the
conversation, so they are taken from the voice assistant.

### 3. Waiting time

**+1 point for every minute the case has waited, up to +40.** This is the fairness rule: a less urgent case that has
been waiting a long time slowly climbs the queue and doesn't get stuck behind a steady stream of bigger cases. The
score is recalculated every time the queue is read, so the waiting time is always current.

### The "no gaming" rule

If a call is labelled **scam in progress** but the account shows **no warning signs at all**, the issue weight is
**capped at 60** instead of 100, and the case is flagged *"Customer reports scam, no account signals yet: officer to
verify"*. Words alone cannot put a case at the top of the queue. The same goes for the voice assistant's own score:
it is stored for reference as the "voice agent estimate" but **never used for ranking**.

### Bands (what the score means)

| Band | Score | What the voice assistant tells the caller |
|---|---|---|
| **P1** | 120 or more | Next available specialist, warm transfer to the fraud team |
| **P2** | 70 to 119 | About 5 minutes |
| **P3** | 30 to 69 | About 20 minutes, a reference number, callback offered |
| **P4** | under 30 | Callback within one business day |

### Worked example: Maria

| Reason | Points |
|---|---:|
| Scam in progress | +100 |
| New payee added in the 24 hours before the transfer | +15 |
| Transfer over $1,000 ($4,800) | +15 |
| Customer says a caller is pressuring her | +20 |
| Signs she may be vulnerable | +10 |
| Waiting 0 minutes | +0 |
| **Total** | **160 → P1** |

Every reason is shown to the officer in plain words, each ending in its points, exactly like the table above.

---

## The officer console

A web page, built to read clearly on a projector. Colour is never the only signal: every band is shown as a coloured
tag **and** as text ("P1 URGENT", "P2 HIGH", "P3 MEDIUM", "P4 LOW").

**Queue view**
- Cases sorted by score, highest first. It refreshes by itself every 2 seconds, with no button to press.
- Each row shows the band, customer, case reference, issue, score, how long it has waited, a short summary and an
  **Open** button. The reasons for the ranking sit underneath each row.

**Case view** (after pressing Open)
- Customer, case reference, status, issue, score, linked transactions and risk signals.
- **Why it ranks here:** the full list of reasons.
- For a customer who didn't speak English, a label such as **"Vietnamese (translated)"**, and a switch to read the
  summary in their own language.
- The **suggested fix** and the three buttons: **Approve**, **Modify**, **Do it myself**.
- **Re-rank this case:** move a case to a different band, with a reason that must be filled in.
- The **audit log**: a table of everything that has happened on the case.

A **Reset demo data** button in the left sidebar clears everything for a fresh run.

---

## The demo customers

Five made-up customers, each set up to show a different situation.

| ID | Name | Situation | Result |
|---|---|---|---|
| CUST-001 | Maria Russo | Paid $4,800 to a brand-new payee after a caller claiming to be from the bank told her to move her savings | Score **160, P1**. Jumps to the top |
| CUST-002 | Sam Taylor | Asking when a replacement card will arrive (dispatched 12 Nov, due 19 Nov) | Answered by the assistant. **Not in the queue** |
| CUST-003 | Priya Sharma | A $89 charge she doesn't recognise (SP DIGITALHUB SUBS) | Score **40, P3**. Suggests raising a dispute |
| CUST-004 | Minh Nguyen | Sent $650 rent by Osko but the landlord says it never arrived. Speaks Vietnamese | Score **70, P2**. Shows "Vietnamese (translated)" |
| CUST-005 | Alex | Replacement card due 19 Nov, with an everyday account and an eSaver account | Example customer for card-delivery questions |

The data lives in `backend/data/` as three plain files (`customers.json`, `transactions.json`, `cards.json`). Each
customer has between 3 and 7 transactions so the screens look realistic.

---

## Run it

**You need:** Python 3 (built and tested on 3.9) and a terminal. Nothing else to install.

### 1. Start the backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2. Start the officer console (a second terminal)

```bash
cd console
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run officer_app.py
```

The console opens in your browser (normally at `http://localhost:8501`).

### 3. Send in some cases

Without the phone assistant, post cases by hand. Open a third terminal:

```bash
# Priya: disputed charge. Score 40, P3
curl -s localhost:8000/case -H 'content-type: application/json' -d '{"customer_id":"CUST-003","customer_name":"Priya S.","issue_type":"DISPUTE_CHARGE","linked_transactions":"TX-7001","proposed_actions":"RAISE_DISPUTE","summary_en":"$89 charge I do not recognise"}'

# Minh: missing rent, in Vietnamese. Score 70, P2
curl -s localhost:8000/case -H 'content-type: application/json' -d '{"customer_id":"CUST-004","customer_name":"Minh N.","issue_type":"MONEY_MISSING","language":"vi","language_label":"Vietnamese","linked_transactions":"TX-8001","summary_en":"Missing $650 rent payment","summary_customer_lang":"Mất khoản tiền thuê nhà $650"}'

# Maria: scam in progress. Score 160, P1. Watch her jump to the top
curl -s localhost:8000/case -H 'content-type: application/json' -d '{"customer_id":"CUST-001","customer_name":"Maria R.","issue_type":"SCAM_IN_PROGRESS","linked_transactions":"TX-9001","risk_signals":"CUSTOMER_REPORTS_PRESSURE,VULNERABILITY_CUES","proposed_actions":"ACTIVATE_SAFEBLOCK,DRAFT_PAYMENT_RECALL,DRAFT_SCAM_REPORT,BOOK_CALLBACK","proposed_explanation":"Likely bank impersonation scam. Protect the account and attempt recovery.","summary_en":"Caller says someone claiming to be from Westpac told her to move her savings.","case_reference":"WGM-0412"}'
```

Watch the console: Priya and Minh appear, then Maria arrives and takes the top spot within two seconds. Open her
case, read the reasons, and press **Approve**.

More ready-made examples (Sam's card question, a scam claim with nothing behind it) are in
[`backend/README.md`](backend/README.md).

### Starting over

Cases are saved, so restarting the backend does **not** clear the queue. For a clean run, press **Reset demo data**
in the console sidebar, or:

```bash
curl -X POST localhost:8000/admin/reset
```

---

## Connecting the voice assistant

Point the Retell agent's post-call webhook at:

```
POST http://<your backend address>:8000/webhook/retell
```

Retell needs to be able to reach that address over the internet, so for a laptop demo use a tunnelling tool or run the
backend on a machine with a public address. `POST /case` accepts exactly the same body and is meant for testing by
hand.

The body is one flat set of fields, with lists written as comma-separated text. Field names must match exactly.

| Field | Meaning |
|---|---|
| `customer_id`, `customer_name` | Who is calling |
| `language`, `language_label` | For example `vi` and `Vietnamese` |
| `issue_type` | One of the eight issues in the table above. Anything else is rejected |
| `summary_en`, `summary_customer_lang` | Short summary in English and in the customer's own language |
| `linked_transactions` | For example `TX-9001,TX-9002` |
| `risk_signals` | The two conversation signals: `CUSTOMER_REPORTS_PRESSURE`, `VULNERABILITY_CUES` |
| `customer_confirmed`, `customer_sentiment` | Whether the customer confirmed the summary, and how they sounded |
| `proposed_explanation`, `proposed_actions` | The suggested fix, as text and a list of action names |
| `status` | `TIER1_RESOLVED` (answered already, keep out of the queue) or `QUEUED` |
| `case_reference` | An existing `WGM-####` reference. If missing, one is made starting at `WGM-0900` |
| `priority_score`, `priority_band`, `priority_reasons`, `safeblock_activated` | Accepted but **never used for ranking**. The score and band are kept only as the assistant's estimate |

Actions the backend doesn't recognise are dropped. See [What the officer can do](#what-the-officer-can-do) for the
allowed list.

---

## What the officer can do

Three choices on every open case:

| Button | What happens |
|---|---|
| **Approve** | Runs every action the assistant suggested |
| **Modify** | The officer picks which actions to run from the allowed list, then approves that list |
| **Do it myself** | Runs nothing. The case is marked as handled manually |

A case can only be decided **once**. After a decision it leaves the queue and keeps the score it had when it was
decided.

### The allowed actions

The system will only ever run actions from this fixed list, and every one is **pretend**: it records that the action
happened and changes some demo data, nothing more.

| Action | What it records |
|---|---|
| `ACTIVATE_SAFEBLOCK` | Switches SafeBlock on for the customer's account |
| `BLOCK_CARD` | Marks the customer's card as blocked |
| `RAISE_DISPUTE` | Creates a dispute reference |
| `DRAFT_PAYMENT_RECALL` | Creates a recall **draft only**. Money is never moved. The screen says so |
| `DRAFT_SCAM_REPORT` | Creates a scam report **draft only** |
| `BOOK_CALLBACK` | Records a callback time |
| `SEND_CUSTOMER_UPDATE` | Records that a message was sent |

### Re-ranking

If an officer knows something the numbers don't (for example the customer is elderly and alone), they can move a case
to a different band. **A reason is required.** The change is logged and the reason is shown with the case's other
reasons. A re-ranked case keeps its new score and stops gaining waiting-time points, so the officer's decision is not
quietly undone.

### The audit log

Every decision, action and re-rank adds a line: **who** did it, **when**, **what**, the **before and after**, and the
result. It is shown on the case and available from `GET /audit/{case id}`.

---

## Reference: backend endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/webhook/retell` | Receives a case from the voice assistant, scores it and files it |
| POST | `/case` | Same as above, for posting test cases by hand |
| GET | `/queue` | Open cases, most urgent first, with reasons and current waiting time |
| GET | `/case/{id}` | One full case card |
| POST | `/case/{id}/decision` | `{"decision": "APPROVE" \| "MODIFY" \| "MANUAL", "actions": [...], "officer": "name"}` |
| POST | `/case/{id}/rerank` | `{"band": "P1", "reason": "..."}` or `{"score": 150, "reason": "..."}`. Reason required |
| GET | `/audit/{id}` | The audit log for a case |
| POST | `/admin/reset` | Clears all cases and demo account changes (no password; demo only) |

Errors: `404` unknown case, `409` the case was already decided, `422` the request is invalid (unknown issue, missing
reason, an action not on the allowed list).

Interactive documentation is available while the backend runs at `http://localhost:8000/docs`.

---

## Where data is kept

- **Customer data** (accounts, transactions, cards) is read from the three files in `backend/data/` every time the
  backend starts. Treat them as a fixed starting point.
- **Cases** are saved in a small **SQLite** database file, `backend/nry.db`. SQLite comes with Python, so there is
  nothing to install and no database server to run. The file is created on first start and is not committed to git.
- What survives a restart: every case, its audit log, any re-rank, plus changes the actions made to the demo accounts
  (SafeBlock on, card blocked) and the draft reference numbers.
- To empty it, use **Reset demo data** or `POST /admin/reset`. To keep a separate copy for testing, set `NRY_DB`.

---

## Settings

All optional. They are environment variables.

| Variable | Default | Used by | Meaning |
|---|---|---|---|
| `NRY_API` | `http://localhost:8000` | Console | Where the backend is |
| `NRY_OFFICER` | `officer` | Console | Name written in the audit log for decisions made in this console |
| `NRY_DB` | `backend/nry.db` | Backend | Where the database file lives |

Example: `NRY_OFFICER="j.smith" streamlit run officer_app.py`

---

## Tests

Run these from the `backend` folder with its environment switched on (`source .venv/bin/activate`):

| Command | What it proves |
|---|---|
| `python priority.py` | The scoring rules: Maria 160/P1, Priya 40/P3, Minh 70/P2, a scam claim with no evidence capped at 80/P2, another customer's transaction earns no signals, waiting time stops at +40 |
| `python test_api.py` | The whole backend through its endpoints, covering the demo scenarios below plus decisions, re-ranking and error cases |
| `python test_db.py` | Restarts the backend for real and checks nothing was lost |

The demo scenarios the tests check:

| # | Scenario | Expected |
|---|---|---|
| 1 | Sam asks when his card arrives | Dispatched 12 Nov, due 19 Nov, answered, **not in the queue** |
| 2 | Priya disputes a $89 charge | Score 40, P3, suggests a dispute |
| 3 | Maria is being pressured to move her savings | Score 160, P1, first in the queue, Approve updates status and audit log |
| 4 | Minh's $650 rent is missing, in Vietnamese | Score 70, P2, shows "Vietnamese (translated)" with the original available |
| 5 | A scam claim with nothing in the account to back it up | Weight capped at 60, flagged "officer to verify", cannot reach P1 on words alone |
| 6 | Two cases waiting, one for a long time | The older case's score rises and it climbs the queue |

The tests use a throwaway in-memory database, so running them never touches `nry.db`.

---

## Project layout

```
Team-Astars/
├── README.md             this file
├── BUILD.md              the original build brief
├── backend/
│   ├── main.py           the web service and its endpoints
│   ├── priority.py       the scoring rules, waiting time, the "no gaming" cap and bands
│   ├── store.py          keeps cases, runs officer decisions and re-ranks, restores after a restart
│   ├── models.py         the shape of incoming requests
│   ├── mock_data.py      read-only look-ups over the demo customers and transactions
│   ├── db.py             saving to and loading from the SQLite file
│   ├── data/             customers.json, transactions.json, cards.json (made-up data)
│   ├── test_api.py  test_db.py
│   ├── requirements.txt
│   └── README.md         extra ready-to-paste test commands
└── console/
    ├── officer_app.py    the officer console
    └── requirements.txt
```

---

## What is real and what is pretend

| Real | Pretend (on purpose, for the demo) |
|---|---|
| Receiving cases and scoring them from account data | Customer log-in and Face ID checks |
| The queue order, waiting time, bands and the "no gaming" rule | The phone line itself (the voice assistant is a separate project) |
| Officer decisions, re-ranking and the audit log | SafeBlock, blocking cards, disputes, callbacks and messages: these only *record* that they happened |
| Saving cases to a database | Payment recall: always a **draft**, money is never moved |
| | All the banking data: it's invented |

---

## Known limits and future work

- **No log-in.** Anyone who can reach the backend can read the queue and make decisions. The reset endpoint has no
  password. Fine on one laptop, not fine on a shared network.
- **The queue refreshes by asking every 2 seconds**, not by being pushed. It's simple and reliable, but a very large
  queue would need something better.
- **One machine, one process.** The database is a single file with a single connection. That suits a demo; a real
  deployment would need a proper database server.
- **Demo dates.** The sample transactions are dated 10 to 15 November 2026. Look-ups of "recent transactions" use the
  real clock, so they come back empty once those dates are more than a few weeks old. Scoring is unaffected because it
  compares a payee's age to the transfer date, not to today.
- **Not built:** customer-facing status and confirmation pages, a chat channel, hiding personal details from
  summaries, and protection against people trying to trick the voice assistant. They are listed as future work.
- **Wide-open access from any website** is switched on for the backend (CORS) to keep the demo simple. Restrict it to
  the console's address before using it anywhere else.
- The voice assistant's transfer number used in the Retell setup (`+61400000000`) is a placeholder and always fails.
  To demo a live hand-off, swap in a teammate's mobile number. It isn't needed for the console demo.

---

*Built by Team Astars for the Westpac hackathon.*
