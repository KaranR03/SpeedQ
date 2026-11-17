# Westpac SpeedQ: submission video shot list

Team Astars · target length **about 7:15** (8:00 maximum) · 16:9, 1080p

Scenes 1 and 3 are AI-generated in Higgsfield. Scene 2 is the team on camera plus a screen recording of the
live demo (`/demo`). **All text, logos, phone screens, clocks and captions are added in the edit**, not
generated. AI tools garble text, and BRANDING.md says brand-use guidance applies.

---

## 0. Pipeline

1. **Character references (3 images).** Maria, Sam and the Officer. Every video shot uses these as
   `image_references`, so the same faces appear in Scene 1 and Scene 3.
2. **Video shots (14 clips).** Model: **Seedance 2.0** (`seedance_2_0`). It is reference-driven and keeps the
   same identity across shots. Settings: 16:9, 5–6 s, `generate_audio: false`. Narration, hold music and
   ambience are added in the edit.
   - **Draft pass:** `mode: fast`, 720p, so takes are cheap to re-roll.
   - **Final pass:** `mode: std`, 1080p, only for the takes you pick.
3. **Fallback if time or credits run out:** use the 3 character stills (plus a few keyframe stills) with slow
   Ken Burns zooms in the editor. Do this rather than skipping the scenes.

### Style bible (append to every video prompt)

> Photoreal cinematic film, Apple product-film aesthetic, 35mm lens, shallow depth of field, slow controlled
> camera move, clean minimalist modern Australian interiors, natural soft light, subtle film grain. No text,
> no subtitles, no logos, no brand marks, no readable screens.

- **Scene 1 grade:** cool, slightly desaturated, late-afternoon to dusk, harsh fluorescent office light.
- **Scene 3 grade:** warm, bright morning light. Same compositions as Scene 1, so the "after" shots rhyme
  with the "before" shots.

### Framing for split screen

Scene 1 and Scene 3 put Maria (left) and Sam (right) side by side. Generate in **16:9 with the subject
centred and space either side**, so each clip can be cropped to a half-width panel without cutting off the
face.

---

## 1. Character references (image generation)

| ID | Character | Prompt |
|---|---|---|
| C1 | **Maria Russo**, scam victim (P1) | Photoreal portrait of a 64-year-old Italian-Australian woman, warm olive skin, shoulder-length silver-grey hair, reading glasses on a chain, soft cream cardigan over a navy blouse, kind but tired face. Seated at a wooden kitchen table in a bright Queenslander-style home in Brisbane. Natural window light, 50mm, neutral expression, looking slightly off camera. Plain background detail, no text, no logos. |
| C2 | **Sam Taylor**, card delivery question (P4) | Photoreal portrait of a 27-year-old Australian man, light brown messy hair, short stubble, relaxed friendly face, grey crew-neck t-shirt. Sitting on a light linen couch in a modern Brisbane apartment with plants. Soft daylight, 50mm, relaxed expression, looking slightly off camera. No text, no logos. |
| C3 | **Customer Service Officer** | Photoreal portrait of a 33-year-old South Asian Australian woman, dark hair in a low bun, slim black over-ear headset with a boom mic, plain charcoal knit top, no name badge. Seated at a modern contact-centre desk with a monitor beside her, soft office light, 50mm, attentive expression. No text, no logos, screen not readable. |

---

## 2. Scene 1: the problem (≈60 s, 8 shots)

On-screen card first, in the edit: **"Dramatisation. Every caller joins the same line."**

| Shot | Dur | Split panel | Prompt (+ style bible + Scene 1 grade) | Edit overlay |
|---|---|---|---|---|
| S1-01 | 5 s | Full frame | Extreme close-up of a smartphone lying face-up on a wooden kitchen table, screen glowing softly with an on-hold call, speakerphone on. Dust in a beam of late-afternoon light, slow push-in. | Hold music starts |
| S1-02 | 6 s | Left (Maria) | [C1] Maria holds a phone to her ear at her kitchen table, worried, other hand pressed to her forehead, an open laptop behind her. Slow push-in on her face. | Timer starts `00:00` |
| S1-03 | 6 s | Right (Sam) | [C2] Sam lounges on his couch eating a bowl of cereal, phone on speaker resting on his knee, relaxed and idly waiting. Static camera, gentle handheld feel. | Timer starts `00:00` |
| S1-04 | 5 s | Right (Sam) | [C3] The officer answers a call, adjusts her headset mic, smiles politely and starts typing. Medium shot. | Sam's timer stops at **`05:12`**. "Hi, when's my new card arriving?" |
| S1-05 | 6 s | Left (Maria) | [C1] Same framing as S1-02. Time-lapse: window light shifts from golden afternoon to blue dusk while Maria keeps waiting, rocking slightly, phone still at her ear. | Maria's timer runs on to **`30:00+`**. Insert: "$4,800 sent to a new payee" (phone screenshot) |
| S1-06 | 6 s | Full frame | [C3] Wide shot of a contact-centre floor. Every desk is busy, officers on calls, desk phones blinking. Slow pull-back from the officer rubbing her temples. | "Calls waiting" counter climbs |
| S1-07 | 5 s | Full frame | [C3] Close-up of the officer typing, pausing, sighing, re-reading a notepad covered in scribbles, as if asking a caller to repeat everything again. | VO: "Can I get your customer number… and what happened?" |
| S1-08 | 5 s | Left → full | [C1] Maria finally lowers the phone from her ear and closes her eyes. Hold on her face, fade to black. | Line: **"The most urgent caller waited the longest."** |

