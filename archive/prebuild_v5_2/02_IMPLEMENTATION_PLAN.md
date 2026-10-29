# CaseProof Enterprise v5.2 Implementation Plan

> 실행자: `01_TARGET_DESIGN.md`와 이 계획을 함께 읽는다. 아래 체크박스는 미래 구현 작업이다. **현재 이 패키지에는 v5.1 기준 코드만 있으며 해당 계획을 실행하지 않았다.** 단계별 실행 전에 사용 가능한 관련 개발·검증 skill을 선택하고, 동작 결과를 증거로 남긴다.

**Goal:** 합성 데이터 검증 시제품의 승인·감사 결함을 우선 차단하고, 실험·보험 업무·운영 준비도를 증거 기반으로 높인다.

**Architecture:** 기존 FastAPI/SQLAlchemy/SQLite 레퍼런스를 보존하면서 전이 이력과 결정·감사를 같은 트랜잭션으로 묶고, 실제 PostgreSQL 테넌트 격리 및 독립 증거 보존을 단계적으로 추가한다. 보험 룰 및 AI 어댑터는 검증 도구로만 사용하며 실지급·계약 실행은 없다.

**Tech Stack:** Python, FastAPI, Pydantic v2, SQLAlchemy 2, SQLite local; 이후 PostgreSQL, Alembic, Playwright. 실제 버전은 클린 환경에서 잠금 파일과 해시로 기록한다. 브라우저/API는 공식 문서 버전 확인 후 적용.

**Spec:** `prebuild/01_TARGET_DESIGN.md`; 보험 실험은 `prebuild/03_INSURANCE_AND_EXPERIMENT.md`; 각 Gate의 독립 결과는 `prebuild/04_ACCEPTANCE_AND_EVIDENCE.md`.

## 전역 규칙

- 현재 소스는 `current/`. 같은 이름의 historical archive는 런타임 정본이 아니다.
- 합성 데이터와 격리 테스트 DB만 사용. 실행 전 DB URL·서비스·파일 삭제 경로·외부 연결·권한 명령 확인. 운영 DB 삭제/마이그레이션 금지.
- 테스트 정답·평가기준·과거 로그 삭제 또는 수정으로 PASS 위조 금지. 이전 결과와 신규 결과를 분리한다.
- 모든 미실행은 SKIPPED와 이유; exit 0과 관찰 기록이 없는 항목은 PASS 금지. 오류·로그는 secret/PII 없이 재현 가능하게 보관.
- 하나의 구현 작업은 실패하는 테스트 → 최소 수정 → 통과 테스트 → 기존 회귀 → 기록 순서. 이 문서는 사용자 요청에 따라 **구현 코드를 작성하지 않았다.**

## 변경 파일·책임 지도

| 대상 | 작업 | 역할 |
|---|---|---|
| `current/service/app.py` | 수정 | 인증/권한 경계, 상태 전이, 무결성 검사, 안전한 트랜잭션 경로 |
| `current/service/models.py` | 수정 | transition/decision/idempotency·tenant 제약 |
| `current/service/schemas.py` | 수정 | 엄격한 입력, 필수 사유, OpenAPI 계약 |
| `current/service/db.py` | 수정 | 세션/트랜잭션 경계, G2의 PostgreSQL tenant context |
| `current/service/seed.py` | 수정 | 가상업무팩 seed, 사람과 출처 가상 데이터만 |
| `current/reference/resolver.py` | 수정 | 승인·시점·특약 불확실성을 안전하게 처리 |
| `current/reference/paired_benchmark.py` | 수정 | 기준/후보 양측 완료·정답 라벨·비교 유효성 |
| `current/service/static/index.html` | 수정 | 역할별 접근·거절 사유·복구·이력 및 접근성 |
| `current/tests/` 신규 테스트 | 추가 | 독립 실패→성공 회귀. 기존 테스트와 정답 보존 |
| `current/migrations/` | G2 신규 | Alembic schema/role 정책. 과거 승인 복구를 가장한 event 생성 금지 |
| `current/reports/runs/<UTC-run-id>/` | 신규 | 명령, exit code, 환경·DB 종류, 입력 SHA, 상세 결과, 미실행 사유 |
| `current/scripts/` | 수정 또는 신규 | 설치/DB 안전성, 브라우저·재현 도구. 고정 테스트 DB 자동 삭제 제거 |
| `current/docs/` | 수정 | 코드로 증명된 것만 현재 상태, 목표는 계획으로 분리 |

