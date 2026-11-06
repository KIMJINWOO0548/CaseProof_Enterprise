# Scoped comparison triage reconnaissance — 2026-11-06

Scope: help reviewers narrow the existing saved-run comparison to changed cases. Replica recon/diff applies to this slice, not complete Langfuse feature or visual parity.

Primary public source: https://langfuse.com/docs/evaluation/experiments/compare-experiments . The coordinator verified the documented flow from aggregate comparison to changed/regressed cases and trace inspection. The previously attempted `/experiment-ui` page returned 404 and is not evidence for product behavior. Public capture metadata is recorded after successful observation; no account, private API, source bundle, image asset or product code is reused.

Screen inventory: S01 public comparison documentation (observed documentation, not authenticated product); S02 existing CaseProof saved-run history and comparison; S03 filtered comparison table with total/visible count and empty result guidance.

F01 load history → choose baseline/candidate → compare → choose change dimension → optionally search case ID → inspect saved sides and hash references. Filtering requires no network or mutation; selectors changing the compared run remove the old results. F02 no matches → explicit empty message → adjust filters. Full context warnings and summary/hash evidence remain visible regardless of row filter.

Components: existing native select, labeled search input, live visible/total status, existing responsive table. Inferred adaptation: CaseProof hash-dimension filtering is useful triage analogous to the documented case drilldown; no claim that the competitor uses these exact dimensions. Our search is an additional local choice, not an observed competitor feature.

Data model: reuse validated evaluation_comparison_v1 rows (case_id, baseline/candidate saved result, changes flags). No schema or API mutation. Filtering preserves original case order and intersects literal case-insensitive ID text with one dimension; search input is rendered only as text. No private gold or raw model/source text is exposed.

Size S: one existing render block plus actual-handler regression. Existing full-history authorization, latest-run gate and immutable execution records remain server responsibilities. Trace inspection, score ranking, causal quality claims and real-model runs are out of scope. Layout comparison is not applicable: documentation and our local reviewer UI are different surfaces.

Observed evidence: REA 6.8.0 captured the correct public page with Chromium 156.0.8078.80, exit 0, provider-owned browser cleaned up. Accessibility snapshot SHA-256 `fdafdbc95245f30f1586b12ea68380bc7df3866d9a185914495e453009f50763`. The page describes threshold-based narrowing, side-by-side cases and incomplete evaluator handling. This implementation adapts narrowing to CaseProof's existing change flags; it does not reproduce numeric score filtering. Raw page text and screenshots stay local and are not shipped.
