"""Numeric-claim proof of concept built on canonical resolver.
No external AI calls, no legal judgement, no production auth.
"""
from .resolver import resolve

def verify_numeric_claim(query: dict, ai_days_claim: int, rules=None) -> dict:
    base = resolve(query, rules)
    if base.status != 'RESOLVED':
        return {'verdict':'INCONCLUSIVE','reason':base.reason_codes[0],
                'resolved_rule_id':base.rule_id,'expected_days':None}
    if isinstance(ai_days_claim,bool) or not isinstance(ai_days_claim,int) or ai_days_claim < 0:
        return {'verdict':'INCONCLUSIVE','reason':'UNSUPPORTED_CLAIM',
                'resolved_rule_id':base.rule_id,'expected_days':base.value}
    if ai_days_claim != base.value:
        return {'verdict':'BLOCK','reason':'NUMERIC_POLICY_MISMATCH',
                'resolved_rule_id':base.rule_id,'expected_days':base.value,
                'ai_days_claim':ai_days_claim,'basis_date':base.basis_date,'source_clause':base.clause}
    return {'verdict':'PASS','reason':'NUMERIC_POLICY_MATCH',
            'resolved_rule_id':base.rule_id,'expected_days':base.value,
            'ai_days_claim':ai_days_claim,'basis_date':base.basis_date,'source_clause':base.clause}
