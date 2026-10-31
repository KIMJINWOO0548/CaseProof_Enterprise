# G1.2 isolated v1 persistence

`service/models_v1.py` defines `BaseV1` with independent metadata and `v1_`
tables. It is not imported by the baseline application and does not register
`/api/v1`, open a database, seed data, or run migrations on startup. The baseline
models, database, digest and historical evidence remain their existing contract.

## Migration boundary

Use an explicitly disposable SQLite file, from the repository root:

```powershell
$env:CASEPROOF_V1_DATABASE_URL = 'sqlite:///absolute/path/to/new-disposable.db'
$env:CASEPROOF_V1_MIGRATION_MODE = 'disposable'
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
```

The URL has no baseline-variable fallback. Offline SQL and non-SQLite engines
are refused pending G2. The environment inspects the existing schema before
Alembic creates its own `caseproof_v1_alembic_version` table. Existing baseline,
foreign, unversioned, or view-bearing schemas are refused. This is not an import
API. Baseline facts remain **legacy-unverified** for the future v1 protocol;
no approvers, DOMAIN events, snapshots, or approvals are inferred. A future
read-only import needs an explicit requirement and original-byte provenance.

The frozen `0001_v1` revision contains explicit historical `op.create_table`
DDL and SQLite triggers, with an explicit SQLite BEGIN for DDL rollback; it never calls live `metadata.create_all`. Downgrade
checks every v1 table for records before dropping anything and refuses even a
single row. Empty disposable upgrade/downgrade/upgrade is supported; production
rollback, backup restoration, and production databases are outside this work.

## Storage and caller responsibilities

Immutable payload-bearing records store `schema_version`, `canonical_payload`
(binary canonical JSON), and `payload_sha256`. The complete contract payload,
including nested objects and arrays, is stored in those bytes; relational
columns expose the keys needed for joins, FK/UNIQUE/CHECK constraints. Callers
must use `service.domain.canonical` and the G1.1 DTOs before insertion. No
constructor supplies hashes, approval defaults, identities or timestamps.
Database hash-shape checks are not a canonicalization or history verifier.

Snapshot tables cover source bytes/metadata, policy, candidate, source bundle,
dataset, suite, evaluator, adapter, model, prompt and source eligibility. Original
source blobs and their `blob_sha256` are represented in the snapshot payload;
large file storage and actual source eligibility checks remain later work.
Source bundle membership, run source references, and assessment run/decision/
transition-event references have explicit relation tables with tenant-composite
FKs. G1.3 must compare those relation rows to canonical payload references,
including completeness/order/hash agreement; their mere existence is not proof.
Assessment and envelope have tenant-scoped hash uniqueness for hash references;
other immutable payloads may share a digest. There is no global digest identity.

All actor and object references use tenant-composite FKs. Revision references
use the full `(tenant_id, change_id, revision)` key. SQLite connections used by
writers must enable and verify `PRAGMA foreign_keys=ON` before a transaction;
the migration connection does so explicitly. Referenced tenant rows precede
child rows, while cyclic workflow FKs are `DEFERRABLE INITIALLY DEFERRED` and
checked at commit. Tests insert workflow children before their parents and
verify the final database with `foreign_key_check`.

`Change` has **no latest-revision FK**, the fixed contract choice. Create inserts
a skeleton with revision 0/status `INCOMPLETE`, then revision/transition/event
and side records, updates the projection, and commits once in the future G1.3
executor. Revision 0 cannot carry an approval status. The database cannot prevent
a caller from committing an incomplete skeleton: the executor must reject this
and reconstruct all history before any mutation. G1.2 tests transaction rollback,
not a yet-unimplemented executor. No DB-only projection-integrity claim is made.

The active run and its recorded revision have deferred FKs. Jobs have no table
until G5: `active_job_id` remains only a payload field and must stay null in G1.
Pack/product/workflow/rule identifiers remain registry labels in payloads, not
invented records. Payload references and hashes must be resolved and compared
by the future history verifier. Arrays cannot be trusted merely because JSON
can be decoded. Assessment checkpoint/event order, actor separation, state
transitions, full-suite gates and approval evidence remain G1.3/G1.5/G1.6 work.

SQLite triggers reject direct SQL UPDATE/DELETE on immutable tables, including
relation rows, and DELETE on Change. BEFORE INSERT guards reject all primary/unique-key collisions, including INSERT OR REPLACE when recursive triggers are disabled. Tenant/actor administration, audit head,
and Change projection remain mutable. An SQLite file owner can disable foreign
keys, drop triggers, or rewrite the database: this is not owner-resistant
integrity or external anchoring. G2 must provide real PostgreSQL application
privileges, RLS and concurrency checks with a non-owner role; SQLite tests do
not establish them.

## Verification scope

`tests/v1/test_schema.py` uses disposable files, real Alembic migration,
FK-enabled connections, every tenant-composite reference, required uniqueness,
integer bounds, rollback, SQL immutability, baseline byte preservation and
all-table downgrade refusal. Payload storage tests deliberately use marked
relational fixtures, not fabricated valid approvals/history. Alembic `check`
and empty upgrade/downgrade/upgrade compare frozen DDL against current metadata.
On this Windows host the project `scripts.windows_checks` wrapper is used; it
retries only socketpair initialization, not requests or assertions. Full-suite,
packaging and release evidence are coordinated separately by the parent task.
