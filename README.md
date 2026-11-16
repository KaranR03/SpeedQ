# Beacon Assist

**Team Astars · Westpac Innovation & Coding Competition (Hackathon) 2026**

> *Red answers questions. Beacon's agents work the case: they look things up, protect you, rank you fairly, and hand
> a ready-to-approve solution to a person.*

When a customer needs help from their bank, they often explain the problem to a bot, then again to a person, then
again to a specialist. Meanwhile a customer being scammed *right now* waits in the same line as someone asking when
their card will arrive.

**Beacon Assist** fixes both, inside the Westpac app the customer is already signed in to, using two AI agents:

- **Clario** (the front door) talks to the customer by text or voice, answers what it safely can from the customer's
  own data or the Westpac knowledge base, protects scam victims first, and writes the problem up **once** as a
  **Customer Service Card** that the customer can see and correct.
- **Prorio** (Priority and Protocol) works behind the scenes. It ranks every card by **how fast harm grows**, using
  account evidence rather than how loudly someone asks, and drafts a proposed solution from the bank's **Protocol
  Database**.

A **Customer Service Officer** then sees the ranked list, reads why each case sits where it does, and chooses
**Approve**, **Modify** or **Manual**. Every decision feeds back into the Protocol Database, under a team lead's
approval, so proposals improve over time.

> All customer data in this project is made up. No real banking data is used anywhere. The AI never moves money.

---

## Contents

