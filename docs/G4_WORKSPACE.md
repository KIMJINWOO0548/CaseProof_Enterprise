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
historical integrity, current source eligibility and external anchor status separately.
The legacy JSON field `current_approval_eligibility` describes source eligibility
only. The UI labels it `현재 출처 적격성`: an ELIGIBLE source verdict does not
authorize approval or replace the evaluation gate, workflow state or role separation.
For example, a complete failed evaluation can retain eligible sources while submission
returns `RELEASE_GATE_BLOCKED`. The JSON field name and domain predicate are preserved.
Pack, candidate, source, suite and run-result hash references remain readable.

Bearer tokens never enter browser persistent storage. An uncertain mutation keeps
its original serialized body, path, key and revision under the authenticated tenant
and actor in memory. All server 5xx, network loss and unparseable responses retain
that request. Recovery explicitly retries the same request, with no automatic new
key. Another role cannot recover it; switching back to the original actor can.
A first known 4xx clears that failed request. After an uncertain outcome, a later 4xx retains the original key until its committed result is resolved. Both report the server code/request ID.
Mutations cannot overlap. Session and selection counters discard stale responses.
Failed reads and unauthorized or unhandled mutation failures clear prior detail/evidence instead of leaving a stale verdict.
Page reload clears pending recovery; durable cross-reload recovery is outside scope.

Normal submission is enabled only for the existing owned DRAFT/ANALYST UI path
with a latest COMPLETE/PASS run. Missing, blocked or incomplete runs have visible
evaluation guidance beside the disabled button. This is an affordance; current
source, workflow, role and gate checks remain authoritative on the server.

A first known 409 with `RELEASE_GATE_BLOCKED`, `EVALUATION_INCOMPLETE`,
`SOURCE_NOT_ELIGIBLE` or `STALE_REVISION` triggers one fresh authorized current
read for the still-selected change. Only a valid response restores same-suite
typed inputs and updates that selected queue row's summary. Other rows and filters
are preserved. The original error/request ID stays visible and the UI never
automatically resubmits the rejected mutation. A 401/403/404 or invalid current
history clears the old detail and does not restore typed data. Pending uncertain
requests do not take this known-conflict path: their original serialized request
remains available through the separate recovery control even while normal
submission is disabled.

Server-controlled strings use `textContent`/text nodes. Native dialog Escape and
focus restoration, explicit form labels, keyboard-visible focus, live status,
loading/error/empty text and a 375px layout are implemented. This is a synthetic
local demo; external models, independent anchors and production approval are absent.

`node scripts/v1_ui_probe.js` runs API-independent checks of the actual request
client: exact replay, actor isolation, immutable original body, 503 recovery,
known-error cleanup and concurrent-mutation refusal. Its initial execution failed
because the client file did not exist; after implementation it passed (exit 0).
`node --check service/static/v1.js` also passed (exit 0).

`node scripts/check_evidence_labels.cjs` exercises the actual evidence click handler
with synthetic responses in a small DOM harness. It checks that a BLOCK evaluation
and source-only ELIGIBLE remain distinct, the displayed label is precise, the visible
qualifier explains the other approval conditions, and raw evidence JSON is preserved.
This is not a browser layout or accessibility observation.

`node scripts/check_submit_flow.cjs` checks the actual handlers with a small DOM
and transport harness: four readiness states, four known 409 conflicts, mutation
and recovery-read 401/403/404 clearing, and exact uncertain evaluation replay.
Its 15 scenarios also check current queue revision, correction input, selected
state and original error visibility. The separate regular Playwright run records
actual HTTP, desktop/mobile screenshots and deliberate response-loss recovery;
that rendered evidence is not inferred from the harness.

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
