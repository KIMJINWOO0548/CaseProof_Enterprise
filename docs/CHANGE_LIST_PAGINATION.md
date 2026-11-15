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
