"""Priority engine. score = issue_weight + signal weights + ageing (1/min, cap 40).

Account signals are recomputed from mock data, never trusted from the voice agent.
"""
from datetime import timedelta

import mock_data as md

ISSUE_WEIGHTS = {
    "SCAM_IN_PROGRESS": 100, "FRAUD_UNAUTHORISED": 80, "MONEY_MISSING": 70,
    "CARD_LOST_STOLEN": 60, "HARDSHIP": 60, "DISPUTE_CHARGE": 40,
    "CARD_DELIVERY": 10, "GENERAL_ENQUIRY": 10,
}
ISSUE_LABELS = {
    "SCAM_IN_PROGRESS": "scam in progress", "FRAUD_UNAUTHORISED": "unauthorised fraud",
    "MONEY_MISSING": "money missing", "CARD_LOST_STOLEN": "card lost or stolen",
    "HARDSHIP": "financial hardship", "DISPUTE_CHARGE": "disputed charge",
    "CARD_DELIVERY": "card delivery", "GENERAL_ENQUIRY": "general enquiry",
}
ACCOUNT_SIGNALS = {  # name -> (weight, reason text)
    "NEW_PAYEE_24H": (15, "New payee added in last 24h"),
    "LARGE_TRANSFER": (15, "Transfer over $1,000"),
    "RECENT_LOCKOUT": (10, "Recent account lockout"),
    "SAFEBLOCK_ACTIVATED": (10, "SafeBlock activated"),
}
CALLER_SIGNALS = {  # taken from the call: cannot be derived from account data
    "CUSTOMER_REPORTS_PRESSURE": (20, "Customer reports pressure from a caller"),
    "VULNERABILITY_CUES": (10, "Vulnerability cues in the call"),
}
AGEING_CAP = 40
SCAM_CAP = 60
LARGE_TRANSFER_MIN = 1000
SCAM_NO_SIGNALS = "Customer reports scam, no account signals yet: officer to verify"


def band_for(score):
    return "P1" if score >= 120 else "P2" if score >= 70 else "P3" if score >= 30 else "P4"


def account_signals(customer_id, linked_transactions):
    """Derive account signals from the customer's own linked transactions + account state."""
    cust = md.get_customer(customer_id)
    if not cust:
        return set()
    sig = set()
    payees = {p["name"]: md.parse_ts(p["added_at"]) for p in cust["payees"]}
    for tx_id in linked_transactions:
        tx = md.get_transaction(tx_id)
        if not tx or tx["customer_id"] != customer_id or tx["amount"] >= 0:
            continue  # unknown, someone else's, or incoming: ignore
        if tx["type"] in ("transfer", "osko", "payid") and -tx["amount"] > LARGE_TRANSFER_MIN:
            sig.add("LARGE_TRANSFER")
        added = payees.get(tx["payee"])
        # relative to the transfer, not the wall clock, so demo scores are stable across runs
        if added and timedelta(0) <= md.parse_ts(tx["date"]) - added <= timedelta(hours=24):
            sig.add("NEW_PAYEE_24H")
    if cust["lockouts"]:
        sig.add("RECENT_LOCKOUT")
    if cust["safeblock"]:
        sig.add("SAFEBLOCK_ACTIVATED")
    return sig


def score_case(issue_type, customer_id, linked_transactions, caller_signals, created_at, now=None):
    """Return {score, band, reasons, signals, minutes_waiting}. created_at: datetime (UTC)."""
    now = now or md.utcnow()
    acct = account_signals(customer_id, linked_transactions)
    caller = {s for s in caller_signals if s in CALLER_SIGNALS}
    weight = ISSUE_WEIGHTS.get(issue_type, 10)
    label = ISSUE_LABELS.get(issue_type, issue_type.lower())
    reasons = []
    if issue_type == "SCAM_IN_PROGRESS" and not acct:
        weight = min(weight, SCAM_CAP)
        reasons.append(SCAM_NO_SIGNALS)
    reasons.append(f"Issue type: {label} (+{weight})")
    total = weight
    for table, found in ((ACCOUNT_SIGNALS, acct), (CALLER_SIGNALS, caller)):
        for name, (w, text) in table.items():  # table order keeps reasons stable
            if name in found:
                total += w
                reasons.append(f"{text} (+{w})")
    mins = max(0, int((now - created_at).total_seconds() // 60))
    ageing = min(mins, AGEING_CAP)
    total += ageing
    reasons.append(f"Waiting {mins} min (+{ageing})")
    return {"score": total, "band": band_for(total), "reasons": reasons,
            "signals": sorted(acct | caller), "minutes_waiting": mins}


if __name__ == "__main__":  # Checkpoint 1 check: python priority.py
    now = md.utcnow()
    run = lambda *a: score_case(*a, created_at=now, now=now)
    maria = run("SCAM_IN_PROGRESS", "CUST-001", ["TX-9001"], ["CUSTOMER_REPORTS_PRESSURE", "VULNERABILITY_CUES"])
    assert (maria["score"], maria["band"]) == (160, "P1"), maria
    priya = run("DISPUTE_CHARGE", "CUST-003", ["TX-7001"], [])
    assert (priya["score"], priya["band"]) == (40, "P3"), priya
    minh = run("MONEY_MISSING", "CUST-004", ["TX-8001"], [])
    assert (minh["score"], minh["band"]) == (70, "P2"), minh
    bare = run("SCAM_IN_PROGRESS", "CUST-002", [], ["CUSTOMER_REPORTS_PRESSURE"])
    assert (bare["score"], bare["band"]) == (80, "P2") and SCAM_NO_SIGNALS in bare["reasons"], bare
    # anti gaming: Retell claiming someone else's transaction must not earn signals
    gamed = run("SCAM_IN_PROGRESS", "CUST-002", ["TX-9001"], [])
    assert gamed["score"] == 60, gamed
    # ageing: +1/min, capped at 40
    aged = score_case("DISPUTE_CHARGE", "CUST-003", [], [], now - timedelta(minutes=500), now)
    assert aged["score"] == 80, aged
    assert md.get_card_delivery_status("CUST-002")["expected"] == "2026-11-19"
    assert md.get_card_delivery_status("CUST-005")["expected"] == "2026-11-19"
    assert [t["id"] for t in md.get_recent_transactions("CUST-005", 30, now=md.parse_ts("2026-11-16T00:00:00Z"))] == ["TX-5001", "TX-5002", "TX-5003"]
    assert len(md.CUSTOMERS) == 5
    print("Checkpoint 1 OK"); print("\n".join(maria["reasons"]))