## 공통 Review Focus

1. 동일인이 여러 role을 가져도 요청·현업·최종 승인을 모두 통과할 수 없어야 한다 — G1 `test_multirole_separation`.
2. DB 상태/승인자/전이/note/event의 단독 변경과 삭제·중복·역순은 실패해야 한다 — G1 `test_transition_integrity_*`.
3. 동일 idempotency 키의 동시 요청 및 응답 유실 뒤 재전송은 결과를 한 번만 생성한다 — G1/G2 `test_idempotency_*`.
4. 테넌트 context 누락·위조 및 연결 풀 재사용은 데이터를 노출하지 않는다 — G2 `test_rls_*`.
5. 미승인/시점 오류/미확인 특약 및 baseline/candidate incomplete는 정상 PASS로 처리하지 않는다 — G3/G5 테스트.

---

## Gate 0 — 실행 환경과 기준선 확보

**의존성:** 없음. **복잡도:** S–M. **결과:** 코드 변경 없이 당시 환경의 사실을 로그로 남긴다.

- [ ] 원본 ZIP SHA/manifest를 확인하고 임시 복사본에서 `current/`를 작업 디렉터리로 한다. 코드·datasets·tests를 비교해 이전 감사 당시와 같은지 기록한다.
- [ ] 실제 Python·OS, lockfile 여부, pip 설치 대상·프록시, DB URL·demo_mode, 토큰/비밀·외부 요청·삭제 경로를 검토한다. 의존성이 없으면 별도 venv에서 설치 시도하고 실패 원인을 기록한다. 설치 실패 시 우회·무근거 PASS 금지.
- [ ] `python -m pytest -q`와 `python -m scripts.smoke`를 실행한다. `smoke.py`는 성공 시 현재 디렉터리의 `reports/integration_smoke.json`을 덮으므로 별도 작업 복사본에서만 실행한다. 상세 로그와 exit code 기록.
- [ ] JS 문법, `service.schemas` JSON Schema, `/openapi.json`과 HTML 응답을 각각 실제 가능한 범위에서 검사한다. API 서버를 시작할 수 없다면 OpenAPI는 SKIPPED로 기록한다.
- [ ] 감사 당시의 49 unittest 성공, 전체 pytest·smoke 미실행, 과거 90+22/12 기록을 각각 분리한다. 이번 환경의 새 결과와 섞지 않는다.

**인수:** 코드·데이터 변화 없이 환경/명령/출력/미실행을 남기고 `run_id`로 이후 결과와 연결. 실패한 환경에서 다음 Gate의 실제 통과는 주장하지 않는다.

## Gate 1 — 실제 SQLite P0 재현·수정과 기본 API 계약

**의존성:** Gate 0의 의존성 확보. **복잡도:** L. **우선순위:** 최상.

### Task 1.1 — P0 실제 적대 테스트

**파일:** 기존 `service/app.py`, `models.py`; 신규 `tests/test_transition_integrity.py`; 참고 `../independent_audit/audit_probe.py`, `../independent_audit/live_probes.py`.

- [ ] 임시 SQLite + TestClient에서 요청 생성, 서로 다른 규정 PASS 2건, 제출까지 수행한다. DB `Change.status`만 `PENDING_RELEASE`로 바꾸고 DOMAIN note/event는 생성하지 않는다.
- [ ] 다른 release approver로 최종 승인을 호출한다. **수정 후 기대:** 409, `APPROVED_FOR_DEMO` 없음, 신규 release note/event 없음. 수정 전 실제 응답이 200인지 409인지 기록하고, ORM 스텁에서 확인한 결과와 구분한다. 재현이 안 되면 조건·버전 차이를 설명한다.
- [ ] 동일한 실제 DB에서 domain_reviewer_id/status/revision 개별 변조, note/event 누락/중복/역순, tenant 뒤섞임, 승인 후 평가 변경을 각 테스트로 추가한다.
- [ ] 정상적인 세 사람의 합성 승인과 evidence 결과가 기존 테스트와 함께 성공하는 대조군을 둔다.

