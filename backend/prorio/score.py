"""Scoring: the Westpac SpeedQ harm-clock score (0 to 100) and the gates. Every point has a written reason.

Score = Harm (0-60) + Time to harm (0-20) + Verified account signals (+10 each, max 20) + Care needs (+10)
        + Waiting (+2 per 10 minutes, max 10), capped at 100.
"""
from . import evidence, protocols

BAND_FLOOR = {"P1": 80, "P2": 60, "P3": 40, "P4": 0}
BAND_ORDER = ("P4", "P3", "P2", "P1")
BAND_LABEL = {"P1": "P1 Critical", "P2": "P2 High", "P3": "P3 Medium", "P4": "P4 Low"}

HARM_LABEL = {
    "SCAM_IN_PROGRESS": "Scam in progress", "UNAUTHORISED": "Money taken without consent",
    "ACCOUNT_ACCESS": "Locked out of own money or possible account takeover", "CARD_LOST": "Card lost or stolen",
    "PAYMENT_MISSING": "Payment missing", "HARDSHIP": "Financial hardship or safety",
    "DISPUTE": "Disputed charge", "COMPLAINT": "Complaint about service", "SERVICE": "Service request",
    "GENERAL": "General question",
}
# Things only the caller can tell us. They feed time-to-harm and care needs, never the verified signals (gate G1).
CALLER_SIGNALS = ("CUSTOMER_REPORTS_PRESSURE", "VULNERABILITY_CUES", "ESSENTIALS_AT_RISK")
CARE_TEXT = {"VULNERABILITY_CUES": "vulnerability cues in the conversation",
             "ESSENTIALS_AT_RISK": "can't pay for essentials"}

SIGNAL_POINTS, SIGNAL_MAX = 10, 20
NOW_POINTS, RECOVERABLE_POINTS = 20, 10
CARE_POINTS = 10
WAIT_STEP_MIN, WAIT_STEP_POINTS, WAIT_MAX = 10, 2, 10
G1_CAP = 79
SCAM_NO_SIGNALS = "Customer reports scam, no account signals yet: officer to verify"
NO_SIGNALS = "No verified account signals yet: capped below P1, officer to verify"
FIRST_SEEN = "Merchant never seen before on this account: scored as possible unauthorised, officer to confirm"

# What the customer is told for each band (never the score). Used in the reply to Clario.
BAND_MESSAGE = {
    "P1": "A fraud specialist is joining now.",
    "P2": "You're near the front of the queue. An officer will be with you within 30 minutes, or we can book "
          "a callback.",
    "P3": "Our team will look at this today.",
    "P4": "You'll get updates in the app, usually within minutes.",
}
HANDOFF = {"P1": "WARM_TRANSFER_FRAUD", "P2": "QUEUE", "P3": "QUEUE", "P4": "QUEUE"}
EXECUTOR = {"P1": "OFFICER", "P2": "OFFICER", "P3": "OFFICER", "P4": "AI_AFTER_APPROVAL"}


def band_for(score):
    for band in ("P1", "P2", "P3"):
        if score >= BAND_FLOOR[band]:
            return band
    return "P4"


def _band_up(band, steps=1):
    i = min(BAND_ORDER.index(band) + steps, len(BAND_ORDER) - 1)
    return BAND_ORDER[i]


