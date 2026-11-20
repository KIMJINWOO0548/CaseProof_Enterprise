# Recovery validation of unused snapshots

Local recovery previously walked only existing changes and their referenced
history. A corrupt source, policy, candidate, source bundle, dataset, suite,
evaluator or adapter snapshot with no change yet could pass inspection, be
backed up and be restored. SQLite physical and foreign-key checks stayed valid.

Inspection now also decodes every stored canonical payload using the same
repository verifier as normal reads. This verifies canonical bytes, stored
hash, schema tag, tenant, identity and indexed aliases. Existing history and
request-ledger checks run first and retain their error boundaries. No business
rules, fixture gold answers, permissions or UI were changed.

Eight snapshot kinds across inspect/backup/restore produced 24 expected RED
failures before the patch and 24 PASS afterward (19.67s). Damage is injected into
synthetic disposable fixtures while preserving physical and FK validity and
restoring original trigger definitions. Tests check that rejected input remains
byte-identical and that no final backup/restore target is published.

These are consistency checks, not authentication against an attacker who can
rewrite both data and hashes. They do not validate independent business truth,
actual PostgreSQL, external anchoring, or all semantic schemas. Whole-database
inspection remains an offline maintenance operation and reads each payload once
in addition to existing history walks. Full regression and independent review
are pending.

Full unchanged suite: 1045 passed, 458 skipped, 22 subtests passed, 3 warnings
in 300.85s. Windows socketpair initialization-only retries: 6. Normal approved
execution was used because prior sandbox taskkill authentication failures are
separately documented. Real PostgreSQL checks remain skipped. Structural package
and byte manifest checks passed for 438 files. Independent review is pending.

Independent review completed without a scoped blocker: new regression 24/24,
existing recovery/history/request-ledger group 39/39, and 32 additional isolated
mutations across eight snapshot types (hash, schema, tenant and identity) all
rejected with source bytes preserved. For identity/schema checks the review
recomputed hashes so the test reached the intended comparison rather than merely
failing on the digest. These extra 32 checks were reviewer experiments, not yet
permanent repository tests. The reviewer did not repeat the whole suite.

Separate remaining boundary: inspection and subsequent backup-copy acquisition
are not one locked snapshot. Concurrent modification between those operations
is not fixed by this patch and must not be claimed resolved. Backups intended
for restore should remain immutable/offline; production concurrency and external
authentication need their own design and validation.

Follow-up: the original-path inspection/copy race described above is now
addressed by private digest-bound input snapshots; see
[Restore snapshot binding](RESTORE_SNAPSHOT_BINDING.md) for the precise standalone
artifact/WAL contract and remaining private-workspace/power-loss limitations.
