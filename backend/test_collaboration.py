"""Real claim races, identity checks and draft-to-case lifecycle: python test_collaboration.py."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import copy
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

os.environ["NRY_DB"] = ":memory:"

from fastapi.testclient import TestClient
from main import app
import store
import intake_drafts
import db

ALEX = {"x-demo-officer": "Alex Morgan"}
TAYLOR = {"x-demo-officer": "Taylor Lee"}


class CollaborationTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"NRY_STAFF_PASSWORD":"", "NRY_STAFF_ACCOUNTS":"", "NRY_WEBHOOK_SECRET":""})
        self.env.start()
        self.client = TestClient(app)
        store.reset()

    def tearDown(self):
        self.client.close()
        store.reset()
        self.env.stop()

    def case(self, customer="CUST-005", issue="GENERAL_ENQUIRY"):
        r=self.client.post("/case",json={"customer_id":customer,"issue_type":issue,"summary_en":"Customer needs help"})
        self.assertEqual(r.status_code,200,r.text)
        return r.json()

    def claim(self, case, headers):
        return self.client.post(f"/case/{case['case_id']}/pickup",json={"expected_revision":case['revision']},headers=headers)

    def test_simultaneous_claims_and_decisions_have_one_winner(self):
        case=self.case()
        barrier=threading.Barrier(2)
        def claim(headers):
            barrier.wait()
            with TestClient(app) as client:
                return client.post(f"/case/{case['case_id']}/pickup",json={"expected_revision":case['revision']},headers=headers)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(claim,(ALEX,TAYLOR)))
        self.assertEqual(sorted(r.status_code for r in results),[200,409])
        current=self.client.get(f"/case/{case['case_id']}").json()
        self.assertEqual(sum(a['action']=='PICKED_UP' for a in current['audit_log']),1)
        winner=ALEX if current['assignment']['officer']=='Alex Morgan' else TAYLOR
        loser=TAYLOR if winner is ALEX else ALEX
        url=f"/case/{case['case_id']}/decision"
        body={"decision":"APPROVE","expected_revision":current['revision'],"officer":current['assignment']['officer']}
        self.assertEqual(self.client.post(url,json=body,headers=loser).status_code,409)
        self.assertEqual(self.client.post(url,json=body,headers=winner).status_code,200)
        self.assertEqual(self.client.post(url,json=body,headers=loser).status_code,409)
        final=self.client.get(f"/case/{case['case_id']}").json()
        self.assertEqual(sum(a['action']=='DECISION_APPROVE' for a in final['audit_log']),1)
        self.assertEqual(final['completed_by'],current['assignment']['officer'])

    def test_release_transfer_and_manual_completion_preserve_ownership(self):
        case=self.claim(self.case(),ALEX).json()
        url=f"/case/{case['case_id']}"
        self.assertEqual(self.client.post(url+'/release',json={},headers=TAYLOR).status_code,409)
        self.assertEqual(self.client.post(url+'/release',json={"expected_revision":case['revision']-1},headers=ALEX).status_code,409)
        released=self.client.post(url+'/release',json={"expected_revision":case['revision']},headers=ALEX).json()
        self.assertIsNone(released['assignment'])
        self.assertEqual(released['status'],'QUEUED')
        claimed=self.claim(released,TAYLOR).json()
        manual=self.client.post(url+'/decision',headers=TAYLOR,json={"decision":"MANUAL","expected_revision":claimed['revision']}).json()
        self.assertEqual(self.client.post(url+'/complete',headers=ALEX,json={"note":"Wrong officer"}).status_code,409)
        released=self.client.post(url+'/release',headers=TAYLOR,json={"expected_revision":manual['revision']}).json()
        self.assertEqual(released['status'],'MANUAL')
        claimed=self.claim(released,ALEX).json()
        result=self.client.post(url+'/complete',headers=ALEX,json={"note":"Resolved by the new officer","expected_revision":claimed['revision']})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['completed_by'],'Alex Morgan')

    def test_customer_correction_invalidates_an_open_approval(self):
        case=self.claim(self.case(),ALEX).json()
        self.client.post('/webhook/retell',json={"customer_id":"CUST-005","issue_type":"GENERAL_ENQUIRY",
            "case_reference":case['case_id'],"correction":"More context","summary_en":"An updated customer summary"})
        r=self.client.post(f"/case/{case['case_id']}/decision",headers=ALEX,json={"decision":"APPROVE","expected_revision":case['revision']})
        self.assertEqual(r.status_code,409)
        current=self.client.get(f"/case/{case['case_id']}").json()
        self.assertEqual(current['summary_en'],'An updated customer summary')
        self.assertEqual(current['assignment']['officer'],'Alex Morgan')
        self.assertFalse(any(a['action']=='DECISION_APPROVE' for a in current['audit_log']))

    def test_different_officers_can_complete_independent_cases(self):
        one=self.claim(self.case(),ALEX).json()
        two=self.claim(self.case('CUST-002','CARD_DELIVERY'),TAYLOR).json()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(self.client.post,f"/case/{c['case_id']}/decision",headers=h,
                     json={"decision":"APPROVE","expected_revision":c['revision']}) for c,h in ((one,ALEX),(two,TAYLOR))]
            self.assertEqual([f.result().status_code for f in futures],[200,200])
        rows=self.client.get('/workspace/cases').json()
        self.assertEqual({c['completed_by'] for c in rows},{'Alex Morgan','Taylor Lee'})
        self.assertTrue(all(c['stage']=='DONE' for c in rows))
        self.assertEqual(self.client.get('/workspace/insights').json()['active'],0)

    def test_authenticated_accounts_ignore_spoofed_names_and_demo_headers(self):
        case=self.case()
        accounts=json.dumps({'alex':'test-only-alex','taylor':'test-only-taylor'})
        with patch.dict(os.environ,{'NRY_STAFF_ACCOUNTS':accounts}):
            self.assertEqual(self.client.get('/workspace/cases',headers=ALEX).status_code,401)
            claim=self.client.post(f"/case/{case['case_id']}/pickup",auth=('alex','test-only-alex'),headers=TAYLOR,json={'officer':'someone-else'})
            self.assertEqual(claim.status_code,200)
            self.assertEqual(claim.json()['assignment']['officer'],'alex')
            self.assertEqual(self.client.post(f"/case/{case['case_id']}/decision",auth=('taylor','test-only-taylor'),
                headers=ALEX,json={'decision':'APPROVE','officer':'alex'}).status_code,409)
            session=self.client.get('/workspace/session',auth=('taylor','test-only-taylor')).json()
            self.assertTrue(session['authenticated'])
            self.assertEqual(session['available_officers'],[])
        with patch.dict(os.environ,{'NRY_STAFF_ACCOUNTS':'{broken json'}):
            self.assertEqual(self.client.get('/workspace/cases').status_code,401)

    def test_drafts_never_rank_before_confirmation_and_reject_foreign_facts(self):
        draft=self.client.post('/intake/drafts',json={'customer_id':'CUST-001'}).json()
        url='/intake/drafts/'+draft['draft_id']
        self.assertEqual(self.client.get('/workspace/insights').json()['active'],0)
        self.assertNotIn('priority',draft)
        for fields in ({'linked_transactions':['TX-7001']},{'risk_signals':['NEW_PAYEE_24H']},{'priority_score':100}):
            self.assertEqual(self.client.post(url,json={'expected_revision':draft['revision'],**fields}).status_code,422)
        draft=self.client.post(url,json={'expected_revision':draft['revision'],'issue_type':'SCAM_IN_PROGRESS',
            'summary_en':'The customer reports being asked to send money.','phase':'CHECKING','linked_transactions':['TX-9001']}).json()
        self.assertIn('NEW_PAYEE_24H',draft['verified_signals'])
        self.assertEqual(self.client.get('/queue').json(),[])
        self.assertEqual(self.client.post(url+'/confirm',json={'expected_revision':draft['revision'],'customer_confirmed':False}).status_code,422)
        self.assertEqual(self.client.post(url,json={'expected_revision':1,'summary_en':'Stale overwrite'}).status_code,409)

    def test_repeated_concurrent_confirmation_creates_one_case(self):
        draft=self.client.post('/intake/drafts',json={'customer_id':'CUST-005'}).json()
        url='/intake/drafts/'+draft['draft_id']
        draft=self.client.post(url,json={'expected_revision':draft['revision'],'issue_type':'GENERAL_ENQUIRY',
            'summary_en':'Please help with a general question.','phase':'CONFIRMING'}).json()
        body={'expected_revision':draft['revision'],'customer_confirmed':True}
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=[f.result() for f in [pool.submit(self.client.post,url+'/confirm',json=body) for _ in range(2)]]
        self.assertEqual([r.status_code for r in results],[200,200])
        self.assertEqual(results[0].json(),results[1].json())
        self.assertEqual(len(self.client.get('/workspace/cases').json()),1)
        saved=self.client.get(url).json()
        self.assertEqual(saved['status'],'SUBMITTED')
        self.assertEqual(self.client.post(url,json={'expected_revision':saved['revision'],'summary_en':'Too late'}).status_code,409)

    def test_cancelled_and_invalid_drafts_cannot_create_cases(self):
        self.assertEqual(self.client.post('/intake/drafts',json={'customer_id':'UNKNOWN'}).status_code,422)
        draft=self.client.post('/intake/drafts',json={'customer_id':'CUST-002'}).json()
        url='/intake/drafts/'+draft['draft_id']
        self.assertEqual(self.client.post(url+'/confirm',json={'expected_revision':1,'customer_confirmed':True}).status_code,422)
        self.assertEqual(self.client.post(url+'/cancel',json={'expected_revision':1}).status_code,200)
        self.assertEqual(self.client.get('/workspace/intake').json()['active_count'],0)
        self.assertEqual(self.client.post(url+'/confirm',json={'expected_revision':2,'customer_confirmed':True}).status_code,409)
        self.assertEqual(self.client.get('/workspace/cases').json(),[])

    def test_interrupted_submission_recovers_even_if_case_was_completed(self):
        draft=self.client.post('/intake/drafts',json={'customer_id':'CUST-005'}).json()
        url='/intake/drafts/'+draft['draft_id']
        draft=self.client.post(url,json={'expected_revision':draft['revision'],'issue_type':'GENERAL_ENQUIRY','summary_en':'A confirmed request'}).json()
        pending=copy.deepcopy(intake_drafts.DRAFTS[draft['draft_id']])
        submitted=self.client.post(url+'/confirm',json={'expected_revision':draft['revision'],'customer_confirmed':True}).json()
        store.decide(submitted['case_reference'],'APPROVE',None,'Alex Morgan')
        # Restore the durable pre-confirmation draft, simulating an interrupted second write.
        intake_drafts.DRAFTS[draft['draft_id']]=pending
        db.save_doc('intake_drafts',draft['draft_id'],pending)
        recovered=self.client.post(url+'/confirm',json={'expected_revision':draft['revision'],'customer_confirmed':True})
        self.assertEqual(recovered.status_code,200,recovered.text)
        self.assertEqual(recovered.json()['case_reference'],submitted['case_reference'])
        self.assertFalse(recovered.json()['queued'])
        self.assertEqual(len(self.client.get('/workspace/cases').json()),1)

    def test_claims_and_unsubmitted_drafts_survive_a_process_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            env={**os.environ,'NRY_DB':os.path.join(directory,'restart.db')}
            writer="""import store,intake_drafts\nfrom models import RetellPayload,DraftUpdate\nc=store.create_case(RetellPayload(customer_id='CUST-005',issue_type='GENERAL_ENQUIRY',case_reference='RESTART'))\nstore.pick_up(c['case_id'],'Alex Morgan')\nd=intake_drafts.start('CUST-002')\nintake_drafts.update(d['draft_id'],DraftUpdate(expected_revision=1,issue_type='CARD_DELIVERY',summary_en='Card delivery help'))\n"""
            reader="""import store,intake_drafts\nassert store.CASES['RESTART']['assignment']['officer']=='Alex Morgan'\nd=intake_drafts.listing()\nassert d['active_count']==1 and d['drafts'][0]['revision']==2\nassert d['drafts'][0]['summary_en']=='Card delivery help'\n"""
            for source in (writer,reader):
                r=subprocess.run([sys.executable,'-c',source],env=env,capture_output=True,text=True)
                self.assertEqual(r.returncode,0,r.stderr)


if __name__=='__main__':
    unittest.main(verbosity=2)
