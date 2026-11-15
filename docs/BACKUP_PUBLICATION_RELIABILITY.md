# Verified-only backup publication

The G6 local recovery boundary now stages SQLite online backups next to their
requested destination. Integrity/schema/evidence checks and the SHA-256 digest
complete before the destination name is published. Existing destinations and a
concurrent publisher are never overwritten. No changes to restore, approval
policy, UI, main, or production databases are included.

An ordinary copy, validation, or publication failure removes only this call's
staging file. If publication succeeded but a later error obscured the outcome,
the final backup is preserved. Inspect it before choosing another destination;
do not treat an exception as proof that no backup exists. A retry to the same
existing path fails closed. Metadata is still returned to the caller, not
atomically stored alongside the database.

Tests initially reproduced three failures: missing source left an empty target,
invalid source left a rejected target and prevented retry, and final filename
was visible before validation. The five focused tests now pass, including
publication failure before/after success and concurrent winner preservation.
The earlier operations run passed 56 tests (before two added publication cases),
with zero Windows socketpair initialization retries.

Limits: Windows local filesystem tested. The POSIX no-replace hard-link branch
is not tested on a POSIX host here. This does not claim fsync/power-loss durability,
network filesystem atomicity, protection from privileged local file mutation,
external anchoring, actual PostgreSQL validation, or independent business gold.
Full regression and independent review results are recorded separately.

Independent review: focused 5/5 passed; two real concurrent publishers produced
one valid winner and FileExistsError for the loser with source bytes preserved.
A forced subprocess exit after copy/before validation left no final backup and
preserved source bytes, but left one hidden staging file. After confirming no
backup process still owns it, an operator may inspect and remove such orphan
staging files. Automatic cleanup does not run on process kill or power loss.

Full regression: 1020 passed, 458 skipped, 22 subtests passed, 3 warnings,
1 failed in 314.28s; initialization retries 0. The failure was
`tests/v1/test_demo_startup.py::test_real_demo_cli_starts_and_preserves_existing_database`
in its finally taskkill cleanup (nonzero taskkill exit), not a backup assertion.
This full run is NOT a full-suite PASS. Real PostgreSQL skipped without its
runtime environment. Independent business-answer validation remains unrun.
Package structural check: 436 files; JavaScript syntax check passed.

Cleanup diagnosis: a fresh harmless sleep child under the sandbox reproduced
`taskkill` exit 1 with "user name or password incorrect" while the child remained
alive. The child was then terminated through its Popen handle and waited for.
The unchanged CLI test file under normal approved execution passed 5/5 in 2.79s
with zero initialization retries. No test assertion or application code was
changed to hide the cleanup failure. A full normal-execution rerun is pending.

Full normal-execution rerun completed: 1021 passed, 458 skipped, 22 subtests
passed, 3 warnings in 218.09s. Windows initialization-only workaround retried
socketpair construction 137 times; application requests/assertions were not
retried. The initial sandbox failure remains recorded above. No PostgreSQL or
independent business dataset validation was performed in this run.
