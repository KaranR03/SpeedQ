"""In-memory case store. No database: a dict is enough for the demo."""
import threading

import db
import mock_data as md
import priority
from models import ACTIONS, ISSUE_TYPES, RetellPayload

CASES = {}  # case_id -> case dict (created_at kept as datetime, serialised on the way out)
QUEUE_STATUSES = {"QUEUED", "AWAITING_CUSTOMER_CONFIRM", "IN_REVIEW"}
_lock = threading.Lock()
_counter = 899  # generated refs start at WGM-0900 so they never clash with Retell's own (e.g. WGM-0412)


def _split(s):
    return [x.strip() for x in s.split(",") if x.strip()]


def _new_id():
    global _counter
    _counter += 1
    while f"WGM-{_counter:04d}" in CASES:  # cases now survive restarts, so skip taken references
        _counter += 1
    return f"WGM-{_counter:04d}"


def _params(action, linked, params=None):
    p = dict(params or {})
    if action == "DRAFT_PAYMENT_RECALL" and linked:
        p.setdefault("transaction_id", linked[0])
    if action == "BOOK_CALLBACK":
        p.setdefault("when", "tomorrow 10:00")
    return p


def rescore(case, now=None):
    """Recompute priority from account data. Called on every queue read so ageing is current."""
    if case["priority"] and case["status"] not in QUEUE_STATUSES:
        return  # decided cases keep the score they were decided at (SafeBlock etc. must not rewrite history)
    case["priority"] = priority.score_case(
        case["issue_type"], case["customer_id"], case["linked_transactions"],
        case["_caller_signals"], case["created_at"], now)
    case["risk_signals"] = case["priority"]["signals"]
    ov = case.get("_override")  # officer re-rank pins the score; the reason stays visible
    if ov:
        p = case["priority"]
        p["score"], p["band"] = ov["score"], priority.band_for(ov["score"])
        p["reasons"].append(f"Manually re-ranked by {ov['actor']}: {ov['reason']}")


def create_case(p: RetellPayload):
    if p.issue_type not in ISSUE_TYPES:
        raise ValueError(f"unknown issue_type {p.issue_type!r}")
    cust = md.get_customer(p.customer_id) or {}
    linked = _split(p.linked_transactions)
    actions = []
    for a in _split(p.proposed_actions):
        if a not in ACTIONS:
            continue  # whitelist only
        actions.append({"action": a, "params": _params(a, linked)})
    with _lock:
        cid = p.case_reference if p.case_reference and p.case_reference not in CASES else _new_id()
        case = {
            "case_id": cid,
            "customer_id": p.customer_id,
            "customer_name": p.customer_name or cust.get("short_name", ""),
            "language": p.language,
            "language_label": p.language_label or cust.get("language_label", ""),
            "channel": "voice",
            "created_at": md.utcnow(),
            "issue_type": p.issue_type,
            "summary_en": p.summary_en,
            "summary_customer_lang": p.summary_customer_lang,
            "linked_transactions": linked,
            "risk_signals": [],
            "customer_confirmed": p.customer_confirmed,
            "customer_sentiment": p.customer_sentiment,
            "priority": {},
            "retell_estimate": {"score": p.priority_score, "band": p.priority_band,
                                "safeblock_claimed": p.safeblock_activated},
            "proposed_solution": {"explanation": p.proposed_explanation, "actions": actions},
            "status": "TIER1_RESOLVED" if p.status == "TIER1_RESOLVED" else "QUEUED",
            "officer_decision": None,
            "audit_log": [],
            "_caller_signals": _split(p.risk_signals),
        }
        rescore(case)
        CASES[cid] = case
        db.save_case(case)
    return case


_refs = {}


def _ref(prefix):
    _refs[prefix] = _refs.get(prefix, 0) + 1
    db.save_state(f"ref|{prefix}", _refs[prefix])
    return f"{prefix}-{_refs[prefix]:04d}"


def _now_str():
    return md.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def run_action(case, name, params, actor):
    """Mocked effects only: records that the action ran. Nothing here moves money."""
    cid = case["customer_id"]
    cust = md.get_customer(cid) or {}
    before = after = None
    ok, result = True, ""
    if name == "ACTIVATE_SAFEBLOCK":
        before, after = {"safeblock": cust.get("safeblock")}, {"safeblock": True}
        cust["safeblock"] = True
        db.save_state(f"safeblock|{cid}", 1)
        result = "SafeBlock switched on (mock)"
    elif name == "BLOCK_CARD":
        card = next((c for c in md.CARDS if c["customer_id"] == cid and c.get("kind") == "existing"), None)
        if card:
            before, after = {"blocked": card["blocked"]}, {"blocked": True}
            card["blocked"] = True
            db.save_state(f"blocked|{cid}|{card['mask']}", 1)
            result = f"Card {card['mask']} blocked (mock)"
        else:
            ok, result = False, "No active card on file"
    elif name in ("RAISE_DISPUTE", "DRAFT_PAYMENT_RECALL"):
        tx = md.get_transaction(params.get("transaction_id", ""))
        if not tx or tx["customer_id"] != cid:
            ok, result = False, "Transaction not found for this customer"
        elif name == "RAISE_DISPUTE":
            result = f"Dispute {_ref('DSP')} raised for {tx['id']} (mock)"
        else:
            result = f"Recall draft {_ref('RCL')} created for {tx['id']}. DRAFT ONLY: no money moved"
    elif name == "DRAFT_SCAM_REPORT":
        result = f"Scam report draft {_ref('RPT')} created. DRAFT ONLY"
    elif name == "BOOK_CALLBACK":
        result = f"Callback {_ref('CBK')} booked: {params.get('when', 'unspecified')} (mock)"
    elif name == "SEND_CUSTOMER_UPDATE":
        result = f"Customer update {_ref('MSG')} recorded as sent (mock)"
    return {"ts": _now_str(), "actor": actor, "action": name, "params": params,
            "before": before, "after": after, "ok": ok, "result": result}


