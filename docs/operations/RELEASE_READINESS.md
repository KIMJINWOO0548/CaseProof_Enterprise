# Release readiness gates

Local G6 recovery readiness is bounded to executable synthetic SQLite drills.
Consult the actual fresh recovery-drill JSON and test logs before marking any
gate verified; an implementation or checklist alone is not execution evidence.

- [x] Four local exercises PASS with actual timestamps/environment: owned server
  outage/restart HTTP readiness, stolen token disabled, tamper blocks release,
  new-file restore verifies checkpoint/envelope/rows and records observed RTO/RPO.
  [Executed evidence](../evidence/g1-g6/recovery-drill.json), Windows/Python 3.12.10,
  synthetic SQLite, one worker; these are local measurements.
- [ ] Regression suite, smoke, UI syntax and distribution checks run on the exact
  release source; preserve command, exit code and source hashes.
- [ ] Wheel/sdist installation verified on the final source; agent-operated
  isolated installation is tracked separately from independent Windows installation.
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
