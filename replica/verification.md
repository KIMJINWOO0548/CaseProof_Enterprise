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

## Phase 2
See [depth review](depth-review.md) for new RED/GREEN, own-only measurement, merge preservation and explicitly remaining external checks. Prior phase1 results do not validate phase2.

## Phase2 host verification — completed
Parent host logs were read directly from phase2/verification/CaseProof_Enterprise. `python -m scripts.windows_checks pytest -q --basetemp=<owned tmp>`: **962 passed,458 skipped,22 subtests**,3 existing warnings,exit0,247.58s wall time. Optional skips include unavailable real PostgreSQL and optional evaluation/browser dependencies; these are not passes. Initialization-only Windows socketpair wrapper reported **0 retries**. `scripts.windows_checks scripts.smoke`:12/12 PASS (1.81s); UI inline syntax exit0; package structural check421files PASS. Added real-handler tests12/12 and submit/recovery15/15 pass; v1.js syntax exit0.

Executed `scripts/check_comparison_browser.cjs` against Chrome156 with intercepted local synthetic API; see the browser verification below. This remains distinct from backend E2E and competitor interaction evidence.

## Phase2 actual browser verification — completed

Chrome156.0.8078.80 executed the real source UI with synthetic intercepted API responses. At1440px and390px the document had0px horizontal overflow and no page exceptions. This is actual browser behavior/layout evidence, not live-backend E2E, assistive-technology certification or competitor testing. Backend behavior is covered separately by the full host suite.

Native Enter on a case moved focus to `comparison-case-detail`. Paging/search preserved the global warning and latest incomplete gate; comparison rows remained bounded and no POST occurred. Case control measured60px at both widths. Mobile screenshot reviewed: provenance stacks and hashes wrap; the comparison table uses contained horizontal scrolling. [Result](evidence/browser/result.json), [desktop](evidence/browser/case-review-1440.png), [mobile](evidence/browser/case-review-390.png).

## Actual public reference interaction — account gate
Independent REA capture opened https://langfuse.com/cloud/demo?utm_campaign=demo_project, rejected optional cookies and clicked the Europe demo link. The destination displayed account creation/sign-in; no account, credentials or form submission was attempted. The comparison application was therefore inaccessible within the authorized public-only scope. This is evidence of portal navigation and an account gate, not validation of experiment comparison or trace behavior.

[Capture summary](evidence/langfuse/summary.json) (SHA256 `ac1a4115498d1e2448da3c7eb4b73d3d72b68dea03ecd9aff2a1ecc1fbc66cf3`) and local destination accessibility snapshot (SHA256 `4f640bc846e4151d843f0ceb88bc70d2ee7f2544908532fa82910b426598e042`; retained only under task `phase2/refs/langfuse-europe-demo-flow/5-accessibility.txt`). Five initial actions completed; the final destination wait failed because `main, h1, form` matched multiple elements. CLI exit0 does not override `completeness=incomplete` and `equality_eligible=false`. The captured destination still establishes the account gate. Owned Chromium process cleanup completed. Equal-condition competitor tests remain NOT_RUN.