### Task 1.2 — 원자적 전이·무결성

- [ ] `models.py`의 transition 모델을 목표 설계 I-03에 맞춰 추가한다. `NONE/0 → DRAFT/1` genesis, 평가의 DRAFT 내 revision 증가, revision gap·중복 거부, tenant 복합 FK 및 합법적 상태/이벤트 매핑을 둔다. 신규 DB에서 검증한다.
- [ ] `app.py`에서 생성·평가·제출·검토·승인/반려 전이가 공통 검증을 통과하도록 정리한다. 각 단계의 상태, revision, 담당자, 존재해야 할 note/event, 제출·평가 결과를 교차 대조한다. 없는 과거 이력을 조작해 만들지 않는다.
- [ ] 한 트랜잭션에서 status/revision/CAS + note + audit + 전이 이력을 기록한다. 중간 단계에 예외를 주입해 네 종류 레코드가 함께 rollback되는지 확인한다.
- [ ] assessment manifest와 approval envelope의 순서를 설계 I-06대로 구현한다. DOMAIN 승인 근거와 승인 직전 revision/event 집합을 동결하고 이후 revision/event로 재구성하지 않는다. 해시가 자기 자신을 참조하지 않는지 확인한다. 최종 승인 후 변경/삭제가 검출돼야 한다.
- [ ] 기존 SQLite 테스트와 `python -m pytest -q`, `python -m scripts.smoke`를 다시 실행한다. smoke의 고정 출력 경로를 옵션으로 바꾸거나 별도 실행 사본을 사용해 기존 `current/reports/` 파일을 보존하고, 새 결과를 `reports/runs/<run_id>/`에 기록한다.

**인수:** 모든 적대 테스트 403/409·원자적 rollback, 정상 시나리오 승인, 기존 테스트 이상 없음. DB 전체 조작을 막는다고 주장하지 않는다.

### Task 1.3 — 입력·권한·재시도

**파일:** `schemas.py`, `app.py`, `models.py`, `service/static/index.html`; 신규 `tests/test_api_contract.py`, `tests/test_idempotency.py`.

- [ ] `Decision.reason`을 필수로 노출하고 입력 원문과 strip 결과를 각각 Unicode code point 기준 8–500으로 검증. `/openapi.json`의 required/minLength/maxLength 및 trim 후 검증 규칙 설명을 확인한다. 공백만 또는 trim 후 7자 거부.
- [ ] `claim_days`는 strict JSON integer(0–9999). `true`, `1.0`, `"30"`, 음수·10000은 422; 정수 30은 정상. JSON Schema integer는 1.0 거부를 표현할 수 없으므로 stricter runtime 정책은 OpenAPI 설명/확장 및 오류 메시지에 표시하고 실제 HTTP 요청으로 별도 검증한다.
- [ ] create/evaluation/submit/domain-decision/release-decision에 actor·tenant·operation별 key + request hash를 적용한다. fingerprint에 method·정규화 route·change ID·본문·expected_revision을 포함한다. 같은 본문 재전송과 응답 유실 후 replay는 과거 결과와 replay 표시, 같은 key·다른 경로/대상/본문은 409. tenant/actor를 바꾼 replay 불가; 최신 무결성 판정은 별도 조회.
- [ ] 기본 정책으로 requester만 evaluation 가능하도록 UI와 API를 맞춘다. 다른 분석가와 동일인 다중역할의 부정 시도는 각각 403. 대리평가가 추가되면 별도의 명시적 설계와 테스트가 필요.
- [ ] SQLite에서 동시 요청의 제약·롤백을 확인하되 운영 동시성 결론은 G2 실제 PostgreSQL 실행 전 보류한다.

**인수:** 실제 `/openapi.json`과 API 요청 테스트가 일치, 모든 replay/role negative 케이스 통과. 서버 미실행 시 PASS 금지.

## Gate 2 — PostgreSQL·RLS·마이그레이션·동시성

