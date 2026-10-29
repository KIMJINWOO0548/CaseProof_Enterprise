# Changelog

## 5.3.0.dev1 — 2026-10-30

- Merge the supplied v5.3 package into the existing Git repository with runtime sources at the root; retain prior source/evidence in Git and `archive/`, outside distribution manifests.
- Preserve the repository's authoritative transition table, frozen assessment/envelope and atomic idempotency across all five mutation endpoints. Historical replay returns the authorized original response; current integrity is queried separately.
- Add v5.3 strict revisions/extra-field rejection, malformed-record diagnostics, audit-order checks, CLI database consistency, conservative unapproved-rider resolution and incomplete benchmark rejection.
- Import hashed dependencies, isolated browser tooling, planned v1 schemas/vectors, OSS files and CI/build tooling. New local evidence is separate from supplied Linux results.
- Begin G1.1 in an isolated v1 canonicalization module; no planned `/api/v1` routes or PostgreSQL support are advertised as implemented.

## 5.3.0.dev0 — 2026-10-29

Hardened the inherited synthetic `/api` demo and replaced the mixed historical
archive layout with a root-level source repository and explicit `/api/v1` handoff.

- Bind mutable workflow state/revision/reviewers to audited event order; reject
  status-only approval bypass and malformed or inconsistent approval evidence.
- Enforce requester-only evaluations, integrity before replay, strict numeric and
  revision input, required meaningful approval reasons, and forbidden extra fields.
- Mark either incomplete comparison arm INVALID without publishing final metrics;
  reject malformed comparison records. Stop silent fallback from a selected
  unapproved applicable rider to a base rule.
- Isolate browser tests, preserve existing smoke reports, align initializer/server
  database configuration, and keep non-demo startup unsupported.
- Add versioned target contracts, state machine, schemas/examples/canonical vectors,
  implementation tasks and acceptance criteria; these are not implemented v1 routes.
- Add open-source policy files, universal hashed locks, CI definition, wheel/sdist
  checks, package integrity tools and captured verification results.

See docs/VALIDATION.md for actual checks and known limitations. PostgreSQL/RLS,
full target idempotency, complete run/envelope design, real models, private blind
study and external security/insurance reviews remain future work.

## Input baseline

Imported from the user-provided CaseProof Enterprise Prebuild v5.2, whose runtime
was a v5.1 local prototype. Historical releases/scores are not reissued as current
verification. Original archive/file hashes are recorded in docs/PROVENANCE.md.
