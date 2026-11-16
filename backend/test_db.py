"""Persistence check: python test_db.py. Runs the backend code twice against one temp DB file (a real restart)."""
import os
import subprocess
import sys
import tempfile


def write():
    import store
    from models import ActionItem
    from models import RetellPayload as P
    from prorio import learning
    store.create_case(P(customer_id="CUST-001", issue_type="SCAM_IN_PROGRESS", linked_transactions="TX-9001",
                        risk_signals="CUSTOMER_REPORTS_PRESSURE,VULNERABILITY_CUES", case_reference="WGM-0412"))
    store.decide("WGM-0412", "APPROVE", None, "tester")
    c2 = store.create_case(P(customer_id="CUST-003", issue_type="DISPUTE_CHARGE"))
    assert c2["case_id"] == "WGM-0900"
    store.rerank("WGM-0900", "P1", None, "persistence test", "tester")
    # learning loop: one suggestion, approved into a new protocol version (threshold 1 for this test)
    c3 = store.create_case(P(customer_id="CUST-002", issue_type="CARD_DELIVERY", status="QUEUED"))
    store.decide(c3["case_id"], "MODIFY", [ActionItem(action="SEND_GUIDE_LINK")], "tester")
    sid = learning.listing()[0]["id"]
    assert learning.approve(sid, "lead", "2026-11-16T00:00:00Z")["approved_version"] == "2.1"


def read():
    import db
    import mock_data as md
    import store
    from models import RetellPayload as P
    from prorio import learning, protocols
    c = store.CASES["WGM-0412"]
    assert c["status"] == "APPROVED" and c["priority"]["score"] == 100 and c["card_status"]["stage"] == "DONE"
    assert md.CUSTOMERS["CUST-001"]["safeblock"] is True, "SafeBlock state lost"
    assert store._refs["RCL"] == 1, "draft reference counter lost"
    top = store.queue()[0]
    assert top["case_id"] == "WGM-0900" and top["priority"]["score"] == 90, "re-rank lost"
    assert protocols.get("CARD_DELIVERY")["version"] == "2.1", "approved protocol version lost"
    assert learning.listing()[0]["status"] == "APPROVED" and learning.STATS["CARD_DELIVERY"]["MODIFY"] == 1
    assert store.create_case(P(customer_id="CUST-002", issue_type="GENERAL_ENQUIRY"))["case_id"] == "WGM-0902"
    store.reset()
    assert not store.CASES and db.load_cases() == [] and md.CUSTOMERS["CUST-001"]["safeblock"] is False
    assert protocols.get("CARD_DELIVERY")["version"] == "2.0" and not learning.listing()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        {"write": write, "read": read}[sys.argv[1]]()
    else:
        with tempfile.TemporaryDirectory() as d:
            env = {**os.environ, "NRY_DB": os.path.join(d, "t.db"), "NRY_SUGGEST_THRESHOLD": "1"}
            for phase in ("write", "read"):  # two processes = a real restart
                subprocess.run([sys.executable, __file__, phase], env=env, check=True)
        print("Persistence OK")
