"""Officers teach, leads approve.

Every officer decision is counted against the protocol it used. A Modify (with "suggest as a protocol update") or a
Manual decision becomes a protocol suggestion, never a rule. Identical suggestions are merged and counted; once a
suggestion has been made THRESHOLD times it is ready for a protocol owner, who approves (new version) or rejects it.
"""
import os

import db

from . import propose, protocols

THRESHOLD = int(os.environ.get("NRY_SUGGEST_THRESHOLD", "3"))
_SUG, _STATS = "suggestion", "protocol_stats"
SUGGESTIONS, STATS = {}, {}


def _load():
    SUGGESTIONS.clear()
    SUGGESTIONS.update(db.load_docs(_SUG))
    STATS.clear()
    STATS.update(db.load_docs(_STATS))


_load()


def reset():
    SUGGESTIONS.clear()
    STATS.clear()


def _status(s):
    if s["status"] in ("APPROVED", "REJECTED"):
        return s["status"]
    return "READY_FOR_OWNER" if s["count"] >= THRESHOLD else "COLLECTING"


def _save(s):
    s["status"] = _status(s)
    s["threshold"] = THRESHOLD
    db.save_doc(_SUG, s["id"], s)


def record(case, decision, final_actions, actor, note, suggest, ts):
    """Called after every decision. Returns the suggestion it created or joined, or None."""
    proposal = case["proposed_solution"]
    issue, version = proposal["protocol"]["issue_type"], proposal["protocol"]["version"]
    st = STATS.setdefault(issue, {"APPROVE": 0, "MODIFY": 0, "MANUAL": 0})
    st[decision] += 1
    db.save_doc(_STATS, issue, st)

    if decision == "APPROVE" or (decision == "MODIFY" and not suggest):
        return None
    if decision == "MODIFY":
        proposed = sorted({a["action"] for a in proposal["actions"]})
        chosen = sorted(set(final_actions))
        add = [a for a in chosen if a not in proposed]
        remove = [a for a in proposed if a not in chosen]
        if not add and not remove:
            return None
        change = {"add_actions": add, "remove_actions": remove}
        key = f"{issue}|MODIFY|+{','.join(add)}|-{','.join(remove)}|{version}"
    else:
        change = {"handled_manually": True}
        key = f"{issue}|MANUAL|{version}"
    s = next((x for x in SUGGESTIONS.values() if x["key"] == key and x["status"] not in ("APPROVED", "REJECTED")),
             None)
    if s is None:
        sid = f"SUG-{len(SUGGESTIONS) + 1:04d}"
        s = {"id": sid, "key": key, "issue_type": issue, "kind": decision, "from_version": version,
             "proposed_version": protocols.next_version(version), "change": change, "count": 0, "cases": [],
             "officers": [], "notes": [], "created_at": ts, "status": "COLLECTING"}
        SUGGESTIONS[sid] = s
    s["count"] += 1
    s["cases"].append(case["case_id"])
    if actor not in s["officers"]:
        s["officers"].append(actor)
    if note:
        s["notes"].append(note)
    s["updated_at"] = ts
    _save(s)
    return s


def approve(sid, owner, ts):
    """KeyError -> 404, RuntimeError -> 409 (not ready, closed, or protocol already moved on)."""
    s = SUGGESTIONS[sid]
    if s["status"] in ("APPROVED", "REJECTED"):
        raise RuntimeError(f"suggestion already {s['status']}")
    if s["count"] < THRESHOLD:
        raise RuntimeError(f"suggested {s['count']} of {THRESHOLD} times: not ready for the protocol owner yet")
    current = protocols.get(s["issue_type"])
    if current["version"] != s["from_version"]:
        raise RuntimeError(f"protocol is now v{current['version']}; this suggestion was made against "
                           f"v{s['from_version']}")
    ai_may = list(current.get("ai_may", []))
    if s["kind"] == "MODIFY":
        drop = set(s["change"]["remove_actions"])
        ai_may = [i for i in ai_may if propose.parse_ai_may(i)[0] not in drop]
        ai_may += s["change"]["add_actions"]
        change = (f"Officers added {', '.join(s['change']['add_actions']) or 'nothing'} and removed "
                  f"{', '.join(s['change']['remove_actions']) or 'nothing'} ({s['count']} times)")
        note = ""
    else:
        change = f"Officers handled this manually {s['count']} times"
        note = "Officers often handle this manually: " + ("; ".join(s["notes"][-3:]) or "no notes given")
    s["approved_version"] = protocols.add_version(s["issue_type"], ai_may, change, note, owner, ts, sid)
    s["status"], s["decided_by"], s["decided_at"] = "APPROVED", owner, ts
    _save(s)
    return s


def reject(sid, owner, reason, ts):
    s = SUGGESTIONS[sid]
    if s["status"] in ("APPROVED", "REJECTED"):
        raise RuntimeError(f"suggestion already {s['status']}")
    s["status"], s["decided_by"], s["decided_at"], s["reject_reason"] = "REJECTED", owner, ts, reason
    _save(s)
    return s


def listing():
    return sorted(SUGGESTIONS.values(), key=lambda s: s["id"])