def score(card, protocol, ev, minutes_waiting):
    """card: the structured Prorio input (see agent.card_from). Returns the priority dict."""
    reasons, gates = [], []
    issue = card["issue_type"]
    caller = [s for s in card["caller_signals"] if s in CALLER_SIGNALS]

    # 1. Harm, from the protocol's harm category
    harm_cat = protocol["harm_category"]
    if issue == "DISPUTE_CHARGE" and ev["first_seen_merchant"]:
        harm_cat = "UNAUTHORISED"  # safety net for a misfiled unauthorised charge; the issue type is unchanged
        gates.append("SAFETY_NET_FIRST_SEEN_MERCHANT")
    harm = protocols.HARM_POINTS[harm_cat]
    reasons.append(f"Harm: {HARM_LABEL[harm_cat].lower()} (+{harm})")
    if "SAFETY_NET_FIRST_SEEN_MERCHANT" in gates:
        m = ev["first_seen_merchant"]
        reasons.append(f"{FIRST_SEEN} ({m['transaction_id']}, {m['merchant']})")

    # 2. Time to harm: the higher of "happening now" and "still recoverable"
    if issue == "SCAM_IN_PROGRESS" or "CUSTOMER_REPORTS_PRESSURE" in caller:
        time_pts = NOW_POINTS
        why = "someone is pressuring the customer" if "CUSTOMER_REPORTS_PRESSURE" in caller else "scam in progress"
        reasons.append(f"Time to harm: happening now, {why} (+{time_pts})")
    elif ev["recoverable"]:
        time_pts = RECOVERABLE_POINTS
        reasons.append(f"Time to harm: money may still be recoverable today ({', '.join(ev['recoverable'])} is "
                       f"under 72 hours old or pending) (+{time_pts})")
    else:
        time_pts = 0

    # 3. Verified account signals, from account data only
    sig_pts = 0
    for name, detail in ev["signals"].items():
        add = min(SIGNAL_POINTS, SIGNAL_MAX - sig_pts)
        sig_pts += add
        reasons.append(f"{evidence.SIGNALS[name]}: {detail} (+{add})")

    # 4. Care needs, once
    care = [CARE_TEXT[s] for s in caller if s in CARE_TEXT]
    if card["language"] and card["language"] != "en":
        care.append("needs language support")
    care_pts = CARE_POINTS if care else 0
    if care:
        reasons.append(f"Care needs: {', '.join(care)} (+{care_pts})")

    base = min(100, harm + time_pts + sig_pts + care_pts)

    # Gate G3 / protocol floor: some issues never sit below a band
    floor_band = protocol.get("min_band")
    if floor_band and base < BAND_FLOOR[floor_band]:
        gates.append(f"FLOOR_{floor_band}")
        reasons.append(f"Gate: {protocol['title'].lower()} never sits below {floor_band} "
                       f"(raised from {base} to {BAND_FLOOR[floor_band]})")
        base = BAND_FLOOR[floor_band]

    # Waiting, limited by gate G4 (at most one band up)
    wait_pts = min(WAIT_MAX, WAIT_STEP_POINTS * (max(0, minutes_waiting) // WAIT_STEP_MIN))
    ceiling_band = _band_up(band_for(base), 1)
    ceiling = 100 if ceiling_band == "P1" else BAND_FLOOR[_band_up(ceiling_band, 1)] - 1
    total = min(base + wait_pts, ceiling, 100)
    if total < base + wait_pts:
        gates.append("G4_AGEING_CEILING")
    reasons.append(f"Waiting {minutes_waiting} min (+{total - base})")

    # Gate G1: words alone can't reach P1
    if not ev["signals"] and total > G1_CAP:
        total = G1_CAP
        gates.append("G1_NO_VERIFIED_SIGNALS")
        reasons.insert(0, SCAM_NO_SIGNALS if issue in evidence.SCAM_FAMILY or harm_cat == "SCAM_IN_PROGRESS"
                       else NO_SIGNALS)

    band = band_for(total)
    return {"score": total, "band": band, "band_label": BAND_LABEL[band], "reasons": reasons,
            "signals": sorted(ev["signals"]), "caller_signals": sorted(caller),
            "minutes_waiting": minutes_waiting, "gates": gates,
            "parts": {"harm": harm, "time_to_harm": time_pts, "signals": sig_pts, "care": care_pts,
                      "waiting": total - base if total >= base else 0},
            "harm_category": harm_cat, "executor": EXECUTOR[band]}
