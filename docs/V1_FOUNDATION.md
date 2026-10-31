# G1.1 domain foundation

`service/api/schemas_v1.py` defines strict command/header, case-context, revision,
note and run DTOs. `service/domain/state_machine.py` returns a new snapshot for
each of seven allowed transitions. It performs no DB, clock, ID generation or
network operations. No `/api/v1` route is registered; the baseline `/api` and its
legacy evidence digest are unchanged.

Use `parse_body(Model, raw)` for strict UTF-8 JSON parsing before DTO validation.
Calling Pydantic's JSON parser alone does not enforce this raw-body contract.
Input reasons are stripped and offset timestamps become six-digit UTC strings.
Timestamps with more than six fractional digits are rejected rather than losing
precision. Stored note/revision/run payloads must already be canonical; their
content is not silently normalized. Case-context defaults preserve UNKNOWN,
null dates and empty rider arrays as distinct facts.

`ActorContext` comes from server authentication. Command/result contexts detach
and freeze nested JSON containers; use `json_payload()` to obtain a fresh JSON
object for hashing or responding. These types do not authenticate an actor or
validate that a registered ID exists.

## Internal command input

All commands carry `kind`, `change_id`, canonical `occurred_at`,
`expected_revision` (null only for create), `body`, and `checks`.

| Kind | Body | Additional canonical records |
| --- | --- | --- |
| CHANGE_CREATED | CreateChange | parent when a parent relation is present |
| EVALUATION_RECORDED | RecordEvaluation | newly recorded run |
| SUBMITTED_FOR_DOMAIN_REVIEW | SubmitChange | current selected run |
| DOMAIN_APPROVE / DOMAIN_REJECT | Decision | new DOMAIN note |
| APPROVED_FOR_DEMO | Decision | new RELEASE note, existing DOMAIN note, selected run |
| RELEASE_REJECT | Decision | new RELEASE note, existing DOMAIN note |

`checks` must be a frozen `TransitionChecks` instance constructed by trusted
server code. A JSON object with booleans is rejected. The instance binds the
tenant/change/revision and snapshot digest; gate results also bind the exact run
digest. Approval additionally requires matching source and assessment references.
This is a caller assertion and binding, not cryptographic authentication or a
replacement for verification. Never construct it from client assertions.

G1.2 adds a separate persistence model and disposable SQLite migrations; see
[schema boundaries](G12_SCHEMA.md). Importing the model opens no database, and
baseline startup does not run v1 migrations or seed approval history.

G1.3 must reconstruct and verify the complete stored history, authorize parent
access, and perform all side-record writes atomically. G1.5 must independently
compute suite coverage, current gate and source eligibility; G1.6 must build and
verify assessment/envelope bytes. Those tasks are not implemented here. G1.4
must test strict parsing and header handling again through real HTTP endpoints.
