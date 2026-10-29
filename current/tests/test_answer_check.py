import unittest
from reference.verify_answer import verify_numeric_claim

BASE={'tenant':'AURORA_NONLIFE','product':'AUTO-101','workflow':'AUTO_CLAIM_GUIDANCE',
      'rule_key':'DOCUMENT_WINDOW_DAYS','claim_received_date':'2026-06-20',
      'question_date':'2026-10-20','as_of_recorded':'2026-10-28T00:00:00+09:00'}

class TestAnswerCheck(unittest.TestCase):
    def test_wrong_latest_rule_blocked(self):
        r=verify_numeric_claim(BASE,20)
        self.assertEqual((r['verdict'],r['expected_days']),('BLOCK',30))
    def test_correct_old_rule_accepted(self):
        self.assertEqual(verify_numeric_claim(BASE,30)['verdict'],'PASS')
    def test_missing_basis_stays_inconclusive(self):
        c={k:v for k,v in BASE.items() if k!='claim_received_date'}
        self.assertEqual(verify_numeric_claim(c,30)['verdict'],'INCONCLUSIVE')
    def test_bool_not_numeric(self):
        self.assertEqual(verify_numeric_claim(BASE,True)['reason'],'UNSUPPORTED_CLAIM')
    def test_cutover_boundary(self):
        c={**BASE,'claim_received_date':'2026-07-01'}
        self.assertEqual(verify_numeric_claim(c,20)['verdict'],'PASS')

if __name__=='__main__': unittest.main()
