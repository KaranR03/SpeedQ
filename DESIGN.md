# Beacon Assist officer workspace

The officer's first question is “who needs help next?” The first screen answers that with an evidence-ranked queue,
four live counts and a short preview of one customer. The interface never invents response-time statistics or case data.

## Information flow

1. **Scan:** priority, customer, issue, waiting time and status. Search names, references and issue descriptions, or
   filter by priority and waiting status. The scoring engine remains deterministic and unchanged.
2. **Preview:** a short need statement, the primary priority reason and up to three recommended actions. Selection is
   read-only; it does not notify the customer that an officer is working on the case.
3. **Review:** explicitly pick up the case. The case workspace separates the customer's need, recommended plan and
   customer-visible progress. Evidence, sources, protocol conditions and activity history are available on demand.
4. **Decide:** approve, modify or handle manually. A confirmation dialog shows actions and checks before a decision
   is sent. Double submission is blocked while the request is running. Backend conflict checks remain authoritative.
5. **Finish:** automatic/mock decisions record outcomes immediately. Manual cases stay in **In review** until the
   officer writes the customer outcome. Completed cases and their audit trails remain accessible.
6. **Improve:** modifications and manual handling feed the existing learning loop. Suggestions remain separate from
   active protocols until the configured threshold is reached and a human approves a new version.

Required-check acknowledgements are interface safeguards, not proof that a real-world banking check occurred. The
prototype still simulates every banking action. Incomplete customer-message drafts require manual handling in this UI.

## Visual direction and branding

The original interface uses burgundy, a deep wine navigation rail, warm neutral surfaces, restrained line icons,
readable system fonts and generous spacing. Priority labels combine colour with text; urgency is not conveyed by
colour alone. Details are progressively disclosed instead of shrinking operational text to fit everything on screen.

This takes inspiration from the professionalism of banking websites. It does not reproduce Westpac's logo, exact
page composition, proprietary typography, images, copy or website source. The Beacon mark and interface assets in
`frontend/` are original to this project. No external fonts, trackers or UI scripts are loaded by the application.
The interface identifies Team Astars and states that it is an independent hackathon prototype using synthetic data.

These choices reduce copying and affiliation risks; they do not constitute legal clearance. Follow the competition's
brand-use rules and obtain permission before representing the prototype as an official bank service.

## Accessibility and resilience

- Semantic headings, labels, table headers, a skip link, visible keyboard focus and native modal dialogs.
- Search shortcut `/`, Escape to dismiss dialogs/navigation, and required fields before recording decisions.
- Mobile navigation hides its contents from keyboard focus while closed and blocks background clicks while open.
- Responsive queue and case layouts; reduced-motion preferences are respected.
- Connection errors are explicit; stale counts remain visible with an updates-paused status. A failed write stays
  in its dialog with an error instead of showing a false success. Background tabs pause polling.

## Security boundaries

The new interface is served by FastAPI on the same origin as its APIs, avoiding a separate frontend server and CORS
exceptions. All API-derived text is inserted as text nodes; source links must use HTTPS and cannot embed credentials.
There are no inline scripts or event handlers. A strict CSP limits scripts, styles and connections to the same origin;
framing, MIME sniffing, unnecessary browser permissions and caching are restricted. API documentation is self-hosted.

The default synthetic-data demo binds to loopback and rejects remote staff clients. Setting `NRY_STAFF_PASSWORD`
enables Basic authentication for all staff pages and APIs, including administrative operations. Authenticated audit
actors come from the server identity, not a caller's chosen name. Use HTTPS and a strong secret for remote access.
The voice webhook and secret-based case intake use `NRY_WEBHOOK_SECRET`; remote intake and protected staff mode
refuse intake when that secret is missing. Host validation and same-origin checks reject unsolicited browser writes.

Before a production pilot, replace the shared Basic account with organisation SSO, distinct officer/protocol-owner
permissions, session lifecycle controls and operational monitoring. SQLite and process-local state still target a
single-process demonstration. This change does not connect to real banking systems or turn simulated actions into
real operations.

## Validation

Run the three original backend suites, `python test_workspace.py`, and the browser suite described in `README.md`.
Browser tests use their own SQLite database and process, preserve the developer's data and capture desktop/mobile
screenshots. The interface has no build step or production Node dependency.

## Visual insights and case context

Care insights is a separate workspace so that extra information does not crowd the primary queue. Its charts have
text labels and counts, support keyboard input, and link directly to matching cases. Totals describe the saved local
workspace rather than a fabricated daily trend. Current priority drives the response watch, including cases promoted
by waiting; its targets are project design choices. Linked outgoing amounts are deduplicated and checked against the
case's customer and do not represent confirmed loss or recovery.

The Evidence tab shows the backend's five score components and the net effect of caps, floors or an officer override.
It never interprets a score as model confidence. The Customer context tab uses only the current case's customer and
keeps account-record protection separate from customer-reported actions. Recent unlinked history is collapsed. A
replacement card's expected date remains an expectation, not a completed delivery. A handoff brief can be copied only
through an explicit staff action and contains no account balances or full account numbers.

The same origin, strict CSP and text-node rendering apply to the new SVG charts, context and handoff text. There are
no external chart libraries or analytics trackers. New data endpoints require the same access controls as the queue.
See `FEATURE_REVIEW.md` for the source inventory, implemented choices and prerequisites for future ideas.
