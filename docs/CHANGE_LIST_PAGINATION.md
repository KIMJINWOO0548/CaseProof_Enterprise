# Change listing continuation

The workspace listing formerly returned only the first 200 UUID-sorted changes,
without a continuation marker. The existing `data` array is preserved. Responses
now also contain `pagination: {limit, next_cursor}`. The default limit remains
200; clients may request 1 through 200. Follow `?after=<next_cursor>&limit=<n>`
until next_cursor is null. At most limit+1 projections are selected per request;
only the returned page undergoes full history reconstruction.

`after` is a canonical UUIDv4 position, not a credential, signed cursor, row
existence assertion, or stable export snapshot. Every request reauthenticates the
current actor and applies tenant filtering independently of that position. A
foreign or absent UUID cannot expand visibility. Cursor deletion does not require
looking up a missing row. Duplicate, unknown, malformed and out-of-range query
parameters are rejected. The workspace catalog endpoint still rejects queries.

This is live keyset traversal. Inserts at or before an already-consumed position
need a fresh traversal; later inserts may appear. It does not promise snapshot
isolation across HTTP requests or an immutable export. There is no user-facing
delete operation, and this patch adds none. Existing immutable/history guards
are preserved.

The initial two feature tests failed before implementation (ten invalid-query
cases already passed). Existing workspace plus initial pagination tests passed
15/15 after implementation. Additional actual 201-change traversal and concurrent
insertion/absent-position tests, full regression and independent review are
recorded below when complete.

UI layout and UI pagination controls are not changed. The current UI still
requests the first default page; UI continuation remains a separate integration
step under the existing design gate. This patch exposes the server capability
without claiming that screen is now a complete large-data workflow. No actual
PostgreSQL or independent business-answer validation is claimed.

Focused expanded tests: 14/14 passed in 45.77s, including 201 actual persisted
changes traversed as 200+1, insertion between page requests and absent-position
continuation. Independent review ran pagination plus existing workspace tests:
17/17 PASS in 53.59s, initialization retries 0. Nine separate boundary experiments
passed (encoded duplicate keys, whitespace/newline, uppercase/non-v4 UUID,
plus/exponent/empty limits, empty/exact page, min/max cursor, no authentication).
No scoped blocker found. Full regression is pending. Only the API continuation
is completed; the existing UI first-page-only behavior remains explicitly open.

Full normal-execution regression: 1064 passed, 458 skipped, 22 subtests passed,
3 warnings in 342.84s. Windows initialization-only socketpair retries: 2. No
request assertions were weakened or retried. Actual PostgreSQL and independent
business truth remain unverified. Package/manifest checks cover 442 files.

## Independent continuation failure boundaries (2026-11-16)

Three additional migrated-SQLite tests cover a damaged history record on the
middle page, isolation from another tenant's damaged history, and removal of an
actor's roles between page requests. A damaged row is explicitly marked
INTEGRITY_INVALID rather than silently omitted; its position remains usable to
reach later rows. Revocation returns 403 with no-store and no data payload.
These are additional regression checks of existing behavior, not new product
functionality. No UI continuation controls or layout were changed.

Author focused run: 17/17 passed in 45.82s, initialization-only socketpair retries
0. The previous workspace plus pagination baseline separately passed 17/17 in
26.47s. Full regression and independent review results follow when available.

Independent direct pytest (without the socketpair wrapper) passed all 17 paging
tests in 69.76s; no scoped blocker was identified. The initial complete sandbox
run returned 1066 passed, 1 failed, 458 skipped and 22 subtests passed in 347.95s.
The failing real launcher test reproduced a nonzero taskkill exit during server
cleanup. With native execution permission the same unchanged launcher test passed
1/1 in 3.32s. This is not evidence that the initial full run passed; the native
full rerun is recorded separately. No test assertion or product code was relaxed.

Final native-permission full regression: 1067 passed, 458 skipped, 22 subtests
passed and 3 warnings in 247.64s. Initialization-only socketpair retries: 12;
application requests and assertions were not retried by that wrapper. Optional
real PostgreSQL and other unavailable checks remain skipped, not passed.
Package structure and byte manifest checks cover 442 files. Main and UI are
unchanged; the first-page-only UI limitation remains open.

## CP1 integration design

The existing work queue can keep its layout, filters and selection. Read the
list response envelope and render a single **더 불러오기** button below the
current table when `pagination.next_cursor` exists. Append the returned rows
once, deduplicate by change ID, and update the cursor after a successful
authorized response. Disable the button while a page is in flight. Keep the
cursor on a retryable failure and clear the list and cursor on role changes or
authorization failure. A full refresh starts at the first page. Use the current
session counter and a list request counter so stale responses cannot append to a
new session or refreshed list.

Describe title/status filters as applying to loaded rows. A zero-match page
must still offer continuation when a cursor remains. Verify the 201st change
through a real browser after selection, filtering, refresh, and authorization
changes. Ordering follows the live keyset API. This design is recorded for
CP1 and the workspace still loads the first default page.
