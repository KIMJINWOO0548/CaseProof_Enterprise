# Release readiness gates

Local G6 recovery readiness is bounded to executable synthetic SQLite drills.
Consult the actual fresh recovery-drill JSON and test logs before marking any
gate verified; an implementation or checklist alone is not execution evidence.

- [x] Four local exercises PASS with actual timestamps/environment: owned server
  outage/restart HTTP readiness, stolen token disabled, tamper blocks release,
  new-file restore verifies checkpoint/envelope/rows and records observed RTO/RPO.
  [Executed evidence](../evidence/g1-g6/recovery-drill-dev6.json), Windows/Python 3.12.10,
  synthetic SQLite, one worker; these are local measurements.
- [x] Implementation `643e25f`: regression suite, smoke, UI syntax and distribution
  checks ran on that exact commit; [CI evidence](../evidence/g1-g6/ci-643e25f.json) records commands and source SHA.
- [x] Wheel/sdist and source ZIP verified for `643e25f`; [fresh installed evidence](../evidence/g1-g6/installed-643e25f-wheel.json). Agent-operated
  isolated installation is tracked separately from independent Windows installation.
- [x] OSV dependency and redacted Gitleaks scans executed; raw candidates and
  dispositions retained. Tabler notices and reference-only license scopes checked.
- [ ] Complete inherited-rightsholder inventory and full environment/image license
  clearance; unresolved provenance remains in THIRD_PARTY_NOTICES. No clearance is fabricated.
- [x] Fresh CI linked to exact implementation `643e25f`: 9 successful jobs.
  Subsequent documentation-only HEAD is checked separately.
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
