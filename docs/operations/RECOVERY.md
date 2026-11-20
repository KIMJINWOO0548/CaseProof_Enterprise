# Local synthetic recovery

Run `.venv/Scripts/python.exe -m scripts.recovery_drill` from the repository root.
It creates a unique disposable SQLite v1 profile, loopback port and owned server
process. It never resets a configured DB or contacts an external provider.
Evidence is written under a fresh `reports/runs/*-recovery-*/` directory.
The JSON records UTC start/end times, environment, source hashes, actual HTTP
outage/restart readiness, token containment, tamper rejection and backup restore.
`server.log` records the owned process, without bearer tokens.

`service.recovery.backup_database(source, new_backup)` uses SQLite's online
Connection.backup API, including committed WAL data. It requires a new file and
checks integrity, foreign keys, v1 table columns, application evidence, tenant
heads and approval envelope hashes. Returned metadata includes SHA-256 of the
actual backup file, schema digest and row counts. Store metadata separately.
It is local consistency evidence, not independent proof of authorship or safety.
Failed validation may leave a new partial/quarantined file; it never replaces or
deletes an existing target. Investigate before choosing another new filename.

`restore_database(backup, new_target, metadata)` rejects existing targets and
checks file digest and the recorded verified snapshot before copying. It checks
the resulting snapshot again. Keep the original and restored files separate.
Stop writers and use a separately verified frozen backup during recovery.
These functions are local owner-operated tools, not HTTP endpoints.

Before exposing any restored service, rotate the entire demo token registry,
reapply current Actor disablement/revocation from a trusted record and verify
the tenant checkpoint against an independent anchor when one becomes available.
An old backup can undo Actor revocation. The drill does not expose its restored
database to HTTP. Production authentication, key rotation and external anchor
verification remain separate gates.

Separate the database owner (restore and Actor administration), runtime identity
(normal application requests), and independent key custodian (future signing and
retention control). SQLite demo process identity is not production role isolation.
Do not put private profiles, tokens, real customer data or credentials in reports.

RTO is the measured local interval from stopping the owned process through a
successful authenticated HTTP readiness GET, and separately the local restore
operation interval. Readiness polls retry connection failures only; mutations
are sent once. RPO is observed committed tenant-transition loss after backup,
with the actual backup/checkpoint and post-backup commit timestamps recorded.
These synthetic workstation measurements are not production RTO/RPO guarantees.

External signing/WORM, wholesale DB rewrite detection against independent state,
consented human review and independent installation are SKIPPED with bonus 0.

## Success-request ledger consistency

The 2026-11-09 independent increment starts from the accessible remote
`improve/competitive-depth-20261106` commit
`19112383f7387e340a3906d6277e746fc6d41e6d`, on the separate
`improve/recovery-ledger-integrity-20261109` branch. Inaccessible preservation
archives were not read, restored, replaced or integrated by this work.

Inspection also verifies every committed v1 request record using the existing
canonical decoder and replay binding checks. Each verified change revision must
have exactly one request record. The stored actor, method, route, resource,
success status, completion and timestamps must match that historical transition.
The saved response is compared as canonical bytes with its historical snapshot,
including the original run only for an evaluation response. Current projections
do not replace earlier responses during this check.

Damaged payloads, inconsistent fingerprint/status columns, missing records,
duplicates and a missing record compensated by a duplicate of another revision
are rejected. Restore performs this inspection before reserving its new target.
Source files and stored request records are not rewritten. The normal HTTP
authorization and historical replay contract are unchanged.

This checks the stored fingerprint against its indexed value, not an independently
preserved original request body. It does not detect a coordinated owner rewrite
of the entire database and metadata without an external trusted anchor. Token
registry rotation and current revocation review above remain required.

## Restore authorization contract v2 (2026-11-16)

Successful restores now disable **all** restored actors. An old backup cannot
prove that an identity or role is still authorized. The returned report states
`authorization_state=QUARANTINED` and `current_authorization_review_required=true`.
Canonical history, decisions, approval envelopes and original role assignments
remain intact. Only current actor enablement is changed, never the source/backup.
Before exposing the new file, an owner must independently review current
revocations and roles, rotate the token registry, and explicitly enable only
currently authorized identities. There is no automatic enable-all API or bypass.
Restore uses a private sibling staging file, disables actors and verifies it
before atomic no-overwrite publication. Errors before publication leave no new
target; concurrently created targets are preserved. Never serve staging files.
Owner/process interruption cleanup still requires inspecting abandoned staging.
The local owner can edit SQLite; this is not protection from a malicious owner.

Independent Windows review additionally exercised concurrent restores (one
quarantined winner, one FileExistsError), injected publication PermissionError
(no target, staging removed, backup bytes unchanged), and 32 related tests.
POSIX publication has not been runtime-tested in this Windows run. Forced
process termination was not injected; it can leave an orphan staging database.
Staging files are never service inputs and must not be manually published.

## Offline reviewed reactivation

Keep the service stopped. Independently reconcile current identity disablements
and exact roles from the authoritative record, not the old backup. Prepare a
fresh token-hash registry for only the reviewed identities; keep raw tokens out
of source, logs and evidence. Record the quarantined file SHA-256 and review ID.
The owner-only `reactivate_reviewed_actors(path, expected_sha256, grants,
old_registry, new_registry, review_reference)` rejects stale bytes, reused
credential hashes, unknown actors, invalid roles, duplicate grants, nonquarantined
files, and registry identities outside the exact allowlist. It replaces roles
rather than reviving old roles, and leaves all unlisted identities disabled.
Changes occur in one SQLite transaction with a writer lock. WAL/service-online
operation is rejected. Preserve the returned review receipt in private operations
records. Deploy ONLY the new registry before restarting and verify old-token
401, excluded-identity denial and the reviewed least-privilege role.

This is a local owner-operated procedure, not an HTTP endpoint or identity
provider. It does not certify the review, discover omitted historical credentials,
or atomically deploy a registry into another process. A dishonest review source,
owner bypass, or serving the DB with the old registry remains outside its trust
boundary. Do not invoke it against a running service or production data.
