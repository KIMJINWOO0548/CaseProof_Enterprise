import unittest,sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from reference.governance import Actor,DecisionContext,authorize,decide_release
from reference.evidence_pack import (digest,create_evidence_manifest,verify_manifest,
                                     append_audit_event,verify_audit_chain)
from reference.paired_benchmark import compare_runs,wilson_interval

RELEASE = DecisionContext('aurora','author','owner',5,5,True,True,0,0,0,
                          'DOMAIN_APPROVED','PENDING_APPROVAL')
APPROVER = Actor('approver','aurora',frozenset({'RELEASE_APPROVER'}))

class GovernanceTest(unittest.TestCase):
    def test_authorized_read(self):
        self.assertEqual(authorize(APPROVER,'aurora','read'),(True,'AUTHORIZED'))
    def test_cross_tenant_denied(self):
        self.assertEqual(authorize(APPROVER,'horizon','release_approve')[1],'TENANT_MISMATCH')
    def test_disabled_denied(self):
        self.assertFalse(authorize(Actor('x','aurora',frozenset({'RELEASE_APPROVER'}),False),'aurora','read')[0])
    def test_viewer_cannot_approve(self):
        self.assertFalse(authorize(Actor('viewer','aurora',frozenset({'VIEWER'})),'aurora','release_approve')[0])
    def test_tenant_admin_cannot_self_approve(self):
        self.assertFalse(authorize(Actor('admin','aurora',frozenset({'TENANT_ADMIN'})),'aurora','release_approve')[0])
    def test_happy_path_only_demo(self):
        self.assertEqual(decide_release(APPROVER,RELEASE)['status'],'APPROVED_FOR_DEMO')
    def test_no_requester_self_approval(self):
        self.assertIn('SEPARATION_OF_DUTIES',decide_release(Actor('author','aurora',frozenset({'RELEASE_APPROVER'})),RELEASE)['reasons'])
    def test_no_owner_self_approval(self):
        self.assertIn('SEPARATION_OF_DUTIES',decide_release(Actor('owner','aurora',frozenset({'RELEASE_APPROVER'})),RELEASE)['reasons'])
    def test_stale_optimistic_version(self):
        bad=RELEASE.__class__(**{**RELEASE.__dict__,'actual_revision':6})
        self.assertIn('STALE_REVISION',decide_release(APPROVER,bad)['reasons'])
    def test_source_revoked(self):
        bad=RELEASE.__class__(**{**RELEASE.__dict__,'source_approved':False})
        self.assertEqual(decide_release(APPROVER,bad)['status'],'BLOCKED')
    def test_domain_review_missing(self):
        bad=RELEASE.__class__(**{**RELEASE.__dict__,'review_state':'DRAFT'})
        self.assertIn('DOMAIN_REVIEW_NOT_APPROVED',decide_release(APPROVER,bad)['reasons'])
    def test_evidence_must_verify(self):
        bad=RELEASE.__class__(**{**RELEASE.__dict__,'evidence_verified':False})
        self.assertIn('EVIDENCE_INTEGRITY_FAILURE',decide_release(APPROVER,bad)['reasons'])
    def test_critical_block(self):
        bad=RELEASE.__class__(**{**RELEASE.__dict__,'critical_findings':1})
        self.assertEqual(decide_release(APPROVER,bad)['status'],'BLOCKED')
    def test_kill_switch(self):
        bad=RELEASE.__class__(**{**RELEASE.__dict__,'kill_switch':True})
        self.assertEqual(decide_release(APPROVER,bad)['status'],'BLOCKED')
    def test_remaining_review_stays_pending(self):
        bad=RELEASE.__class__(**{**RELEASE.__dict__,'pending_domain_reviews':1})
        self.assertEqual(decide_release(APPROVER,bad)['status'],'PENDING_APPROVAL')

