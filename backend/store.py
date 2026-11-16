"""Case store: keeps Customer Service Cards, runs Prorio on them, and records officer decisions.

Cases live in memory and are saved to SQLite (db.py) so they survive a restart.
"""
import threading
import copy

import db
import mock_data as md
import workspace_events
from models import RetellPayload
from prorio import agent, learning, protocols
from prorio.propose import ACTIONS
from prorio.score import BAND_LABEL, EXECUTOR, band_for

CASES = {}  # case_id -> case dict (created_at kept as datetime, serialised on the way out)
QUEUE_STATUSES = {"QUEUED", "AWAITING_CUSTOMER_CONFIRM", "IN_REVIEW"}
STAGES = ("RECEIVED", "RANKED", "WITH_OFFICER", "ACTION_TAKEN", "DONE")  # what the customer sees on their card
STAGE_TEXT = {"RECEIVED": "Received", "RANKED": "Ranked", "WITH_OFFICER": "With an officer",
              "ACTION_TAKEN": "Action taken", "DONE": "Done"}
_lock = threading.RLock()
_counter = 899  # generated refs start at WGM-0900 so they never clash with Clario's own (e.g. WGM-0412)


def _split(s):
    return [x.strip() for x in s.split(",") if x.strip()]


def _new_id():
    global _counter
    _counter += 1
    while f"WGM-{_counter:04d}" in CASES:  # cases survive restarts, so skip taken references
        _counter += 1
    return f"WGM-{_counter:04d}"


def _now_str():
    return md.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _save(case):
    case["revision"] = case.get("revision", 0) + 1
    case["updated_at"] = _now_str()
    db.save_case(case)
    workspace_events.changed()


def _check_owner(case, actor, expected_revision=None):
    if expected_revision is not None and case.get("revision", 1) != expected_revision:
        raise RuntimeError("This case changed. Refresh it and review the latest version before continuing.")
    owner = case.get("assignment")
    if owner and owner["officer"] != actor:
        raise RuntimeError(f"This case is assigned to {owner['officer']}. Choose another case or ask them to release it.")


def _assign(case, actor):
    if not case.get("assignment"):
        case["assignment"] = {"officer": actor, "claimed_at": _now_str()}


def _params(action, linked, params=None):
    p = dict(params or {})
    if action in ("DRAFT_PAYMENT_RECALL", "DRAFT_PAYMENT_TRACE", "RAISE_DISPUTE") and linked:
        p.setdefault("transaction_id", linked[0])
    if action == "BOOK_CALLBACK":
        p.setdefault("when", "tomorrow 10:00")
    return p


