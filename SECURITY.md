# Security policy

## Supported scope

| Version or deployment | Status |
| --- | --- |
| v5.3 development package / current development branch | Intended target for fixes after a maintainer accepts responsibility; synthetic local use only |
| Inherited v5.1 runtime and historical packages | Research baseline; no separate supported maintenance branch |
| Internet-facing, multi-user production, real insurance or personal-data use | Unsupported |

This archive does not establish a security response team, support SLA, or audited release. The root README and prebuild documents identify implementation gaps. The inherited approval-history bypass was reproduced with real SQLite/HTTP requests and hardened in this version. Its exact regression evidence and remaining scope are recorded in docs/VALIDATION.md. Packaging and a dependency scan do not independently close security findings.

## Reporting a vulnerability

**Private reporting is not configured by an archive.** Before making the repository public, its owner must enable GitHub private vulnerability reporting and verify access for at least one responsible maintainer, or publish a verified private reporting channel here. No email address or hosted repository identity has been invented for this package.

After the GitHub feature is enabled, open the repository's **Security → Advisories → Report a vulnerability** form. If that form is unavailable, do not post exploit details, credentials, or personal data in a public issue. Contact the person who supplied the package through an existing private channel and ask for the reporting route. Public release should wait until a private route exists.

Provide the affected commit/package version, environment, impacted invariant, expected and observed behavior, and a minimal reproduction using synthetic data. Include sanitized evidence and any proposed fix. Do not include live credentials, real customer data, or tests against systems you do not control.

Once maintainership is established, the maintainer should acknowledge, assess, reproduce, fix, and coordinate disclosure with the reporter. Exact response times have not been promised. Record advisories and affected/fixed versions when applicable; preserve reproducible regression coverage.

## Boundaries

- Local bearer tokens and synthetic accounts do not provide SSO, MFA, or production identity assurance.
- A hash chain in the same database is not an independent integrity anchor against a database administrator.
- `/api/health` confirms process availability; it does not verify database integrity, safety, or business fitness.
- CI checks known dependency advisories and selected code/contract behavior. It is not a penetration test, source-code security certification, or insurance compliance review.
- SQLite is restricted to one local demo worker. PostgreSQL, RLS, concurrent actors, external evidence anchors, and real model integrations require their separate acceptance gates.

Official setup guidance: [GitHub private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/working-with-repository-security-advisories/configuring-private-vulnerability-reporting-for-a-repository).