class EvidenceTest(unittest.TestCase):
    def setUp(self):
        h='a'*64
        self.m=create_evidence_manifest(tenant_id='aurora',change_id='ch1',dataset_hash=h,
              evaluator_hash='b'*64,source_hashes=['c'*64],findings_hash='d'*64,
              recorded_at='2026-10-29T00:00:00+09:00')
    def test_deterministic_manifest(self):
        self.assertEqual(self.m['manifest_sha256'],digest(self.m['content']))
    def test_manifest_tenant(self):
        self.assertFalse(verify_manifest(self.m,'horizon'))
    def test_manifest_tamper(self):
        x=copy.deepcopy(self.m)
        x['content']['change_id']='tampered'
        self.assertFalse(verify_manifest(x,'aurora'))
    def test_invalid_hash(self):
        with self.assertRaises(ValueError):
            create_evidence_manifest(tenant_id='aurora',change_id='x',dataset_hash='x',
                 evaluator_hash='b'*64,source_hashes=[],findings_hash='d'*64,recorded_at='now')
    def test_chain_integrity(self):
        events=[]
        events.append(append_audit_event(events,{'action':'SUBMIT'}))
        events.append(append_audit_event(events,{'action':'REVIEW'}))
        self.assertTrue(verify_audit_chain(events))
    def test_chain_detects_edit(self):
        events=[]
        events.append(append_audit_event(events,{'action':'SUBMIT'}))
        events.append(append_audit_event(events,{'action':'REVIEW'}))
        events[0]['event']['action']='CHANGED'
        self.assertFalse(verify_audit_chain(events))
    def test_chain_detects_reorder(self):
        events=[]
        events.append(append_audit_event(events,{'action':'A'}))
        events.append(append_audit_event(events,{'action':'B'}))
        self.assertFalse(verify_audit_chain(events[::-1]))

class BenchmarkTest(unittest.TestCase):
    def setUp(self):
        self.b={'dataset_hash':'a'*64,'evaluator_hash':'b'*64,
                'cases':[{'id':'t1','correct':True,'critical':False,'complete':True},
                         {'id':'t2','correct':False,'critical':False,'complete':True}]}
        self.c=copy.deepcopy(self.b)
    def test_comparable_paired(self):
        self.assertEqual(compare_runs(self.b,self.c)['status'],'ELIGIBLE_FOR_HUMAN_REVIEW')
    def test_new_critical_blocks_even_with_improvement(self):
        self.c['cases'][1].update(correct=True,critical=True)
        report=compare_runs(self.b,self.c)
        self.assertEqual(report['status'],'BLOCKED')
        self.assertEqual(report['accuracy_delta_pp'],50)
    def test_hash_mismatch(self):
        self.c['dataset_hash']='x'*64
        self.assertEqual(compare_runs(self.b,self.c)['status'],'INVALID')
    def test_evaluator_mismatch(self):
        self.c['evaluator_hash']='x'*64
        self.assertEqual(compare_runs(self.b,self.c)['status'],'INVALID')
    def test_missing_id(self):
        self.c['cases'].pop()
        self.assertEqual(compare_runs(self.b,self.c)['status'],'INVALID')
    def test_duplicate_id(self):
        self.c['cases'].append(copy.deepcopy(self.c['cases'][0]))
        self.assertEqual(compare_runs(self.b,self.c)['status'],'INVALID')
    def test_incomplete_blocks(self):
        self.c['cases'][0]['complete']=False
        self.assertIn('INCOMPLETE_EVALUATION',compare_runs(self.b,self.c)['reasons'])
    def test_wilson_bounds(self):
        self.assertEqual(wilson_interval(0,1)[0],0)
        self.assertEqual(wilson_interval(1,1)[1],1)
    def test_invalid_denominator(self):
        with self.assertRaises(ValueError): wilson_interval(0,0)
    def test_missing_label_invalid(self):
        del self.c['cases'][0]['correct']
        self.assertEqual(compare_runs(self.b,self.c)['status'],'INVALID')

if __name__=='__main__': unittest.main()
