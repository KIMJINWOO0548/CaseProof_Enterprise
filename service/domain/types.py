"""Frozen command contexts. Authentication and semantic request validation are caller duties."""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from service.domain.canonical import canonical_bytes


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def json_payload(value):
    """Detach frozen context data back into JSON containers before hashing or responding."""
    if isinstance(value, Mapping):
        return {key: json_payload(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [json_payload(item) for item in value]
    return value


@dataclass(frozen=True)
class ActorContext:
    tenant_id: str
    actor_id: str
    roles: frozenset[str]

    def __post_init__(self):
        object.__setattr__(self, 'roles', frozenset(self.roles))


@dataclass(frozen=True)
class CommandContext:
    method: str
    route_template: str
    resource_id: str
    key: str
    expected_revision: int | None
    body: Mapping[str, Any]

    def __post_init__(self):
        canonical_bytes(self.body)
        object.__setattr__(self, 'body', _freeze(self.body))


@dataclass(frozen=True)
class CommandResult:
    status_code: int
    data: Mapping[str, Any]
    result_revision: int
    replayed: bool

    def __post_init__(self):
        canonical_bytes(self.data)
        object.__setattr__(self, 'data', _freeze(self.data))
