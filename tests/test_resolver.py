import sys
import unittest
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))
from resolver import resolve, load_rules

class TestSyntheticResolver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = json.loads((ROOT / "datasets" / "resolver_test_cases.json").read_text(encoding="utf-8"))

    def test_contract_cases(self):
        for case in self.fixtures["cases"]:
            with self.subTest(case=case["id"]):
                query = dict(case["input"])
                query.setdefault("as_of_recorded", self.fixtures["default_recorded"])
                result = resolve(query)
                self.assertEqual(result.status, case["expected"]["status"])
                for key in ("rule_id","value"):
                    if key in case["expected"]:
                        self.assertEqual(getattr(result, key), case["expected"][key])
                if "reason" in case["expected"]:
                    self.assertIn(case["expected"]["reason"], result.reason_codes)

    def test_source_not_mutated(self):
        rules = load_rules()
        old = json.dumps(rules, sort_keys=True)
        resolve({"tenant":"AURORA_NONLIFE", "product":"AUTO-101", "workflow":"AUTO_CLAIM_GUIDANCE", "rule_key":"DOCUMENT_WINDOW_DAYS", "claim_received_date":"2026-06-30", "as_of_recorded":"2026-10-28T00:00:00+09:00"}, rules)
        self.assertEqual(json.dumps(rules, sort_keys=True), old)

    def test_priority_conflict_fail_closed(self):
        rules = load_rules()
        for r in list(rules):
            if r["rule_id"] == "AR-AUTO-2026-H1":
                copy = dict(r)
                copy["rule_id"] = "ATTACK-DUPLICATE"
                copy["value"] = 999
                rules.append(copy)
                break
        got = resolve({"tenant":"AURORA_NONLIFE", "product":"AUTO-101", "workflow":"AUTO_CLAIM_GUIDANCE", "rule_key":"DOCUMENT_WINDOW_DAYS", "claim_received_date":"2026-06-30", "as_of_recorded":"2026-10-28T00:00:00+09:00"}, rules)
        self.assertEqual((got.status,got.reason_codes), ("INCONCLUSIVE",["POLICY_CONFLICT"]))

if __name__ == "__main__": unittest.main()