STATUS_FOR = {"APPROVE": "APPROVED", "MODIFY": "MODIFIED", "MANUAL": "MANUAL"}


def decide(case_id, decision, actions, actor):
    """KeyError -> 404, RuntimeError -> 409, ValueError -> 422."""
    if decision not in STATUS_FOR:
        raise ValueError(f"unknown decision {decision!r}")
    with _lock:
        case = CASES.get(case_id)
        if not case:
            raise KeyError(case_id)
        if case["status"] not in QUEUE_STATUSES:
            raise RuntimeError(f"case already {case['status']}")
        linked = case["linked_transactions"]
        if decision == "APPROVE":
            todo = [(a["action"], a["params"]) for a in case["proposed_solution"]["actions"]]
        elif decision == "MODIFY":
            if actions is None:
                raise ValueError("MODIFY needs an actions list")
            bad = [a.action for a in actions if a.action not in ACTIONS]
            if bad:
                raise ValueError(f"actions not on the whitelist: {bad}")
            todo = [(a.action, _params(a.action, linked, a.params)) for a in actions]
        else:
            todo = []
        case["audit_log"].append({"ts": _now_str(), "actor": actor, "action": f"DECISION_{decision}",
                                  "params": {}, "before": {"status": case["status"]},
                                  "after": {"status": STATUS_FOR[decision]}, "ok": True,
                                  "result": f"{actor} chose {decision}"})
        for name, params in todo:
            case["audit_log"].append(run_action(case, name, params, actor))
        case["status"] = STATUS_FOR[decision]
        case["officer_decision"] = decision
        db.save_case(case)
    return case


def public(case):
    """JSON-safe copy without internal fields."""
    out = {k: v for k, v in case.items() if not k.startswith("_")}
    out["created_at"] = case["created_at"].strftime("%Y-%m-%dT%H:%M:%SZ")
    return out


def queue():
    now = md.utcnow()
    live = [c for c in CASES.values() if c["status"] in QUEUE_STATUSES]
    for c in live:
        rescore(c, now)
    live.sort(key=lambda c: (-c["priority"]["score"], c["created_at"]))
    return [public(c) for c in live]


BAND_SCORE = {"P1": 120, "P2": 70, "P3": 30, "P4": 10}  # a band pins the score inside that band


def rerank(case_id, band, score, reason, actor):
    """Officer re-rank, always with a reason. The pinned score stops ageing from undoing it.
    KeyError -> 404, RuntimeError -> 409, ValueError -> 422."""
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("a reason is required to re-rank")
    if (band is None) == (score is None):
        raise ValueError("give exactly one of band or score")
    if band is not None and band not in BAND_SCORE:
        raise ValueError(f"unknown band {band!r}")
    if score is not None and score < 0:
        raise ValueError("score must be 0 or more")
    with _lock:
        case = CASES.get(case_id)
        if not case:
            raise KeyError(case_id)
        if case["status"] not in QUEUE_STATUSES:
            raise RuntimeError(f"case already {case['status']}")
        rescore(case)
        before = {"score": case["priority"]["score"], "band": case["priority"]["band"]}
        case["_override"] = {"score": BAND_SCORE[band] if band else score, "reason": reason, "actor": actor}
        rescore(case)
        after = {"score": case["priority"]["score"], "band": case["priority"]["band"]}
        case["audit_log"].append({"ts": _now_str(), "actor": actor, "action": "RERANK", "params": {},
                                  "before": before, "after": after, "ok": True,
                                  "result": f"Re-ranked by {actor}: {reason}"})
        db.save_case(case)
    return case


def reset():
    """Wipe cases and mock account changes (demo rehearsal)."""
    global _counter
    with _lock:
        CASES.clear()
        _refs.clear()
        _counter = 899
        db.clear()
        md.reset()


def _restore():
    """Reload cases and mock account state saved by a previous run."""
    for body in db.load_cases():
        body["created_at"] = md.parse_ts(body["created_at"])
        CASES[body["case_id"]] = body
    for key, val in db.load_state().items():
        kind, *rest = key.split("|")
        if kind == "safeblock" and rest[0] in md.CUSTOMERS:
            md.CUSTOMERS[rest[0]]["safeblock"] = True
        elif kind == "blocked":
            for card in md.CARDS:
                if card["customer_id"] == rest[0] and card["mask"] == rest[1]:
                    card["blocked"] = True
        elif kind == "ref":
            _refs[rest[0]] = int(val)


_restore()
