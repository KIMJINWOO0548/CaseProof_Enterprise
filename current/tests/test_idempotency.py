"""Synthetic HTTP retry contracts; no external service or persistent demo DB."""
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_service import fx, TOKENS, good_request
from service.models import Change, User


def headers(who='aurora-analyst', key=None, revision=None):
    value={'Authorization':'Bearer '+TOKENS[who], 'Idempotency-Key':key or uuid4().hex}
    if revision is not None:
        value['X-Expected-Revision']=str(revision)
    return value


def workflow(client, concurrent=False):
    """Return original requests and responses for each operation."""
    calls=[]
    def post(path, body, who='aurora-analyst', revision=None):
        h=headers(who, revision=revision)
        if concurrent:
            with ThreadPoolExecutor(max_workers=3) as pool:
                results=list(pool.map(lambda _:client.post(path,headers=h,json=body),range(3)))
            assert all(r.status_code in (200,201,409) for r in results)
            successes=[r for r in results if r.status_code in (200,201)]
            result=next(r for r in successes if not r.json()['replayed'])
            assert sum(not r.json()['replayed'] for r in successes)==1
            assert all(r.json()['revision']==result.json()['revision'] for r in successes)
            assert all(r.json().get('id')==result.json().get('id') for r in successes)
        else:
            result=client.post(path, headers=h, json=body)
        assert result.status_code in (200,201),result.text
        calls.append((path,body,h,result))
        return result.json()
    c=post('/api/changes',good_request(client))
    root='/api/changes/'+c['id']
    for days,date in [(30,'2026-06-30'),(20,'2026-07-01')]:
        result=post(root+'/evaluations', {'claim_days':days,'basis_date':date,
            'as_of_recorded':'2026-10-28T00:00:00+09:00'},revision=c['revision'])
        c['revision']=result['revision']
    c=post(root+'/submit',{'expected_revision':c['revision']})
    c=post(root+'/domain-decision',{'expected_revision':c['revision'],
        'decision':'APPROVE','reason':'Synthetic domain approval'},'aurora-reviewer')
    post(root+'/release-decision',{'expected_revision':c['revision'],
        'decision':'APPROVE','reason':'Synthetic release approval'},'aurora-approver')
    return calls


def test_all_operations_replay_original_result_after_state_advanced(fx):
    client,app=fx
    calls=workflow(client)
    for path,body,h,original in calls:
        retry=client.post(path,headers=h,json=body)
        assert retry.status_code==original.status_code
        expected={**original.json(),'replayed':True}
        if 'reused' in expected:
            expected['reused']=True
        assert retry.json()==expected
    with app.state.session_factory() as db:
        assert len(db.scalars(select(Change)).all())==1


@pytest.mark.parametrize('length',[None,11,129])
def test_all_operations_require_bounded_header(fx,length):
    client,_=fx
    for path,body,h,_ in workflow(client):
        h=dict(h)
        h.pop('Idempotency-Key')
        if length is not None:
            h['Idempotency-Key']='k'*length
        assert client.post(path,headers=h,json=body).status_code==422
    for path,item in client.get('/openapi.json').json()['paths'].items():
        if 'post' in item:
            p=next(p for p in item['post']['parameters'] if p['name']=='Idempotency-Key')
            assert p['required'] and p['schema']['minLength']==12 and p['schema']['maxLength']==128


def test_fingerprint_body_revision_resource_and_operation_conflicts(fx):
    client,_=fx
    calls=workflow(client)
    for path,body,h,_ in calls:
        changed=dict(body)
        field='title' if path=='/api/changes' else 'claim_days' if path.endswith('evaluations') else 'expected_revision'
        changed[field]='Another synthetic title' if field=='title' else body[field]+1
        assert client.post(path,headers=h,json=changed).status_code==409
    path,body,h,_=calls[1]
    assert client.post(path,headers={**h,'X-Expected-Revision':'99'},json=body).status_code==409
    other=client.post('/api/changes',headers=headers(),json=good_request(client)).json()
    assert client.post('/api/changes/'+other['id']+'/evaluations',headers=h,json=body).status_code==409
    assert client.post(calls[3][0],headers=calls[0][2],json=calls[3][1]).status_code==409


def test_authorization_precedes_replay_and_current_integrity_is_separate(fx):
    client,app=fx
    calls=workflow(client)
    path,body,h,result=calls[1]
    assert client.post(path,headers={**h,'Authorization':'Bearer invalid'},json=body).status_code==401
    assert client.post(path,headers=headers('horizon-analyst',h['Idempotency-Key'],1),json=body).status_code==404
    assert client.post(path,headers=headers('aurora-reviewer',h['Idempotency-Key'],1),json=body).status_code==403
    with app.state.session_factory() as db:
        reviewer=db.get(User,'aurora-reviewer')
        reviewer.roles_json='["ANALYST","DOMAIN_REVIEWER"]'
        c=db.scalars(select(Change)).one()
        c.title='Tampered current projection'
        db.commit()
    assert client.post(path,headers=headers('aurora-reviewer',h['Idempotency-Key'],1),json=body).status_code==403
    retry=client.post(path,headers=h,json=body)
    assert retry.json()['revision']==result.json()['revision'] and retry.json()['replayed']
    root=path.removesuffix('/evaluations')
    assert client.get(root+'/evidence',headers=h).json()['record_integrity_verified'] is False
    with app.state.session_factory() as db:
        db.get(User,'aurora-analyst').roles_json='[]'
        db.commit()
    assert client.post(path,headers=h,json=body).status_code==403


