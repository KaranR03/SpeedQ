# Protocol Database: where it comes from, and how we stay on the right side of copyright

`protocols.json` is the Beacon Assist Protocol Database: 30 scenarios Prorio can use to draft proposals. This note
explains how it was built and the rules for changing it.

## What it is and isn't

- It is **our own summary**, in our own words, of how banking situations are handled, based on **public** pages read
  on 16 Nov 2026: Westpac's help, security and FAQ pages, plus Australian rules and guidance (ASIC's ePayments Code,
  AFCA, ASIC RG 271 via AFCA, Moneysmart, the Australian Banking Association, Legal Aid NSW).
- It is **not** Westpac's internal procedure, and it does not claim to be. Steps marked `team_design` are our own
  design choices, not published rules.
- Every protocol lists its sources (titles and links). Facts can change; check the link before relying on one.

## The copyright position (read before adding anything)

Westpac's website terms say the information on westpac.com.au is for **personal reference only** and may not be
reproduced, distributed, or incorporated into another document or material
([terms, clause 2.1](https://www.westpac.com.au/terms-and-conditions/)). Westpac's robots.txt allows crawlers to visit,
but that only covers access; it doesn't give permission to copy.

So the database follows these rules:

1. **Facts, not wording.** Facts (for example "a temporary card lock lasts up to 15 days", or "most scam cases are
   resolved within 21 days") are not owned by anyone. The *wording* on the page is. We restate facts in our own words.
2. **No copied text.** We checked every Westpac source page against the file: **no run of 8 or more words matches**
   any of the 44 Westpac pages (checked 16 Nov 2026). Keep it that way.
3. **Link, don't copy.** Each source is a title and a link. Linking is fine.
4. **No page dumps in the repo.** Don't commit crawled pages, screenshots of Westpac pages, PDFs or Westpac logos.
5. **No phone numbers or email addresses** from Westpac pages; they go out of date. Point to the source page instead.
6. **Not an endorsement.** Don't present this as Westpac-approved. It is a hackathon prototype using synthetic data.

This is the team's careful reading, not legal advice. Two follow-ups are worth doing:

- **Ask the Westpac mentors** whether they are comfortable with summarised public help content in a hackathon repo.
  They are the organisers, so their answer settles it.
- **The Retell voice agent's knowledge base** holds 406 crawled westpac.com.au pages in a third-party service. That is
  closer to "reproducing" than this file is. If the voice agent is kept, ask the mentors about it too, or replace it
  with this summarised database.

## The Westpac design system (for the UI)

The organisers listed Westpac's GEL design system as a hackathon resource. The `@westpac/ui` package on npm is
published under the **MIT licence** (checked 16 Nov 2026), so installing it is fine. The GEL-next GitHub repository
itself has no licence file, so install the package rather than copying files from that repo. Don't use Westpac logos
in a way that suggests Westpac built or approved the product.

## How the database is meant to change ("officers teach, leads approve")

- Officers **suggest** changes through Modify or Manual decisions; nothing edits this file directly from the dashboard.
- A protocol owner approves a change; the protocol's `version` goes up (2.0 to 2.1) and the change is added to its
  history.
- Any new fact must come with a source link, in our own words, or be marked `team_design`.

## What each protocol contains

`issue_type`, `title`, `version`, `harm_category` (the README harm row it scores under), `min_band` (a gate, if any),
`clario_can_answer` (what Clario may tell the customer straight away), `protect_first` (the protective action offered
before queuing, always the customer's choice), `steps` (who does what, each with a source), `ai_may`, `officer_must`,
`required_checks`, `customer_message` (template), `timeframes` (each with a source), `notes`, `sources`.

New issue types compared with the README harm table: SCAM_ALREADY_PAID, VERIFY_CONTACT, UNAUTHORISED_ONLINE_BANKING,
IDENTITY_THEFT, LOGIN_HELP, ACCOUNT_RESTRICTED_ID_CHECK, PAYMENT_LIMIT_CHANGE, CARD_DECLINED, CARD_ACTIVATION,
PENDING_TRANSACTION, DIRECT_DEBIT_STOP, BPAY_MISTAKE, PAYID_ISSUE, FAMILY_VIOLENCE_FINANCIAL_ABUSE,
TRUSTED_PERSON_OR_ELDER_ABUSE, BEREAVEMENT, GAMBLING_HARM, ACCOUNT_CLOSURE, OUTAGE_INCIDENT. Each maps to an existing
harm category, so the scoring model doesn't change. One proposed new gate: safety cases (family violence, financial
abuse) never sit below P2.
