# Saved evaluation-run history and comparison

The standalone `/api/v1` workspace can inspect saved v2 runs for its selected
change. Select **평가 이력 조회**, choose a baseline and candidate, then compare.
History is loaded on request. Reading or selecting an older run leaves the
latest evaluation, correction inputs, submission readiness and original-request
recovery intact. Zero or one run shows a message explaining that the normal
two-run comparison workflow needs another saved evaluation.

`GET /api/v1/changes/{change_id}/evaluation-runs` takes no query parameters and
returns `data` with schema `evaluation_run_history_v1`: `runs`, `total_runs`,
`limit: 100` and `truncated`. Runs are ordered by recorded revision descending,
then ID ascending; timestamps are display metadata. The complete authorized
history is validated before the latest 100 summaries are projected. This is a
response limit, not a bound on history validation cost.

`GET /api/v1/changes/{change_id}/evaluation-runs/compare` requires exactly one
`baseline_run_id` and one `candidate_run_id`, each a lowercase UUIDv4. Duplicate,
missing, malformed and extra query values return `INVALID_REQUEST` (422).
Both IDs must belong to the full validated history of the authorized change,
including runs outside the 100 displayed summaries. Unknown and foreign IDs
return generic `NOT_FOUND` (404). Same-run comparison is allowed even when only
one run is stored. Legacy v1 and tampered history fail closed; GETs do not repair
or rewrite any records.

The `evaluation_comparison_v1` response preserves baseline/candidate order and
includes their summaries, case-ID-sorted union `rows`, `changed_counts`, `mode`
and `context_reasons`. Each side contains only the saved verdict, completion,
resolution/error/critical state, input/output hashes and sorted source identity
and hash references. A missing side is `null`. More than 1000 union cases returns
`COMPARISON_LIMIT_EXCEEDED` (422) without case details. The history summary
`payload_sha256` is the original purpose-separated
`content_hash('evaluation-run', original_run)`, never a hash of projected JSON.
Existing version IDs and execution/input digests remain visible.

`presence_changed` counts added/missing cases. On shared cases the remaining
dimensions compare input hashes, output hashes, source refs and result state.
Dimension counts may overlap; `any_changed` counts union rows with any change.
Presence-only rows do not manufacture input/output/result differences against a
missing side. Context reasons are sorted fixed codes: `CASE_SET_CHANGED`,
`CONFIG_CHANGED`, `INPUT_CHANGED`, `SOURCE_REFS_CHANGED`, `VERSION_CHANGED`.

Mode is `INCOMPLETE` if either run is incomplete, otherwise `CONTEXT_CHANGED`
when reasons exist, otherwise `SAME_CONTEXT`. Incomplete comparisons retain
their context reasons. Same-run comparisons have zero changes/reasons, including
an incomplete run. Output-only differences do not themselves change context.
A normal corrected 29→30 demo input produces FAIL→PASS and `INPUT_CHANGED`;
this describes changed inputs and outcomes, without measuring model quality.

Configuration/version/case-set changes cannot normally occur inside one valid
change: changing immutable snapshots requires a new change. Their projection
semantics are tested with separate pure fixtures, while the API retains the
existing fixed-reference integrity checks. No raw historical inputs, source
bodies, model responses or private evaluator gold are reconstructed or exposed.
Hashes cannot explain an exact text/value change. No ranking, significance,
release recommendation or approval is produced.

The two additive response schemas and structural examples are in `contracts/`.
Behavior checks live in `tests/v1/test_run_comparison.py`,
`tests/v1/test_run_projection.py` and the real JavaScript-handler harness
`scripts/check_run_comparison.cjs`. Handler checks are distinct from browser QA.
Current local verification is recorded in [VALIDATION.md](VALIDATION.md).

- [x] Pure descriptive projection, deterministic rows, bounds and original hashes.
- [x] Authenticated tenant-scoped GETs over complete validated same-change history.
- [x] Lazy read-only controls with empty/loading/error/context states and delayed-response guards.
- [x] Full-table equality checks for successful and rejected GETs, including audit,
  idempotency, run payloads, revisions and active-run selection.

Synthetic local demo only. No real-model execution, external expert assessment,
production capacity guarantee or Windows validation is implied by these checks.

## Case triage filters (2026-11-06)

After comparison, use **변경 항목** to show all cases, any change, or one of the five change dimensions. **사례 ID 검색** performs case-insensitive literal substring matching; both filters intersect. The visible/total count and empty-state guidance describe the filtered table. Summary counts, context warnings and the full hash disclosure still describe the entire comparison. Filtering sends no requests, changes no stored data, and does not alter latest-run submission readiness. Selecting another run clears the old comparison and its filters.

The scoped public reference, observed/inferred boundaries and executed feature matrix are in [recon](../replica/recon.md) and [parity](../replica/parity.md). This is a local workflow adaptation, not a model-quality ranking or trace reconstruction.