def test_independent_actor_and_tenant_keys_do_not_replay(fx):
    client,app=fx
    key=uuid4().hex
    first=client.post('/api/changes',headers=headers(key=key),json=good_request(client))
    with app.state.session_factory() as db:
        db.get(User,'aurora-reviewer').roles_json='["ANALYST","DOMAIN_REVIEWER"]'
        db.commit()
    second=client.post('/api/changes',headers=headers('aurora-reviewer',key),json=good_request(client))
    third=client.post('/api/changes',headers=headers('horizon-analyst',key),json=good_request(client,'horizon-analyst'))
    assert all(r.status_code==201 and r.json()['replayed'] is False for r in [first,second,third])
    assert len({r.json()['id'] for r in [first,second,third]})==3


def test_concurrent_same_key_has_one_effect(fx):
    client,app=fx
    body=good_request(client)
    h=headers()
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses=list(pool.map(lambda _:client.post('/api/changes',headers=h,json=body),range(4)))
    assert all(r.status_code in (201,409) for r in responses)
    successes=[r.json() for r in responses if r.status_code==201]
    assert len({r['id'] for r in successes})==1
    assert sum(not r['replayed'] for r in successes)==1
    with app.state.session_factory() as db:
        assert len(db.scalars(select(Change)).all())==1


def test_failure_before_commit_rolls_back_idempotency_and_mutation(fx,monkeypatch):
    client,app=fx
    from service.models import IdempotencyRecord
    body=good_request(client)
    h=headers()
    session_class=app.state.session_factory.class_
    original=session_class.commit
    def fail(_):
        raise RuntimeError('injected commit failure')
    monkeypatch.setattr(session_class,'commit',fail)
    with pytest.raises(RuntimeError,match='injected commit failure'):
        client.post('/api/changes',headers=h,json=body)
    with app.state.session_factory() as db:
        assert not db.scalars(select(Change)).all()
        assert not db.scalars(select(IdempotencyRecord)).all()
    monkeypatch.setattr(session_class,'commit',original)
    assert client.post('/api/changes',headers=h,json=body).status_code==201


def test_all_operations_concurrent_retries(fx):
    client,app=fx
    from service.models import IdempotencyRecord, ChangeTransition, AuditEvent
    workflow(client,concurrent=True)
    with app.state.session_factory() as db:
        assert len(db.scalars(select(IdempotencyRecord)).all())==6
        assert len(db.scalars(select(ChangeTransition)).all())==6
        assert len(db.scalars(select(AuditEvent)).all())==6
    assert client.get('/api/audit/verify',headers=headers('aurora-auditor')).json()['verified']


def test_committed_response_loss_replays_without_second_effect(fx,monkeypatch):
    client,app=fx
    body=good_request(client)
    h=headers()
    session_class=app.state.session_factory.class_
    commit=session_class.commit
    def lose_response(db):
        commit(db)
        raise RuntimeError('response lost after durable commit')
    monkeypatch.setattr(session_class,'commit',lose_response)
    with pytest.raises(RuntimeError,match='response lost'):
        client.post('/api/changes',headers=h,json=body)
    monkeypatch.setattr(session_class,'commit',commit)
    retry=client.post('/api/changes',headers=h,json=body)
    assert retry.status_code==201 and retry.json()['replayed']
    with app.state.session_factory() as db:
        assert len(db.scalars(select(Change)).all())==1


@pytest.mark.parametrize('stage,who',[('domain-decision','aurora-reviewer'),('release-decision','aurora-approver')])
def test_current_separation_checked_before_historical_replay(fx,stage,who):
    client,app=fx
    calls=workflow(client)
    path,body,h,_=next(call for call in calls if call[0].endswith(stage))
    with app.state.session_factory() as db:
        db.scalars(select(Change)).one().owner_id=who
        db.commit()
    response=client.post(path,headers=h,json=body)
    assert response.status_code==403 and response.json()['detail']['code']=='SEPARATION_OF_DUTIES'


def test_sqlite_busy_is_explicit_retryable_conflict(fx):
    client,app=fx
    from sqlalchemy import event
    body=good_request(client)
    h=headers()
    # Bound the test's lock timeout; production engine configuration is unchanged.
    @event.listens_for(app.state.db_engine,'checkout')
    def short_timeout(connection,*_):
        connection.execute('PRAGMA busy_timeout=1')
    with app.state.db_engine.connect() as connection:
        connection.exec_driver_sql('BEGIN IMMEDIATE')
        response=client.post('/api/changes',headers=h,json=body)
        assert response.status_code==409 and response.json()['detail']['retryable'] is True
        connection.rollback()
    assert client.post('/api/changes',headers=h,json=body).status_code==201


def test_two_app_sessions_serialize_different_change_audit_writes(fx):
    client,app=fx
    from fastapi.testclient import TestClient
    from service.app import create_app
    second_app=create_app(str(app.state.db_engine.url),demo_mode=True)
    body=good_request(client)
    try:
        with TestClient(second_app) as second:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(lambda target:target.post('/api/changes',headers=headers(),json=body),
                                      [client,second]))
            assert all(r.status_code==201 for r in results)
            assert results[0].json()['id']!=results[1].json()['id']
        assert client.get('/api/audit/verify',headers=headers('aurora-auditor')).json()['verified']
    finally:
        second_app.state.db_engine.dispose()
