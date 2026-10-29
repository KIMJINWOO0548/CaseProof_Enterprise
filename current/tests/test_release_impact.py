import unittest, sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'reference'))
from impact import select_tests
from release_gate import check_release

CLEAN = {
 'kill_switch':False, 'dataset_hash_mismatch':False,
 'evaluator_hash_mismatch':False, 'sources_approved':True,
 'audit_verified':True, 'mandatory_missing':0,
 'new_critical_failures':0, 'execution_errors':0,
 'unmapped_impact':False, 'unresolved_review_count':0,
 'requester_id':'alice', 'approver_id':'bob'
}
class TestReleaseGate(unittest.TestCase):
  def test_safe_approved_for_demo_only(self):
    self.assertEqual(check_release(dict(CLEAN))['status'],'APPROVED_FOR_DEMO')
  def test_new_critical_blocks_even_if_averages_better(self):
    x={**CLEAN,'new_critical_failures':1,'overall_quality_delta':0.99}
    self.assertIn('CRITICAL_REGRESSION',check_release(x)['blocking_reasons'])
  def test_separation_of_duties(self):
    x={**CLEAN,'approver_id':'alice'}
    self.assertEqual(check_release(x)['status'],'BLOCKED')
  def test_data_evaluator_snapshots(self):
    for key in ['dataset_hash_mismatch','evaluator_hash_mismatch']:
      with self.subTest(key=key):
        self.assertEqual(check_release({**CLEAN,key:True})['status'],'BLOCKED')
  def test_unmapped_review_required(self):
    self.assertEqual(check_release({**CLEAN,'unmapped_impact':True})['status'],'PENDING_APPROVAL')
  def test_audit_failure_blocks(self):
    self.assertEqual(check_release({**CLEAN,'audit_verified':False})['status'],'BLOCKED')
  def test_missing_tests_blocks(self):
    self.assertEqual(check_release({**CLEAN,'mandatory_missing':1})['status'],'BLOCKED')

class TestImpactPlanner(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    cls.graph=json.loads((ROOT/'datasets'/'synthetic_impact_graph.json').read_text(encoding='utf-8'))
  def test_auto_clause_selects_auto_tests(self):
    plan=select_tests(['clause:A.1'],self.graph['edges'],self.graph['sentinel_tests'],self.graph['prior_critical_failures'])
    self.assertIn('T01-old-claim',plan['directly_impacted_test_ids'])
    self.assertNotIn('T07-life-old',plan['directly_impacted_test_ids'])
    self.assertIn('T15-tenant-isolation',plan['selected_test_ids'])
    self.assertFalse(plan['needs_manual_impact_review'])
  def test_unmapped_stays_visible(self):
    plan=select_tests(['clause:UNKNOWN'],self.graph['edges'],self.graph['sentinel_tests'],self.graph['prior_critical_failures'])
    self.assertTrue(plan['needs_manual_impact_review'])
    self.assertIn('clause:UNKNOWN',plan['unmapped_impact_nodes'])
    self.assertTrue(plan['selected_test_ids'])

if __name__=='__main__': unittest.main()
