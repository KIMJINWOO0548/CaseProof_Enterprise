"""Local SQLite v1 recovery, without replacement of existing files or remote anchors."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import sqlite3

from sqlalchemy import select

from service import models_v1 as m
from service.api.schemas_v1 import CreateHeaders
from service.commands import BASE
from service.db import make_engine, session_factory
from service.domain.canonical import canonical_bytes, content_hash
from service.domain.evidence import verify_evidence
from service.idempotency_v1 import replay
from service.repositories import ZERO, decode, load_history


def utc_now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _read_only(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)


def _verify_request_ledger(db, history):
    """Each verified historical transition needs exactly one intact saved result."""
    snapshot = history['snapshot']
    transitions = {row['revision_to']: row for row in history['transitions']}
    snapshots = {row['revision']: row for row in history['snapshots']}
    runs = {row['id']: row for row in history['runs']}
    records = db.execute(select(m.IdempotencyRecord).where(
        m.IdempotencyRecord.tenant_id == snapshot['tenant_id'],
        m.IdempotencyRecord.change_id == snapshot['change_id'])).scalars().all()
    if len(records) != len(transitions):
        raise ValueError('Missing or extra committed request record')
    suffixes = {'CHANGE_CREATED': '', 'EVALUATION_RECORDED': 'evaluation-runs',
                'SUBMITTED_FOR_DOMAIN_REVIEW': 'submit', 'DOMAIN_APPROVE': 'domain-decision',
                'DOMAIN_REJECT': 'domain-decision', 'RELEASE_REJECT': 'release-decision',
                'APPROVED_FOR_DEMO': 'release-decision'}
    seen = set()
    for row in records:
        saved = decode(row)
        replay(row)  # Also checks indexed fingerprint/status aliases against the payload.
        revision = row.result_revision
        if revision not in transitions or revision in seen:
            raise ValueError('Missing or duplicate committed request revision')
        seen.add(revision)
        transition = transitions[revision]
        kind = transition['kind']
        CreateHeaders.model_validate({'Idempotency-Key': row.key})
        if not re.fullmatch('[0-9a-f]{64}', row.fingerprint_sha256):
            raise ValueError('Invalid committed request fingerprint')
        response = dict(snapshots[revision])
        if kind == 'EVALUATION_RECORDED':
            response['run'] = runs[transition['evaluation_run_id']]
        suffix = suffixes[kind]
        expected = {'schema': 'idempotency_record_v1', 'tenant_id': snapshot['tenant_id'],
            'actor_id': transition['actor_id'], 'key': row.key, 'request_sha256': row.fingerprint_sha256,
            'method': 'POST', 'route_template': BASE + ('/{change_id}/' + suffix if suffix else ''),
            'resource_id': snapshot['change_id'] if suffix else 'NEW',
            'response_status': 201 if kind in ('CHANGE_CREATED', 'EVALUATION_RECORDED') else 200,
            'response_data_json': response, 'result_revision': revision,
            'created_at': transition['occurred_at'], 'completed_at': transition['occurred_at'],
            'completion': 'COMMITTED'}
        if canonical_bytes(saved) != canonical_bytes(expected):
            raise ValueError('Committed request does not match its historical transition')


def inspect_database(path):
    """Verify physical/schema/FK and application evidence; describe committed state."""
    with closing(_read_only(path)) as db:
        if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('SQLite integrity check failed')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Foreign key integrity check failed')
        counts = {}
        for table in m.BaseV1.metadata.tables.values():
            actual = [row[1] for row in db.execute(f'PRAGMA table_info("{table.name}")')]
            if actual != [column.name for column in table.columns]:
                raise ValueError('Unsupported v1 schema: ' + table.name)
            counts[table.name] = db.execute(f'SELECT count(*) FROM "{table.name}"').fetchone()[0]
        schema = repr(db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").fetchall()).encode()
        heads = [dict(tenant_id=t, sequence=s, head_sha256=h) for t, s, h in db.execute(
            'SELECT tenant_id,sequence,head_sha256 FROM v1_tenant_audit_head ORDER BY tenant_id')]
    engine = make_engine('sqlite:///file:' + Path(path).resolve().as_posix() + '?mode=ro&uri=true')
    envelopes = []
    try:
        with session_factory(engine)() as db:
            for tenant in db.execute(select(m.Tenant).order_by(m.Tenant.id)).scalars():
                try:
                    head = db.get(m.TenantAuditHead, tenant.id)
                    previous, sequence = ZERO, 0
                    events = db.execute(select(m.AuditEvent).where(m.AuditEvent.tenant_id == tenant.id)
                                        .order_by(m.AuditEvent.sequence)).scalars()
                    for sequence, row in enumerate(events, 1):
                        event = decode(row)
                        if (event['sequence'] != sequence or event['prev_hash'] != previous
                                or event['tenant_id'] != tenant.id or event['subject_type'] != 'CHANGE'):
                            raise ValueError('Invalid tenant audit chain')
                        previous = content_hash('audit-event', event)
                    if head is None or head.sequence != sequence or head.head_sha256 != previous:
                        raise ValueError('Invalid tenant audit checkpoint')
                except Exception as error:
                    raise ValueError('Tenant audit integrity check failed') from error
            for change in db.execute(select(m.Change).order_by(m.Change.tenant_id, m.Change.id)).scalars():
                try:
                    history = load_history(db, change.tenant_id, change.id)
                    evidence = verify_evidence(history)
                except Exception as error:
                    raise ValueError('Application evidence integrity check failed') from error
                if evidence['historical_integrity'] != 'VALID':
                    raise ValueError('Application evidence integrity check failed')
                try:
                    _verify_request_ledger(db, history)
                except Exception as error:
                    raise ValueError('Idempotency request ledger integrity check failed') from error
                if evidence['envelope_sha256']:
                    envelopes.append(dict(tenant_id=change.tenant_id, change_id=change.id, sha256=evidence['envelope_sha256']))
    finally:
        engine.dispose()
    return dict(schema_sha256=hashlib.sha256(schema).hexdigest(), integrity_check='ok',
                row_counts=counts, tenant_heads=heads, envelopes=envelopes)


def backup_database(source, target):
    """Online backup includes committed WAL; reserve a new target exclusively."""
    started = utc_now()
    target = Path(target)
    with target.open('xb'):
        pass
    with closing(_read_only(source)) as origin, closing(sqlite3.connect(target)) as destination:
        origin.backup(destination)
    snapshot = inspect_database(target)
    return dict(schema='caseproof.local-backup.v1', started_at=started, completed_at=utc_now(),
                backup_sha256=file_sha256(target), snapshot=snapshot, external_anchor='SKIPPED')


def restore_database(backup, target, metadata):
    """Restore only to a new file, after checking backup bytes and recorded state."""
    started = utc_now()
    target = Path(target)
    if target.exists():
        raise FileExistsError(target)
    if metadata.get('schema') != 'caseproof.local-backup.v1':
        raise ValueError('Unsupported backup metadata schema')
    if file_sha256(backup) != metadata['backup_sha256']:
        raise ValueError('Backup digest mismatch')
    snapshot = inspect_database(backup)
    if snapshot != metadata['snapshot']:
        raise ValueError('Backup schema/checkpoint mismatch')
    with target.open('xb'):
        pass
    with closing(_read_only(backup)) as origin, closing(sqlite3.connect(target)) as destination:
        origin.backup(destination)
    if inspect_database(target) != snapshot:
        raise ValueError('Restored checkpoint mismatch')
    return dict(started_at=started, completed_at=utc_now(), snapshot=snapshot,
                registry_rotation_required=True)