**Edit notes:** the timers and wait numbers are dramatisation. In the edit:
- Put a small **"Dramatisation"** tag in the corner.
- Follow the scene with the evidence cards (§3).
- Don't present 5 and 30 minutes as measured Westpac figures.

---

## 3. Evidence cards (≈25 s, motion graphics, no AI)

Use white type on black and one fact per card, Apple style. Sources come from the research notes.

1. "One hour on hold. Then the call dropped." (ASIC Report 782, hardship case study)
2. "Passed between three departments. Details given to each." (customer reviews)
3. "$26 million penalty for missed hardship requests." (ASIC v Westpac [2026] FCA 651)

Put the source in small type at the bottom of each card.

---

## 4. Scene 2: reveal and live demo (≈4:30, camera + screen recording)

| Time | Segment | What's on screen | Talking points |
|---|---|---|---|
| 1:40–2:10 | Presenters + reveal | Team full-frame against a clean wall, then cut to white with **Westpac SpeedQ** and a red accent `#DA1710` | Who you are. "What if the bank knew who was in danger before anyone picked up?" |
| 2:10–2:55 | Pipeline diagram | 2D animation built one stage at a time: Customer (in app) → **Clario** → **Customer Service Card** → **Prorio** (harm score + Protocol Database) → **Officer** (Approve / Modify / Manual) → outcome → learning loop | Two agents as a firewall: the agent the customer talks to has almost no power, and the agent with power never hears the customer directly |
| 2:55–5:40 | Live demo on `/demo` | Customer app beside the officer dashboard. Face bubble in the corner. Zoom in on each key moment in the edit | See the beats below |
| 5:40–6:10 | Trust | Presenter + three big lines | "AI can close doors; only people open them." · "Priority is calculated by code, not the language model." · "The AI never moves money." |

**Demo beats (record in this order, about 25–30 s each):**
1. Sam asks about his card. Clario answers from his own data (due 19 Nov) and asks "Did that solve it?" He never queues.
2. Maria says she sent money to a new payee. SafeBlock protection is offered **first**.
3. The card builds live on the officer dashboard (live intake). Maria confirms or corrects it.
4. Prorio ranks it at **P1, score 100**. Open the score explanation: harm + time to harm + verified account signals.
5. The officer opens the case: full context and the proposed protocol. Click **Approve**.
6. The customer sees live status and the outcome with a reference number.
7. Learning loop: a modified decision becomes a protocol suggestion that a lead approves.

---

## 5. Scene 3: the world after (≈50 s, 6 shots)

Use the same characters and the same compositions as Scene 1, with the Scene 3 warm grade.

| Shot | Dur | Split panel | Prompt (+ style bible + Scene 3 grade) | Edit overlay |
|---|---|---|---|---|
| S3-01 | 5 s | Left (Maria) | [C1] Maria at the same kitchen table in bright morning light, taps her phone screen with purpose, then lifts it to speak. Slow push-in, mirroring S1-02. | Composite the real customer app screen (Help → Clario) |
| S3-02 | 6 s | Left (Maria) | [C1] Maria speaking to her phone on speaker, then exhaling with relief, hand on her chest, shoulders dropping. | Insert the real SafeBlock screen: "Accounts locked." |
| S3-03 | 5 s | Right (Sam) | [C2] Sam on his couch glances at his phone, reads, smiles, gives a small nod and goes back to his breakfast. | Sam's timer: **answered in seconds**, "Due 19 Nov" |
| S3-04 | 6 s | Full frame | [C3] The officer, calm and focused, looks at her monitor, nods once, clicks the mouse, then speaks into her headset with a warm, reassuring expression. Medium shot. | Composite the real dashboard: Maria at **P1**, Approve |
| S3-05 | 6 s | Full frame | [C3] Wide shot of the same contact-centre floor, now calm, officers working at an even pace, soft warm light. Slow pull-back, mirroring S1-06. | — |
| S3-06 | 5 s | Left → full | [C1] Maria puts her phone down beside a cup of tea, smiles softly, looks out the window. Golden light, hold, fade to white. | **Westpac SpeedQ** · "Right person. Right order. First time." · Team Astars, [University] |

**Keep the claims honest:**
- Don't show a "30 min → 2 min" number. The README calls timings "demonstration targets".
- The point Scene 3 makes is that Sam never waits, Maria is protected first, and the officer starts with full
  context.

---

## 6. Audio

- **Narration:** record yourselves, close-mic'd, in a quiet room.
- **Hold music:** Scene 1, slightly distorted and tinny.
- **Score:** a soft piano or synth bed for Scenes 2 and 3.
- **Silence:** leave a 1-second beat of silence before each title card.
- **Music licence:** use royalty-free music, or generate it, so YouTube doesn't flag the video.

## 7. Credit and time checklist

- [ ] Top up credits. The Higgsfield balance was **10 credits** at planning time, which isn't enough for one
      1080p clip.
- [ ] Generate C1–C3 first and approve the faces before any video.
- [ ] Draft pass (720p fast) for all 14 shots, then pick the takes.
- [ ] Final pass (1080p) for the picked takes only.
- [ ] Record the demo while the AI shots render.
- [ ] Edit, export, upload to YouTube as **unlisted**, email by **4:00pm**.
