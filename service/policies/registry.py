"""In-memory configuration registry; callers persist immutable snapshots separately."""
from copy import deepcopy

from .schema import PolicyPack


class PackRegistry:
    def __init__(self):
        self._packs = {}
        self._versions = {}

    def register(self, snapshot: dict) -> dict:
        pack = PolicyPack.model_validate(snapshot).model_dump(mode='json')
        key = (pack['tenant_id'], pack['pack_id'])
        for (tenant, pack_id, version), old_pack in self._versions.items():
            if (tenant, pack_id) != key:
                continue
            if version == pack['pack_version'] and pack != old_pack:
                raise ValueError('changed pack requires a new version')
            if (old_pack['priorities']['version'] == pack['priorities']['version']
                    and old_pack['priorities'] != pack['priorities']):
                raise ValueError('changed priority policy requires a new version')
            old_workflows = {w['date_basis_version']: w for w in old_pack['workflows']}
            for workflow in pack['workflows']:
                old = old_workflows.get(workflow['date_basis_version'])
                if old is not None and old != workflow:
                    raise ValueError('changed date basis requires a new version')
            old_retro = {p['policy_id']: p for p in old_pack['retroactivity_policies']}
            for policy in pack['retroactivity_policies']:
                if policy['policy_id'] in old_retro and old_retro[policy['policy_id']] != policy:
                    raise ValueError('changed retroactivity policy requires a new version')
        previous = self._packs.get(key)
        if previous:
            sources = {s['source_id']: s for s in pack['sources']}
            for old in previous['sources']:
                new = sources.get(old['source_id'])
                if (new is None or new['policy_version'] != old['policy_version']
                        or new['approval_history'][:len(old['approval_history'])] != old['approval_history']):
                    raise ValueError('source approval history is append-only')
            if pack['pack_version'] == previous['pack_version'] and pack != previous:
                raise ValueError('changed pack requires a new version')
        self._packs[key] = pack
        self._versions[(*key, pack['pack_version'])] = pack
        return deepcopy(pack)

    def get(self, tenant_id: str, pack_id: str) -> dict:
        return deepcopy(self._packs[(tenant_id, pack_id)])

    def list_packs(self, tenant_id: str) -> list[str]:
        return sorted(pack_id for tenant, pack_id in self._packs if tenant == tenant_id)
