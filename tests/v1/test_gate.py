from copy import deepcopy
import pytest
from service.domain.gates import check_run_gate, source_eligibility


def fixture():
    eligibility = {'eligible': True, 'source_refs': [{'id': 's1', 'payload_sha256': 'a'*64, 'policy_version_id': 'v1', 'status': 'APPROVED'}, {'id': 's2', 'payload_sha256': 'b'*64, 'policy_version_id': 'v2', 'status': 'APPROVED'}]}
    suite = {'required_case_ids': ['a','b'], 'case_policy_versions': {'a':['v1'], 'b':['v2']}, 'required_coverage_labels':['edge'], 'coverage_by_case': {'a':['edge'],'b':[]}, 'minimum_distinct_policy_versions':2}
    cases = [dict(case_id=c, source_refs=[{'id':s,'payload_sha256':h*64}], verdict='PASS',complete=True,critical_failure=False,error_code=None) for c,s,h in [('a','s1','a'),('b','s2','b')]]
    return {'case_results':cases},suite,eligibility


def test_full_gate():
    assert check_run_gate(*fixture())['gate_summary'] == 'PASS'


@pytest.mark.parametrize('change', ['missing','duplicate','critical','incomplete','version','source_hash','coverage'])
def test_fail_closed_gate(change):
    run,suite,eligibility=fixture()
    if change=='missing': run['case_results'].pop()
    if change=='duplicate': run['case_results'].append(deepcopy(run['case_results'][0]))
    if change=='critical': run['case_results'][0]['critical_failure']=True
    if change=='incomplete': run['case_results'][0].update(complete=False,verdict='INCONCLUSIVE',critical_failure=None)
    if change=='version': eligibility['source_refs'][1]['policy_version_id']='v1'
    if change=='source_hash': run['case_results'][0]['source_refs'][0]['payload_sha256']='c'*64
    if change=='coverage': suite['required_coverage_labels'].append('missing')
    assert check_run_gate(run,suite,eligibility)['gate_summary']=='BLOCK'


def test_eligibility_uses_sequence_and_rejects_ambiguity():
    h={'snapshot':{'source_bundle_id':'bundle'},'refs':{'source_eligibility':[{'id':'z','source_bundle_id':'bundle','sequence':1,'eligible':True}, {'id':'a','source_bundle_id':'bundle','sequence':2,'eligible':False}]}}
    assert source_eligibility(h)['eligible'] is False
    h['refs']['source_eligibility'].append(dict(h['refs']['source_eligibility'][1],id='b'))
    assert source_eligibility(h)['eligible'] is False
