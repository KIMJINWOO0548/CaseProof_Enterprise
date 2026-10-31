"""Versioned execution inputs, shared by recording and historical verification."""
from service.domain.canonical import content_hash


def execution_config_sha256(refs, adapter):
    payload = {'schema': 'execution_config_v2', **{name: refs[name] for name in (
        'candidate_snapshot', 'source_bundle', 'dataset', 'suite', 'evaluator', 'model', 'prompt')},
        'adapter': adapter}
    return content_hash('run-config-v2', payload)
