"""Evidence: what the account data shows, worked out by code. Never taken from the customer's words.

Only transactions that are linked to the case AND belong to the case's customer are used, so a card cannot borrow
someone else's transaction to earn signals. Times are compared with the demo clock (mock_data.demo_now).
"""
from datetime import timedelta
from statistics import median

import mock_data as md

# Verified account signals (+10 each, maximum +20). Text is shown to the officer.
SIGNALS = {
    "NEW_PAYEE_24H": "New payee added in the 24 hours before the transfer",
    "LARGE_TRANSFER": "Transfer much larger than usual",
    "SECURITY_CHANGE_7D": "Password, device or contact details changed in the last 7 days",
    "UNUSUAL_LOCATION": "Card used somewhere unusual for this customer",
    "PAYEE_IN_OTHER_SCAM_CASES": "Payee already appears in other open scam cases today",
}
TRANSFER_TYPES = ("transfer", "osko", "payid")
LARGE_TRANSFER_MIN = 1000
LARGE_TRANSFER_MULTIPLE = 3
RECOVERABLE_HOURS = 72
SECURITY_DAYS = 7
SECURITY_EVENT_TYPES = ("password_change", "device_added", "contact_change")
UNUSUAL_LOCATION_DAYS = 7
SCAM_FAMILY = ("SCAM_IN_PROGRESS", "SCAM_ALREADY_PAID", "UNAUTHORISED_ONLINE_BANKING", "FRAUD_UNAUTHORISED")


def _money(x):
    return f"${abs(x):,.2f}"


def _outgoing(tx):
    return tx["amount"] < 0


def gather(customer_id, linked_ids, now, other_cases=()):
    """Return the evidence for one card.

    other_cases: open cases of other customers, as dicts with customer_id, issue_type, linked_transactions
    (used only for the cross-case payee check; no personal details are copied across).
    """
    cust = md.get_customer(customer_id)
    ev = {"customer_found": bool(cust), "signals": {}, "own": [], "ignored": [], "recoverable": [],
          "first_seen_merchant": None, "account": {}}
    if not cust:
        return ev
    history = [t for t in md.TRANSACTIONS.values() if t["customer_id"] == customer_id]
    for tx_id in linked_ids:
        tx = md.get_transaction(tx_id)
        if tx and tx["customer_id"] == customer_id:
            ev["own"].append(tx)
        else:
            ev["ignored"].append(tx_id)  # unknown or someone else's: never counted
    payees = {p["name"]: md.parse_ts(p["added_at"]) for p in cust.get("payees", [])}

    for tx in ev["own"]:
        if not _outgoing(tx):
            continue
        when = md.parse_ts(tx["date"])
        amount = -tx["amount"]
        # money may still be stopped: recent enough, or still pending
        age = now - when
        if tx.get("status", "").lower() == "pending" or timedelta(0) <= age <= timedelta(hours=RECOVERABLE_HOURS):
            ev["recoverable"].append(tx["id"])
        if tx["type"] in TRANSFER_TYPES:
            added = payees.get(tx["payee"])
            # relative to the transfer, not the clock, so the signal never expires mid-demo
            if added and timedelta(0) <= when - added <= timedelta(hours=24):
                hrs = int((when - added).total_seconds() // 3600)
                ev["signals"]["NEW_PAYEE_24H"] = (f"{tx['id']}: payee \"{tx['payee']}\" added {hrs} h before "
                                                  f"the transfer")
            earlier = [-t["amount"] for t in history
                       if t["id"] != tx["id"] and _outgoing(t) and t["type"] in TRANSFER_TYPES
                       and md.parse_ts(t["date"]) < when]
            typical = median(earlier) if len(earlier) >= 2 else None
            if amount > LARGE_TRANSFER_MIN:
                ev["signals"]["LARGE_TRANSFER"] = f"{tx['id']}: {_money(amount)} is over $1,000"
            elif typical and amount > LARGE_TRANSFER_MULTIPLE * typical:
                ev["signals"]["LARGE_TRANSFER"] = (f"{tx['id']}: {_money(amount)} is over 3 times the usual "
                                                   f"transfer ({_money(typical)})")
        if tx["type"] == "card" and ev["first_seen_merchant"] is None:
            seen_before = any(t["payee"] == tx["payee"] and md.parse_ts(t["date"]) < when
                              for t in history if t["id"] != tx["id"])
            if not seen_before:
                ev["first_seen_merchant"] = {"transaction_id": tx["id"], "merchant": tx["payee"]}

    recent = [e for e in cust.get("security_events", [])
              if e.get("type") in SECURITY_EVENT_TYPES
              and timedelta(0) <= now - md.parse_ts(e["at"]) <= timedelta(days=SECURITY_DAYS)]
    if recent:
        ev["signals"]["SECURITY_CHANGE_7D"] = "; ".join(f"{e['detail']} ({e['at'][:10]})" for e in recent)

    home = cust.get("home_country", "AU")
    away = [t for t in history if t["type"] == "card" and t.get("country") and t["country"] != home
            and timedelta(0) <= now - md.parse_ts(t["date"]) <= timedelta(days=UNUSUAL_LOCATION_DAYS)]
    if away:
        ev["signals"]["UNUSUAL_LOCATION"] = "; ".join(f"{t['id']}: {t['payee']} in {t['country']}" for t in away)

    # cross-case check: the same payee in other customers' open scam cases (pattern only, no personal details)
    my_payees = {tx["payee"].strip().lower() for tx in ev["own"] if _outgoing(tx) and tx.get("payee")}
    if my_payees:
        hits = 0
        for oc in other_cases:
            if oc["customer_id"] == customer_id or oc["issue_type"] not in SCAM_FAMILY:
                continue
            for tid in oc["linked_transactions"]:
                t = md.get_transaction(tid)
                if t and t["customer_id"] == oc["customer_id"] and t["payee"].strip().lower() in my_payees:
                    hits += 1
                    break
        if hits:
            ev["signals"]["PAYEE_IN_OTHER_SCAM_CASES"] = f"Payee is in {hits} other open scam case(s) today"

    ev["account"] = {"safeblock_on": bool(cust.get("safeblock")),
                     "card_blocked": any(c["blocked"] for c in md.CARDS
                                         if c["customer_id"] == customer_id and c.get("kind") == "existing"),
                     "lockouts": len(cust.get("lockouts", []))}
    return ev
