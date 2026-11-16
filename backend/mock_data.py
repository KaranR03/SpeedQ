"""Read-only tools over the synthetic JSON data (all customer data is fake)."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA = Path(__file__).parent / "data"


def _load(name):
    return json.loads((DATA / name).read_text())


CUSTOMERS, TRANSACTIONS, CARDS = {}, {}, []


def reset():
    """(Re)load the seed JSON in place, discarding mock account changes (SafeBlock, blocked cards)."""
    CUSTOMERS.clear()
    CUSTOMERS.update({c["customer_id"]: c for c in _load("customers.json")})
    TRANSACTIONS.clear()
    TRANSACTIONS.update({t["id"]: t for t in _load("transactions.json")})
    CARDS[:] = _load("cards.json")


reset()


def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def utcnow():
    return datetime.now(timezone.utc)


DEMO_NOW_DEFAULT = "2026-11-15T12:00:00Z"


def demo_now():
    """The "as of" time for account evidence (recoverable payments, recent security changes).

    The sample data is dated 9 to 15 Nov 2026, so a fixed demo clock keeps scores identical on every run.
    NRY_NOW overrides it (an ISO time), and NRY_NOW=real uses the real clock. Queue waiting time always
    uses the real clock.
    """
    val = os.environ.get("NRY_NOW", DEMO_NOW_DEFAULT)
    return utcnow() if val.strip().lower() == "real" else parse_ts(val)


def get_customer(customer_id):
    return CUSTOMERS.get(customer_id)


def get_transaction(tx_id):
    return TRANSACTIONS.get(tx_id)


def get_card_delivery_status(customer_id):
    for c in CARDS:
        if c["customer_id"] == customer_id and c.get("kind") == "replacement":
            return c
    return None


def get_recent_transactions(customer_id, days=30, now=None):
    cutoff = (now or utcnow()) - timedelta(days=days)
    txs = [t for t in TRANSACTIONS.values()
           if t["customer_id"] == customer_id and parse_ts(t["date"]) >= cutoff]
    return sorted(txs, key=lambda t: t["date"], reverse=True)


def get_account_status(customer_id):
    c = CUSTOMERS.get(customer_id)
    if not c:
        return None
    return {k: c[k] for k in ("accounts", "safeblock", "lockouts")}


def get_open_cases(customer_id):
    c = CUSTOMERS.get(customer_id)
    return list(c["open_cases"]) if c else []
