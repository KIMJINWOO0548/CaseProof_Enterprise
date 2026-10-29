# Target contracts — PLANNED

These files describe the future `/api/v1` protocol. They are **not** the running
baseline `/api` OpenAPI and do not make Gate 1 complete. The normative design is
[the implementation contract](../prebuild/08_IMPLEMENTATION_CONTRACTS.md).
Schema validation checks document structure; it cannot prove authentication,
authorization, atomic commits, evidence integrity, or insurance correctness.

All examples are synthetic structural specimens. UUIDs have a valid lowercase
version-4/variant shape but were deliberately chosen as fixtures. Example hashes
are labeled synthetic placeholders, not a mutually verified approval history.
No example grants permission, records a real review, or represents private gold.

## Files and validation entry points

| Schema | Entry point / contents |
| --- | --- |
| `common.schema.json` | Shared scalar and typed immutable-reference definitions |
| `commands.schema.json` | `#/$defs/CreateChange`, `RecordEvaluation`, `SubmitChange`, `Decision`, `CreateHeaders`, `MutationHeaders` |
| `case-context.schema.json` | Typed synthetic dates, rider facts, and recorded-as-of input |
| `change-revision.schema.json` | Complete canonical `ChangeRevision` payload |
| `change-transition.schema.json` | Seven core transition kinds and their required/null references |
| `decision-note.schema.json` | Domain/release decision payload |
| `audit-event.schema.json` | Tenant-chain event payload |
| `evaluation-run.schema.json` | Immutable full-suite run payload and incomplete/PASS structure |
| `assessment-manifest.schema.json` | Fixed preapproval evidence scope |
| `approval-envelope.schema.json` | Final noncyclic approval envelope |
| `mutation-fingerprint.schema.json` | Normalized request payload for purpose `request` |
| `error.schema.json` | Safe structured error response and HTTP-code mapping |

All schemas use JSON Schema Draft 2020-12. Every `$ref` is a sibling filename or
local fragment; resolve it relative to `contracts/` with an explicit local
registry. The standard `$schema` identifier selects the validator's bundled
metaschema; no network retrieval is needed. Use a date/date-time format checker.
ASCII patterns include a full-string end guard so a final line terminator cannot
slip past a regular-expression `$` anchor.

[examples/index.json](examples/index.json) contains an `examples` array. Each
entry has `file` relative to `contracts/`, a `schema` filename with an optional
`#/$defs/...` fragment, and expected JSON Schema boolean `valid`. Optional
`runtime_valid: false` explicitly marks inputs that JSON Schema accepts but the
planned stricter HTTP runtime must reject. There are 62 examples: 29 expected
schema-valid and 33 expected schema-invalid. This is an assertion registry, not
an API execution report. The package checker consumes it with a local registry.

[state-machine.json](state-machine.json) describes the seven core transitions,
required roles, guards, inserted-row counts, and terminal states.
[requirements-traceability.json](requirements-traceability.json) maps target
requirements to gates and planned acceptance-test identifiers. Every runtime
requirement remains `implemented: false`; target test names are not evidence
that those tests exist or pass.

## Command bodies and headers

| Method / path | Body schema | Protocol headers | Success |
| --- | --- | --- | --- |
| POST `/api/v1/changes` | `CreateChange` | `Idempotency-Key`; expected revision forbidden | 201, DRAFT/1 |
| POST `/api/v1/changes/{change_id}/evaluation-runs` | `RecordEvaluation` | Key + expected revision | 201, immutable run + DRAFT/n+1 |
| POST `/api/v1/changes/{change_id}/submit` | `SubmitChange`, exactly `{}` | Key + expected revision | 200, PENDING_DOMAIN_REVIEW/n+1 |
| POST `/api/v1/changes/{change_id}/domain-decision` | `Decision` | Key + expected revision | 200, PENDING_RELEASE or REJECTED/n+1 |
| POST `/api/v1/changes/{change_id}/release-decision` | `Decision` | Key + expected revision | 200, APPROVED_FOR_DEMO or REJECTED/n+1 |