- [Why it's different](#why-its-different)
- [Who and what is involved](#who-and-what-is-involved)
- [How it works, step by step](#how-it-works-step-by-step)
- [Design principles](#design-principles)
- [How priority is worked out](#how-priority-is-worked-out)
- [Who may do what](#who-may-do-what)
- [The Customer Service Card](#the-customer-service-card)
- ["I want to talk to a person"](#i-want-to-talk-to-a-person)
- [The officer dashboard](#the-officer-dashboard)
- [The Protocol Database and the learning loop](#the-protocol-database-and-the-learning-loop)
- [Surge mode (stretch goal)](#surge-mode-stretch-goal)
- [The demo customers](#the-demo-customers)
- [Build status: what this repo runs today](#build-status-what-this-repo-runs-today)
- [Run it](#run-it)
- [Voice channel (optional)](#voice-channel-optional)
- [Reference: backend endpoints](#reference-backend-endpoints)
- [Where data is kept](#where-data-is-kept)
- [Settings](#settings)
- [Tests](#tests)
- [Project layout](#project-layout)
- [What is real and what is pretend](#what-is-real-and-what-is-pretend)
- [Known limits and future work](#known-limits-and-future-work)

---

## Why it's different

1. **Glass-box card.** The customer sees, corrects and tracks the bank's record of their problem. No black-box queue.
2. **Harm clock.** Priority comes from how fast harm grows, and account evidence beats words.
3. **"AI can close doors; only people open them."** A safety rule anyone can remember.
4. **Two agents as a firewall.** The public-facing AI has almost no power; the powerful AI never hears the customer
   directly.
5. **Officers teach, leads approve.** A protocol library that improves safely.
6. **Surge mode** (stretch goal). An outage becomes one incident, not hundreds of separate calls.

Beacon Assist is not a scripted chatbot with fixed menus. The same opening ("I need to talk to someone") leads to
different next steps for different customers, the card shows what each agent looked up (for example *"Checked card
delivery: in transit, due 19 Nov"* or *"Protocol CARD_LOST_STOLEN v1.0"*), and Clario says plainly when something is
beyond it (*"I can't change your address; I've passed it to an officer"*).

---

## Who and what is involved

| Part | What it is |
|---|---|
| **Customer** | A Westpac customer already signed in to the Westpac app. Everything happens inside the app. |
| **Clario** (Agent 1, "query enabler") | The front-door AI. Talks to the customer by text or voice, understands the problem, answers what it safely can, and creates the Customer Service Card. |
| **Prorio** (Agent 2, "Priority and Protocol") | The back-office AI. Ranks every incoming card into one priority list and looks up the Protocol Database to draft a proposed solution. Never talks to the customer directly. |
| **Customer Service Card** | A short structured summary of the customer's issue, created by Clario. The customer can view it and ask Clario to correct it. |
| **User's database** | The signed-in customer's own details (name, customer ID, accounts, cards, deliveries). Clario reads it without asking security questions, because the customer is already logged in. |
| **Westpac knowledge base** | Westpac's public product and help information, used for general questions. |
| **Protocol Database** | The bank's procedures for each type of issue. Prorio reads it to propose solutions; officers' decisions are written back to it as suggestions. |
| **Customer Service Officer Dashboard** | Where human officers see the priority list and proposed solutions and make decisions. |

---

## How it works, step by step

```
 Customer (in app)         Clario                        Prorio                       Officer dashboard
 ────────────────         ────────────────────          ─────────────────────        ──────────────────────
 taps Help, types   ──▶   identifies customer     ──▶   scores and ranks the   ──▶   priority list with
 or speaks                (no security questions)       card (code, not the          reasons and a proposed
                          picks a route A / B / C / D   model), looks up the         solution
                          answers, protects, or         Protocol Database,                 │
                          builds the card               drafts a solution                  ▼
        ▲                        │                                                  Approve / Modify / Manual
        │                        ▼                                                         │
        └──── views and corrects the card, sees live status, gets the outcome ◀────────────┘
                                                                  decision written back to the Protocol Database
```

1. **Customer asks for help.** The customer taps Help in the Westpac app.
2. **Text or voice.** Text goes straight to Clario. Voice is converted to text, with automatic language recognition,
   then sent to Clario.
3. **Clario identifies the customer** from the User's database (name, customer ID, account details). No security
   questions, because the customer is already signed in.
4. **Clario understands the problem and chooses one of four routes:**

   | Route | When | What Clario does | Tier |
   |---|---|---|---|
   | **A. Personalised question** | About the customer's own account, for example "my card hasn't arrived" | Answers from the User's database | **Tier 1** |
   | **B. General question** | About Westpac products or rules | Answers from the Westpac knowledge base, with a source link | **Tier 2** |
   | **C. Scam or priority keywords** | "I'm being scammed", "my account is locked", "money was moved without me" | Does not try to answer. Protects first, then sends the card **straight to Prorio** | n/a |
   | **D. "I want to talk to a person"** | Any time | Never refuses. Asks one triage question, builds a short card and sends it to Prorio | n/a |

   After a Route A or B answer, Clario asks *"Did that solve it?"* (**Yes, thanks** / **No, get me help**). If the
   customer is not satisfied, the card goes to Prorio.
5. **The Customer Service Card.** Whenever a case goes to Prorio, Clario has created a card. The customer can view it
   in the app, and if anything is wrong they tell Clario, who corrects it.
6. **Prorio does two jobs.** **Priority:** scores and ranks every card into one list. **Protocol:** finds the matching
   procedure in the Protocol Database and drafts a **proposed solution**.
7. **Officer dashboard.** The priority list and each proposed solution appear on the dashboard.
8. **Officer decision.** **Approve** (the proposal as is), **Modify** (edit it, then approve) or **Manual** (ignore
   the proposal and handle it from scratch).
9. **Action.** After Approve or Modify, the AI carries out the approved, low-risk actions. With Manual, the officer
   does it.
10. **Outcome.** Clario tells the customer what was done, in their language, with a reference number. The card's
    status ends at **Done**.
11. **Learning loop.** Every decision (approved, modified or manual) is written back to the Protocol Database as a
    suggestion, which a team lead approves before it becomes a rule.

**Who does the work (risk rule).** High-priority and risky cases (P1, P2 and P3, for example locking or checking an
account, scams) are **done by officers**. The lowest-priority, simple cases (P4, for example a delivery date) are
**done by the AI after an officer approves**. Rule of thumb: if an action would be risky in AI hands, a human does it.

---

## Design principles

Every rule in Beacon Assist rests on these six.

1. **Harm clock.** Rank a case by how fast harm grows if nobody acts, not by how loudly the customer asks or which
   menu button they pressed.
2. **AI can close doors; only people open them.** An AI may only take actions that make an account safer, can be
   undone, and the customer asked for (with a fresh Face ID or fingerprint check). Anything that loosens security,
   changes identity or contact details, or moves money needs a human.
3. **Maker and checker.** The AI is the maker (drafts), the officer is the checker (approves). Banks already use this
   four-eyes control; we apply it to AI.
4. **Least privilege, split by audience.** Clario faces customers, so it sees only the signed-in customer and never the
   bank's internal playbooks. Prorio faces staff, so it sees playbooks and cross-case patterns but never takes the
   customer's raw words as instructions.
5. **Glass-box card.** The customer sees what the bank has written down about their problem, can correct it, and can
   watch its status live.
6. **Grounded or escalate.** Every answer comes from the customer's own data or the Westpac knowledge base, with a
   source. If neither has it, Clario says so and offers a person. It never guesses, and it never browses the open web.

---

## How priority is worked out

### What counts as high and low

- **High priority:** money is leaving or about to leave, money was taken without consent, the customer cannot reach
  their own money, someone may be controlling the customer or the account right now, or the account's security is in
  question.
- **Low priority:** information or a routine service where nothing is at risk and nothing about security changes (a
  delivery date, a statement copy, a fee explanation, branch hours).
- **The trap: "looks simple, isn't safe."** Changing an address, phone number or email, adding a device, raising a
  limit, removing a block or giving another person authority over an account look like admin, but they are the first
  steps in an account takeover or financial abuse. These are always handled by an officer, at P3 or higher. ("Finding
  the address" is a safe read; "changing the address" is not.)
- **Safety cases.** Family violence, financial abuse and elder financial abuse can look like a hardship or admin
  request, but someone may be controlling the customer's money. They never sit below P2.
- **Asking is safe.** "Is this call or message really from Westpac?" is ranked as a general question, because checking
  is the behaviour we want to encourage and nothing is at risk yet. The moment the customer says they shared codes,
  installed something, moved money, or that the caller is still on the line telling them what to do, Clario switches
  to the scam path.

### The score (0 to 100)

```
Score = Harm (0-60) + Time to harm (0-20) + Verified account signals (0-20) + Care needs (0-10) + Waiting (0-10)
        capped at 100
```

**The score is computed by code, not by the language model.** Clario's model only classifies the issue type and
extracts cues; a backend function adds the points. The same facts always give the same score, and every point has a
written reason.

| Harm (what is at stake) | Code in `protocols.json` | Points |
|---|---|---:|
| Scam in progress (told to move money, remote access, someone on the line) | `SCAM_IN_PROGRESS` | 60 |
| Unauthorised transaction (money taken without consent) | `UNAUTHORISED` | 45 |
| Locked out of own money, or suspected account takeover | `ACCOUNT_ACCESS` | 40 |
| Card lost or stolen | `CARD_LOST` | 35 |
| Payment missing (sent but not received, mistaken payment) | `PAYMENT_MISSING` | 35 |
| Financial hardship, or a safety case | `HARDSHIP` | 30 |
| Disputed charge (known merchant, wrong amount or service) | `DISPUTE` | 20 |
| Complaint about service | `COMPLAINT` | 15 |
| Service request (delivery, statement, address lookup) | `SERVICE` | 5 |
| General question | `GENERAL` | 0 |

The same codes and points are stored once in `backend/data/protocols.json` (`_about.harm_categories`), and every
protocol names the code it scores under. The scoring code should read the points from there. If a number changes,
change it there and in this table.

| Time to harm | Points |
|---|---:|
| Harm is happening now: money still leaving, scammer still in contact, repeated debits | +20 |
| Money may still be recoverable if acted on today (transaction under 72 hours old or still pending) | +10 |
| Neither | 0 |

| Verified account signal (+10 each, maximum +20; from account data only, never from the customer's words) |
|---|
| New payee added in the last 24 hours |
| Transfer much larger than usual (over $1,000, or over 3 times the customer's typical payment) |
| Password, device or contact details changed in the last 7 days |
| Card used somewhere unusual for this customer |
| Payee already appears in other open scam cards today (Prorio's cross-case check) |

| Care needs (+10 once) |
|---|
| Customer cannot pay for essentials (food, rent, medication), or shows vulnerability cues: distress, confusion, coaching, needs language support, an older customer struggling with digital steps |

| Waiting |
|---|
| +2 for every 10 minutes in the queue, maximum +10 |

### Bands

Response targets are Beacon Assist design targets, not Westpac figures.

| Band | Score | Who handles | AI's job | Design target | Customer sees |
|---|---|---|---|---|---|
| **P1 Critical** | 80 to 100 | Fraud specialist, immediately | Clario has already offered SafeBlock or a card lock; Prorio drafts the recall and scam report | Warm handoff to the next available specialist, aim under 2 minutes | "A fraud specialist is joining now" |
| **P2 High** | 60 to 79 | Officer | Prorio drafts the full proposal | Within 30 minutes, or a booked callback | Position in queue, or callback time |
| **P3 Medium** | 40 to 59 | Officer | Prorio drafts the full proposal | Same business day | "With our team today", reference number |
| **P4 Low** | 0 to 39 | AI prepares, officer approves with one click | Prorio prepares the complete reply or action from the protocol | Same business day, usually minutes | Status updates, then the answer |

Most P4 questions never reach the queue: Clario answers them at Tier 1 or Tier 2. P4 cases are the ones where the
customer was not satisfied or a routine action needs sign-off.

### Gates (they override the score)

| Gate | Rule |
|---|---|
| **G1 Words alone can't reach P1** | Without at least one verified account signal, the score is capped at 79 (P2) and flagged *"Customer reports scam, no account signals yet: officer to verify"*. Typing "scam" does not jump the queue. |
| **G2 Protect first** | For scams, unauthorised transactions and lost cards, Clario offers SafeBlock or a card lock **before** the case is queued (the customer's choice, with Face ID). |
| **G3 Security floor** | Any request that changes identity, contact details or devices, raises a limit, removes a lock or gives another person authority or access is officer-only and never below 40 (P3). |
| **G4 Ageing ceiling** | Waiting can lift a case by at most one band, so routine cases can't overtake real emergencies, but nothing waits forever. |
| **G5 Officer override** | An officer can re-rank any case with a reason; it is logged and reviewed. |
| **G6 One problem, one card** | Repeat contacts about the same issue update the existing card instead of creating new ones. |
| **G7 Safety floor** | Family violence, financial abuse and elder financial abuse are never below 60 (P2), and go to a specialist team. Clario asks only what's needed and sends nothing that could alert someone else. Words alone can reach P2 here, never P1 (G1 still applies): a false claim costs an officer a few minutes, but a missed one can cost someone their safety. |

### Worked examples (synthetic customers)

| Case | Calculation | Score and band |
|---|---|---|
| **Maria:** "Someone from the bank told me to move my savings"; $4,800 to a new payee 2 hours ago | Scam 60 + happening now 20 + new payee 10 + large transfer 10 | **100, P1** |
| Same words, but no unusual activity on the account | Scam 60 + happening now 20 = 80, capped by G1 | **79, P2**, "officer to verify" |
| **Priya:** $89 "SP DIGITALHUB SUBS" that isn't hers (after Clario first shows her the merchant details) | Unauthorised 45 + recoverable 10 | **55, P3**; card lock offered at once (G2) |
| Priya, and the card was also used overseas yesterday | 55 + unusual location 10 | **65, P2** |
| **Minh:** $650 rent sent by Osko, landlord says not received, prefers Vietnamese | Payment missing 35 + recoverable 10 + care (rent, language) 10 | **55, P3** |
| Locked out after a password change from a new phone, can't buy groceries | Locked out 40 + device change 10 + care 10 | **60, P2** |
| Lost job, can't make the home loan payment | Hardship 30 + care 10 | **40, P3**, officer-led (hardship is a regulated assessment) |
| **Sam:** "When is my new card arriving?", not satisfied after Clario's answer | Service 5 | **5, P4**, AI prepares, officer approves |
| "Please change my address" | Service 5, raised by G3 | **40, P3**, officer-only |
| "I want my daughter to be able to help with my banking" | Service 5, raised by G3 | **40, P3**, officer-only; Clario first checks the choice is the customer's own |
| "My son keeps taking money from my account and I'm scared to say no" | Hardship 30 + care 10 = 40, raised by G7 | **60, P2**, specialist team |
| "Is this text really from Westpac?" (nothing shared, nothing moved) | General 0 | **0, P4**, Clario answers at Tier 2 and checks for a genuine bank contact on file |
| Same question, but "they're still on the phone and want my code" | Switches to scam in progress: Scam 60 + happening now 20 = 80, capped by G1 unless account signals back it | **79, P2** (or P1 with signals), SafeBlock offered first |

### Why this holds up

- It ranks by harm and recoverability, which is how fraud teams already think: minutes matter while money can still be
  stopped.
- Account evidence outweighs words, so it is hard to game, and a gamed case still lands with an officer, not an AI.
- Vulnerability gets a boost, but a capped one (+10), so it helps without overriding real emergencies.
- It is **designed to support** the complaint and hardship response timeframes in ASIC RG 271 and the
  detect-and-disrupt expectations of the Scams Prevention Framework. It is a prototype; we do not claim compliance.

---

## Who may do what

**Yes** = may use directly. **Draft** = may prepare, a human submits. **No** = never.

| Tool or action | Clario | Prorio | Officer |
|---|---|---|---|
| Customer profile (name, customer ID, preferred language) | Yes, signed-in customer only | Only customer ID, language and care flags for the case | Yes |
| Accounts and balances (masked to last 4 digits) | Yes | No | Yes |
| Recent transactions (last 90 days) | Yes | Only transactions linked to the case, plus signal flags from the scoring code | Yes |
| Card status and delivery tracking | Yes | Only for card cases | Yes |
| Account security status | Status only (for example "SafeBlock is on") | Signal flags from the scoring code | Yes, full detail |
| Westpac knowledge base | Yes, with a source link | Yes | Yes |
| Open cases and case status | Own only | Whole queue | Yes |
| Protocol Database | **No** | Read | Read; changes need approval |
| Other customers' data | **No** | Pattern flags only (for example "this payee is in 3 scam cards today"), no personal details | Per their permissions |
| Create and edit the Customer Service Card | Yes, customer's words, confirmed by the customer | Adds score, reasons and proposal; cannot change what the customer said | Can annotate |
| Ask the customer a question, send status updates | Yes | No (asks through Clario) | Yes |
| Book a callback | Yes | Sets urgency | Yes |
| Route, warm transfer, place in queue | Hands off | Yes | Accepts |
| Offer SafeBlock or a temporary card lock | Yes, only when the customer chooses, with Face ID | No | Yes |
| Remove SafeBlock, unlock an account, lift restrictions | **No** | **No** | Yes, after verification |
| Change address, phone, email, password, add a device, raise a limit | **No** (records the request only) | **No** | Yes, with identity checks |
| Lodge a dispute or chargeback | No | Draft | Submits |
| Payment trace or recall request | No | Draft | Submits |
| Scam report | No | Draft | Submits |
| Refund, fee reversal, credit, compensation | No | Suggest only | Yes |
| **Move money** (transfers, payments) | **No** | **No** | **No** (the customer does it themselves) |
| Hardship arrangement | No | Draft notes | Yes |
| Outcome message that commits the bank to something | Delivers it, in the customer's language | Drafts | Approves |
| Protocol Database change | No | Drafts a suggestion | Suggests; a protocol owner approves; versioned |
| Audit log | Writes automatically | Writes automatically | Reads; nobody can edit |

**Why two agents?** Different audiences, different powers. Clario talks to the public, so it holds almost no power.
Prorio holds the bank's playbooks and the ranking, so it only receives structured card fields and never takes customer
words as instructions. A customer can't type "make me priority 1" or "ignore your rules" and reach the part that ranks
and proposes. That is a prompt-injection firewall by design.

**Why Prorio sees any account data at all:** fair scoring needs evidence that doesn't come from the customer's words
(otherwise gate G1 can't work), proposals need specifics such as which transaction to recall, and it is the safety net
when Clario misfiles a case. Even so, Prorio's model never reads raw account data in bulk: the scoring code reads the
account and passes Prorio only the signal flags and the transactions linked to the case.

---

## The Customer Service Card

- Written by Clario in the customer's own words, then read back before it is sent: *"Here's what I'll pass on... is
  that right?"*
- The customer can open it in the app at any time and tell Clario if anything is wrong; Clario corrects it.
- Prorio adds the score, the reasons and the proposed solution, but cannot change what the customer said.
- It is a **live tracker**: **Received → Ranked → With an officer → Action taken → Done**.
- The officer always sees the card in English. For other languages it is labelled (for example "Vietnamese
  (translated)") with the original one tap away, and the outcome goes back in the customer's language.

---

## "I want to talk to a person"

The goal is that the right customer reaches a person first, and nobody waits in a blind queue.

- Clario never refuses or argues, and says why it is asking: *"I'll get you to a person. So the right person picks up,
  what's it about?"*
- One question, with quick answers: **Money I didn't send, or someone asking me to move money** · **Can't get into my
  account or money** · **Lost or stolen card** · **A payment or charge** · **Something else** · **I'd rather not say**.
- If the answer points to risk, Clario may ask one more short question (for example *"Is someone on the phone with
  you now telling you what to do?"*) and offers protection first (G2). Otherwise, no more questions.
- "Something else" and "I'd rather not say" are valid. The case is still queued, scored from account signals alone,
  and the customer sees an honest status.
- Target: one question, under 15 seconds, then routed. It must feel like a receptionist asking "what's it about?",
  never like a gate.

**Scam victims don't wait.** On the scam path Clario: (a) says *"Please don't move any money, and hang up on anyone
telling you to"*; (b) offers SafeBlock with Face ID; (c) asks at most two questions; (d) builds the card in the
background; (e) Prorio warm-hands to a fraud specialist (P1) or flags "officer to verify" (P2). Protection happens in
under a minute, before any ranking.

**Misclassification safety net.** Prorio runs the account-signal checks on every card, whatever route it came from.
If Clario filed a scam as a general question, the signals still raise it. Any customer can ask for a person at any
time, and officers can re-rank.

---

## The officer dashboard

- The priority list, sorted by score, with the band shown as a coloured tag **and** as text, and the reasons for each
  ranking visible.
- Each case shows the card, linked transactions, account signals, the language label, and Prorio's proposed solution
  with the protocol and version it used.
- Three choices on every case:

  | Button | What happens |
  |---|---|
  | **Approve** | The proposal goes ahead as is. For P4, the AI then carries out the approved reply or action. |
  | **Modify** | The officer edits the proposal, then approves it. The dashboard asks *"Suggest as a protocol update?"* |
  | **Manual** | The officer ignores the proposal and handles the case themselves. |

- **Re-rank** any case with a required reason (G5). It is logged.
- An **audit log** on every case: who did what, when, and what changed.

What makes it more than a ticket queue (all live in `web/`, see [Run it](#run-it)):

- **The list re-orders itself.** New cases flash in, and rows slide to their new place when a more urgent case lands.
- **A score receipt.** Every point is a line, tagged **Verified** (account data), **Said** (the customer's words),
  **Issue type**, **Rule** or **Clock**, so it's obvious why typing "scam" can't jump the queue.
- **"View as": Officer, Prorio or Customer.** The same card through three sets of permissions. Prorio's view shows
  that it never reads the customer's words; the customer's view shows that they never see the score or which fraud
  alarms tripped. Least privilege and the two-agent firewall, visible in two seconds.
- **What the agents did.** Prorio's step-by-step trace, and in the customer app each look-up Clario made.
- **"Officer only" is shown, not hidden.** Anything that opens a door is listed as a task only a person may do.
- **Corrections arrive live.** When a customer adds to their card, the officer's card highlights the change.

---

## The Protocol Database and the learning loop

For the demo, the Protocol Database is [`backend/data/protocols.json`](backend/data/protocols.json): **31 protocols**,
one per issue type, written in our own words from public sources. Each protocol lists its sources, and steps marked
`team_design` are our own design, not a published rule. It is **not** Westpac's internal procedure.
[`PROTOCOLS_SOURCES.md`](backend/data/PROTOCOLS_SOURCES.md) explains how it was built and the copyright rules for
changing it.

One entry, shortened (the `clario_can_answer` list is cut to one item):

```json
{
  "issue_type": "CARD_DELIVERY",
  "title": "When will my card arrive?",
  "version": "2.0", "harm_category": "SERVICE", "min_band": null,
  "clario_can_answer": ["Answer from card tracking: dispatched, carrier, status, expected date."],
  "protect_first": null,
  "steps": [
    {"who": "AI (Clario)", "step": "Answer from tracking data", "source": "team_design"},
    {"who": "AI (Prorio)", "step": "If past the expected date, prepare a replacement to the address on file", "source": "team_design"},
    {"who": "officer", "step": "One-click approve (P4)", "source": "team_design"}
  ],
  "ai_may": ["prepare ORDER_REPLACEMENT_CARD", "SEND_CUSTOMER_UPDATE"],
  "officer_must": ["approve the replacement"],
  "required_checks": ["address changes go to DETAILS_CHANGE"],
  "customer_message": "Your card was sent on {dispatched} and should arrive by {expected}. You can use your digital card in the app until then.",
  "timeframes": []
}
```

| Field | Meaning |
|---|---|
| `harm_category` | Which row of the harm table the case scores under |
| `min_band` | A gate: the lowest band the case may sit in (`null` means the score decides) |
| `clario_can_answer` | What Clario may tell the customer straight away (Tier 1 or 2) |
| `protect_first` | The protective action offered before queuing (G2), always the customer's choice |
| `steps` | Who does what, in order: customer, AI (Clario), AI (Prorio) or officer, each with a source |
| `ai_may` / `officer_must` | What the AI may prepare or do, and what only a person may decide |
| `required_checks`, `customer_message`, `timeframes`, `sources` | Checks before acting, the reply template, sourced timeframes, and links |
| `change_log` | What changed in each version and why |

**All 31 issue types, by harm category** (a gate is shown where the protocol sets a minimum band):

| Harm code | Points | Issue types |
|---|---:|---|
| `SCAM_IN_PROGRESS` | 60 | `SCAM_IN_PROGRESS` |
| `UNAUTHORISED` | 45 | `SCAM_ALREADY_PAID`, `FRAUD_UNAUTHORISED`, `UNAUTHORISED_ONLINE_BANKING` |
| `ACCOUNT_ACCESS` | 40 | `IDENTITY_THEFT` (G3, P3+), `ACCOUNT_ACCESS` (G3, P3+), `ACCOUNT_RESTRICTED_ID_CHECK` (G3, P3+) |
| `CARD_LOST` | 35 | `CARD_LOST_STOLEN` |
| `PAYMENT_MISSING` | 35 | `MONEY_MISSING`, `BPAY_MISTAKE` |
| `HARDSHIP` | 30 | `HARDSHIP`, `FAMILY_VIOLENCE_FINANCIAL_ABUSE` (G7, P2+), `ELDER_FINANCIAL_ABUSE` (G7, P2+), `BEREAVEMENT`, `GAMBLING_HARM` |
| `DISPUTE` | 20 | `DISPUTE_CHARGE` |
| `COMPLAINT` | 15 | `COMPLAINT` |
| `SERVICE` | 5 | `LOGIN_HELP`, `DETAILS_CHANGE` (G3, P3+), `PAYMENT_LIMIT_CHANGE` (G3, P3+), `CARD_DECLINED`, `CARD_DELIVERY`, `CARD_ACTIVATION`, `PENDING_TRANSACTION`, `DIRECT_DEBIT_STOP`, `PAYID_ISSUE`, `TRUSTED_PERSON_ACCESS` (G3, P3+), `ACCOUNT_CLOSURE`, `OUTAGE_INCIDENT` |
| `GENERAL` | 0 | `VERIFY_CONTACT`, `GENERAL_ENQUIRY` |

Some protocols switch a case to another one when the facts change: `VERIFY_CONTACT` becomes `SCAM_IN_PROGRESS` as
soon as anything is at risk, `PENDING_TRANSACTION` is routed to a fraud, dispute or scam protocol, and
`TRUSTED_PERSON_ACCESS` becomes `ELDER_FINANCIAL_ABUSE` if the customer is being pressured.

**Officers teach, leads approve.** An officer's Modify or Manual decision becomes a protocol *suggestion*, not a rule.
When the same change has been suggested several times (for example 3), it is offered to a protocol owner (a team lead)
who approves or rejects it. Every protocol has a version number, every proposal shows which version it used, every
change is recorded in the protocol's `change_log`, and any change can be rolled back. The protocols start at v2.0; the
four changed after the team's review are at v2.1. In the demo, an officer modifies a proposal and it appears as the
next version, "pending approval".

---

## Surge mode (stretch goal)

When many cards with the same symptom arrive at once (for example "app not loading" during an outage), Prorio groups
them into one incident card for the officers, and Clario tells affected customers proactively what is happening.
Officers handle one incident instead of hundreds of separate cards.

---

## The demo customers

Six made-up customers. Data lives in `backend/data/` (`customers.json`, `transactions.json`, `cards.json`).

| ID | Name | Situation | Expected under Beacon Assist |
|---|---|---|---|
| CUST-001 | Maria Russo | Paid $4,800 to a brand-new payee after a caller claiming to be from the bank told her to move her savings | Scam path: SafeBlock offered first, **100, P1**, warm handoff to a fraud specialist |
| CUST-002 | Sam Taylor | Asking when a replacement card will arrive (dispatched 12 Nov, due 19 Nov) | **Route A, Tier 1**: answered from his data. Only queued (**5, P4**) if he is not satisfied |
| CUST-003 | Priya Sharma | A $89 charge she doesn't recognise (SP DIGITALHUB SUBS) | Card lock offered (G2), **55, P3**, Prorio drafts a dispute |
| CUST-004 | Minh Nguyen | Sent $650 rent by Osko but the landlord says it never arrived. Prefers Vietnamese | **55, P3**, card shown as "Vietnamese (translated)", outcome returned in Vietnamese |
| CUST-005 | Alex | Replacement card due 19 Nov, with an everyday account and an eSaver account | Extra example for card-delivery questions |
| CUST-006 | Jordan Lee | Locked out after the password was changed from a new phone; can't buy groceries | `ACCOUNT_ACCESS` with `ESSENTIALS_AT_RISK`: **60, P2** (locked out 40 + device change 10 + care 10) |

The demo proves three things on screen: the officer understands a case from the card in seconds with **zero
re-asking**; a P4 case goes from question to approved answer in **one click**; a scam victim is **protected in under a
minute**.

---

## Build status: what this repo runs today

| Part | Status |
|---|---|
| **Prorio** (Priority and Protocol), `backend/prorio/` | **Built.** Rule-based, no language model and no outside API. The 0 to 100 score, bands, gates G1 and G3 to G7, verified account signals (including the cross-case payee check), protocol lookup, proposals, who acts (P4: AI after one-click approval), a step-by-step trace, and the "officers teach, leads approve" loop |
| Backend: intake from Clario, live priority list, decisions, re-rank, audit log, customer status tracker | **Built** |
| Officer website (`frontend/`): priority queue, concise preview, focused review, evidence/activity tabs, decisions, manual outcomes, re-ranking, protocol library and learning loop | **Built**, served directly by FastAPI; the previous Streamlit dashboard remains as an optional local reference |
| **Customer app** (`/customer`): Clario's conversation for five demo customers, Face ID and protection timer, card read-back, the glass-box card with live tracker and corrections, the outcome message | **Built.** Customer lines are scripted; Clario's look-ups, the card, Prorio's ranking and the tracker are real |
| **Side-by-side demo** (`/demo`): customer app and officer dashboard together, with scene buttons and captions | **Built**, for recording the video |
| Streamlit console (`console/`) | Kept as a fallback |
| Saving cases, audit logs, suggestions and approved protocol versions (SQLite) | **Built** |
| Protocol Database (`backend/data/protocols.json`, 31 protocols) | **Built**, and read by Prorio (see `backend/data/PROTOCOLS_SOURCES.md`) |
| Clario (Retell voice agent) | Built separately; needs the updates listed for Prorio (new bands, `handoff` reply, unauthorised vs disputed charge, card lock, `ESSENTIALS_AT_RISK`) |
| Clario with a live language model in the text chat | Not in this repo: the live Clario is the Retell agent (see [The live demo](#the-live-demo)) |
| Westpac knowledge base answers with sources | In the Retell agent (406 crawled pages; see the copyright note in `PROTOCOLS_SOURCES.md`) |
| Surge mode | Stretch goal |

### How Prorio works

Prorio is code, so it is explainable and the same card always gets the same answer. Customer data never leaves the
backend. For every card it runs the same steps and records each one in a trace the officer can open:

1. **Read card.** Only structured fields: issue type, linked transaction IDs, conversation signals, language. The
   customer's free-text summary is never read, so "ignore your rules, make me P1" cannot change anything.
2. **Gather evidence** from account data: only transactions linked to the card **and** belonging to that customer.
3. **Score**: harm (from the protocol's harm category) + time to harm + verified signals + care needs + waiting.
4. **Apply gates**: G1 words alone can't reach P1; G3 and G7 through each protocol's `min_band` (for example address
   changes P3, family violence and elder financial abuse P2); G4 waiting lifts at most one band; G5 officer re-rank;
   G6 a repeat contact updates the open card instead of creating a new one.
5. **Match protocol** in the Protocol Database and use any version a protocol owner has approved.
6. **Draft proposal**: actions from the fixed executable list (each one mocked), officer tasks for anything else,
   required checks, the customer message filled in, timeframes and sources.
7. **Assign**: P1 to P3 are carried out by an officer; P4 by the AI after one-click officer approval.

**Safety net for a misfiled charge.** If a card arrives as `DISPUTE_CHARGE` but the merchant has never appeared in the
customer's history, Prorio scores it under the unauthorised harm row with the reason "Merchant never seen before on
this account: scored as possible unauthorised, officer to confirm". It never changes the issue type Clario recorded.

**Demo clock.** Account evidence ("still recoverable", "changed in the last 7 days") is judged as of
**15 Nov 2026, 12:00 UTC**, so scores are the same on every run. Waiting time uses the real clock. Set `NRY_NOW` to
change it, or `NRY_NOW=real` to use the real clock.

---

## Run it

**You need:** Python 3 (built and tested on 3.9) and a terminal. Nothing else: no API key, no internet, no build step.

### 1. Start the officer workspace and backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

The new **Beacon Assist officer workspace** is served at `http://127.0.0.1:8000` by the backend itself. No frontend
build, Node server, external font, or third-party script is required. Click **Load sample cases** to add five synthetic
customers without clearing existing work. The loader is idempotent and is disabled when staff authentication is enabled.

The workspace includes a searchable priority queue, a compact case preview, a focused review screen, evidence and
activity tabs, manual case tracking, completed outcomes, the protocol library and the learning loop. Opening a preview
does not pick up a case; **Review case** explicitly records pickup. Decisions require a confirmation step. Unfilled
customer-message fields route officers to manual handling so they can record a complete outcome.

**Care insights** adds interactive urgency, issue mix, case stages, open-case age, decision distribution, evidence
coverage and response-watch visuals. Selecting a band, issue or stage opens the matching real cases. Amounts are
deduplicated, ownership-checked linked outgoings in AUD; they are not confirmed losses. Response-watch thresholds are
project design targets, not bank SLAs. The dashboard explicitly distinguishes its live case clock from the fixed
account-evidence clock.

Within a case, **Evidence** explains the score with component bars and adjustments. **Customer context** shows masked
accounts, linked owned transactions, optional recent history, security/access events and card-delivery milestones.
Reported protection is kept separate from verified account state. **Handoff brief** prepares a concise staff summary
for an explicit copy action; it does not send anything externally.

See [the dataset and feature feasibility review](FEATURE_REVIEW.md) for sources, limitations and ideas worth deferring.

### Customer app and side-by-side demo

The customer app remains at `/customer`, case tracking at `/customer?track=<reference>`, and the recording view at
`/demo`. Its officer pane uses the redesigned workspace at `/officer`. These two child pages allow same-origin
framing for the demo; other sites cannot frame them. The root `/` remains the standalone officer workspace.

### Recording the video

1. Open `/demo` in a full-screen browser window, press **Reset demo**, and set the speed (1× for the video).
2. Play the scenes in this order: **Maria** (protected in under a minute, jumps to P1), **Minh** (Vietnamese; adds to
   his card and the officer sees it live), **Sam** (P4: one click and the AI sends the answer), **Priya**, **Jordan**
   ("talk to a person").
3. Between scenes, work the officer side: choose **Review case** for Maria, show **Evidence** and **Customer context**,
   then **Review & approve** and confirm. Review Sam's AI-after-approval plan: his card on the left reaches Done.
   Open Minh and **Modify plan** (add a callback) to create a suggestion, then show **Learning loop** and **Protocol library**.
4. To show a lead approving a new protocol version in one go, start the backend with `NRY_SUGGEST_THRESHOLD=1`.

The yellow caption strip says what is happening in each scene, so the video reads without a voice-over. The phone
footer says plainly that the customer's lines are scripted and everything else is live.

### The live demo

For the on-site pitch, everything runs on one laptop, exactly as above. Only a live Clario needs the internet.

- **Live Clario = the Retell agent.** It already has its own language model, voice, language detection and knowledge
  base, and its key stays in Retell, so no AI key is needed in this repo. It sends each card to `/webhook/retell`.
  Retell can't reach `localhost`, so open a tunnel (for example `ngrok http 8000`) and use your phone's hotspot, not
  the venue Wi-Fi. Open `/customer?track=<reference>` to show the customer's live card while the officer works.
- **Hand a judge the phone.** Remote access needs HTTPS, `NRY_STAFF_PASSWORD`, the intended hostname in
  `NRY_ALLOWED_HOSTS`, and `NRY_WEBHOOK_SECRET` for intake. The default demo permits only loopback clients.
  This remains a shared staff demonstration, not customer authentication for a deployed bank service.
- **Fallback.** If the internet or Retell fails, the scripted scenes on `/demo` still run the real backend, and the
  recorded video is the last resort.
- **Before going on stage:** reset the demo, run one scene end to end, check the officer name, and close other tabs.

### 2. Optional: legacy Streamlit dashboard

The previous dashboard remains available for reference. It is not needed for the new website. It does not implement
the new staff sign-in; use the same-origin website when authentication is enabled.

```bash
cd console
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run officer_app.py
```

It normally runs at `http://localhost:8501`. The recommended workspace is the new website on port 8000.

### 3. Send in cards by hand

Without Clario or the customer app, post cards from another terminal.

```bash
# Priya: $89 charge she didn't make, card already locked. 55, P3
curl -s localhost:8000/case -H 'content-type: application/json' -d '{"customer_id":"CUST-003","customer_name":"Priya S.","issue_type":"FRAUD_UNAUTHORISED","linked_transactions":"TX-7001","card_locked":true,"summary_en":"$89 charge I did not make"}'

# Minh: missing rent, in Vietnamese. 55, P3
curl -s localhost:8000/case -H 'content-type: application/json' -d '{"customer_id":"CUST-004","customer_name":"Minh N.","issue_type":"MONEY_MISSING","language":"vi","language_label":"Vietnamese","linked_transactions":"TX-8001","summary_en":"Missing $650 rent payment","summary_customer_lang":"Mất khoản tiền thuê nhà $650"}'

# Sam: not satisfied with the card delivery answer. 5, P4: the AI acts after one click
curl -s localhost:8000/case -H 'content-type: application/json' -d '{"customer_id":"CUST-002","customer_name":"Sam T.","issue_type":"CARD_DELIVERY","status":"QUEUED","summary_en":"Card not here yet; wants help"}'

# Maria: scam in progress. 100, P1. Watch her jump to the top
curl -s localhost:8000/case -H 'content-type: application/json' -d '{"customer_id":"CUST-001","customer_name":"Maria R.","issue_type":"SCAM_IN_PROGRESS","linked_transactions":"TX-9001","risk_signals":"CUSTOMER_REPORTS_PRESSURE,VULNERABILITY_CUES","summary_en":"Caller says someone claiming to be from Westpac told her to move her savings.","case_reference":"WGM-0412"}'
```

Watch the dashboard: Priya, Minh and Sam appear, then Maria arrives and takes the top spot on the next refresh (within
ten seconds in the new workspace, two in the legacy dashboard). Open
her case, read the reasons and evidence, and choose **Review & approve**, then confirm. Review Sam's routine case to
see the **AI acts after your approval** plan. More examples are in [`backend/README.md`](backend/README.md).

### Starting over

Cases are saved, so restarting the backend does **not** clear the queue. Press **Reset demo** on the dashboard or the
demo page, or:

```bash
curl -X POST localhost:8000/admin/reset
```

---

## Voice channel (optional)

The plan is **text first**. Voice reaches Clario only if the existing Retell voice agent is retuned to this design and
a test call passes in time; otherwise the demo runs by text and voice stays on the roadmap.

The Retell agent was built for the earlier plan, so its prompt still uses the old bands and lets the model estimate
the score. Whatever it sends, Prorio **recomputes the score itself** and never ranks on the agent's estimate. The
agent should use the band and `handoff` in the webhook reply instead of its own estimate.

If it is used, it sends the card by calling a **custom function** at the end of the conversation:

1. Make the backend reachable from the internet (Retell can't call `localhost`), for example `ngrok http 8000`. The
   address is then `https://<tunnel address>/webhook/retell`.
2. In Retell, add a custom function: method **POST**, that address, **Payload: args only** on, execution mode **Wait
   for completion**.
3. Define its parameters using the field names below, and tell the agent to call it once, after the customer confirms
   the card.
4. If you set `NRY_WEBHOOK_SECRET`, add an `x-webhook-secret` header with the same value.

| Field | Meaning |
|---|---|
| `customer_id`, `customer_name` | Who the customer is |
| `language`, `language_label` | For example `vi` and `Vietnamese` |
| `issue_type` | One of the 31 issue types in `backend/data/protocols.json` (the original 8 still work). Anything else is rejected |
| `summary_en`, `summary_customer_lang` | Short summary in English and in the customer's language |
| `linked_transactions` | For example `TX-9001,TX-9002` |
| `risk_signals` | Conversation cues only: `CUSTOMER_REPORTS_PRESSURE`, `VULNERABILITY_CUES`, `ESSENTIALS_AT_RISK`. Account signals are worked out by Prorio and ignored if sent |
| `customer_confirmed`, `customer_sentiment` | Whether the customer confirmed the card, and how they sounded |
| `proposed_explanation`, `proposed_actions` | Optional. Kept for reference; Prorio drafts the proposal from the Protocol Database |
| `status` | `TIER1_RESOLVED` (answered already, kept out of the queue) or `QUEUED` |
| `case_reference` | An existing `WGM-####` reference. If missing, one is made starting at `WGM-0900` |
| `safeblock_activated`, `card_locked` | Whether the customer turned on SafeBlock or locked their card during the conversation. Recorded, not scored |
| `priority_score`, `priority_band`, `priority_reasons` | Accepted but **never used for ranking** |

Lists may be sent as comma-separated text or as a JSON list, and `null` means "not provided". The webhook replies
with a short note for the agent, for example
`{"case_reference": "WGM-0412", "queued": true, "priority_band": "P1", "handoff": "WARM_TRANSFER_FRAUD",
"caller_message": "A fraud specialist is joining now.", "updated_existing_case": false}`. `handoff` is
`WARM_TRANSFER_FRAUD` (P1 only), `QUEUE` or `NONE`. If the customer already has an open card about the same issue, that
card is updated and its reference returned (gate G6).

---

## Reference: backend endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/webhook/retell` | Receives a card from Clario; Prorio scores it and drafts a proposal; short reply with band, `handoff` and caller message. With `case_reference` and `correction`, records the customer's correction on their open card |
| POST | `/case` | Same as above, for posting cards by hand; returns the full card |
| GET | `/queue` | The priority list: open cases, most urgent first, with reasons and current waiting time |
| GET | `/case/{id}` | One full card, including Prorio's proposal and trace |
| GET | `/case/{id}/proposal` | Prorio's proposed solution: protocol and version, actions, officer tasks, checks, customer message, sources |
| GET | `/case/{id}/trace` | What Prorio did, step by step |
| GET | `/case/{id}/status` | The customer's view: Received, Ranked, With an officer, Action taken, Done, and the outcome. No score |
| POST | `/case/{id}/pickup` | An officer opens the case (`{"officer": "name"}`); the customer sees "With an officer" |
| POST | `/case/{id}/decision` | `{"decision": "APPROVE" \| "MODIFY" \| "MANUAL", "actions": [...], "officer": "name", "note": "...", "suggest_update": true}` |
| POST | `/case/{id}/complete` | Close a Manual case: `{"note": "what was done"}` (sent to the customer) |
| POST | `/case/{id}/rerank` | `{"band": "P1", "reason": "..."}` or `{"score": 90, "reason": "..."}` (0 to 100). Reason required |
| GET | `/audit/{id}` | The audit log for a case |
| GET | `/protocols` | Every protocol with its version, harm category, minimum band and decision counts |
| GET | `/protocols/{issue_type}` | One protocol as Prorio uses it, with approved changes and sources |
| POST | `/protocols/{issue_type}/rollback` | Undo the latest approved version |
| GET | `/suggestions` | Protocol suggestions from officers' Modify and Manual decisions |
| POST | `/suggestions/{id}/approve` | Protocol owner approves (only once it has been suggested enough times); creates a new version |
| POST | `/suggestions/{id}/reject` | Protocol owner rejects |
| GET | `/meta` | Fixed lists for the dashboard: actions, bands, issue types, demo clock |
| GET | `/` | The new same-origin officer workspace |
| GET | `/workspace/session` | Current staff identity and local demo status; never credentials |
| GET | `/workspace/cases` | Compact active, manual and completed case list |
| GET | `/workspace/insights` | Read-only analytics across saved cases; ownership-checked payment totals and live response watch |
| GET | `/case/{id}/context` | Masked records belonging to this case's customer, reported/verified protection and evidence-clock history |
| POST | `/demo/seed` | Add synthetic examples once, preserving existing work; local demo mode only |
| GET | `/clario/{customer_id}/lookup` | Clario's read-only look-up for the signed-in customer: first name, masked accounts, card delivery, payees, recent transactions. No balances |
| GET | `/demo`, `/officer`, `/customer` | Recording demo, redesigned officer workspace and retained customer app |
| POST | `/admin/reset` | Clears all cases, demo account changes, suggestions and approved versions (no password; demo only) |

Errors: `404` not found, `409` already decided or not ready, `422` invalid request (unknown issue, missing reason, an
action not on the allowed list). Searchable, self-hosted API/schema reference: `http://localhost:8000/docs` while
the backend runs. The OpenAPI document is at `/openapi.json`.

Executable actions (all mocked, they only record that they happened): `ACTIVATE_SAFEBLOCK`, `BLOCK_CARD`,
`RAISE_DISPUTE`, `DRAFT_PAYMENT_RECALL`, `DRAFT_PAYMENT_TRACE`, `DRAFT_SCAM_REPORT`, `DRAFT_HARDSHIP_NOTES`,
`DRAFT_COMPLAINT_RESPONSE`, `ORDER_REPLACEMENT_CARD`, `BOOK_CALLBACK`, `SEND_CUSTOMER_UPDATE`, `SEND_GUIDE_LINK`,
`REFER_SPECIALIST_TEAM`. Drafts are always drafts, and money is never moved.

---

## Where data is kept

- **Customer data** (accounts, transactions, cards) is read from `backend/data/` on every start.
- **Cases** are saved in a small **SQLite** file, `backend/nry.db`, created on first start and not committed to git.
  Cases, audit logs, re-ranks, mocked account changes, protocol suggestions and approved protocol versions survive a
  restart. `protocols.json` itself is never written by code.
- To empty it, use **Reset demo data** or `POST /admin/reset`. Set `NRY_DB` to use a separate file.

---

## Settings

All optional environment variables. (The `NRY_` prefix is left over from the earlier project name.)

| Variable | Default | Used by | Meaning |
|---|---|---|---|
| `NRY_API` | `http://localhost:8000` | Dashboard | Where the backend is |
| `NRY_OFFICER` | `officer` | Dashboard | Name written in the audit log for decisions |
| `NRY_DB` | `backend/nry.db` | Backend | Where the database file lives |
| `NRY_WEBHOOK_SECRET` | none (open) | Backend | If set, `/webhook/retell` and `/case` need this value in an `x-webhook-secret` header |
| `NRY_NOW` | `2026-11-15T12:00:00Z` | Backend | The demo clock for account evidence. `real` uses the real clock |
| `NRY_SUGGEST_THRESHOLD` | `3` | Backend | How many times a protocol suggestion must be made before the owner can approve it. Set `1` for a quick demo |
| `NRY_CORS_ORIGINS` | none | Backend | Comma-separated web origins allowed to call the API from a browser. Not needed: the pages are served by the backend itself |
| `NRY_STAFF_PASSWORD` | unset | Backend / new website | Enables HTTP Basic staff authentication for the website, staff APIs, docs and administration. Use a strong secret and HTTPS for remote access; never commit it |
| `NRY_STAFF_USER` | `officer` | Backend / new website | Staff username when password protection is enabled; this authenticated identity is used in audit records |
| `NRY_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1],testserver` | Backend | Comma-separated hostnames accepted by the server. Add the actual hostname when placing the application behind an HTTPS proxy; avoid wildcards |

Without a staff password, staff access is restricted to loopback clients. Secret-authenticated intake can still be
used by a server-to-server voice integration. Remote intake and intake in staff mode require `NRY_WEBHOOK_SECRET` to be
configured; an unset secret fails closed. The browser never receives either secret. Cross-origin browser mutations
are rejected unless their origin is explicitly trusted through `NRY_CORS_ORIGINS`; unrestricted CORS has been removed, and the website uses a strict self-only Content Security Policy,
frame protection, no-store responses and text-only rendering of API data.

This is still a single-account prototype, not production banking authentication: it has no SSO, per-officer accounts,
role separation or session revocation. Use synthetic data only. See [the interface design and security notes](DESIGN.md).

---

## Tests

Run from the `backend` folder with its environment switched on.

| Command | What it checks |
|---|---|
| `python -m prorio.selftest` | Every worked example in "How priority is worked out", the gates, the cross-case check, the firewall (summaries are ignored), and that all 31 protocols produce a proposal |
| `python test_api.py` | The whole backend through its endpoints: priority order, `handoff` reply, one problem one card, decisions, the P4 AI action, the customer status tracker, the learning loop, re-ranking and error cases |
| `python test_db.py` | Restarts the backend for real and checks nothing was lost, including approved protocol versions |
| `python test_workspace.py` | Website assets, local-only demo access, staff authentication, protected intake, audit identity, origin/host checks and additive sample loading |
| `python test_insights.py` | Empty and populated analytics, payment deduplication, customer ownership, clocks, stages, response-watch boundaries and context access control |

The API/workspace tests use an in-memory database; persistence checks use a temporary file. They never touch `nry.db`.

Browser regression checks (Node 22.12+; development dependencies only):

```bash
cd frontend
npm ci
# If Chromium is not installed: npx playwright install chromium
npm test
```

The browser suite starts its own backend and temporary database, uses installed Chromium when available, and checks
the real UI: filtering, pickup, cancellation, approval, modified actions, manual outcomes, re-ranking, protocol changes,
hostile content, connection failures, chart drill-downs, score caps, customer context, handoffs, responsive layouts and automated WCAG accessibility checks. Screenshots and
accessibility reports (including checks requiring manual review) are written to ignored `frontend/test-results/`.
Set `BEACON_CHROMIUM` to choose another Chromium executable, `BEACON_PYTHON` for the backend Python executable, or
`BEACON_TEST_PORT` if its default port 8025 is occupied.

---

## Project layout

```
Team-Astars/
├── README.md             this file
├── BUILD.md              the original build brief (earlier plan, kept for reference)
├── backend/
│   ├── main.py           the web service and its endpoints
│   ├── prorio/           Prorio, the Priority and Protocol agent
│   │   ├── agent.py      the steps and the trace; card_from() is the firewall
│   │   ├── evidence.py   verified account signals from account data
│   │   ├── score.py      the 0 to 100 score, bands and gates
│   │   ├── protocols.py  reads protocols.json plus approved versions
│   │   ├── propose.py    turns a protocol into a proposal; the executable action list
│   │   ├── learning.py   officers teach, leads approve
│   │   └── selftest.py   python -m prorio.selftest
│   ├── store.py          keeps cases, runs Prorio, officer decisions, re-ranks and the status tracker
│   ├── models.py         the shape of incoming requests
│   ├── mock_data.py      read-only look-ups over the demo customers and transactions
│   ├── db.py             saving to and loading from the SQLite file
│   ├── data/             customers.json, transactions.json, cards.json (made-up data),
│   │                     protocols.json (Protocol Database), PROTOCOLS_SOURCES.md (its sources and copyright rules)
│   ├── test_api.py  test_db.py
│   ├── requirements.txt
│   └── README.md         extra ready-to-paste test commands
├── frontend/             the new website: self-hosted HTML, CSS and JavaScript; no build step
│   └── tests/            isolated browser workflow checks
└── console/             optional legacy Streamlit interface
    ├── officer_app.py    the officer dashboard
    └── requirements.txt
```

---

## What is real and what is pretend

| Real in the prototype | Pretend (on purpose) |
|---|---|
| Scoring cards in code from account data, with written reasons | Customer log-in and Face ID checks |
| The queue order, bands, gates and waiting-time rule | SafeBlock, card locks, disputes, callbacks and messages: they only *record* that they happened |
| Officer decisions, re-ranking and the audit log | Payment recall and scam reports: always **drafts**; money is never moved |
| Saving cases to a database | All the banking data: it's invented |

Guardrails throughout: the customer is told they are talking to an AI; answers come only from the customer's data or
the Westpac knowledge base; the AI never moves money; "talk to a person" is always available; every action is logged.

---

## Known limits and future work

- **Prototype access control.** The new website supports optional staff authentication and otherwise restricts staff
  access to loopback clients. This is not production SSO or role-based banking access. The legacy Streamlit app is for
  local reference only. Reset is available through the protected API, not as a prominent website button.
- **The new queue refreshes every 10 seconds**, pauses polling in background tabs and makes failed updates visible.
  The legacy Streamlit queue polls every 2 seconds. Neither uses push.
- **One machine, one process.** SQLite with a single connection suits a demo, not production.
- **Demo dates.** Sample transactions are dated 9 to 15 November 2026. Scoring uses a fixed demo clock (`NRY_NOW`), so
  it is unaffected; the plain "recent transactions" look-up uses the real clock and comes back empty once the dates
  are old.
- **Not yet built:** see [Build status](#build-status-what-this-repo-runs-today).
- The Retell agent's transfer number (`+61400000000`) is a placeholder and always fails.

---

*Built by Team Astars for the Westpac hackathon.*
