import json
from pathlib import Path

import pytest

from test_bitemporal import ASOF, context, pack
from service.policies.registry import PackRegistry
from service.policies.resolver import resolve_context


@pytest.mark.parametrize('field', ['tenant_id', 'pack_id', 'product_id', 'workflow'])
def test_scope_isolation(pack, context, field):
    context[field] = 'other'
    assert resolve_context(context, pack, ASOF)['status'] == 'INCONCLUSIVE'


def test_register_three_packs_without_core_changes(context):
    registry = PackRegistry()
    for path in sorted(Path('datasets/packs').glob('fictional_*.json')):
        pack = json.loads(path.read_text(encoding='utf-8'))
        registry.register(pack)
        context['pack_id'] = pack['pack_id']
        result = resolve_context(context, registry.get('fictional', pack['pack_id']), ASOF)
        assert result['status'] == 'RESOLVED'
    assert len(registry.list_packs('fictional')) == 3
    with pytest.raises(KeyError):
        registry.get('other', 'lantern')


def test_registry_append_only_source_history(pack):
    registry = PackRegistry()
    registry.register(pack)
    pack['sources'][0]['approval_history'][0]['status'] = 'REVOKED'
    with pytest.raises(ValueError):
        registry.register(pack)


def test_registry_defensive_copies_and_append(pack):
    registry = PackRegistry()
    registered = registry.register(pack)
    registered['pack_id'] = 'mutated'
    fetched = registry.get('fictional', 'harbor')
    fetched['sources'].clear()
    assert registry.get('fictional', 'harbor')['sources']
    pack['pack_version'] = 'v2'
    pack['sources'][0]['approval_history'].append(dict(recorded_at='2025-09-01T00:00:00Z', status='REVOKED', evidence_id='fictional-revocation'))
    assert len(registry.register(pack)['sources'][0]['approval_history']) == 2


@pytest.mark.parametrize('target', ['priority', 'basis'])
def test_registry_requires_new_rule_version_for_changed_policy(pack, target):
    registry = PackRegistry()
    registry.register(pack)
    pack['pack_version'] = 'v2'
    if target == 'priority':
        pack['priorities']['ranks']['base'] = 100
    else:
        pack['workflows'][0]['date_basis'] = 'contract_date'
    with pytest.raises(ValueError):
        registry.register(pack)
