# Verification — 2026-11-06

Status: implementation and automated checks complete. Full host suite passed with the explicit optional skips below. Scoped parity is not production acceptance.

- Existing package manifest before edits: `python VERIFY_PACKAGE.py`, PASS 410 files, exit 0.
- New actual-handler RED: `node scripts/check_run_comparison.cjs`, 10 passed / 1 failed, exit 1 (missing filter controls).
- GREEN same command: 11 passed / 0 failed, exit 0.
- `node --check service/static/v1.js`: exit 0.
- Installed Replica parity.py on replica/features.csv: exit 0; only two selected workflow features scored. Initial relative-path invocation failed (exit 2); corrected absolute skill path succeeded.
- Sandbox full pytest first failed to create its default temp directory. Explicit owned basetemp progressed through optional PostgreSQL skips but hung on socket/TestClient work; stopped and delegated unchanged tests to coordinator host execution. No suite pass is claimed from those attempts.
- No package installs, global changes, real databases, external model calls or deployment. Browser visual review, live PostgreSQL and external human acceptance are separate checks.

## Final host evidence

The coordinator ran the existing desktop CaseProof virtual environment; summary.json and raw logs were inspected directly.

| Command | Actual result |
|---|---|
| python -m scripts.windows_checks pytest -q --basetemp=<owned verification/CaseProof_Enterprise/tmp/pytest-full> | 962 passed, 458 skipped, 3 warnings, 22 subtests passed; 376.41 seconds; exit 0 |
| python -m scripts.windows_checks scripts.smoke | synthetic 12/12; exit 0 |
| python -m scripts.check_ui_syntax | 1 baseline inline script; exit 0 |
| python -m scripts.check_package | 14 canonical vectors, 65 examples, 15 schemas, 414 source files; exit 0 |

The modified v1.js also passed its independent Node syntax check and all 11 comparison-handler scenarios. Full-suite skips: 457 real PostgreSQL checks (no configured disposable PG17) and 1 optional Playwright browser check (package absent). Warnings: existing Starlette deprecation and two Alembic cyclic-FK sorting warnings. The Windows wrapper only retries socketpair initialization; this run and smoke needed **0 retries**, and assertions/requests were not retried.

Raw evidence: task workspace verification/CaseProof_Enterprise/{0,1,2,3}-validation.log and summary.json. Smoke report: reports/runs/20261106T150958Z-756cda09/integration_smoke.json. Package source count is the observed run count, not a fixed release manifest. No release distribution was generated; the original 410-file source manifest is deliberately retained as baseline and would require regeneration for a new distribution.

Acceptance: focused local behavior and automated regressions verified. Real browser visual execution, PostgreSQL, external human review and production/model evaluation remain unrun. No claim of whole-product or visual parity.
