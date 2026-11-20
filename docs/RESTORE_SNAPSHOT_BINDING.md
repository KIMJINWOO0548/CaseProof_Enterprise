# Restore snapshot binding

Restore now reads the caller's backup file once into a private temporary input
file and verifies its SHA-256 before inspecting or copying it with SQLite. Both
inspection and recovery use that same private input. The caller's path is never
reopened by SQLite during restore. The output is switched to DELETE journal mode
before actor quarantine, then verified and published without replacing a target.
Input and output use separate owned temporary directories. Input uses the
standard temporary root to avoid extending a long caller path. Output uses a
short basename inside a sibling directory on the destination filesystem so
publication remains on that filesystem. Ordinary-failure sidecars are cleaned
with their owning temporary directory.

Contract: restore consumes the exact standalone backup artifact named by
`backup_sha256`, not a live SQLite database plus independently changing WAL.
Transactions appended to the caller's WAL after the approved backup was created
are not covered by that digest and are not restored. To include current committed
WAL state, first run `backup_database` to produce a new online backup and metadata.
This does not discard, checkpoint or modify the caller's live database/WAL.
Copy-time byte changes fail digest validation; later original changes or pathname
replacement cannot influence the private verified input.

Observed RED: changing original actor roles after inspection, or appending WAL
changes while preserving the main-file digest, changed the previous restore
result despite approved metadata. Both tests failed. The first private-snapshot
patch exposed leftover output WAL/shm files in the WAL test (85 PASS/1 FAIL in
operations). Switching output to DELETE journal mode and containing all staging
inside the private directory fixed that observed failure, not by relaxing tests.

Tests cover update and pathname-replacement races, WAL changes outside approved
bytes, partial copy failure, copied-byte corruption, complete actor quarantine,
no published target on failure, and ordinary cleanup. Existing restore collision
and source-preservation tests remain unchanged. Full regression and independent
review are pending.

Limits: privileged mutation of the private temporary workspace, physical
power-loss durability and POSIX host behavior are not certified. Forced process
termination can leave a private temporary directory; inspect only after verifying
its owner process has stopped. Metadata is not independently authenticated.
Actual PostgreSQL and independent business-answer correctness remain unverified.

Independent review found initial nested staging caused two existing #/% path
tests to fail under the long default Windows sandbox root. Separating input
and shortening output fixed all three existing special-path tests using their
unchanged default temporary root (3/3 PASS), not a shortened basetemp.

Independent re-review: default sandbox-root focused five plus special-path three
passed (8/8 in 9.33s); no short basetemp override. A real two-thread publication
race yielded one successful quarantined DELETE-mode output and one FileExistsError.
Tracked temporary directories confirmed both input default-temp and output
same-parent locations were deleted. Injected copy and publication PermissionError
both preserved source bytes and cleaned owned temporary directories. No scoped
blocker remains; privileged workspace mutation, ACL certification, POSIX and
physical power loss are outside this review. Final whole-suite rerun pending.

Final normal-execution full regression after path fix: 1050 passed, 458 skipped,
22 subtests passed, 3 warnings in 248.81s. Windows socketpair initialization-only
retries 49; no application request/assertion retries added. Actual PostgreSQL and
independent business gold remain unverified. Initial normal-execution full run
also passed but did not exercise the reviewer's long sandbox path; that result
does not replace the explicit default-path 8/8 re-review above.
