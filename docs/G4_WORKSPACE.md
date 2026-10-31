# v1 correction workspace

`/v1` is a separate plain HTML/JavaScript workspace for `/api/v1`.
The baseline `index.html` and vendored Tabler 1.7.3 stylesheet remain unchanged.
The UI uses local Tabler tables, forms and buttons with native accessible dialogs;
no frontend dependency or external resource is added.

The current visual layer adds a locally bundled, unmodified OFL-1.1 SUIT font
and a current-stage rail, with separate evidence at wide widths. See
[visual design, primary references and browser checks](VISUAL_DESIGN.md).

The workspace authenticates with an entered bearer token, lists changes with
search/status filters, and uses registered synthetic presets including the third
fictional pack. Analysts create immutable changes, edit public case claim-day
inputs, evaluate the entire suite and submit. A rejected change opens a new
`CORRECTS_REJECTED` request. Neither evaluations nor approvals are copied.
Distinct domain and release reviewers record 8–500-character reasons. Server
authorization remains authoritative. Evidence is requested separately and displays
historical integrity, current eligibility and external anchor status separately.
Pack, candidate, source, suite and run-result hash references remain readable.

Bearer tokens never enter browser persistent storage. An uncertain mutation keeps
its original serialized body, path, key and revision under the authenticated tenant
and actor in memory. All server 5xx, network loss and unparseable responses retain
that request. Recovery explicitly retries the same request, with no automatic new
key. Another role cannot recover it; switching back to the original actor can.
A first known 4xx clears that failed request. After an uncertain outcome, a later 4xx retains the original key until its committed result is resolved. Both report the server code/request ID.
Mutations cannot overlap. Session and selection counters discard stale responses.
Failed reads/mutations clear prior detail/evidence instead of leaving a stale verdict.
Page reload clears pending recovery; durable cross-reload recovery is outside scope.

Server-controlled strings use `textContent`/text nodes. Native dialog Escape and
focus restoration, explicit form labels, keyboard-visible focus, live status,
loading/error/empty text and a 375px layout are implemented. This is a synthetic
local demo; external models, independent anchors and production approval are absent.

`node scripts/v1_ui_probe.js` runs API-independent checks of the actual request
client: exact replay, actor isolation, immutable original body, 503 recovery,
known-error cleanup and concurrent-mutation refusal. Its initial execution failed
because the client file did not exist; after implementation it passed (exit 0).
`node --check service/static/v1.js` also passed (exit 0).

`scripts/v1_ui_probe.js` exports `browserProbe(page, config)` for an existing
Playwright session. Config contains `baseURL`, runtime-only `tokens` with
`analyst`, `domain`, `release`, plus optional `presetIndex` (default 2) and
`passingDays` (default 24, the Lantern fixture value). The probe runs a third-pack rejection/correction/
approval path, drops a committed submit response, recovers it, checks inert XSS,
memory-only credentials, mobile width and native dialog Escape/focus.

`tests/browser/test_v1_workspace.py` runs the Node checks and an optional real
Python Playwright flow. Provide a running disposable demo through
`CASEPROOF_V1_BROWSER_URL`, an ignored credentials JSON file through
`CASEPROOF_V1_BROWSER_CREDENTIALS`, and optionally
`CASEPROOF_V1_BROWSER_PASSING_DAYS`. Missing optional tooling, browser or runtime
configuration produces an explicit pytest skip. Browser execution and server/DB
assertions must be recorded separately by the integration run; the Node checks
are not browser evidence. A five-participant user study and independent external
review remain unperformed.

The standalone synthetic server is `service.workspace.create_workspace_app`.
It requires `CASEPROOF_DEMO_MODE=1`, mounts the existing v1 router and serves
the separate workspace at `/` and `/v1`. Authenticated catalog/list reads
recheck current DB identity and tenant scope. The list is limited to 200 changes;
invalid history is shown as an integrity diagnostic rather than a valid approval.
There is no migration, seed or token creation at application startup.

For a fresh disposable profile, set `CASEPROOF_DEMO_MODE=1` and run
`python -m scripts.v1_demo --prepare-only`. It runs the frozen Alembic migration
against a unique `.runtime/v1-demo-<uuid>/workspace.db`, explicitly seeds three
fictional policy fixtures and four separate actors, and writes runtime tokens
and a hashed authentication registry to its private `profile.json`. Only the
profile path and local URL are printed. Start/restart with
`python -m scripts.v1_demo --profile <profile.json>`; this preserves the existing
DB. Default binding is `127.0.0.1:8766`, one worker. Windows socket initialization
may require `python -m scripts.windows_checks scripts.v1_demo ...`.

`python -m scripts.windows_checks pytest tests/v1/test_workspace.py -q` passed
2 tests after an initial missing-module failure. The tests use actual Alembic
SQLite migration and HTTP routes: all three presets resolve and evaluate PASS;
Lantern reaches three-person approval and VALID evidence; catalog/list enforce
missing/invalid/revoked tokens and tenant isolation. This run needed 0 socketpair
initialization retries and retained the existing Starlette deprecation warning.
Actual CLI `--prepare-only` also returned exit 0 without printing credentials.