**의존성:** Gate 1. **복잡도:** L. **파일:** `db.py`, `models.py`, `migrations/`, `compose.*`, `tests/test_pg_rls.py`, `tests/test_pg_concurrency.py`.

- [ ] 버전 잠금·hash 및 disposable PostgreSQL DB를 만들고 schema migration을 빈 DB에 적용/다운그레이드/재적용한다. 임의 이름/URL이나 기존 DB 삭제 금지. 외부서비스 연결은 별도 승인·명시 설정.
- [ ] owner/migration role과 non-owner/NOBYPASSRLS app role을 분리. tenant 테이블의 SELECT/INSERT/UPDATE/DELETE 별 USING/WITH CHECK 적용. app role로만 시험; owner/superuser 우회는 별도 관찰하고 통과 근거로 쓰지 않는다.
- [ ] 인증된 tenant context는 transaction-local로 세팅한다. 인증 누락, context null/빈 문자열, forged tenant, rollback·connection pool 재사용, 타사 ID/복합 FK·join/insert/update/delete 및 오류 누출을 검사한다. SET context 자체가 DB 신원보증은 아니므로 SQL injection/app role 침해 모델을 별도 기술한다.
- [ ] tenant-head → change → 관련 기록 → idempotency 순서의 락과 CAS를 모든 쓰기 경로에서 통일한다. 서로 다른 session/worker에서 같은 revision 동시 승인 및 같은 idempotency 동시 호출, 다른 change의 tenant audit 동시 append, lock timeout/deadlock과 재시도를 확인한다.
- [ ] 적어도 100회 경합 반복은 회귀 탐지 예시일 뿐 무경합·성능 보증이 아니다. 성공/충돌/예상치 못한 5xx 및 중복 승인 수, DB·격리수준·worker 수를 공개한다.
- [ ] v5.1 legacy 데이터는 기존 기록을 보존하고 `legacy-unverified`로 격리하는 마이그레이션 계획을 테스트한다. 임의의 DOMAIN 승인 이력 생성 금지.

**인수:** 비소유 app role 기준 tenant A→B 노출·수정 0, 정상 처리, 요청당 승인 최대 1, 허용 충돌 외 예외 0, rollback 및 복구 확인. 데이터베이스 슈퍼유저의 전체 재작성은 외부 앵커 전 탐지 보장 불가.

## Gate 3 — 합성 보험 규정·업무팩

**의존성:** G1, 업무팩은 G2의 tenant model과 결합. **복잡도:** L.

- [ ] `models.py`, `resolver.py`, `schemas.py`, `seed.py`에 pack/source/version/contract context와 시점별 승인 상태를 도입한다. 기존 합성 데이터는 명시적으로 버전업·검증하고 숨겨 수정하지 않는다.
- [ ] 계약/사고/청구/상담 날짜를 서로 다르게 입력한다. 기준일 누락, 원문 미승인, DRAFT 특약, unknown과 confirmed-none 구분, 미승인 상위 우선순위, 같은 우선순위 충돌, 소급·미등록 시점, 유사 상품 및 타 tenant 문서 섞임은 fail-closed.
- [ ] 보험 현업 검토 전 '개별 특약이 있을 때 기본 규칙으로 돌아가도 된다'는 정책을 확정하지 않는다. 기본값은 INCONCLUSIVE; 담당자가 근거를 확인한 정책만 별도 버전으로 허용한다.
- [ ] 세 번째 완전 독립 가상 업무팩을 코어 수정 없이 등록. 기존 두 팩과 격리, API·DB·UI 생성→평가→검토→승인→증거의 E2E를 수행한다. 외부인이 독립 수행한 증거가 있어야 B05 1점을 준다.

**인수:** 정해진 합성 사례 전부 재현 가능, 불확실성을 거짓 PASS로 바꾸지 않음. 실제 약관의 해석·금융법 적합성은 SME 서면 검토 전 별도 미검증.

## Gate 4 — 업무 UI·시정·복구·접근성

**의존성:** G1, G3에서 확장된 정보. **복잡도:** M–L.