`Idempotency-Key` is a case-sensitive, untrimmed ASCII value matching
`[A-Za-z0-9_-]{12,128}`. `X-Expected-Revision` is an ASCII positive decimal string
without leading zeros. The header schemas validate only the extracted protocol
header map, not ordinary headers such as Authorization or Content-Type. HTTP
header **names** remain case-insensitive; normalize names before applying these
schemas. Reject duplicate/conflicting protocol headers at the HTTP boundary.
Create rejects the revision header; all other mutations require it. Mutations
accept no query parameters.

Every request body and nested typed DTO forbids unknown properties. The body
cannot supply tenant, actor, roles, requester, owner, or expected revision.
Authentication determines tenant and actor; create assigns requester and owner
to that actor. Apply DTO defaults and normalization before fingerprinting.
JSON Schema's `default` is descriptive and does **not** perform that work.

Successful mutation responses are `{data,result_revision,replayed}`. `data` and
the original status/revision are frozen at commit. A replay only changes
`replayed` to true and does not substitute current state or reverify current
evidence. A failed evaluation that is successfully recorded still returns 201;
inspect its completion and gate fields. Failed requests never become successful
idempotency records or workflow transitions.

## Concrete v5.3 structural choices

These choices complete names left implicit in the prose contract and are part
of this planned version, rather than choices left for each implementer:

- Payload schema labels are `change_revision_v1`, `change_transition_v1`,
  `decision_note_v1`, `audit_event_v1`, `evaluation_run_v1`,
  `mutation_fingerprint_v1`, `assessment_manifest_v1`, and
  `approval_envelope_v1`.
- `PayloadRef` is exactly `{id,payload_sha256}`. `RunRef` additionally contains
  `recorded_revision`; `DecisionRef` contains `output_revision`; `EventRef`
  contains `sequence`. `TransitionRef` contains `revision_to` and a nested
  `audit_event_ref: EventRef`. Envelope decision/transition refs are
  `PayloadRef`, and its event ref is `EventRef`. Resolve each reference to its
  expected immutable schema type and the same tenant; matching a string alone
  is insufficient.
- API-issued object/snapshot IDs are UUIDv4. Tenant, actor, existing synthetic
  pack-version scope, product, workflow, rule and case IDs use `RegisteredId`.
  `adapter_version_id` identifies an immutable UUIDv4 adapter version. These
  choices preserve registered synthetic identifiers without allowing a client
  to choose authorization identity.
- The exhaustive `ChangeRevision` field is `active_run_id`. It points to the
  latest committed run while DRAFT and becomes the frozen selected run after
  submit. The assessment field is named `selected_run_id`; it must equal that
  frozen snapshot value. There is no extra `selected_run_id` snapshot field.
- Transition run ID/hash fields are non-null for `EVALUATION_RECORDED` and
  `SUBMITTED_FOR_DOMAIN_REVIEW`; other core transitions use null. Decision
  ID/hash fields occur only on decision transitions. Only release APPROVE
  carries a non-null assessment hash. Every declared payload field is present;
  absent optional values are explicit nulls in canonical payloads.
- A rider uses `{code,enrolled_from,enrolled_to,confirmation_evidence_id}`.
  Unknown dates/evidence may be null and must be evaluated as uncertainty.
  Missing context properties default to null dates/as-of, `UNKNOWN`, and `[]`;
  they do not silently satisfy a required suite fact. Record non-null
  `recorded_as_of` in the fixed UTC representation before hashing.
- Case `source_refs` are immutable `PayloadRef` values. `resolution_status`
  and `error_code` are registered identifiers whose allowed meanings belong to
  the versioned evaluator; the three verdicts are PASS, FAIL, INCONCLUSIVE.
  Run completion is COMPLETE/INCOMPLETE and gate summary is PASS/BLOCK.
