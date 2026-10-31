# CaseProof v1 Implementation Plan — v5.3 handoff

> For agentic workers: implement one reviewable task at a time. Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` when available; otherwise the same test-first procedure works without installed skills. Checkboxes below track **v1 acceptance work**, separately from the hardened `/api` baseline. Checked items have recorded execution evidence; unchecked items can contain implemented portions whose full acceptance matrix is not yet evidenced.

**Verification checkpoint (2026-11-01 KST):** implementation commit `e9b67ac`; [local evidence](../docs/VALIDATION.md), [PG17 CI job](https://github.com/KIMJINWOO0548/CaseProof_Enterprise/actions/runs/41214934555). Final UI revision and complete release CI are tracked separately. An implemented feature does not close a broader unexecuted acceptance matrix.

**Goal:** 합성 답변 변경의 평가·사람 승인·증거를 일관되게 연결하고, 공개 저장소에서 재현할 수 있는 v1을 만든다.

**Architecture:** FastAPI/SQLAlchemy 모듈형 단일 서비스. 불변 snapshot/transition/note/run과 조회 projection을 한 transaction에 쓰며, 외부 모델·외부 anchor는 별도 gate 뒤 연결한다.

**Tech stack:** Python 3.11–3.13, Pydantic2, SQLAlchemy2, FastAPI, SQLite local; G2 PostgreSQL/Alembic, G4 Playwright. 실행 버전·hash는 lock으로 고정하고 변경 시 전체 검증한다.

**Spec:** [01 설계](01_TARGET_DESIGN.md), [08 정확한 계약](08_IMPLEMENTATION_CONTRACTS.md), [03 실험](03_INSURANCE_AND_EXPERIMENT.md), [04 인수](04_ACCEPTANCE_AND_EVIDENCE.md).

## Global constraints

- 저장소 루트의 `service/`가 코드다. `current/`를 다시 만들지 않는다.
- `/api` baseline과 `/api/v1` target은 분리한다. 기존 테스트·합성 정답을 삭제/수정하여 성공시키지 않는다.
- 모든 v1 mutation: `(tenant_id,actor_id,key)` UNIQUE, create 외 expected revision header, `extra=forbid`.
- `caseproof.c14n.v1`, `H(purpose,payload)`와 전이 필드는 08 계약 그대로 사용한다.
- synthetic only; real-model capability는 G5 job 경계가 통과하기 전 false.
- 성공 결과/전이/행/head/idempotency는 원자적이다. 외부 network I/O와 DB transaction을 겹치지 않는다.
- 각 task는 실패 테스트 → 실패 확인 → 구현 → 해당 시험+전체 회귀 → 증거와 focused commit 순서다.
- 외부 인프라·검수자 미확보는 SKIPPED; fake evidence 또는 빈 테스트 collection로 gate를 통과시키지 않는다.

## Review focus

1. 같은 사람이 여러 역할로 자기 승인한다 → G1.3 `test_multirole_self_approval_denied`.
2. 응답 유실·권한 회수·서로 다른 대상에서 key가 재사용된다 → G1.4 `test_replay_*`.
3. 최신 incomplete를 과거 PASS로 대체하거나 옛 실패를 삭제한다 → G1.5 `test_latest_run_veto`.
4. 승인 뒤 다른 change/event/source 버전 때문에 hash가 바뀐다 → G1.6 `test_unrelated_updates_preserve_seal`.
5. RLS 인증 bootstrap·rollback·pool 재사용 또는 model input에서 tenant/gold가 새어 나온다 → G2.2, G5.1.

## 파일·인터페이스 지도

| 모듈 | 인터페이스 / 책임 |
| --- | --- |
| `service/domain/canonical.py` | `canonical_bytes(value: object) -> bytes`, `content_hash(purpose: str, value: object) -> str` |
| `service/domain/types.py` | frozen `ActorContext(tenant_id, actor_id, roles)`, `CommandContext(method, route_template, resource_id, key, expected_revision, body)`, `CommandResult(status_code, data, result_revision, replayed)` |
| `service/domain/state_machine.py` | `apply_transition(snapshot: dict|None, command: dict, actor: ActorContext) -> dict`; no DB/clock/network |
| `service/domain/gates.py` | `check_run_gate(run: dict, suite: dict, source_eligibility: dict) -> dict` |
| `service/domain/evidence.py` | `build_assessment(history: dict, preapproval_revision: int) -> dict`; `verify_evidence(material: dict) -> dict` |
| `service/commands.py` | `execute_command(session_factory, actor: ActorContext, command: CommandContext) -> CommandResult`; one unit of work |
| `service/auth.py` | `authenticate(token: str, registry, db) -> ActorContext` with G2 bootstrap boundary |
| `service/evaluation/runner.py` | `run_suite(case_inputs: list[dict], suite: dict, snapshots: dict, adapter) -> dict` |
| `service/evaluation/adapters.py` | `FakeDeterministicAdapter.evaluate(case_input: dict, context: dict) -> dict` with no gold input |
| `service/api/v1.py` | `build_router(session_factory, authenticator) -> APIRouter` |
| `service/models_v1.py`, `migrations/` | exact target records and revisioned DDL |

`dict` payloads above are the typed schemas in `contracts/`, not arbitrary dictionaries accepted from HTTP. Define Pydantic/domain types from those schemas in G1.1. Helper functions do not commit; only execute_command owns the commit. Avoid introducing another competing transaction helper.

## G0 — fresh baseline / artifact checks

**Files:** existing `requirements*.lock`, `scripts/check_package.py`, `tests/`, `docs/STATUS.md`.

- [x] Run `python VERIFY_PACKAGE.py` before changing the package; record source SHA. Once edited, the original manifest is expected to differ.
- [x] Create a fresh venv; install `python -m pip install --require-hashes -r requirements-dev.lock`; run `python -m pip check`.
- [x] Run `python -m pytest -q`, `python -m scripts.smoke`, `python -m scripts.check_ui_syntax`, `python -m scripts.check_package` and save actual exit codes.
- [x] Read `docs/VALIDATION.md` for earlier observations, but do not reuse them as this run's result. Record platform/DB/role/worker and source hashes.

**Done:** baseline reproduces; failures are investigated before v1 work. Original approved-row bypass regression remains green.

## G1.1 — strict DTOs, canonical bytes, pure state machine

**Create:** `service/domain/{types,canonical,state_machine}.py`, `service/api/{schemas_v1,errors}.py`; `tests/v1/test_contracts.py`, `tests/v1/test_state_machine.py`.
**Consumes:** `contracts/` and 08 §§1–4,8–10. **Produces:** shared types/functions in the map.

- [x] Write `test_canonical_vectors` using stored canonical UTF-8 hex/hash literals; reject float, int outside ±9007199254740991, duplicate raw JSON keys, lone surrogate, malformed UTF-8.
- [x] Write `test_revision_and_actor_rules`: genesis=1; allowed commands increment once; all illegal state/kind combinations, missing note, requester=reviewer and reviewer=approver reject.
- [x] Run `python -m pytest tests/v1/test_contracts.py tests/v1/test_state_machine.py -q`; confirm genuine failures before implementation.
- [x] Implement typed normalization and the pure state table. Inject ID/time through command input; state machine does not call uuid/clock itself. Validate field combinations and preserve null vs empty arrays.
- [x] Run targeted tests then entire suite. Commit `feat: define versioned command and evidence contracts`.

**Done:** target data shapes/golden vectors are deterministic; `/api` behavior unchanged. Test vectors are not proof the future HTTP route enforces raw JSON policy—test that again in G1.4.

## G1.2 — immutable schema and fresh-DB migration

**Create:** `service/models_v1.py`, `migrations/env.py`, `migrations/versions/0001_v1.py`, `tests/v1/test_schema.py`.
**Consumes:** G1.1 types. **Produces:** tables in 08 §5.

- [x] Test `(tenant,change,revision_to)` and `(tenant,change,stage)` uniqueness, revision bounds, tenant composite FKs and no partial genesis records after rollback.
- [x] Test baseline DB import stays legacy-unverified; no fabricated DOMAIN events or automatic approval. No import API is provided; baseline migration is refused without changing its bytes.
- [x] Implement Alembic on disposable DBs. Choose **no latest_revision FK** as fixed in 08; keep child FKs. Per-command projection verification remains G1.3, not a G1.2 DB-only guarantee.
- [x] Run `python -m pytest tests/v1/test_schema.py -q`, blank-DB `alembic upgrade head`, `downgrade base`, `upgrade head`, and whole suite.
- [x] Commit `feat: add immutable change record schema` with actual migration logs (`fdac40d`).

**Done:** empty SQLite migration and integrity tests pass; PG behavior still unverified until G2. Production data rollback is not tested by dropping an empty test schema.

## G1.3 — atomic transition executor

**Create:** `service/commands.py`, `service/repositories.py`, `tests/v1/test_transactions.py`, `tests/v1/test_integrity.py`.
**Consumes:** G1.1+G1.2. **Produces:** `execute_command(...)`, `load_history(db,tenant_id,change_id)->dict`.

- [x] Add status-only P0 reproduction to v1; expected 409 and zero new release note/transition/audit.
- [ ] Test mutation of each status/revision/actor/hash, deletion/duplication/reordering of every record type and cross-tenant child FK. Honest three-person path remains possible.
- [x] Parameterize exception injection after projection/note/snapshot/transition/audit/head stages; assert **all** persisted state equals pre-request state, not merely response 500.
- [x] Implement deterministic reconstruction, common lock order, CAS, rollback and structured errors. Validate reject paths too. App roles cannot UPDATE/DELETE immutable tables (enforce in PG G2).
- [x] Run `python -m pytest tests/v1/test_transactions.py tests/v1/test_integrity.py -q` plus whole suite; recorded implementation commit `e9b67ac`.

**Done:** every mutation uses one executor; malformed data fails closed without uncaught parsing exceptions. Full DB owner rewrite is explicitly out of threat coverage.

**Evidence boundary:** projection/status P0 and all-stage rollback tests passed. `test_record_links.py` additionally checks nested references and assessment relations. The broader every-record deletion/duplication/reorder matrix above is not yet independently enumerated. Implementation and tests were committed in `e9b67ac`, rather than using the originally suggested commit title.

## G1.4 — idempotency and actual v1 HTTP boundaries

**Create:** `service/api/v1.py`, `service/idempotency_v1.py`, `tests/v1/test_http.py`, `tests/v1/test_idempotency.py`.
**Runtime boundary:** `service/workspace.py` registers the standalone target router with explicit configuration; baseline `service/app.py` route behavior is preserved.
**Consumes:** executor/types/auth. **Produces:** endpoint table in 08 §8 and actor-scoped result lookup.

- [ ] Test same key+same semantic request returns same object/status/result_revision; only replayed changes. Test same actor key across route/resource/body/revision gives 409.
- [x] Simulate successful commit followed by lost response, advance change state and retry original key: original result is replayed before stale checking. Revoked/disabled actor receives no replay.
- [ ] Test raw JSON duplicate key, bool/float/string claim_days, missing/whitespace reason, extra tenant/actor/revision body fields; invalid revision header/leading zeros/key; cross-tenant IDs are 404.
- [x] Implement normalized fingerprint and success-record transaction. Failure responses do not reserve keys; 503 outcome unknown tells client to query/retry same key. `POST create` rejects revision header.
- [x] Run `python -m pytest tests/v1/test_http.py tests/v1/test_idempotency.py -q`; export actual v1 OpenAPI and compare DTO/header/errors to contracts; run whole suite and commit.

**Done:** HTTP enforcement is proven independently of JSON Schema limitations. Actual multi-session PG duplicate/race tests belong to G2.

**Evidence boundary:** actual create replay/lookup, current revocation, body conflicts, strict raw JSON/claim days and headers passed. Explicit same-actor cross-route/resource/revision conflict cases and missing/whitespace decision-reason cases through HTTP are not yet a complete recorded matrix; domain DTO coverage is separate.

## G1.5 — immutable full-suite runs and current-run gate

**Create:** `service/evaluation/{adapters,runner}.py`, `service/domain/gates.py`, `tests/v1/test_runs.py`, `tests/v1/test_gate.py`.
**Consumes:** immutable snapshot refs and `EvaluationRun` model. **Produces:** full run and one EVALUATION_RECORDED transition.

- [x] Test exact required case set, duplicates/missing/unknown IDs, snapshot mismatch, insufficient distinct **policy_version** coverage, critical failure and incomplete output.
- [x] Test run1 BLOCK→run2 full PASS permits submit while run1 persists; run3 INCOMPLETE blocks without falling back to run2. Partial PASS fragments cannot be combined.
- [x] Implement fake deterministic adapter and synchronous full suite under bounded local computation. Record completion/gate_summary independently of HTTP 201.
- [x] Run `python -m pytest tests/v1/test_runs.py tests/v1/test_gate.py -q`, end-to-end three-role scenario and whole suite; commit.

**Done:** selected run is `active_run_id` frozen at submit. Candidate/source change requires a new immutable change snapshot, not altered old results.

## G1.6 — frozen assessment and final approval envelope

**Create:** `service/domain/evidence.py`, `tests/v1/test_evidence.py`.
**Consumes:** complete history from G1.3 and selected run from G1.5. **Produces:** assessment/envelope and evidence diagnostic endpoint.

- [x] Test preapproval revision p excludes final p+1 from assessment; envelope includes final note/transition/event without a hash cycle.
- [ ] Test changes to frozen source bytes, note reason, event or run invalidate evidence; unrelated later tenant events/new source versions preserve historical seal.
- [x] Test source withdrawn after sealing: historical integrity stays valid and current eligibility changes separately. No anchor configured stays NOT_CONFIGURED.
- [x] Implement canonical payload reconstruction from immutable records, compare stored bytes/hash, emit three separate integrity/eligibility/anchor dimensions.
- [x] Run `python -m pytest tests/v1/test_evidence.py -q` and whole suite; commit.

**G1 completion:** all G1 tasks and real HTTP/SQLite end-to-end pass. Snapshot bytes and code hashes are recorded. Still no production release or PG claim.

**Evidence boundary:** frozen source, reason, event and run mutation plus unrelated tenant activity and later withdrawal are tested. A separately enumerated new-source-version-after-seal case remains to complete the broader assertion above.

## G2.1 — PostgreSQL role/migration foundation

**Create:** `compose.postgres-test.yaml`, `scripts/pg_test_bootstrap.py`, migration role/policy SQL, `tests/postgres/test_roles.py`, `tests/postgres/test_migrations.py`.
**Modify:** `service/db.py`, dev optional dependencies with Alembic and psycopg locks.

- [x] Use a clearly disposable PG17 test instance with generated credentials outside Git. Refuse non-test database names and never reset a user-configured production URL.
- [x] Test migrator owner, non-owner/NOBYPASSRLS app role, explicit grants and no app schema create/immutable update/delete. Fail setup if app is superuser/owner/BYPASSRLS.
- [x] Apply migration on empty DB; verify downgrade/upgrade in disposable DB, source snapshots and FK consistency.
- [x] Run `python -m pytest tests/postgres/test_roles.py tests/postgres/test_migrations.py -q` against real PG. No engine→SQLite substitution.

## G2.2 — RLS authentication and cross-tenant isolation

**Modify:** `service/auth.py`, `service/db.py`; **Create:** `tests/postgres/test_rls.py`, `tests/postgres/test_auth_bootstrap.py`.

- [x] Test registry→tenant context→enabled User lookup before data access; null/empty/malformed context reads zero rows and denies writes.
- [x] Test SELECT/INSERT/UPDATE/DELETE/FK for every tenant table as app role, not owner. Test A rollback→B and A exception→no-context on reused pooled connection.
- [x] Implement transaction-local context and parameterized SQL. Store secret registry outside repo; unknown/duplicate registry entry is handled per 08 §11.
- [x] Run both files, full PG tests and baseline suite. Record context/role/DB version, excluding credentials.

## G2.3 — independent-session concurrency and bounded failure

**Create:** `tests/postgres/test_concurrency.py`, `tests/postgres/test_lock_failure.py`.

- [x] Barrier-start two real sessions with same revision/key: one effect, coherent replay or specified conflict, no duplicate note/head sequence. Repeat 100 trials and record counts.
- [ ] Race different changes under same tenant; inject lock timeout/deadlock; verify entire rollback and 503 Retry-After 1. No unbounded automatic retries.
- [ ] Verify no external adapter calls occur while transaction holds tenant lock; request cancellation cannot commit half a state.
- [ ] Run target and full suites; commit G2 completion only with actual role/worker/DB/latency evidence.

**Evidence boundary:** 100 two-physical-session same-key races, actual PostgreSQL deadlock victim rollback, lock timeout rollback, and separate executor/HTTP 503 mapping are tested. A different-change race under one tenant and an explicit external-adapter lock-boundary test are not recorded; no external adapter is enabled. Cancellation rollback is covered in the SQLite executor test, not claimed as a separate PG cancellation test.

## G3 — approved synthetic policy packs and time/context

**Create:** `service/policies/{schema,resolver,registry}.py`, `datasets/packs/`, `tests/policies/test_bitemporal.py`, `test_riders.py`, `test_pack_isolation.py`.
**Interface:** `resolve_context(context: dict, pack_snapshot: dict, recorded_as_of: str) -> dict`; result includes reasons and source/version/clause refs.

- [x] Test valid/recorded interval boundaries, contract/incident/claim/consultation dates that differ, missing required date, timezone normalization and from>=to registration rejection.
- [x] Test CONFIRMED-empty vs UNKNOWN rider, unknown/unapproved/withdrawn rider, ambiguity/priority conflict, unapproved retroactivity and wrong tenant/product/source.
- [x] Implement the ordered filtering contract in 08 §12; preserve candidate rejection reasons and conservative INCONCLUSIVE. Do not encode unreviewed real insurance law as fact.
- [ ] Register a third fictional pack using the registry API/config only; record unchanged core hash and full API/DB/browser flow. External B05 credit still needs an external tester.
- [x] Run `python -m pytest tests/policies -q`, full suites; commit.

**Evidence boundary:** all three packs resolve through registry configuration and the third pack completes actual API/DB and browser approval. The explicit before/after unchanged-core-hash registration artifact is not recorded; independent third-pack testing remains SKIPPED, bonus 0.

## G4 — UI correction, retry recovery, accessibility

**Modify:** `service/static/`; **Create:** `tests/browser/test_v1_workspace.py`, `scripts/v1_ui_probe.js`, `scripts/check_uncertain_recovery.cjs`.

- [x] Exercise analyst→full suite→submit→domain reject→linked new change→re-evaluate→different reviewers approve→evidence.
- [x] Simulate dropped success response; UI keeps exact pending key/body/revision, offers same-key recovery, never creates a new key automatically for an uncertain outcome.
- [ ] Exercise 403/404/409/422/loading/empty/network states, keyboard navigation, focus restoration, labels, textual verdicts and narrow viewport.
- [ ] Render user/source/model text with text nodes; test XSS payloads in reason/title/output, no executable HTML. Do not store bearer tokens in browser persistent storage.
- [ ] Run real Playwright clicks with three distinct users and server+DB assertions. Record browser/version and failures separately from API tests. User study with five participants remains a separate observed activity.

**Evidence boundary:** the first recorded Chrome MCP flow completed correction, distinct-reviewer approval, evidence lookup, response-loss recovery, XSS title/reason, no WebStorage, narrow viewport and focus restoration. Later native-click timeouts are retained as failures. A full browser matrix for every listed HTTP/error state and model-output XSS is not recorded; the final AI-reference layout has its own subsequent visual check. The optional Python Playwright test was skipped when its dependency was absent.

## G5.1 — model/gold boundary and metrics

**Create:** `service/evaluation/{datasets,benchmark,metrics}.py`, `tests/evaluation/test_gold_boundary.py`, `test_paired.py`, `test_split.py`.

- [x] Test model input allowlist excludes GoldRecord/expected annotations; group connected components cannot appear in multiple splits; private gold never enters ZIP/Git/UI.
- [x] Test both arms incomplete, mismatched case/snapshot/rubric, critical severity vs observed critical failure, zero denominator and insufficient clusters.
- [x] Implement exact 08 §14 paired/group-bootstrap specification using newly locked NumPy; do not label two Wilson intervals a paired CI.
- [x] Run synthetic hand-checked count/CI fixtures and full suite. Public dev examples remain demo; 160/80/120 private study is not fabricated to fill quotas.

## G5.2 — optional external model job boundary

**Create:** `service/evaluation/{jobs,worker}.py`, `tests/evaluation/test_jobs.py`, optional provider adapter/config.

- [ ] Before external provider activation, implement 08 §15 queue/lease/attempt/terminal run contract with network outside DB locks.
- [ ] Test response loss, duplicate completion, cancel/complete race, worker crash/restart, lease expiry and latest incomplete veto; another change under same tenant must progress during network wait.
- [ ] Use synthetic input only; require explicit provider config, cost cap and timeout. Record model/prompt/source/input/output hash; don't log secret/raw private data. No payment/insurance-decision tool.
- [x] Provider unavailable leaves real-model capability false and deterministic workflow usable. Actual model/red-team results are only reported if executed.

**Optional mode status:** external job/lease/attempt/cancellation code and its provider tests are unimplemented. Only the checked disabled-capability fallback is implemented and exercised; no real model or red-team result is claimed.

## G6 — external evidence and release candidate

**Create:** `service/anchors/`, backup/restore runbooks and tests only when infrastructure exists.

- [ ] Define signed anchor payload as tenant checkpoint + approval envelope hash, key ID/version and retention; separate writer key and DB owner. Verify DB wholesale rewrite and restored checkpoint against independent anchor.
- [x] Run four synthetic exercises: service outage, token theft, evidence tampering, rollback/restore. Measure actual RTO/RPO with environment and timestamps; planned targets are not results.
- [ ] Obtain consented written feedback from two insurance-domain reviewers; independent Windows install, technical review and third-pack exercise. If unavailable, keep each SKIPPED and bonus at 0.
- [ ] Execute publishing procedure, fresh CI, distribution/wheel validation, dependency/secret audit and license/provenance review. Public Git remote creation/push remains an explicit user action or separately authorized task.

**External evidence status:** independent anchor/WORM/custodian and consented domain-reviewer/installation/user-study evidence are SKIPPED, bonus 0, because none is available. Local recovery is verified; final-source CI/distribution/audit/provenance review remains a separate release checklist. Git commits/pushes were explicitly authorized by the user; no package publication or deployment is implied.

## Per-task report

`task ID | changed files/behavior | red-test evidence | green commands/exit | environment/DB/role | regressions | skipped checks | evidence path | remaining limitation | next task`.

Only mark a checkbox after its assertions pass. Update status and release notes to the final behavior, not the initial plan. An internal coding-agent review is useful engineering review and is never an external SME/security certification.
