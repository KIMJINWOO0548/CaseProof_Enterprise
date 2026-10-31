"""Local SQLite v1 recovery, without replacement of existing files or remote anchors."""
from contextlib import closing
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sqlite3

from sqlalchemy import select

from service import models_v1 as m
from service.db import make_engine, session_factory
from service.domain.canonical import content_hash
from service.domain.evidence import verify_evidence
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
                    evidence = verify_evidence(load_history(db, change.tenant_id, change.id))
                except Exception as error:
                    raise ValueError('Application evidence integrity check failed') from error
                if evidence['historical_integrity'] != 'VALID':
                    raise ValueError('Application evidence integrity check failed')
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