- Error `details` is `{}` except optional `current_revision` on STALE_REVISION
  and optional allowlisted `fields` on INVALID_REQUEST. No raw inputs, SQL,
  credentials, tenant identifiers, or exception details belong there.

The G1 core keeps `active_job_id` null and real-model capability false. The
optional G5 job extension is named but inactive in the state-machine artifact;
its two new transition kinds are intentionally not accepted by the core schema.
Enabling it requires a new versioned schema extension and its acceptance tests.

## Canonical bytes and fixed reference vectors

Use `caseproof.c14n.v1`, not the name of a full RFC 8785 implementation. Sort
object keys by Unicode code point; preserve array order and Unicode composition.
Encode compact UTF-8 with no BOM or trailing newline, lowercase control `\u00xx`
escapes, no escaped slash, and no extra whitespace. Permit only objects with
string keys, arrays, strings, booleans, null, and safe integers between
−9007199254740991 and 9007199254740991. Floats and decimals are forbidden.

`H(purpose,payload) = SHA256(UTF8("caseproof:" + purpose + ":v1\n") || C(payload))`.
Purpose values are `change-revision`, `transition`, `decision`, `audit-event`,
`evaluation-run`, `assessment`, `approval-envelope`, and `request`, matching
each schema's `x-hash-purpose`. A payload excludes its own hash. File-byte
`blob_sha256 = SHA256(original_bytes)` has no domain prefix and is distinct from
a normalized payload hash.

[canonical_vectors_v1.json](../tests/fixtures/canonical_vectors_v1.json) fixes
14 inputs, canonical UTF-8 hex values, and hashes. It includes Korean composed
and decomposed characters, combining accents, Unicode code-point key ordering,
control/quote/newline escaping, bool/int distinction, safe integer limits,
null/empty values, distinct purposes, and UTC conversion. `input` is the value
**after** defaults/normalization; `pre_normalization_input`, when present,
documents the offset input. The canonicalizer must not infer timestamps from
arbitrary strings. The empty-object vector illustrates generic canonicalization;
protocol-specific optional fields still require explicit nulls.

The fixed hashes were compared with both Python `hashlib.sha256` and the system
`sha256sum` utility during artifact preparation. This independently checks the
digest calculation; it does not establish another-language serializer
equivalence, a service canonicalizer, or valid runtime approval evidence.

## Required runtime checks beyond JSON Schema

JSON Schema's integer type accepts the numeric value `1.0`. The integral-float
example is therefore schema-valid and explicitly runtime-invalid. Strict HTTP
tests must reject floats, booleans/strings used as claim days, NaN/Infinity,
duplicate object keys, invalid UTF-8, lone surrogates, and values outside safe
integer bounds. [http-negative-cases.json](http-negative-cases.json) contains
planned raw-body/header cases; none is represented as an executed HTTP test.

String lengths do not perform Python `str.strip()` or reject all surrogate
encodings. Check both original and stripped reason lengths, then store only the
stripped value without NFC/NFD conversion. Dates require semantic calendar
checks; offsets require normalization; a business date remains a date rather
than an invented UTC instant.

Schemas cannot enforce unique case IDs when other fields differ, sorted arrays,
consecutive revisions, cross-record hash equality, tenant-scoped foreign keys,
immutable version meaning, current role membership, separation of duties,
manifest completeness, source eligibility, exact suite coverage, atomicity,
idempotency concurrency, lock order, or historical reconstruction. Enforce
these in domain/DB/HTTP tests. A suite inheriting the existing synthetic scope
requires at least two distinct approved policy-version IDs, not two rule-row
IDs; a genuinely different pack may use a separately reviewed suite version.
The default latest-revision FK omission is
deliberate: verify projection integrity on every mutation and test atomicity;
do not claim a complete DB-only invariant. Actual PostgreSQL role/lock/RLS
tests, independent human review, private holdout evaluation, and external
anchors remain separately evidenced gates.
