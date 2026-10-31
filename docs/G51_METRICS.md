# G5.1 evaluator boundary and paired metrics

This isolated module implements contracts §13–14 for public synthetic development
fixtures. It does not connect a model, serve an API, authorize approval, or supply
an independently reviewed or blind study. The baseline benchmark is unchanged.

`datasets.model_payload()` accepts exactly `ModelCaseInput` fields: `case_id`,
`query`, `context_snapshot`, `source_bundle_id`, `business_as_of`, `recorded_as_of`.
It rejects extra fields and nested gold/annotation/metadata keys. The caller is
responsible for trusted source selection: a key allowlist cannot detect an answer
hidden in ordinary natural-language text. `GoldRecord` is evaluator-only.
`public_manifest()` exposes only dataset ID and public count; private gold records,
paths and case-level commitments must remain outside the UI and model payload.
`assert_public_artifacts()` checks path inventories; it is not a secret scanner.
The repository/package guards are maintained separately by the root workflow.

`connected_groups()` joins transitive shared document, source version, product
family, contract, incident and scenario relations. `validate_split()` rejects
cross-split components, conflicting source hashes and mismatched manifest IDs.
Freeze the group manifest before assigning splits. Never split components to fill
the planned 160/80/120 quotas. The tests contain small public synthetic examples,
not private holdout cases or evidence of SME review.

`benchmark.compare_paired(baseline, candidate, gold, metadata, comparison_spec,
lock_path=...)` consumes evaluator-owned gold and metadata. Each arm contains:

- `snapshots`: exact `input_sha256`, `source_sha256`, `dataset_sha256`,
  `gold_sha256`, `rubric_sha256`, `evaluator_sha256` (64 lowercase hex).
- `policy`: integer `budget_micro_usd`, `timeout_ms`, `retry`.
- `settings`: recorded `model`, `version`, `temperature`, `seed`, `max_tokens`,
  `permissions`, `infrastructure`, `measurement_interval`; optional prompt hash.
- `case_results`: unique nonempty IDs, per-case input/source hashes, boolean
  `complete`, nullable `correct`, `critical_failure`, `risk_flagged`, `error_code`.
- Optional `cost_micro_usd`: model/infrastructure/human_review; `latency_ms`:
  model/total/human_review. Missing values remain null with `NOT_RECORDED`.

The caller must resolve the snapshot hashes to the frozen authorized manifests;
matching hash strings alone do not authenticate supplied data. Both arms must have
the same case IDs and immutable hashes and policy. Only settings named explicitly
in `comparison_spec.allowed_differences` may differ. Optional preregistered gates
are `minimum_accuracy` and `maximum_new_critical`; any new critical regression
always blocks. Gold severity describes case importance and does not itself mean
an observed critical failure. Arm overrides of severity/risk are invalid.

Contract mismatch returns `INVALID`. Any incomplete case returns `INCOMPLETE`,
counts and raw results with all statistical headlines null. Otherwise critical
regression or gate violation returns `BLOCKED`; remaining results are
`ELIGIBLE_FOR_HUMAN_REVIEW`, never automatically approved. Zero recall/FPR
denominators return null with an explicit reason. Raw results are evaluator-only
and must not be exposed through the public manifest.

The bootstrap uses sorted scenario families, NumPy `Generator(PCG64(20261028))`,
10,000 uniform replacement draws of M groups, all paired cases per selected group,
case-weighted deltas and `quantile([.025,.975], method="linear")`. Results record
NumPy version, SHA-256 of the supplied dependency lock, cluster/source/critical-case
counts and the independent-scenario-family assumption. M<2 returns null with
`INSUFFICIENT_CLUSTERS`. With M>=2, missing NumPy or lock raises
`EvaluationDependencyUnavailable`; no substitute RNG or CI is used.

Initial checks: genuine missing-module RED and subsequent targeted test logs are
under `reports/runs/20261031T033543Z-g51-5d9f9d96/`. The approved project environment now uses NumPy 2.4.6 from requirements-evaluation.lock; the paired numeric fixture ran in the coordinator's ordinary suite. No blind/SME outcome is claimed.
