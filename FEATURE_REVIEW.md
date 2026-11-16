# Feasibility review: make the existing data useful

The selected implementation extends the officer workspace. The priority queue remains the first screen, and a new
**Care insights** view offers a graphical route into the work. The review and human approval flow stays intact.

## What is actually available

| Source | Records | Useful facts | Limits |
|---|---:|---|---|
| `backend/data/customers.json` | 6 | Masked accounts, balances, language, payees, security and lockout events | Synthetic snapshots; not live banking feeds |
| `backend/data/transactions.json` | 31 | Owner, amount, payee, timestamp and transaction type | Not labelled fraud outcomes; not a representative behavioural history |
| `backend/data/cards.json` | 6 | Current/mock block state and replacement delivery milestones | Expected delivery is not proof of arrival |
| `backend/data/protocols.json` | 31 protocols | Harm points, minimum bands, checks, actions and sources | Procedures do not establish that checks occurred in real life |
| Saved case and audit records | Varies by local workspace | Current stages, scores, score parts, decisions, pickup history, repeat contacts and protocol suggestions | Small demonstration history; case creation uses the live clock |

Account evidence is anchored to the existing fixed demo clock. Current case age uses the live clock. Both are labelled
in the interface; joining them into a single unqualified “today” chart would misrepresent the data.

## Implemented additions

| Addition | Officer benefit | Evidence and safeguards |
|---|---|---|
| Interactive urgency ring and issue bars | Understand the queue and open the matching cases directly | Counts come from active saved cases; the charts filter the real queue |
| Case-stage flow and open-age distribution | Find waiting, manual, completed and ageing work | Stages are mutually exclusive; age includes active work already in review |
| Decision distribution | See approved, modified and manual decisions | Counts decisions once; does not claim accuracy, recovery or satisfaction |
| Response watch | Surface urgent cases that still need their first pickup | Current P1/P2 bands, actual creation times and the README's 2/30-minute project targets; never presented as bank SLAs |
| Evidence coverage and language support | Find cases requiring verification or language assistance | Separates account signals from conversation cues; counts active cases rather than inventing confidence percentages |
| Linked outgoing payment total | Understand the size of the payments being reviewed | Deduplicates transaction IDs, checks customer ownership, excludes completed cases, and labels AUD amounts as unconfirmed outgoings rather than losses |
| Visual priority components | Explain why the backend selected a priority | Uses backend score parts; explicitly reconciles caps, floors and overrides instead of treating the subtotal as the final score |
| Customer context | Bring relevant account, payment and delivery facts into the case | Masks account references, uses only the case's customer, separates reported protection from verified state, and collapses unrelated recent history |
| Handoff brief | Give the next officer a concise, consistent starting point | Explicitly initiated copy action; no external messaging, no full account numbers or copied account balances; labels simulated data |

The new visuals use local SVG, native meters and semantic controls. They require no chart service, AI API key,
production JavaScript dependency, new database, frontend build or separate server.

## Ideas to defer, and what would make them feasible

| Idea | Why it is deferred | Useful prerequisite |
|---|---|---|
| Queue forecasts and staffing recommendations | Six synthetic customers and a short saved-case history cannot support reliable demand predictions | Sustained arrival/handling history, staffing capacity, business calendars and evaluation against actual outcomes |
| Fraud network or payee risk scores | Common payees do not establish fraud; the supplied examples do not form a validated fraud network | More representative ownership-checked cases and adjudicated outcomes; keep existing cross-case signals as evidence for human review |
| “Money saved”, AI accuracy or customer happiness charts | Simulated actions and decisions contain none of these outcome measurements | Verified recovery events, labelled evaluations and consented feedback |
| Automatic translation or a new voice agent | A preferred language and one supplied translation are not a translation system | An approved translation/voice integration, credentials and a checked customer-facing workflow |
| Real callbacks, account changes or payment recovery | The repository intentionally mocks these actions | Authorised bank integrations, authentication, permissions, operational controls and end-to-end validation |
| Production deployment with a shared staff password | The current password option is a prototype control | SSO, individual identities, protocol-owner roles, session controls and monitoring |

## Review priorities

The browser checks exercise chart-to-case filtering, empty states, score reconciliation, customer ownership, delivery
milestones, handoff content, existing decisions, mobile layout and automated accessibility rules. Backend checks cover
deduplication, ownership boundaries, age buckets, waiting-driven priority promotion, clock separation, manual/completed
stage counts, unknown customers and inherited authentication. Reports retain checks needing manual accessibility review.

The next practical increment should be selected from observed officer feedback: which chart helps select a case,
which account fact saves a lookup, and whether handoff notes make follow-up easier. More charts should earn their place
by helping with one of those decisions.
