"""Current DB identity is authoritative, including for historical replay."""
import hashlib
import re

from sqlalchemy import select, text

from service.api.errors import DomainError
from service.domain.canonical import parse_json
from service.domain.types import ActorContext
from service.models_v1 import Actor


def tenant_context(db, tenant_id):
    if db.bind.dialect.name == 'postgresql':
        db.execute(text("SELECT set_config('app.tenant_id', :tenant, true)"), {'tenant': tenant_id})


def current_actor(db, actor):
    tenant_context(db, actor.tenant_id)
    row = db.execute(select(Actor).where(Actor.tenant_id == actor.tenant_id, Actor.id == actor.actor_id)).scalar_one_or_none()
    if row is None or not row.enabled:
        raise DomainError('UNAUTHENTICATED')
    try:
        roles = parse_json(row.roles_payload)
        if not isinstance(roles, list) or any(role not in ('ANALYST', 'DOMAIN_REVIEWER', 'RELEASE_APPROVER', 'AUDITOR') for role in roles):
            raise ValueError('roles')
        return ActorContext(actor.tenant_id, actor.actor_id, frozenset(roles))
    except (ValueError, TypeError):
        raise DomainError('UNAUTHENTICATED') from None


def authenticate(token, registry, db):
    entry = registry.get(hashlib.sha256(token.encode('utf-8')).hexdigest())
    if entry is None:
        raise DomainError('UNAUTHENTICATED')
    return current_actor(db, ActorContext(entry['tenant_id'], entry['actor_id'], frozenset()))


class DemoTokenAuthenticator:
    def __init__(self, registry):
        entries = list(registry.items()) if isinstance(registry, dict) else list(registry)
        self.registry = {}
        for digest, entry in entries:
            if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest) or digest in self.registry:
                raise ValueError('invalid token registry')
            if not isinstance(entry, dict) or set(entry) != {'tenant_id', 'actor_id'} or any(
                    not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}', value)
                    for value in entry.values()):
                raise ValueError('invalid token registry')
            self.registry[digest] = dict(entry)
        if not self.registry:
            raise ValueError('empty token registry')

    def __call__(self, token, db):
        return authenticate(token, self.registry, db)
