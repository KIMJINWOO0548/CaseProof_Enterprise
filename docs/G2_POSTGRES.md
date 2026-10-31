# Disposable PostgreSQL verification

`python -m pytest tests/postgres -q` uses real PostgreSQL only. Supply a private
`CASEPROOF_PG_ADMIN_URL`, or `.runtime/g1-g6/postgres/test-config.json` containing
`admin_url`. Neither credentials nor the private config belong in source control.
Missing configuration produces explicit skips, never an SQLite fallback.

The bootstrap creates random `caseproof_test_<hex>` databases and separate random
owner/runtime roles, then removes only resources created by that invocation.
It never resets the database named by the supplied administrator URL. Use a
dedicated disposable PG17 instance; `compose.postgres-test.yaml` provides one.

The frozen PostgreSQL migration is separate from the existing SQLite migration.
All tenant tables, including actors, use FORCE RLS with USING and WITH CHECK.
The runtime is a non-owner without superuser/BYPASSRLS/role or database creation,
schema CREATE, or immutable-record UPDATE/DELETE/TRUNCATE privileges. The owner
sets transaction-local context when seeding. Populated downgrade is refused.

Tests cover schema/FKs, empty downgrade/upgrade, role grants, all-table scoped
reads and denied cross-tenant UPDATE/DELETE, denied INSERT, deferred FK rejection,
registry authentication/current roles and disabled users, and physical connection
reuse following commit/rollback/exception. One hundred barrier-started trials use
two independent backend sessions through the actual command executor, asserting
one committed create effect plus coherent replay. A real lock-timeout test checks
rollback and reusable idempotency keys.

Tenant B seed UUIDs and actor IDs are distinct from tenant A, with canonical
payload hashes and nested source/policy references recomputed. All 86 composite
FKs are attacked as the runtime role using a real B-only parent identifier. Each
test asserts that no matching A parent exists and checks SQLSTATE 23503 plus the
exact violated constraint name; all tenant tables are populated for read checks.

Deadlock injection uses opposite transaction-local advisory lock order in two
real runtime sessions, with an eight-second SQL timeout. PostgreSQL chooses one
40P01 victim; its inserted row rolls back while the survivor commits. The captured
real DBAPI error is separately passed through the executor mapping and HTTP
response path, which must emit 503 and `Retry-After: 1`. This is a database-level
deadlock reproduction plus boundary mapping, not a deadlock between full HTTP
workflow requests.

Immutable related records and committed idempotency results are read after the
executor acquires the tenant head lock; they are not individually locked using
`FOR UPDATE`, which PostgreSQL requires UPDATE privileges to execute. The head
serializes runtime writes, the mutable change is separately locked, and runtime
credentials cannot update/delete historical records. No immutable UPDATE grant
is introduced to accommodate row locking.

On this Windows host libpq Kerberos/SSPI probing returned socket error 10014 for
new owner/runtime connections. Only disposable bootstrap URLs use
`gssencmode=disable`; database operations and assertions are never retried. This
is separate from `scripts.windows_checks`' initialization-only socketpair retry.

Execution results must be recorded separately after running on the target host.
This is synthetic demo verification, not production hardening or external review.
The application role can set another tenant's GUC; RLS does not contain a
compromised application credential. Real-model calls and external anchoring are
outside this gate.
