"""Read-only workspace analytics and customer context from existing synthetic records.

Case age uses the live clock. Account-history windows use the fixed evidence clock.
No ranking, transaction, protection or case state is changed here.
"""
from collections import Counter
from datetime import timedelta

import mock_data as md

ACTIVE = {"QUEUED", "AWAITING_CUSTOMER_CONFIRM", "IN_REVIEW", "MANUAL"}
AGE_BUCKETS = (("under10", "Under 10 min", 0, 10), ("10to30", "10–30 min", 10, 30),
               ("30to60", "30–60 min", 30, 60), ("60plus", "60+ min", 60, None))
# Project design targets from README, not a bank SLA or a guaranteed response time.
RESPONSE_TARGETS = {"P1": 2, "P2": 30}


def _stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def _is_open(case):
    return case["status"] in ACTIVE and case["card_status"]["stage"] != "DONE"


def _age(case, now):
    return max(0, int((now - case["created_at"]).total_seconds() // 60))


def _stage(case):
    if case["card_status"]["stage"] == "DONE":
        return "done"
    if case["status"] == "MANUAL":
        return "manual"
    if case["card_status"]["stage"] == "WITH_OFFICER":
        return "review"
    return "waiting"


def summarize(cases, now=None):
    """Aggregate a consistent snapshot. Payments are deduplicated and ownership-checked."""
    now = now or md.utcnow()
    live = [c for c in cases if _is_open(c)]
    priority = Counter(c["priority"]["band"] for c in live)
    stages = Counter(_stage(c) for c in cases)
    issues = Counter(c["issue_type"] for c in live)
    decisions = Counter(c["officer_decision"] for c in cases if c.get("officer_decision"))
    linked = {}
    watch = []
    for case in live:
        for tid in case["linked_transactions"]:
            tx = md.get_transaction(tid)
            if tx and tx["customer_id"] == case["customer_id"] and tx["amount"] < 0:
                linked[tid] = tx
        band = case["priority"]["band"]
        target = RESPONSE_TARGETS.get(band)
        if target is not None and _stage(case) == "waiting" and _age(case, now) >= target:
            watch.append({"case_id": case["case_id"], "customer_name": case["customer_name"],
                          "band": band, "age_minutes": _age(case, now), "target_minutes": target})
    watch.sort(key=lambda c: (c["band"], -c["age_minutes"], c["case_id"]))
    return {
        "generated_at": _stamp(now), "evidence_as_of": _stamp(md.demo_now()), "scope": "all_saved_cases",
        "total": len(cases), "active": len(live), "currency": "AUD",
        "priority": [{"band": band, "count": priority[band]} for band in ("P1", "P2", "P3", "P4")],
        "stages": [{"key": key, "label": label, "count": stages[key]} for key, label in
                   (("waiting", "Waiting"), ("review", "Officer review"), ("manual", "Manual handling"),
                    ("done", "Completed"))],
        "issues": [{"issue_type": key, "count": count} for key, count in
                   sorted(issues.items(), key=lambda item: (-item[1], item[0]))],
        "age": [{"key": key, "label": label, "count": sum(
            start <= _age(c, now) and (end is None or _age(c, now) < end) for c in live)}
                for key, label, start, end in AGE_BUCKETS],
        "decisions": [{"decision": key, "count": decisions[key]} for key in ("APPROVE", "MODIFY", "MANUAL")],
        "coverage": {"with_signals": sum(bool(c["priority"]["signals"]) for c in live),
                     "without_signals": sum(not c["priority"]["signals"] for c in live),
                     "language_support": sum(bool(c["language"] and c["language"] != "en") for c in live),
                     "repeat_contacts": sum(max(0, c.get("contacts", 1) - 1) for c in live),
                     "linked_payments": len(linked),
                     "linked_outgoing_amount": round(sum(-t["amount"] for t in linked.values()), 2)},
        "response_watch": {"count": len(watch), "cases": watch[:5], "targets": RESPONSE_TARGETS},
    }


def customer_context(case):
    """Only this case's customer, masked accounts and owned transactions. No raw customer dump."""
    cid = case["customer_id"]
    customer = md.get_customer(cid)
    as_of = md.demo_now()
    result = {"case_id": case["case_id"], "customer_id": cid, "found": bool(customer),
              "evidence_as_of": _stamp(as_of), "snapshot_at": _stamp(md.utcnow()), "currency": "AUD",
              "accounts": [], "transactions": [], "security_events": [], "cards": [],
              "protection": None, "ignored_links": len(case["linked_transactions"])}
    if not customer:
        return result
    result["accounts"] = [{key: a[key] for key in ("type", "mask", "balance")}
                          for a in customer.get("accounts", [])]
    owned_links = {tid for tid in case["linked_transactions"] if (tx := md.get_transaction(tid))
                   and tx["customer_id"] == cid}
    result["ignored_links"] = len(set(case["linked_transactions"]) - owned_links)
    history = sorted((t for t in md.TRANSACTIONS.values() if t["customer_id"] == cid
                      and as_of - timedelta(days=30) <= md.parse_ts(t["date"]) <= as_of),
                     key=lambda t: t["date"], reverse=True)[:8]
    transactions = {t["id"]: t for t in history}
    transactions.update({tid: md.get_transaction(tid) for tid in owned_links})
    result["transactions"] = [{**{key: t[key] for key in ("id", "date", "amount", "type", "payee", "desc")},
                               "linked": t["id"] in owned_links, "status": t.get("status", "Not supplied"),
                               "after_evidence_clock": md.parse_ts(t["date"]) > as_of}
                              for t in sorted(transactions.values(), key=lambda t: t["date"], reverse=True)]
    result["security_events"] = [{"type": e["type"], "at": e["at"], "detail": e.get("detail", "")}
                                 for e in customer.get("security_events", [])
                                 if as_of - timedelta(days=30) <= md.parse_ts(e["at"]) <= as_of]
    result["security_events"] += [{"type": "lockout", "at": e["at"], "detail": e.get("reason", "")}
                                  for e in customer.get("lockouts", [])
                                  if as_of - timedelta(days=30) <= md.parse_ts(e["at"]) <= as_of]
    result["security_events"].sort(key=lambda e: e["at"], reverse=True)
    result["cards"] = [{key: c[key] for key in
                        ("card", "mask", "kind", "status", "blocked", "ordered", "dispatched", "expected", "carrier")
                        if key in c} for c in md.CARDS if c["customer_id"] == cid]
    existing = [c for c in result["cards"] if c["kind"] == "existing"]
    result["protection"] = {"safeblock_verified": bool(customer.get("safeblock")),
                            "card_blocked_verified": any(c["blocked"] for c in existing) if existing else None,
                            "card_locked_reported": case["clario_reported"].get("card_locked", False),
                            "safeblock_reported": case["clario_reported"].get("safeblock_activated", False)}
    return result