def _minutes(case, now=None):
    return max(0, int(((now or md.utcnow()) - case["created_at"]).total_seconds() // 60))


def _open_cases():
    return [c for c in CASES.values() if c["status"] in QUEUE_STATUSES]


def _stage(case, stage):
    if not case["card_status"]["history"] or case["card_status"]["history"][-1]["stage"] != stage:
        case["card_status"]["history"].append({"stage": stage, "ts": _now_str()})
    case["card_status"]["stage"] = stage
    case["card_status"]["label"] = STAGE_TEXT[stage]


def _audit(case, actor, action, before=None, after=None, result="", params=None, ok=True):
    case["audit_log"].append({"ts": _now_str(), "actor": actor, "action": action, "params": params or {},
                              "before": before, "after": after, "ok": ok, "result": result})


def rescore(case, now=None):
    """Recompute priority with Prorio. Called on every queue read so waiting time stays current."""
    if case["priority"] and case["status"] not in QUEUE_STATUSES:
        return  # decided cases keep the score they were decided at
    card = agent.card_from(case)
    pr, _, _ = agent.rank(card, _minutes(case, now), _open_cases())
    ov = case.get("_override")  # officer re-rank (gate G5) pins the score; the reason stays visible
    if ov:
        pr["score"], pr["band"] = ov["score"], band_for(ov["score"])
        pr["band_label"] = BAND_LABEL[pr["band"]]
        pr["executor"] = EXECUTOR[pr["band"]]
        pr["reasons"].append(f"Manually re-ranked by {ov['actor']}: {ov['reason']}")
        pr["gates"].append("G5_OFFICER_OVERRIDE")
    case["priority"] = pr
    case["risk_signals"] = pr["signals"] + pr["caller_signals"]
    if case.get("proposed_solution"):
        case["proposed_solution"]["executor"] = pr["executor"]


def _draft(case):
    """Full Prorio run: priority, proposal and trace."""
    pr, proposal, trace = agent.draft(agent.card_from(case), _minutes(case), _open_cases())
    case["proposed_solution"] = proposal
    case["prorio_trace"] = trace
    case["priority"] = {}
    rescore(case)  # applies any officer override and keeps one code path for priority


def _find_repeat(p: RetellPayload):
    """Gate G6: one problem, one card. An open card for the same customer and issue, or the reference given."""
    if p.case_reference and p.case_reference in CASES:
        c = CASES[p.case_reference]
        if c["customer_id"] == p.customer_id and c["status"] in QUEUE_STATUSES:
            return c
    if p.status == "TIER1_RESOLVED":
        return None
    return next((c for c in _open_cases() if c["customer_id"] == p.customer_id and c["issue_type"] == p.issue_type),
                None)


def create_case(p: RetellPayload, intake_draft_id=None):
    if p.issue_type not in protocols.ISSUE_TYPES:
        raise ValueError(f"unknown issue_type {p.issue_type!r}")
    cust = md.get_customer(p.customer_id) or {}
    linked = _split(p.linked_transactions)
    clario = {"score": p.priority_score, "band": p.priority_band, "reasons": p.priority_reasons,
              "safeblock_claimed": p.safeblock_activated,
              "proposed_actions": _split(p.proposed_actions), "explanation": p.proposed_explanation}
    with _lock:
        existing = _find_repeat(p)
        if existing:
            return _update_repeat(existing, p, linked, clario, intake_draft_id)
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
            "retell_estimate": clario,
            "clario_reported": {"safeblock_activated": p.safeblock_activated, "card_locked": p.card_locked},
            "proposed_solution": {},
            "prorio_trace": [],
            "status": "TIER1_RESOLVED" if p.status == "TIER1_RESOLVED" else "QUEUED",
            "card_status": {"stage": "RECEIVED", "label": STAGE_TEXT["RECEIVED"], "history": []},
            "officer_decision": None,
            "outcome": None,
            "contacts": 1,
            "customer_corrections": [],
            "assignment": None,
            "completed_by": None,
            "completed_at": None,
            "audit_log": [],
            "_caller_signals": _split(p.risk_signals),
            "_intake_draft_ids": [intake_draft_id] if intake_draft_id else [],
        }
        _stage(case, "RECEIVED")
        _draft(case)
        if case["status"] == "TIER1_RESOLVED":
            _stage(case, "DONE")  # Clario answered it; no officer needed
        else:
            _stage(case, "RANKED")
        _audit(case, "AI (Prorio)", "PRORIO_DRAFT", after={"score": case["priority"]["score"],
                                                            "band": case["priority"]["band"]},
               result=case["proposed_solution"]["explanation"])
        CASES[cid] = case
        _save(case)
    return case


def _update_repeat(case, p, linked, clario, intake_draft_id=None):
    before = {"score": case["priority"]["score"], "band": case["priority"]["band"]}
    case["linked_transactions"] += [t for t in linked if t not in case["linked_transactions"]]
    case["_caller_signals"] += [s for s in _split(p.risk_signals) if s not in case["_caller_signals"]]
    for k in ("summary_en", "summary_customer_lang"):
        if getattr(p, k):
            case[k] = getattr(p, k)
    for k in ("safeblock_activated", "card_locked"):
        case["clario_reported"][k] = case["clario_reported"][k] or getattr(p, k)
    case["retell_estimate"] = clario
    case["customer_confirmed"] = case["customer_confirmed"] or p.customer_confirmed
    if intake_draft_id and intake_draft_id not in case.setdefault("_intake_draft_ids", []):
        case["_intake_draft_ids"].append(intake_draft_id)
    after = lambda: {"score": case["priority"]["score"], "band": case["priority"]["band"]}
    if p.correction:  # glass-box card: the customer corrected their own card through Clario
        case.setdefault("customer_corrections", []).append({"ts": _now_str(), "text": p.correction[:500]})
        _draft(case)
        _audit(case, "Customer (via Clario)", "CUSTOMER_CORRECTION", before=before, after=after(),
               result=f"Customer corrected the card: {p.correction[:500]}")
    else:
        case["contacts"] = case.get("contacts", 1) + 1
        _draft(case)
        _audit(case, "AI (Prorio)", "REPEAT_CONTACT", before=before, after=after(),
               result=f"Customer contacted again about the same issue (contact {case['contacts']}); card updated, "
                      f"not duplicated")
    _save(case)
    case["_updated_existing"] = True  # read (and removed) by the webhook reply; never saved
    return case


_refs = {}


def _ref(prefix):
    _refs[prefix] = _refs.get(prefix, 0) + 1
    db.save_state(f"ref|{prefix}", _refs[prefix])
    return f"{prefix}-{_refs[prefix]:04d}"


DRAFT_PREFIX = {"DRAFT_PAYMENT_TRACE": ("TRC", "Payment trace draft"), "DRAFT_SCAM_REPORT": ("RPT", "Scam report draft"),
                "DRAFT_HARDSHIP_NOTES": ("HSN", "Hardship notes draft"),
                "DRAFT_COMPLAINT_RESPONSE": ("CMP", "Complaint response draft")}


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
    elif name in ("RAISE_DISPUTE", "DRAFT_PAYMENT_RECALL", "DRAFT_PAYMENT_TRACE"):
        tx = md.get_transaction(params.get("transaction_id", ""))
        if not tx or tx["customer_id"] != cid:
            ok, result = False, "Transaction not found for this customer"
        elif name == "RAISE_DISPUTE":
            result = f"Dispute {_ref('DSP')} raised for {tx['id']} (mock)"
        elif name == "DRAFT_PAYMENT_RECALL":
            result = f"Recall draft {_ref('RCL')} created for {tx['id']}. DRAFT ONLY: no money moved"
        else:
            result = f"Payment trace draft {_ref('TRC')} created for {tx['id']}. DRAFT ONLY"
    elif name in DRAFT_PREFIX:
        prefix, text = DRAFT_PREFIX[name]
        result = f"{text} {_ref(prefix)} created. DRAFT ONLY"
    elif name == "ORDER_REPLACEMENT_CARD":
        result = f"Replacement card request {_ref('RPL')} prepared to the address on file (mock)"
    elif name == "BOOK_CALLBACK":
        result = f"Callback {_ref('CBK')} booked: {params.get('when', 'unspecified')} (mock)"
    elif name == "SEND_CUSTOMER_UPDATE":
        result = f"Customer update {_ref('MSG')} recorded as sent (mock)"
    elif name == "SEND_GUIDE_LINK":
        result = f"How-to link {_ref('LNK')} recorded as sent (mock)"
    elif name == "REFER_SPECIALIST_TEAM":
        result = f"Referral {_ref('REF')} to the specialist team recorded (mock)"
    else:
        ok, result = False, f"Unknown action {name}"
    return {"ts": _now_str(), "actor": actor, "action": name, "params": params,
            "before": before, "after": after, "ok": ok, "result": result}


STATUS_FOR = {"APPROVE": "APPROVED", "MODIFY": "MODIFIED", "MANUAL": "MANUAL"}


def decide(case_id, decision, actions, actor, note="", suggest_update=True, expected_revision=None):
    """KeyError -> 404, RuntimeError -> 409, ValueError -> 422."""
    if decision not in STATUS_FOR:
        raise ValueError(f"unknown decision {decision!r}")
    with _lock:
        case = CASES.get(case_id)
        if not case:
            raise KeyError(case_id)
        if case["status"] not in QUEUE_STATUSES:
            raise RuntimeError(f"case already {case['status']}")
        _check_owner(case, actor, expected_revision)
        rescore(case)
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
        _assign(case, actor)
        executor = case["priority"]["executor"]
        doer = f"AI (Prorio), approved by {actor}" if executor == "AI_AFTER_APPROVAL" else actor
        _audit(case, actor, f"DECISION_{decision}", before={"status": case["status"]},
               after={"status": STATUS_FOR[decision]},
               result=f"{actor} chose {decision}" + (f": {note}" if note else ""))
        for name, params in todo:
            case["audit_log"].append(run_action(case, name, params, doer))
        case["status"] = STATUS_FOR[decision]
        case["officer_decision"] = decision
        if case["card_status"]["stage"] != "WITH_OFFICER":
            _stage(case, "WITH_OFFICER")
        if decision != "MANUAL":
            case["completed_by"], case["completed_at"] = actor, _now_str()
            _stage(case, "ACTION_TAKEN")
            case["outcome"] = {"message": case["proposed_solution"]["customer_message"],
                               "language": case["language"], "sent_at": _now_str()}
            _stage(case, "DONE")
        sug = learning.record(case, decision, [n for n, _ in todo], actor, note, suggest_update, _now_str())
        if sug:
            _audit(case, actor, "PROTOCOL_SUGGESTION", after={"suggestion": sug["id"], "count": sug["count"]},
                   result=f"Suggested as a protocol update for {sug['issue_type']} v{sug['from_version']} "
                          f"-> v{sug['proposed_version']} ({sug['count']} of {sug['threshold']}, pending approval)")
            case["protocol_suggestion"] = sug["id"]
        _save(case)
    return case


def pick_up(case_id, actor, expected_revision=None):
    """An officer opens the case: the customer's card shows "With an officer"."""
    with _lock:
        case = CASES.get(case_id)
        if not case:
            raise KeyError(case_id)
        if case["status"] not in QUEUE_STATUSES | {"MANUAL"} or case["card_status"]["stage"] == "DONE":
            raise RuntimeError(f"case already {case['status']}")
        _check_owner(case, actor, expected_revision)
        if not case.get("assignment"):
            _assign(case, actor)
            if case["status"] != "MANUAL":
                case["status"] = "IN_REVIEW"
            _stage(case, "WITH_OFFICER")
            _audit(case, actor, "PICKED_UP", result=f"{actor} is working on the case")
            _save(case)
    return case


def release(case_id, actor, note="", expected_revision=None):
    with _lock:
        case = CASES.get(case_id)
        if not case:
            raise KeyError(case_id)
        if case["status"] not in QUEUE_STATUSES | {"MANUAL"} or case["card_status"]["stage"] == "DONE":
            raise RuntimeError("Only active cases can be released.")
        _check_owner(case, actor, expected_revision)
        if not case.get("assignment"):
            raise RuntimeError("This case has no assigned officer.")
        case["assignment"] = None
        if case["status"] != "MANUAL":
            case["status"] = "QUEUED"
        _stage(case, "RANKED")
        _audit(case, actor, "CASE_RELEASED", result=f"{actor} returned the case to the shared queue" + (f": {note}" if note else ""))
        _save(case)
    return case


def complete(case_id, actor, note, expected_revision=None):
    """Close a case the officer handled manually."""
    note = (note or "").strip()
    if not note:
        raise ValueError("say what was done")
    with _lock:
        case = CASES.get(case_id)
        if not case:
            raise KeyError(case_id)
        if case["status"] != "MANUAL" or case["card_status"]["stage"] == "DONE":
            raise RuntimeError("only an open manual case can be completed")
        _check_owner(case, actor, expected_revision)
        _assign(case, actor)
        _stage(case, "ACTION_TAKEN")
        case["outcome"] = {"message": note, "language": case["language"], "sent_at": _now_str()}
        _stage(case, "DONE")
        case["completed_by"], case["completed_at"] = actor, _now_str()
        _audit(case, actor, "MANUAL_COMPLETE", result=note)
        _save(case)
    return case


def public(case):
    """JSON-safe copy without internal fields."""
    with _lock:
        out = copy.deepcopy({k: v for k, v in case.items() if not k.startswith("_")})
        out["created_at"] = case["created_at"].strftime("%Y-%m-%dT%H:%M:%SZ")
    return out


def customer_view(case):
    """What the customer may see on their card: no score, no reasons, no internal notes."""
    return {"case_reference": case["case_id"], "issue_type": case["issue_type"], "summary": case["summary_en"],
            "summary_customer_lang": case["summary_customer_lang"], "status": case["card_status"]["label"],
            "stage": case["card_status"]["stage"], "history": case["card_status"]["history"],
            "outcome": case["outcome"], "corrections": case.get("customer_corrections", []),
            "assigned_officer": (case.get("assignment") or {}).get("officer"),
            "completed_by": case.get("completed_by")}


def queue():
    now = md.utcnow()
    live = _open_cases()
    for c in live:
        rescore(c, now)
    live.sort(key=lambda c: (-c["priority"]["score"], c["created_at"]))
    return [public(c) for c in live]


def workspace():
    """Compact staff list including manual and completed work, without audit payloads."""
    fields = ("case_id", "customer_id", "customer_name", "issue_type", "summary_en", "status", "language_label", "language", "contacts")
    with _lock:
        for c in _open_cases():
            rescore(c)
        cases = sorted(CASES.values(), key=lambda c: (-c["priority"]["score"], c["created_at"]))
        return [{**{k: c[k] for k in fields}, "created_at": c["created_at"].isoformat(),
                 "priority": c["priority"], "stage": c["card_status"]["stage"],
                 "revision": c.get("revision", 1), "assignment": c.get("assignment"),
                 "completed_by": c.get("completed_by"), "completed_at": c.get("completed_at")} for c in cases]


def insights():
    """Aggregate under the store lock so stages, decisions and totals agree."""
    import workspace_insights
    with _lock:
        for case in _open_cases():
            rescore(case)
        return workspace_insights.summarize(list(CASES.values()))


BAND_SCORE = {"P1": 90, "P2": 70, "P3": 50, "P4": 20}  # a band pins the score in the middle of that band


def rerank(case_id, band, score, reason, actor, expected_revision=None):
    """Officer re-rank (gate G5), always with a reason. The pinned score stops waiting time from undoing it.
    KeyError -> 404, RuntimeError -> 409, ValueError -> 422."""
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("a reason is required to re-rank")
    if (band is None) == (score is None):
        raise ValueError("give exactly one of band or score")
    if band is not None and band not in BAND_SCORE:
        raise ValueError(f"unknown band {band!r}")
    if score is not None and not 0 <= score <= 100:
        raise ValueError("score must be between 0 and 100")
    with _lock:
        case = CASES.get(case_id)
        if not case:
            raise KeyError(case_id)
        if case["status"] not in QUEUE_STATUSES:
            raise RuntimeError(f"case already {case['status']}")
        _check_owner(case, actor, expected_revision)
        rescore(case)
        before = {"score": case["priority"]["score"], "band": case["priority"]["band"]}
        case["_override"] = {"score": BAND_SCORE[band] if band else score, "reason": reason, "actor": actor}
        rescore(case)
        after = {"score": case["priority"]["score"], "band": case["priority"]["band"]}
        _audit(case, actor, "RERANK", before=before, after=after, result=f"Re-ranked by {actor}: {reason}")
        _save(case)
    return case


def reset():
    """Wipe cases, mock account changes and the learning loop (demo rehearsal)."""
    global _counter
    with _lock:
        CASES.clear()
        _refs.clear()
        _counter = 899
        db.clear()
        md.reset()
        learning.reset()
        protocols.reset()
        import intake_drafts
        intake_drafts.DRAFTS.clear()
        workspace_events.changed()


def _restore():
    """Reload cases and mock account state saved by a previous run."""
    for body in db.load_cases():
        if "card_status" not in body:
            continue  # saved by the pre-Prorio backend: press Reset demo data to clear it
        body["created_at"] = md.parse_ts(body["created_at"])
        body.setdefault("revision", 1)
        if "assignment" not in body:
            claim = next((a for a in reversed(body.get("audit_log", []))
                          if a["action"] == "PICKED_UP" or a["action"].startswith("DECISION_")), None)
            body["assignment"] = {"officer": claim["actor"], "claimed_at": claim["ts"]} if claim else None
        completed = next((a for a in reversed(body.get("audit_log", [])) if a["action"] in
                          ("MANUAL_COMPLETE", "DECISION_APPROVE", "DECISION_MODIFY")), None)
        body.setdefault("completed_by", completed["actor"] if completed else None)
        body.setdefault("completed_at", completed["ts"] if completed else None)
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
