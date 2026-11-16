"""The Protocol Database: read-only access to data/protocols.json plus approved versions from the learning loop.

protocols.json is maintained by hand (see data/PROTOCOLS_SOURCES.md) and is never written by code. When a protocol
owner approves a suggestion, the new version is stored in SQLite as an overlay on top of the file, so it can be
rolled back and the file stays exactly as its authors wrote it.
"""
import copy
import json
import re
from pathlib import Path

import db

PATH = Path(__file__).resolve().parent.parent / "data" / "protocols.json"
_RAW = json.loads(PATH.read_text(encoding="utf-8"))

HARM_POINTS = dict(_RAW["_about"]["harm_categories"])   # harm category -> points (README harm table)
SOURCES = dict(_RAW["sources"])                          # source id -> {"title", "url"}
BASE = {p["issue_type"]: p for p in _RAW["protocols"]}
ISSUE_TYPES = tuple(BASE)

_KIND = "protocol_versions"   # db docs: issue_type -> [overlay, ...] (oldest first)
_overlays = {}


def _load():
    _overlays.clear()
    _overlays.update(db.load_docs(_KIND))


_load()


def reset():
    _overlays.clear()


def get(issue_type):
    """The effective protocol: the file's version plus any approved overlays. None if unknown."""
    base = BASE.get(issue_type)
    if base is None:
        return None
    p = copy.deepcopy(base)
    p.setdefault("change_log", [])
    for ov in _overlays.get(issue_type, []):
        p["version"] = ov["version"]
        p["ai_may"] = list(ov["ai_may"])
        if ov.get("note"):
            p["notes"] = (p.get("notes") or "") + f" [v{ov['version']}] {ov['note']}"
        p["change_log"].append({k: ov[k] for k in ("version", "change", "approved_by", "approved_at",
                                                   "suggestion_id", "from_version")})
    return p


def sources_for(protocol):
    return [{"id": s, **SOURCES[s]} for s in protocol.get("sources", []) if s in SOURCES]


def next_version(version):
    m = re.fullmatch(r"(\d+)\.(\d+)", str(version))
    return f"{m.group(1)}.{int(m.group(2)) + 1}" if m else f"{version}.1"


def add_version(issue_type, ai_may, change, note, approved_by, approved_at, suggestion_id):
    """Store an approved change as a new version. Returns the new version string."""
    current = get(issue_type)
    version = next_version(current["version"])
    ov = {"version": version, "from_version": current["version"], "ai_may": list(ai_may), "change": change,
          "note": note, "approved_by": approved_by, "approved_at": approved_at, "suggestion_id": suggestion_id}
    _overlays.setdefault(issue_type, []).append(ov)
    db.save_doc(_KIND, issue_type, _overlays[issue_type])
    return version


def rollback(issue_type):
    """Undo the latest approved version. Returns the version now in force. ValueError if nothing to undo."""
    if not _overlays.get(issue_type):
        raise ValueError(f"{issue_type} has no approved changes to roll back")
    _overlays[issue_type].pop()
    if _overlays[issue_type]:
        db.save_doc(_KIND, issue_type, _overlays[issue_type])
    else:
        del _overlays[issue_type]
        db.delete_doc(_KIND, issue_type)
    return get(issue_type)["version"]


def summary():
    """One line per protocol for listings."""
    out = []
    for it in ISSUE_TYPES:
        p = get(it)
        out.append({"issue_type": it, "title": p["title"], "version": p["version"],
                    "harm_category": p["harm_category"], "harm_points": HARM_POINTS[p["harm_category"]],
                    "min_band": p.get("min_band"), "approved_changes": len(_overlays.get(it, []))})
    return out
