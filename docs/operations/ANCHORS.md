# Independent anchor boundary

Status: **SKIPPED / bonus 0**. No external provider, signing key, WORM storage,
network call or independently controlled writer exists in this implementation.
Local metadata hashes detect mismatches against supplied local metadata; a DB
owner able to replace both database and metadata can rewrite that evidence.

Future signed payload contract must include:

| Field | Meaning |
| --- | --- |
| schema | Versioned anchor payload contract |
| tenant_id | Tenant identity bound to the independent writer |
| checkpoint | Committed tenant audit sequence and head SHA-256 |
| approval_envelope_sha256 | Exact approval envelope digest, or explicitly null |
| issued_at | Actual UTC signing time |
| key_id / key_version | Independent custodian's key identity and version |
| algorithm | Explicit signature and canonicalization algorithms |
| retention_until / retention_policy | Enforced independent retention contract |

The independent writer must authenticate tenant scope, reject rollback or
conflicting same-sequence checkpoints, use a key unavailable to the DB owner and
runtime, and return a verifiable signed receipt with independent retention.
Verification must validate canonical payload, signature, key version/revocation,
retention and tenant identity before comparing restored checkpoint/envelope.
Test a wholesale DB rewrite and old-backup rollback against that receipt before
claiming independent anchoring. Key rotation, recovery, access auditing and
retention enforcement require infrastructure and separate executable tests.

An application hash, local JSON, local timestamp or locally held signing key
does not satisfy this independent-writer contract. No provider is enabled here.
