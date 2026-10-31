from service.domain.evidence import build_assessment, build_envelope, verify_evidence
from service.commands import execute_command
from service.repositories import load_history
from service.domain.types import json_payload
from tests.v1.helpers import setup, command
from copy import deepcopy


def approved(tmp_path):
    factory, actors, body = setup(tmp_path)
    result=execute_command(factory, actors['analyst'], command(body))
    identity=result.data['change_id']
    payload={'suite_version_id':body['suite_version_id'], 'case_inputs':[{'case_id':c,'claim_days':30,'case_context':{}} for c in ('case-a','case-b')]}
    execute_command(factory,actors['analyst'],command(payload,'evaluation-runs',identity,1))
    execute_command(factory,actors['analyst'],command({},'submit',identity,2))
    execute_command(factory,actors['reviewer'],command({'decision':'APPROVE','reason':'Reviewed synthetic evidence'},'domain-decision',identity,3))
    execute_command(factory,actors['approver'],command({'decision':'APPROVE','reason':'Approved synthetic evidence'},'release-decision',identity,4))
    with factory() as db:
        return factory, actors, body, load_history(db,'tenant-a',identity)


def test_preapproval_excludes_final_and_no_anchor(tmp_path):
    _,_,_,h=approved(tmp_path)
    assert h['assessment']['preapproval_revision']==4
    assert [t['revision_to'] for t in h['assessment']['transition_refs']]==[1,2,3,4]
    assert h['envelope']['approved_revision']==5
    assert verify_evidence(h)['historical_integrity']=='VALID'
    assert verify_evidence(h)['external_anchor']=='NOT_CONFIGURED'


def test_unrelated_updates_preserve_seal_and_withdrawal_separate(tmp_path):
    factory,actors,body,h=approved(tmp_path)
    execute_command(factory,actors['analyst'],command(body))
    with factory() as db:
        later=load_history(db,'tenant-a',h['snapshot']['change_id'])
    assert verify_evidence(later)['historical_integrity']=='VALID'
    revoked=deepcopy(later['refs']['source_eligibility'][0])
    revoked.update(id='withdrawal',sequence=2,eligible=False)
    later['refs']['source_eligibility'].append(revoked)
    assert verify_evidence(later)['historical_integrity']=='VALID'
    assert verify_evidence(later)['current_approval_eligibility']=='BLOCKED'


def test_frozen_record_changes_invalidate(tmp_path):
    _,_,_,h=approved(tmp_path)
    for collection, field, value in [('runs','gate_summary','BLOCK'),('decisions','reason','Tampered reason'),('events','actor_id','someone')]:
        changed=deepcopy(h)
        changed[collection][0][field]=value
        assert verify_evidence(changed)['historical_integrity']=='INVALID'
    changed=deepcopy(h)
    changed['refs']['sources'][0]['claim_days']=99
    assert verify_evidence(changed)['historical_integrity']=='INVALID'
