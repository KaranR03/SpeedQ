"""Persistence check: python test_db.py. Runs the backend code twice against one temp DB file."""
import os
import subprocess
import sys
import tempfile


def write():
    import store
    from models import RetellPayload as P
    store.create_case(P(customer_id="CUST-001", issue_type="SCAM_IN_PROGRESS", linked_transactions="TX-9001",
                        risk_signals="CUSTOMER_REPORTS_PRESSURE,VULNERABILITY_CUES",
                        proposed_actions="ACTIVATE_SAFEBLOCK,DRAFT_PAYMENT_RECALL", case_reference="WGM-0412"))
    store.decide("WGM-0412", "APPROVE", None, "tester")
    c2 = store.create_case(P(customer_id="CUST-003", issue_type="DISPUTE_CHARGE"))
    assert c2["case_id"] == "WGM-0900"
    store.rerank("WGM-0900", "P1", None, "persistence test", "tester")


def read():
    import db
    import mock_data as md
    import store
    c = store.CASES["WGM-0412"]
    assert c["status"] == "APPROVED" and len(c["audit_log"]) == 3 and c["priority"]["score"] == 160
    assert md.CUSTOMERS["CUST-001"]["safeblock"] is True, "SafeBlock state lost"
    assert store._refs["RCL"] == 1, "draft reference counter lost"
    top = store.queue()[0]
    assert top["case_id"] == "WGM-0900" and top["priority"]["score"] == 120, "re-rank lost"
    from models import RetellPayload as P
    assert store.create_case(P(customer_id="CUST-002", issue_type="GENERAL_ENQUIRY"))["case_id"] == "WGM-0901"
    store.reset()
    assert not store.CASES and db.load_cases() == [] and md.CUSTOMERS["CUST-001"]["safeblock"] is False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        {"write": write, "read": read}[sys.argv[1]]()
    else:
        with tempfile.TemporaryDirectory() as d:
            env = {**os.environ, "NRY_DB": os.path.join(d, "t.db")}
            for phase in ("write", "read"):  # two processes = a real restart
                subprocess.run([sys.executable, __file__, phase], env=env, check=True)
        print("Persistence OK")
