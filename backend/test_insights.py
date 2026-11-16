"""Analytics semantics, dataset ownership and clock boundaries: python test_insights.py."""
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

os.environ["NRY_DB"] = ":memory:"

from fastapi.testclient import TestClient
from main import app
from models import RetellPayload
import mock_data as md
import store
import workspace_insights as wi

NOW = datetime(2026, 11, 17, 1, tzinfo=timezone.utc)


class InsightsTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"NRY_STAFF_PASSWORD": "", "NRY_WEBHOOK_SECRET": "",
                                          "NRY_NOW": "2026-11-15T12:00:00Z"})
        self.env.start()
        self.clock = patch.object(md, "utcnow", return_value=NOW)
        self.clock.start()
        self.client = TestClient(app)
        store.reset()

    def tearDown(self):
        self.client.close()
        store.reset()
        self.clock.stop()
        self.env.stop()

    def seed(self):
        self.assertEqual(self.client.post("/demo/seed").status_code, 200)

    def summary(self):
        response = self.client.get("/workspace/insights")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_empty_workspace_has_no_invented_metrics(self):
        data = self.summary()
        self.assertEqual((data["total"], data["active"]), (0, 0))
        self.assertEqual(data["coverage"]["linked_outgoing_amount"], 0)
        self.assertEqual(data["issues"], [])
        self.assertEqual(data["response_watch"]["count"], 0)
        self.assertTrue(all(c["count"] == 0 for c in data["priority"] + data["age"] + data["decisions"]))

    def test_seed_aggregates_reconcile_with_source_cases(self):
        self.seed()
        data = self.summary()
        self.assertEqual((data["total"], data["active"]), (5, 5))
        self.assertEqual([c["count"] for c in data["priority"]], [1, 1, 2, 1])
        self.assertEqual(sum(c["count"] for c in data["stages"]), data["total"])
        self.assertEqual(sum(c["count"] for c in data["issues"]), data["active"])
        self.assertEqual(data["coverage"], {"with_signals": 2, "without_signals": 3,
            "language_support": 1, "repeat_contacts": 0, "linked_payments": 3, "linked_outgoing_amount": 5539.0})
        self.assertNotEqual(data["generated_at"], data["evidence_as_of"])
        self.assertTrue(all(len(c["audit_log"]) == 1 for c in store.CASES.values()), "Reading insights added audit entries")

    def test_payments_deduplicated_and_foreign_links_ignored(self):
        self.seed()
        store.create_case(RetellPayload(customer_id="CUST-001", issue_type="SCAM_ALREADY_PAID",
                                       linked_transactions="TX-9001", case_reference="DUPLICATE-LINK"))
        store.create_case(RetellPayload(customer_id="CUST-002", issue_type="GENERAL_ENQUIRY",
                                       linked_transactions="TX-9001,UNKNOWN", case_reference="FOREIGN-LINK"))
        data = self.summary()
        self.assertEqual(data["coverage"]["linked_outgoing_amount"], 5539.0)
        self.assertEqual(data["coverage"]["linked_payments"], 3)
        context = self.client.get("/case/FOREIGN-LINK/context").json()
        self.assertEqual(context["ignored_links"], 2)
        self.assertNotIn("TX-9001", [t["id"] for t in context["transactions"]])
        self.assertEqual(len(context["accounts"]), 1)
        self.assertEqual(context["accounts"][0]["mask"], "...7731")
        self.assertNotIn("id", context["accounts"][0])
        self.assertTrue(all(md.TRANSACTIONS[t["id"]]["customer_id"] == "CUST-002" for t in context["transactions"]))

    def test_manual_and_completed_stages_do_not_double_count(self):
        self.seed()
        self.client.post("/case/DEMO-0416/decision", json={"decision": "MANUAL", "officer": "tester"})
        data = self.summary()
        self.assertEqual([s["count"] for s in data["stages"]], [4, 0, 1, 0])
        self.assertEqual(data["active"], 5)
        self.client.post("/case/DEMO-0416/complete", json={"note": "Delivery date confirmed."})
        data = self.summary()
        self.assertEqual([s["count"] for s in data["stages"]], [4, 0, 0, 1])
        self.assertEqual(data["active"], 4)
        self.assertEqual(data["decisions"][-1], {"decision": "MANUAL", "count": 1})

    def test_live_age_boundaries_and_first_pickup_targets(self):
        self.seed()
        for case, age in zip(store.CASES.values(), (9, 10, 30, 60, 59)):
            case["created_at"] = NOW - timedelta(minutes=age)
        data = self.summary()
        self.assertEqual([b["count"] for b in data["age"]], [1, 1, 2, 1])
        # Waiting promotes the two 55-point cases to P2. Watch uses current bands.
        self.assertEqual(data["response_watch"]["count"], 3)
        self.assertEqual(data["response_watch"]["cases"][0]["case_id"], "DEMO-0412")
        store.CASES["DEMO-0413"]["created_at"] = NOW - timedelta(minutes=31)
        self.assertEqual(self.summary()["response_watch"]["count"], 4)
        self.client.post("/case/DEMO-0412/pickup", json={"officer": "tester"})
        self.assertEqual(self.summary()["response_watch"]["count"], 3)
        self.client.post("/case/DEMO-0413/decision", json={"decision": "MANUAL"})
        self.assertEqual(self.summary()["response_watch"]["count"], 2)
        for cid in ("DEMO-0414", "DEMO-0415"):
            self.client.post(f"/case/{cid}/pickup", json={"officer": "tester"})
        self.assertEqual(self.summary()["response_watch"]["count"], 0)

    def test_customer_context_clock_scope_and_reported_protection(self):
        self.seed()
        context = self.client.get("/case/DEMO-0414/context").json()
        self.assertTrue(context["protection"]["card_locked_reported"])
        self.assertFalse(context["protection"]["card_blocked_verified"])
        # History is anchored to the evidence clock, not the later live clock.
        self.assertIn("TX-7001", [t["id"] for t in context["transactions"]])
        md.TRANSACTIONS["FUTURE"] = {"id": "FUTURE", "customer_id": "CUST-003", "date": "2026-11-16T00:00:00Z",
            "amount": -1, "type": "card", "payee": "Future merchant", "desc": "Future"}
        self.assertNotIn("FUTURE", [t["id"] for t in wi.customer_context(store.CASES["DEMO-0414"])["transactions"]])
        jordan = self.client.get("/case/DEMO-0413/context").json()
        self.assertEqual(len(jordan["security_events"]), 3)
        sam = self.client.get("/case/DEMO-0416/context").json()
        self.assertEqual(sam["cards"][0]["expected"], "2026-11-19")

    def test_missing_customer_stays_unknown_and_new_routes_require_staff_auth(self):
        case = store.create_case(RetellPayload(customer_id="UNKNOWN", issue_type="GENERAL_ENQUIRY"))
        context = self.client.get(f"/case/{case['case_id']}/context").json()
        self.assertFalse(context["found"])
        self.assertIsNone(context["protection"])
        self.assertEqual(context["accounts"], [])
        self.assertEqual(self.client.get("/case/NONE/context").status_code, 404)
        with patch.dict(os.environ, {"NRY_STAFF_PASSWORD": "test-only-password"}):
            self.assertEqual(self.client.get("/workspace/insights").status_code, 401)
            self.assertEqual(self.client.get(f"/case/{case['case_id']}/context").status_code, 401)


if __name__ == "__main__":
    unittest.main(verbosity=2)
