"""Dashboard integration and browser security regression checks: python test_workspace.py."""
import os
import unittest
from unittest.mock import patch

os.environ["NRY_DB"] = ":memory:"

from fastapi.testclient import TestClient
from main import app
import store


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"NRY_STAFF_PASSWORD": "", "NRY_WEBHOOK_SECRET": ""})
        self.env.start()
        self.client = TestClient(app)
        store.reset()

    def tearDown(self):
        self.client.close()
        self.env.stop()

    def test_same_origin_assets_and_security_headers(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Priority queue", page.text)
        self.assertIn("frame-ancestors 'none'", page.headers["content-security-policy"])
        self.assertNotIn("unsafe-inline", page.headers["content-security-policy"])
        self.assertEqual(page.headers["x-content-type-options"], "nosniff")
        self.assertEqual(page.headers["cache-control"], "no-store")
        self.assertEqual(self.client.get("/assets/app.js").status_code, 200)
        self.assertEqual(self.client.get("/assets/styles.css").status_code, 200)
        self.assertEqual(self.client.get("/assets/package.json").status_code, 404)
        self.assertEqual(self.client.get("/assets/node_modules/playwright/package.json").status_code, 404)
        self.assertEqual(self.client.get("/", headers={"host": "attacker.invalid"}).status_code, 400)

    def test_browser_cross_origin_changes_denied(self):
        for headers in ({"origin": "https://attacker.invalid"}, {"origin": "null"},
                        {"sec-fetch-site": "cross-site"}, {"origin": "http://testserver.attacker.invalid"}):
            self.assertEqual(self.client.post("/demo/seed", json={}, headers=headers).status_code, 403)
        self.assertEqual(self.client.get("/workspace/cases").json(), [])
        allowed = self.client.post("/demo/seed", json={}, headers={"origin": "http://testserver"})
        self.assertEqual(allowed.status_code, 200)
        self.assertNotIn("access-control-allow-origin", allowed.headers)

    def test_seed_is_additive_and_idempotent(self):
        self.assertEqual(self.client.post("/demo/seed").json(), {"added": 5})
        self.assertEqual(self.client.post("/demo/seed").json(), {"added": 0})
        cases = self.client.get("/workspace/cases").json()
        self.assertEqual(len(cases), 5)
        self.assertEqual(cases[0]["priority"]["band"], "P1")
        self.assertNotIn("audit_log", cases[0])
        self.client.post("/case/DEMO-0416/decision", json={"decision": "MANUAL", "officer": "tester"})
        cases = self.client.get("/workspace/cases").json()
        self.assertTrue(any(c["status"] == "MANUAL" for c in cases))
        self.client.post("/case/DEMO-0416/complete", json={"note": "Delivery date confirmed."})
        self.assertTrue(any(c["stage"] == "DONE" for c in self.client.get("/workspace/cases").json()))
        self.assertEqual(self.client.post("/demo/seed").json(), {"added": 0})

    def test_staff_auth_protects_data_mutations_and_docs(self):
        with patch.dict(os.environ, {"NRY_STAFF_PASSWORD": "test-only-password", "NRY_STAFF_USER": "alice"}):
            for path in ("/", "/queue", "/workspace/cases", "/protocols", "/docs", "/openapi.json", "/audit/x"):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 401, path)
                self.assertIn("Basic", response.headers["www-authenticate"])
            self.assertEqual(self.client.post("/admin/reset").status_code, 401)
            self.assertEqual(self.client.get("/queue", auth=("alice", "wrong")).status_code, 401)
            self.assertEqual(self.client.get("/queue", headers={"authorization": "Basic !!!"}).status_code, 401)
            self.assertEqual(self.client.get("/queue", auth=("alice", "test-only-password")).status_code, 200)
            self.assertEqual(self.client.post("/demo/seed", auth=("alice", "test-only-password")).status_code, 403)
            self.assertEqual(self.client.post("/webhook/retell", json={}).status_code, 503)

    def test_demo_frames_preserve_same_origin_restriction(self):
        for path in ("/officer", "/customer"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn("frame-ancestors 'self'", response.headers["content-security-policy"])
            self.assertEqual(response.headers["x-frame-options"], "SAMEORIGIN")
        for path in ("/", "/demo"):
            self.assertEqual(self.client.get(path).headers["x-frame-options"], "DENY")

    def test_explicit_trusted_origin_preserves_upstream_configuration(self):
        with patch.dict(os.environ, {"NRY_CORS_ORIGINS": "https://trusted.example"}):
            response = self.client.post("/demo/seed", json={},
                headers={"origin": "https://trusted.example", "sec-fetch-site": "cross-site"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.client.post("/demo/seed", json={},
                headers={"origin": "https://untrusted.example"}).status_code, 403)

    def test_unauthenticated_demo_rejects_remote_staff_access(self):
        with TestClient(app, client=("203.0.113.4", 50000)) as remote:
            self.assertEqual(remote.get("/workspace/cases").status_code, 403)
            self.assertEqual(remote.post("/admin/reset").status_code, 403)
            self.assertEqual(remote.post("/webhook/retell", json={}).status_code, 503)
            with patch.dict(os.environ, {"NRY_WEBHOOK_SECRET": "test-only-webhook"}):
                payload = {"customer_id": "CUST-005", "issue_type": "GENERAL_ENQUIRY"}
                self.assertEqual(remote.post("/webhook/retell", json=payload,
                    headers={"x-webhook-secret": "test-only-webhook"}).status_code, 200)
            with patch.dict(os.environ, {"NRY_STAFF_PASSWORD": "test-only-password"}):
                self.assertEqual(remote.get("/workspace/cases").status_code, 401)
                self.assertEqual(remote.get("/workspace/cases", auth=("officer", "test-only-password")).status_code, 200)

    def test_webhook_secret_and_authenticated_audit_identity(self):
        self.client.post("/demo/seed")
        with patch.dict(os.environ, {"NRY_STAFF_PASSWORD": "test-only-password", "NRY_STAFF_USER": "alice",
                                    "NRY_WEBHOOK_SECRET": "test-only-webhook"}):
            payload = {"customer_id": "CUST-005", "issue_type": "GENERAL_ENQUIRY"}
            self.assertEqual(self.client.post("/webhook/retell", json=payload).status_code, 401)
            self.assertEqual(self.client.post("/webhook/retell", json=payload,
                headers={"x-webhook-secret": "test-only-webhook"}).status_code, 200)
            self.assertEqual(self.client.post("/case", json=payload,
                headers={"x-webhook-secret": "test-only-webhook"}).status_code, 200)
            result = self.client.post("/case/DEMO-0416/decision", auth=("alice", "test-only-password"),
                                      json={"decision": "APPROVE", "officer": "forged-name"})
            self.assertEqual(result.status_code, 200)
            audit = result.json()["audit_log"]
            self.assertTrue(any(a["actor"] == "alice" and a["action"] == "DECISION_APPROVE" for a in audit))
            self.assertFalse(any(a["actor"] == "forged-name" for a in audit))


if __name__ == "__main__":
    unittest.main(verbosity=2)
