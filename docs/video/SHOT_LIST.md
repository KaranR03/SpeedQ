# Westpac SpeedQ: presentation-slide video plan

Team Astars is making the submission video from **presentation slides with recorded narration**. Use original
slide diagrams and screenshots captured from this prototype. The deck and exported video are still to be produced;
this document is the production plan.

A working target is **about six minutes**, in 16:9. Confirm the competition's actual duration, submission format,
deadline and upload rules before recording; this target is not a verified competition requirement.

## Slide sequence

| Slide | Target | What to show | Narration and evidence |
|---|---:|---|---|
| 1. The idea | 20 s | Westpac SpeedQ, Team Astars and one sentence: “Explain once. Reach the right person.” | Introduce the independent hackathon prototype and synthetic data. Apply the [brand-use guidance](../../BRANDING.md) to the logo. |
| 2. The customer problem | 35 s | A simple journey diagram contrasting an urgent scam report with a card-delivery question | Explain why context and urgency matter. Label the journey illustrative; use no invented wait-time or savings figures. |
| 3. How it works | 45 s | Customer → Clario → confirmed Customer Service Card → Prorio → officer → customer outcome | Clario collects the need; deterministic code ranks it from evidence and approved protocols. Explain where confirmation and human approval happen. |
| 4. A card taking shape | 45 s | Two or three screenshots: customer conversation, unranked Live intake draft, confirmed card | Show what the customer can read and correct. Label captures from scripted scenes; distinguish them from a rehearsed live Retell session. |
| 5. Priority with reasons | 45 s | Maria's urgent case and its evidence/score explanation; a small comparison with Sam's delivery question | Show the score and band actually displayed in the captured run. The score measures project priority, not AI confidence or predicted loss. |
| 6. People stay in control | 55 s | Officer review/approval and outcome; a small second-officer ownership or completion screenshot | Explain Approve, Modify and Manual, claim protection, the audit trail and shared completion updates. Banking actions are simulated. |
| 7. Useful insight and learning | 40 s | One Care insights chart and a protocol suggestion/version example | Charts describe saved cases. A human approves protocol changes. Do not describe chart counts as measured bank productivity or the learning loop as model retraining. |
| 8. Delivery and next steps | 35 s | Implemented prototype, live rehearsal still required, team credits and the closing message | Summarise the user benefit, state what remains, and distinguish the working prototype from production deployment. |

The sequence totals approximately 5:20, leaving about 40 seconds for transitions. Shorten narration to match the
confirmed submission limit. Keep one main message on each slide and put source links beside any external fact.

## Build the slides

1. Use the team's preferred slide editor. Choose large readable type, white/off-white backgrounds and restrained
   red accents matching the dashboard. Keep the current dashboard layout in screenshots.
2. Use diagrams, short labels and speaker notes. Crop screenshots to the relevant interaction rather than shrinking
   an entire dashboard into an unreadable slide. Use simple reveals to explain the handoff in order.
3. Record your own narration in a quiet room. Add captions or provide the narration transcript. Use readable contrast
   and avoid rapid transitions or information conveyed only by colour.
4. Include Team Astars, the synthetic-data disclosure and the independent-prototype statement. Use the Westpac logo
   only within the scope of confirmed competition rules or permission; see [BRANDING.md](../../BRANDING.md).
5. Keep researched claims separate from the example story. An illustration of a slow queue is not a measurement of
   Westpac's actual service. Use verified sources for external statistics, or leave those statistics out.

## Capture the prototype

Follow [BUILD.md](../../BUILD.md) for the current setup and [the README recording guide](../../README.md#recording-the-video).
Use a disposable rehearsal database before using **Reset demo**; preserve existing team cases.

- Officer workspace: `/officer` (or `/`). Use **Load sample cases** for an additive synthetic queue.
- Customer and scripted side-by-side scenes: `/customer` and `/demo`. Capture only the states needed for the slides.
- Show draft → confirmation → ranking → officer review → outcome in order. Capture the reasons shown by the backend.
- For collaboration, use two local demo officer tabs and show an actual claim or named completion.
- For a learning-loop screenshot, a disposable demo can use `NRY_SUGGEST_THRESHOLD=1`. Restart after changing settings.
- Live voice/chat requires the configured Retell agents and [LIVE_TEST_CHECKLIST.md](../../LIVE_TEST_CHECKLIST.md).
  The deterministic scripted fallback remains available without an external AI key.

## Claims and assets

- SafeBlock, card locks, disputes, callbacks and payment recall are simulated or drafts. No money is moved.
- A screenshot of a live intake card does not establish that a real phone transfer worked. The configured fictional
  transfer number cannot connect to a real fraud team.
- Demo timing is illustrative. Do not claim measured wait reduction, fraud accuracy, recovery totals or satisfaction.
- Source/copyright guidance is in [PROTOCOLS_SOURCES.md](../../backend/data/PROTOCOLS_SOURCES.md). Capture this prototype's
  interface rather than importing Westpac website photographs or marketing artwork.

## Record and export

- [ ] Confirm the competition's duration, deadline, file/link requirements and brand-use rules.
- [ ] Agree the slide outline and narration with the team; assign a presenter and a final reviewer.
- [ ] Capture current screenshots, label scripted scenes and check that only synthetic data is visible.
- [ ] Finish the slide deck and speaker notes. Check text at normal presentation size.
- [ ] Record the slide presentation with narration using the chosen editor or screen recorder.
- [ ] Export a broadly playable video, such as MP4 at 1080p if the submission rules permit it; retain a PDF deck backup.
- [ ] Watch the complete export on another device, checking sound, captions, cropping, pacing and readability.
- [ ] Verify the submission link/file opens with the intended access, then submit through the official process.

## Current delivery status

The software is implemented on `main` through PR #19. The slide deck, narration, final export, live Retell rehearsal
and organiser confirmation of logo use are **not marked complete** by this document. Update this checklist only when
the team has the corresponding evidence.
