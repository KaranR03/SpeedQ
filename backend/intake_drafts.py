"""Durable, unranked intake drafts. Confirmation creates a case once under the store lock."""
import copy
from uuid import uuid4

import db
import mock_data as md
import store
import workspace_events
from models import RetellPayload
from prorio import evidence, protocols
from prorio.score import BAND_MESSAGE, CALLER_SIGNALS, HANDOFF

DRAFTS = db.load_docs("intake_drafts")


def _save(draft):
    draft["revision"] += 1
    draft["updated_at"] = store._now_str()
    db.save_doc("intake_drafts", draft["draft_id"], draft)
    workspace_events.changed()


def _get(draft_id):
    if draft_id not in DRAFTS:
        raise KeyError(draft_id)
    return DRAFTS[draft_id]


def _editable(draft, revision):
    if draft["status"] != "DRAFT":
        raise RuntimeError("This draft is no longer editable.")
    if draft["revision"] != revision:
        raise RuntimeError("This draft changed. Read its latest revision before updating it.")


def public(draft):
    out = copy.deepcopy(draft)
    out.pop("submission", None)
    ev = evidence.gather(draft["customer_id"], draft["linked_transactions"], md.demo_now())
    out["verified_signals"] = dict(ev["signals"])
    out["verified_protection"] = ev["account"]
    out["evidence_as_of"] = md.demo_now().isoformat()
    out["linked_payments"] = [{key: tx[key] for key in ("id", "amount", "payee", "date")} for tx in ev["own"]]
    case = store.CASES.get(draft.get("case_reference")) if draft["status"] == "SUBMITTED" else None
    if case:
        out.update(case_stage=case["card_status"]["stage"], case_status=case["card_status"]["label"],
                   assigned_officer=(case.get("assignment") or {}).get("officer"), completed_by=case.get("completed_by"))
    return out


def start(customer_id):
    cust = md.get_customer(customer_id)
    if not cust:
        raise ValueError("No matching customer in the demonstration dataset.")
    with store._lock:
        draft = {"draft_id": "DRAFT-" + uuid4().hex, "customer_id": customer_id,
                 "customer_name": cust["short_name"], "language": cust["language"],
                 "language_label": cust["language_label"], "status": "DRAFT", "phase": "LISTENING",
                 "issue_type": None, "summary_en": "", "summary_customer_lang": "",
                 "linked_transactions": [], "risk_signals": [], "safeblock_activated": False,
                 "card_locked": False, "customer_confirmed": False, "case_reference": None,
                 "revision": 0, "created_at": store._now_str(), "updated_at": store._now_str()}
        DRAFTS[draft["draft_id"]] = draft
        _save(draft)
        return public(draft)


def update(draft_id, payload):
    with store._lock:
        draft = _get(draft_id)
        _editable(draft, payload.expected_revision)
        fields = payload.model_dump(exclude_unset=True, exclude={"expected_revision"})
        if fields.get("issue_type") is not None and fields["issue_type"] not in protocols.ISSUE_TYPES:
            raise ValueError("Unknown issue type.")
        if any(signal not in CALLER_SIGNALS for signal in fields.get("risk_signals") or []):
            raise ValueError("Only conversation cues may be supplied; account signals are verified by the backend.")
        for tid in fields.get("linked_transactions") or []:
            tx = md.get_transaction(tid)
            if not tx or tx["customer_id"] != draft["customer_id"]:
                raise ValueError("A linked transaction is unknown or does not belong to this customer.")
        for key, value in fields.items():
            if value is not None:
                draft[key] = list(dict.fromkeys(value)) if isinstance(value, list) else value
        _save(draft)
        return public(draft)


def confirm(draft_id, payload):
    with store._lock:
        draft = _get(draft_id)
        if not payload.customer_confirmed:
            raise ValueError("The customer must confirm the card before it enters the queue.")
        if draft["status"] == "SUBMITTED":
            return dict(draft["submission"])  # a retried confirmation never creates another case
        _editable(draft, payload.expected_revision)
        if not draft["issue_type"] or not draft["summary_en"].strip():
            raise ValueError("An issue and a customer summary are required before confirmation.")
        card = RetellPayload(customer_id=draft["customer_id"], customer_name=draft["customer_name"],
            language=draft["language"], language_label=draft["language_label"], issue_type=draft["issue_type"],
            summary_en=draft["summary_en"], summary_customer_lang=draft["summary_customer_lang"],
            linked_transactions=",".join(draft["linked_transactions"]), risk_signals=",".join(draft["risk_signals"]),
            safeblock_activated=draft["safeblock_activated"], card_locked=draft["card_locked"],
            customer_confirmed=True, case_reference=payload.case_reference)
        # Recover if a process stopped after saving the case but before saving the submitted draft.
        # The association is persisted with the case, even if an officer has since completed it.
        case = next((c for c in store.CASES.values() if draft_id in c.get("_intake_draft_ids", [])), None)
        if case is None:
            case = store.create_case(card, intake_draft_id=draft_id)
        updated = case.pop("_updated_existing", False)
        band = case["priority"]["band"]
        queued = case["card_status"]["stage"] != "DONE"
        result = {"case_reference": case["case_id"], "queued": queued, "priority_band": band if queued else None,
                  "handoff": HANDOFF[band] if queued else "NONE",
                  "caller_message": BAND_MESSAGE[band] if queued else "This case is already complete. Review the recorded outcome.",
                  "updated_existing_case": updated}
        draft.update(status="SUBMITTED", phase="CONFIRMED", customer_confirmed=True,
                     case_reference=case["case_id"], submitted_at=store._now_str(), submission=result)
        _save(draft)
        return dict(result)


def cancel(draft_id, revision):
    with store._lock:
        draft = _get(draft_id)
        _editable(draft, revision)
        draft.update(status="CANCELLED", phase="CANCELLED")
        _save(draft)
        return public(draft)


def listing():
    with store._lock:
        active = sorted((d for d in DRAFTS.values() if d["status"] == "DRAFT"), key=lambda d: d["updated_at"], reverse=True)
        recent = sorted((d for d in DRAFTS.values() if d["status"] == "SUBMITTED"), key=lambda d: d["updated_at"], reverse=True)[:5]
        return {"active_count": len(active), "drafts": [public(d) for d in active[:20] + recent],
                "truncated": len(active) > 20}
