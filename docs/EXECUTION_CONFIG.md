# Execution configuration boundary — dev6

New executions use `schema=evaluation_run_v2`. Their `run_config_sha256` is
`H("run-config-v2", payload)`, where payload has `schema=execution_config_v2`
and the complete canonical candidate, source bundle, dataset, suite, evaluator,
selected model/prompt (or null), and selected adapter snapshots. Bundle members
bind source/policy hashes, which repository reconstruction also checks against
their stored bytes. Only the selected configuration is checked; registering an
unrelated adapter, model, prompt or source version does not change an old seal.

The same helper records and verifies the digest. Verification happens when
loading evaluated history, before submission or approval, as well as when
checking a historical seal. This prevents a DB-owner partial rewrite of one
snapshot and its own hash from being silently sealed after evaluation. Runtime
roles retain their immutable-table restrictions. This is not protection against
a DB owner rewriting the entire mutually consistent database; independent
anchoring remains unavailable.

`evaluation_run_v1` bytes, hashes, fixtures and strict parser are preserved as
historical artifacts. They lack the complete execution binding and cannot be
promoted to v2 by changing a digest or label. Runtime history loading refuses
them with `EXECUTION_CONFIG_UNVERIFIED` (409). Authenticated current/evidence GETs
report `LEGACY_UNVERIFIED`; evidence returns `immutable_refs: null`. The UI offers
no evaluation or approval action for that unverified record. No automatic data
migration or deletion occurs. Preserve an earlier profile and use the launcher
without `--profile` to prepare a new disposable profile and run a fresh evaluation.
An authorized same-key replay remains its original historical response; consult
the separate evidence GET for current verification.

For validated history, evidence GET exposes `immutable_refs` as canonical
identities and purpose-separated `payload_sha256` values: candidate, bundle,
dataset, suite, evaluator, optional model/prompt, selected adapters, sources,
policies, source-eligibility records, revisions, runs, decisions, transitions,
events and optional assessment/envelope. Revision identities are change/revision;
assessment/envelope identities are change IDs. Raw snapshot contents, credentials
and gold answers are not returned by this projection. INVALID or legacy records
provide diagnostics without trusted references. Authentication and tenant scope
are checked before returning either form.

Independent failing tests reproduced adapter rewrites and dataset/bundle rewrites
between evaluation and sealing. Non-null model/prompt and unrelated-registration
regressions supplement the original numeric fixture. Commands and actual results
are recorded in [VALIDATION](VALIDATION.md); implementation alone is not evidence
that the final checks ran.
