# Live Clario test: end-to-end checklist

Goal: a real Retell call (or chat) as a demo customer, and watch the card form and rank on the officer screen.
Full background is in the README section "Live Clario (Retell voice and chat)". Tick each box as you go.
Never commit keys: type the `export` lines in your own terminal only.

## A. Have ready (5 min)

- [ ] **Retell API key**: Retell dashboard, Settings, API keys
- [ ] **Voice agent ID** and **chat agent ID** (both start with `agent_`)
- [ ] Both agents have the four custom functions: `lookup_customer`, `update_card`, `submit_card`, `correct_card`
- [ ] **ngrok** installed (`ngrok version`)
- [ ] Use a **phone hotspot**, not venue Wi-Fi
- [ ] Chrome or Edge, with microphone allowed for `localhost`

## B. Start everything (10 min)

1. [ ] **Tunnel** (terminal 1): `ngrok http 8000`. Copy the hostname, e.g. `abc123.ngrok-free.app`
2. [ ] **Backend** (terminal 2):
   ```bash
   cd backend && source .venv/bin/activate
   export RETELL_API_KEY=...
   export RETELL_VOICE_AGENT_ID=agent_...  RETELL_CHAT_AGENT_ID=agent_...
   export NRY_ALLOWED_HOSTS="localhost,127.0.0.1,[::1],abc123.ngrok-free.app"
   uvicorn main:app --host 127.0.0.1 --port 8000
   ```
   Keep this window visible: every Retell tool call prints here.
3. [ ] **Retell, both agents**: each of the four functions points to `https://abc123.ngrok-free.app/retell/tools/<name>`
   - [ ] Method **POST**
   - [ ] **Payload: args only: OFF** (the backend needs the call object to know who is calling)
   - [ ] **Wait for completion: ON**
   - [ ] If the tunnel was restarted, the hostname changed: update `NRY_ALLOWED_HOSTS` **and** all functions
4. [ ] Open the **customer app**: `http://localhost:8000/customer` (use `localhost`, not the tunnel address)
5. [ ] Open the **officer screen** in a second window: `http://localhost:8000/officer`
6. [ ] Click **Reset demo** first so you start clean (or load the sample cases)

## C. Run the test (10 min)

Use **Text Clario** first (quicker to debug), then **Call Clario**.

1. [ ] In the customer app, pick **Maria** in the bar above the phone, then **Get help**
2. [ ] Backend shows `POST /clario/session/chat` (or `/call`)
3. [ ] Clario greets Maria **by name** and asks no security questions
4. [ ] Say: *"Someone from the bank told me to move my savings to a new account. I already paid $4,800."*
5. [ ] **Officer screen, Live intake:** the card forms while you talk (not ranked yet)
6. [ ] Clario reads the card back. Say **yes**
7. [ ] Backend shows `POST /retell/tools/submit_card`
8. [ ] Clario says the returned message: **"A fraud specialist is joining now."**
9. [ ] Officer queue: Maria's case at **P1**, top of the list, with the reasons shown
10. [ ] Customer tracking page (`/customer?track=<reference>`) shows the card
11. [ ] Officer: **Review case**, then **Approve**. Check the audit log

Expected and fine: the P1 transfer to `+61 7 5550 4800` does **not** connect. That number is from a range
reserved for fiction.

## D. Repeat with other customers

- [ ] **Priya** ($89 charge you don't recognise): should be a lower band, not P1
- [ ] **Minh** (Vietnamese): card shows "Vietnamese (translated)" with the original summary available
- [ ] **Sam** (card delivery): answered without an officer, **not** in the queue
- [ ] **Correction:** after filing, tell Clario you forgot something. The filed card updates (`correct_card`)

## E. If something goes wrong

| Symptom | Likely cause and fix |
|---|---|
| `503` starting a call or chat | A `RETELL_*` setting is missing in the terminal that started the backend. Restart with all three |
| `400` on `/retell/tools/...` | Tunnel hostname not in `NRY_ALLOWED_HOSTS`. Fix it and restart the backend |
| `401` on a tool call | Wrong `RETELL_API_KEY`, or the request was altered |
| Clario can't find the customer | **Payload: args only** is ON. Turn it off |
| Card forms but never ranks | Clario never called `submit_card`. Check the agent's prompt and the customer's "yes" |
| No microphone | Allow it for `localhost`. Only `/customer` may use the mic |
| Nothing reaches the backend | Tunnel stopped or hostname changed. Check `ngrok` and the Retell function URLs |

## F. Fallback and before going on stage

- [ ] **Fallback if the internet or Retell fails:** `http://localhost:8000/demo` runs the scripted scenes on the same backend
- [ ] Press **Reset demo**, run one scene end to end, check the officer name, close other tabs
- [ ] Have the recorded video ready as a last resort
