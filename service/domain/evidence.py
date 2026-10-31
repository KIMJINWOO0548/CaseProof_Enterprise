"""Non-recursive reconstruction of frozen preapproval and final evidence."""
from copy import deepcopy
from service.api.errors import DomainError
from service.domain.canonical import content_hash
from service.domain.gates import check_run_gate, source_eligibility


def _require(condition):
    if not condition:
        raise ValueError('evidence mismatch')


def _ref(purpose, payload, **extra):
    return dict(id=payload['id'],payload_sha256=content_hash(purpose,payload),**extra)


def _one(rows, key, value):
    found=[row for row in rows if row[key]==value]
    _require(len(found)==1)
    return found[0]


def _eligibility_refs(history, eligibility):
    sources=history['refs']['sources']
    refs=eligibility.get('source_refs',[])
    _require(eligibility['source_bundle_id']==history['snapshot']['source_bundle_id'])
    _require(len(refs)==len(sources) and len({ref['id'] for ref in refs})==len(refs))
    for ref in refs:
        source=_one(sources,'id',ref['id'])
        _require(ref['payload_sha256']==content_hash('source',source))
        _require(ref['policy_version_id']==source['policy_version_id'])


def build_assessment(history, p):
    snapshot=_one(history['snapshots'],'revision',p)
    refs=history['refs']
    runs=sorted([r for r in history['runs'] if r['recorded_revision']<=p],key=lambda r:(r['recorded_revision'],r['id']))
    decisions=sorted([r for r in history['decisions'] if r['output_revision']<=p],key=lambda r:(r['output_revision'],r['id']))
    transitions=sorted([r for r in history['transitions'] if r['revision_to']<=p],key=lambda r:r['revision_to'])
    _require([t['revision_to'] for t in transitions]==list(range(1,p+1)))
    _require(runs and snapshot['active_run_id']==runs[-1]['id'])
    eligibility=source_eligibility(history)
    _eligibility_refs(history,eligibility)
    _require(check_run_gate(runs[-1],refs['suite'],eligibility)['gate_summary']=='PASS')
    transition_refs=[]
    for transition in transitions:
        event=_one(history['events'],'transition_id',transition['id'])
        _require(event['transition_sha256']==content_hash('transition',transition))
        _require(event['sequence']<=history['tenant_head']['sequence'])
        transition_refs.append(_ref('transition',transition,revision_to=transition['revision_to'],
            audit_event_ref=_ref('audit-event',event,sequence=event['sequence'])))
    manifest=dict(schema='assessment_manifest_v1',tenant_id=snapshot['tenant_id'],change_id=snapshot['change_id'],
        preapproval_revision=p,preapproval_snapshot_sha256=content_hash('change-revision',snapshot),
        tenant_audit_checkpoint=dict(history['tenant_head']),selected_run_id=snapshot['active_run_id'],
        run_refs=[_ref('evaluation-run',r,recorded_revision=r['recorded_revision']) for r in runs],
        decision_refs=[_ref('decision',r,output_revision=r['output_revision']) for r in decisions],
        transition_refs=transition_refs,source_eligibility_snapshot_ref=_ref('source-eligibility',eligibility))
    for name,purpose,target in [('candidate_snapshot','candidate','candidate_snapshot_ref'),('source_bundle','source-bundle','source_bundle_ref'),
        ('dataset','dataset','dataset_ref'),('suite','suite','suite_ref'),('evaluator','evaluator','evaluator_ref'),
        ('model','model','model_ref'),('prompt','prompt','prompt_ref')]:
        manifest[target]=_ref(purpose,refs[name]) if refs[name] is not None else None
    return manifest


def build_envelope(assessment, snapshot, note, transition, event):
    return dict(schema='approval_envelope_v1',tenant_id=snapshot['tenant_id'],change_id=snapshot['change_id'],
        preapproval_revision=assessment['preapproval_revision'],approved_revision=snapshot['revision'],
        assessment_sha256=content_hash('assessment',assessment),release_decision_ref=_ref('decision',note),
        release_transition_ref=_ref('transition',transition),release_event_ref=_ref('audit-event',event,sequence=event['sequence']),
        approved_snapshot_sha256=content_hash('change-revision',snapshot),approver_id=note['actor_id'],approved_at=note['occurred_at'])


def verify_evidence(history):
    """History must first pass repository ledger/row validation; never reload it here."""
    result=dict(historical_integrity='VALID',current_approval_eligibility='NOT_APPLICABLE',
                external_anchor='NOT_CONFIGURED',approved_revision=None,envelope_sha256=None)
    try:
        latest=source_eligibility(history)
        _eligibility_refs(history,latest)
        current=latest.get('eligible') is True and all(ref['status']=='APPROVED' for ref in latest['source_refs'])
    except (KeyError,TypeError,ValueError):
        current=False
    if history['snapshot']['status'] != 'REJECTED':
        result['current_approval_eligibility']='ELIGIBLE' if current else 'BLOCKED'
    assessment,envelope=history.get('assessment'),history.get('envelope')
    if assessment is None and envelope is None:
        if history['snapshot']['status']=='APPROVED_FOR_DEMO':
            result['historical_integrity']='INVALID'
        return result
    try:
        _require(assessment is not None and envelope is not None)
        p=assessment['preapproval_revision']
        checkpoint=assessment['tenant_audit_checkpoint']
        sequence=checkpoint['sequence']
        _require(type(sequence) is int and sequence>=p)
        prefix=sorted([e for e in history['tenant_events'] if e['sequence']<=sequence],key=lambda e:e['sequence'])
        previous='0'*64
        for index,event in enumerate(prefix,1):
            _require(event['sequence']==index and event['prev_hash']==previous)
            previous=content_hash('audit-event',event)
        _require(len(prefix)==sequence and previous==checkpoint['head_sha256'])
        frozen=_one(history['refs']['source_eligibility'],'id',assessment['source_eligibility_snapshot_ref']['id'])
        reconstruction=dict(history,tenant_head=dict(checkpoint),refs=dict(history['refs'],source_eligibility=[frozen]))
        _require(build_assessment(reconstruction,p)==assessment)
        snapshot=_one(history['snapshots'],'revision',p+1)
        transition=_one(history['transitions'],'revision_to',p+1)
        note=_one(history['decisions'],'output_revision',p+1)
        event=_one(history['events'],'transition_id',transition['id'])
        _require(event['sequence']==sequence+1 and event['prev_hash']==checkpoint['head_sha256'])
        _require(_one(history['tenant_events'],'id',event['id'])==event)
        _require(snapshot['status']=='APPROVED_FOR_DEMO' and note['stage']=='RELEASE' and note['decision']=='APPROVE')
        digest=content_hash('assessment',assessment)
        _require(snapshot['assessment_sha256']==note['assessment_sha256']==transition['assessment_sha256']==digest)
        _require(build_envelope(assessment,snapshot,note,transition,event)==envelope)
        result.update(approved_revision=p+1,envelope_sha256=content_hash('approval-envelope',envelope))
    except (KeyError,TypeError,ValueError,IndexError,DomainError):
        result['historical_integrity']='INVALID'
    return result
