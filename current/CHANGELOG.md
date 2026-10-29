# 변경 기록

## v5.2 설계·인수 문서 보완 · 2026-10-29
- 독립 평가의 P0 승인 이력 누락 후보, API 스키마, 합성 약관, 비교시험, RLS·브라우저 등 미검증 항목에 대해 `../prebuild/` 설계 및 인수 계획을 추가했다.
- **서비스/reference/테스트/dataset 코드는 변경하지 않았다. P0 수정·전체 테스트·외부 검증은 아직 완료되지 않았다.**
- 과거 프롬프트/계획을 `archive_v5_1_planning/`에 보존하고 최신 문서로 연결했다.

## v5.1 · 2026-10-29
- DB-backed synthetic MVP: HTTP API, actual SQLAlchemy transactions, role and tenant scoped UI, request/approval state machine.
- Source/dataset/evaluator snapshot hash verification, idempotent evaluation POST, stale revision rejection.
- **Critical audit gap addressed:** append audit event with request/result hashes and validate DB records against event content, not audit chain alone.
- Tamper tests cover evaluation input/result/deletion, change creation snapshot, domain decision reason, post-approval verification, corrupt audit JSON.
- 90 pytest tests + 22 subtests pass, separate 12/12 API smoke flow.
- Browser localhost interaction unable to validate due to container admin restriction; documented, not counted as passed.
- v4 blueprints retained read-only for architectural context; v5 implementation contract wins.

## v4 · archived baseline
- Reference resolver, governance, evidence hash chain, synthetic dataset and offline UI.
- v4 105-point rubric baseline 76/105.
