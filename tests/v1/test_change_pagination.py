"""Tenant-scoped continuation of real persisted changes without silent truncation."""
import pytest
from service import models_v1 as m
from tests.v1.test_workspace import workspace, headers, mutate


def create(client, actor='analyst', title='Synthetic paging case'):
    preset = client.get('/api/v1/workspace', headers=headers(actor)).json()['data']['presets'][0]
    return mutate(client, '', dict(preset['create_body'], title=title), actor=actor)['change_id']


def test_pages_cover_saved_changes_once_and_respect_revocation(workspace):
    client, factory, _ = workspace
    expected = sorted(create(client, title=f'Synthetic {n}') for n in range(5))
    foreign = create(client, actor='other')
    first = client.get('/api/v1/changes?limit=2', headers=headers())
    assert first.status_code == 200, first.text
    data = first.json()
    assert [x['change_id'] for x in data['data']] == expected[:2]
    assert data['pagination'] == {'limit': 2, 'next_cursor': expected[1]}
    second = client.get('/api/v1/changes', params={'limit': 2, 'after': data['pagination']['next_cursor']}, headers=headers()).json()
    assert [x['change_id'] for x in second['data']] == expected[2:4]
    third = client.get('/api/v1/changes', params={'limit': 2, 'after': second['pagination']['next_cursor']}, headers=headers()).json()
    assert [x['change_id'] for x in third['data']] == expected[4:]
    assert third['pagination']['next_cursor'] is None
    assert foreign not in expected
    with factory.begin() as db:
        db.get(m.Actor, ('fictional', 'analyst')).enabled = False
    assert client.get('/api/v1/changes', params={'after': expected[1]}, headers=headers()).status_code == 401


@pytest.mark.parametrize('query', ['limit=0', 'limit=201', 'limit=-1', 'limit=1.5', 'limit=01',
    'limit=2&limit=3', 'after=bad', 'after=', 'after=x&after=y', 'unknown=1'])
def test_invalid_paging_query_is_rejected(workspace, query):
    client, _, _ = workspace
    assert client.get('/api/v1/changes?' + query, headers=headers()).status_code == 422


def test_default_shape_and_foreign_position_never_leak_tenant_rows(workspace):
    client, _, _ = workspace
    foreign = create(client, actor='other')
    expected = create(client)
    result = client.get('/api/v1/changes', headers=headers()).json()
    assert isinstance(result['data'], list)
    assert [x['change_id'] for x in result['data']] == [expected]
    assert result['pagination'] == {'limit': 200, 'next_cursor': None}
    positioned = client.get('/api/v1/changes', params={'after': foreign}, headers=headers())
    assert positioned.status_code == 200
    assert all(x['tenant_id'] == 'fictional' for x in positioned.json()['data'])
    assert client.get('/api/v1/workspace?limit=2', headers=headers()).status_code == 422


def test_default_cap_exposes_continuation_after_two_hundred(workspace):
    client, _, _ = workspace
    preset = client.get('/api/v1/workspace', headers=headers()).json()['data']['presets'][0]
    expected = sorted(mutate(client, '', dict(preset['create_body'], title=f'Synthetic bulk {n}'))['change_id']
                      for n in range(201))
    first = client.get('/api/v1/changes', headers=headers()).json()
    assert [row['change_id'] for row in first['data']] == expected[:200]
    assert first['pagination']['next_cursor'] == expected[199]
    last = client.get('/api/v1/changes', params={'after': expected[199]}, headers=headers()).json()
    assert [row['change_id'] for row in last['data']] == expected[200:]
    assert last['pagination']['next_cursor'] is None


def test_position_is_not_an_offset_or_required_existing_record(workspace):
    from uuid import uuid4
    client, _, _ = workspace
    saved = [create(client) for _ in range(4)]
    first = client.get('/api/v1/changes?limit=2', headers=headers()).json()
    cursor = first['pagination']['next_cursor']
    saved.append(create(client))
    continuation = client.get('/api/v1/changes', params={'after': cursor}, headers=headers()).json()
    assert [x['change_id'] for x in continuation['data']] == sorted(x for x in saved if x > cursor)
    absent_position = str(uuid4())
    positioned = client.get('/api/v1/changes', params={'after': absent_position}, headers=headers())
    assert positioned.status_code == 200
    assert [x['change_id'] for x in positioned.json()['data']] == sorted(x for x in saved if x > absent_position)