- [ ] 생성→결과 확인→반려→새 version 시정→재평가→다른 사람이 승인→감사 증거의 UI 화면과 입력 오류·권한 거부·통신 단절·복구 화면을 구현한다.
- [ ] REJECTED를 terminal로 두고 새 change_id에 parent_change_id를 연결해 새로 평가하며, 반려 이력과 기존 증거를 덮지 않는다. 실행 성공 후 응답 유실 시 UI가 pending 작업의 동일 Idempotency-Key와 fingerprint를 유지해 같은 결과를 재생한다. 새 키를 매번 생성하는 현재 동작은 재시도 경로에서 바꾼다. `scripts/browser_e2e.py`의 고정 파일 삭제는 제거하고 `tempfile.TemporaryDirectory`를 사용한다.
- [ ] Playwright 실제 브라우저로 세 역할의 클릭·POST·DB·화면 변화·감사 확인 및 P0 negative를 검증한다. `browser_acceptance.py`의 로그인 검사는 전체 E2E가 아님을 명시한다.
- [ ] 키보드/스크린리더/초점/레이블·색 외 텍스트·반응형을 시험한다. 사용자 관찰은 5명 이상을 목표로 하되 참여자·업무 경험·시나리오·실패율·시간·편향을 기록한다. 사용자 미참여면 미실시.

## Gate 5 — 모델 어댑터·360건 비교 실험

**의존성:** G1–G3. **복잡도:** L.

- [ ] 가상 모델 어댑터부터 검증한 후 외부 모델은 별도 설정·키·비용·egress 확인 하에 선택적으로 연결한다. 실제 고객자료 금지. 실제 지급·계약 API/tool 호출 금지.
- [ ] paired benchmark에서 기준/후보 양쪽 `complete`를 검증한다. 한쪽이라도 미완료면 정확도·신뢰구간·개선치의 확정 결과를 내지 않는다; 재시도 또는 `INVALID/INCOMPLETE` 반환.
- [ ] `03_INSURANCE_AND_EXPERIMENT.md`의 160/80/120 고정 split, 독립 검수, 데이터 누수 방지, baseline·예산·지표·쌍체 차이·비용을 준수한다. 전체 360건 및 전문가 검수는 아직 계획이다.
- [ ] 실서비스 연결 전 Promptfoo 등 외부 도구는 라이선스·가격·로컬/호스팅·전송처를 다시 확인한다. 경쟁 도구의 강점은 재사용하며 기술적 우위는 동일조건 실험 전 주장 금지.

## Gate 6 — 운영 리허설·외부 검증

**의존성:** G1–G5 중 해당 기능 완료. **복잡도:** L.

- [ ] 독립 계정/서명키 기반 외부 WORM 앵커·이벤트 경계, 키 회전, 접근 감사 및 복구를 구현하고 DB 전체 변조/복구 시 탐지 재현. SHA 체인만으로 WORM이라 주장하지 않는다.
- [ ] 백업/복구 RTO/RPO는 목표와 실제 측정을 분리한다. 장애/토큰 탈취/감사변조/롤백 4개 시나리오를 합성 환경에서 훈련하고 원인·조치·재시험을 남긴다. B03은 외부 수행 증빙까지 필요.
- [ ] 실무자 2명 이상의 독립 서면 검토, 제3자 Windows 설치, 독립 보안·기술 리뷰 및 제3팩 무수정 E2E의 증빙을 보존한다. 미참여·비동의 시 0점이고 대체 생성하지 않는다.
- [ ] 금융당국/금융보안원 가이드 원문·적용 버전과 전문, 회사 정보보호 요구사항을 해당 시점에 다시 확인한다. 이번 보도자료 확인은 인증·법률 자문이 아니다.

## 최종 보고 형식

각 Gate에 대해 `변경 파일 / 변경 내용 / 실제 명령 / 환경 / 테스트 수와 성공·실패 / 미실행 / 제한 / 증거 파일 / 남은 위험`을 기록한다. 점수는 `SCORECARD_105.csv` 각 세부 항목별 0·절반·만점과 실제 증거를 기준으로 독립 재채점한다. 외부 보너스는 외부 증거 없이는 0이다. 단계 완료와 전체 105점은 동일하지 않다.
