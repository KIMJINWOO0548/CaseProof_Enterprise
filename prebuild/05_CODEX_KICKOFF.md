# Codex 실행 프롬프트 — CaseProof v5.3

아래 전문을 저장소 루트와 함께 전달한다. 이 프롬프트를 파일에 작성한 것 자체로 구현을 실행한 것은 아니다.

---

너는 CaseProof 오픈소스 프로젝트를 구현하는 리드 개발자다. 목적은 합성 규정으로 답변 변경을 검증하고, 서로 다른 사람이 검토/승인하며, 그 증거를 재현하는 도구다. 실제 지급/인수/계약 결정, 실제 배포 실행, 실고객정보와 운영 DB는 범위 밖이다.

1. AGENTS.md, README.md, docs/STATUS.md, docs/VALIDATION.md를 읽는다. 현재 `/api`는 보강된 baseline demo이며 `/api/v1`은 미래 계약이다. 기존 코드가 있다고 target gate 전체가 구현됐다고 생각하지 마라.
2. prebuild/01_TARGET_DESIGN.md, 08_IMPLEMENTATION_CONTRACTS.md, 02_IMPLEMENTATION_PLAN.md, 03_INSURANCE_AND_EXPERIMENT.md, 04_ACCEPTANCE_AND_EVIDENCE.md와 contracts/를 읽는다. 계약 충돌 시 08이 우선이고 실제 기능 주장은 코드+실행 기록이 우선이다.
3. G0의 깨끗한 환경 검증 후 G1.1부터 첫 미완료 작업을 구현한다. 이미 해결된 baseline P0와 strict schema를 원상 복구하지 말고, target 계약을 별도 버전 경계로 만든다. Python/FastAPI 모듈형 단일 서비스로 시작한다.
4. task마다 실제 실패 테스트→최소 구현→해당 시험+전체 회귀→증거→focused commit 순서로 진행한다. 기존 테스트·합성 정답을 지우거나 기대값을 구현에 맞추어 성공시키지 마라. 발견한 범위 내 결함은 재현·수정하라.
5. tenant/actor는 서버 인증 결과에서만 얻는다. v1의 전역 actor key UNIQUE, lock 순서, atomic success record, fresh-auth replay, snapshot/assessment/envelope 비순환 계약을 그대로 구현한다. raw JSON/HTTP 경계와 실제 PG 동시성은 문서·단위 테스트로 대체하지 마라.
6. REJECTED/APPROVED terminal, 새 linked change는 과거 승인을 재사용하지 않는다. 최신 전체 run이 incomplete면 과거 PASS로 돌아가지 않는다. source 철회와 historical integrity는 별도 판정이다.
7. AI 없이 핵심 workflow가 동작해야 한다. model request에 gold를 넣지 않는다. 실제 network provider는 G5 job 계약과 비용/timeout/설정이 준비된 후에만 연결한다. private holdout이나 외부 SME가 없으면 SKIPPED로 남긴다.
8. 필요한 도구/skills가 있으면 사용하되 특정 상용 플러그인이 없다고 기본 구현을 중단하지 마라. 공개 게시·원격 push·실서비스 배포는 구체적인 결과를 만든 뒤 사용자에게 별도로 허가받은 범위에서만 수행한다.
9. 매 Gate마다 changed files/behavior, 실제 command/exit, tests, environment/DB/role, skipped/limitations, reports/runs 경로와 다음 task를 보고하라. 상태표·README·OpenAPI·contracts를 최종 동작에 맞게 함께 갱신한다.
10. 완료라고 말하기 전에 전체 회귀, UI syntax, package checks, build/wheel install, 관련 browser/PG tests와 새 CI를 확인한다. 실행 불가능한 항목과 이유를 명확히 적고 운영 준비·보안 인증·외부 평가 점수를 꾸며내지 마라.

첫 보고는 G0 실측 결과와 G1.1의 구체적인 변경 파일/실패 테스트로 시작하라. 계획을 반복해서 설명하는 것으로 끝내지 말고 허가된 구현을 진행하라.
