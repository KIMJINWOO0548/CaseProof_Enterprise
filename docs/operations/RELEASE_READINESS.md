# Release readiness gates

Local G6 recovery readiness is bounded to executable synthetic SQLite drills.
Consult the actual fresh recovery-drill JSON and test logs before marking any
gate verified; an implementation or checklist alone is not execution evidence.

- [ ] Four local exercises PASS with actual timestamps/environment: owned server
  outage/restart HTTP readiness, stolen token disabled, tamper blocks release,
  new-file restore verifies checkpoint/envelope/rows and records observed RTO/RPO.
- [ ] Regression suite, smoke, UI syntax and distribution checks run on the exact
  release source; preserve command, exit code and source hashes.
- [ ] Wheel/sdist installation and clean independent Windows installation verified.
- [ ] Dependency and secret audit run; license/provenance review covers repository,
  locked dependencies, vendored UI assets, datasets and distributed artifacts.
- [ ] Fresh CI linked to the exact release commit; prior CI is not fresh evidence.
- [ ] Restore registry rotated and current revocations reapplied before exposure.
- [ ] Independent anchor/WORM and custodian separation verified against wholesale
  rewrite and rollback: **SKIPPED, infrastructure unavailable, bonus 0**.
- [ ] Two consented insurance-domain reviewers and written feedback:
  **SKIPPED, consented reviewer data unavailable, bonus 0**.
- [ ] Independent technical review/installation/third-pack exercise:
  **SKIPPED until independent evidence exists, bonus 0**.

Local agent-operated synthetic runs are not independent human review, insurance
certification or production readiness. Publishing/push/deployment remain separate
explicitly authorized actions. Git commits and pushes were separately authorized in this session; no package release or deployment is performed.
