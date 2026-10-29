# CaseProof Enterprise — 구현 전 보완 설계 v5.2

> 문서 버전 v5.2 / 2026-10-29. **기존 서비스는 v5.1이며 아래 v5.2 기능은 아직 미구현이다.** 이 문서는 향후 구현 목표다. 근거: `../independent_audit/REPORT.md`, `../current/service/`, `../current/tests/`. 평가의 19/105는 그 환경에서 검증하지 못한 것을 0으로 처리한 2026-10-29 점수이지 제품의 고정 성능 점수가 아니다.

## 1. 제품 목표와 범위

금융 AI 답변의 **출처·적용 맥락·수치 정합성을 검토하고 사람이 변경을 승인하는 검증 보조 도구**. 처음에는 합성 손보·생보 데이터, 가짜 모델, 단일 로컬 사용자 환경에서 재현한다. 실제 보험금 지급, 계약 체결·거절, 외부 업무시스템 수정, 실개인정보는 범위 밖이다. PASS는 검증한 범위의 결과일 뿐 업무상 정당성이나 최종 지급 승인을 보장하지 않는다. 소비자 위해 가능성이 보이면 자동 승인하지 않는다.

현재 구현은 날짜 기반 **숫자 일수 비교**에 국한된다. 향후 LLM/RAG 문장 평가, PDF/OCR, 에이전트, 금융기관 연계·실제 상품 검증은 아래 후속 단계에서 별도로 만든다. 금융사 채용 포트폴리오에는 본인의 기여와 AI 도움·미구현 기능·실측 결과를 분명히 한다.

## 2. 현재 증거와 미해결 위험

| 항목 | 현재 사실 | 미래 목표 |
|---|---|---|
| P0 승인 이력 | 원본 함수 + ORM 스텁에서 상태만 변조해 DOMAIN note 없이 데모 승인하는 경로 재현. 진짜 TestClient/SQL DB 재현은 못 했다 | 실제 임시 SQLite 재현 후 수정, SQLite+PostgreSQL에 회귀 시험 |
| 승인·평가 감사 | DB 행과 감사 event 일부 대조. 변경 상태·검토자·revision의 전이 정합성은 부족 | 상태/결정/이벤트 연결, 동일 트랜잭션, 외부 독립 앵커 |
| 보험 규칙 | 합성 JSON 10개 규칙, 합성 정답 20건; 시간·특약 테스트 | 승인된 규정·특약·상품·계약 사실의 출처/시점 검수. 실제 정답은 SME 검증 전 확정 금지 |
| API·운영 | FastAPI/SQLAlchemy 코드 및 정적 UI. 기존 기록상 90+22 테스트·12/12 스모크. 2026-10-29 감사 환경에서는 전체 재실행 불가 | 깨끗한 환경에서 실제 API/DB/브라우저 검증. PG/RLS/SSO·WORM은 별도 구현/실증 |
| 실증 | 공식 자료·경쟁 기능은 독립 조사; 해당 제품의 수요·우위는 가설 | 현업 인터뷰, 독립 검수, 동일조건 실험, 결과 공개 |

## 3. 설계안 비교와 선택한 기본안

1. **현재 상태값만 검사:** 수정이 쉽지만 상태 행이 변조되면 승인 이력 누락을 발견할 수 없다. 기각.
2. **전이 원장과 승인 기록을 교차 검증하고 같은 트랜잭션에서 상태·결정·감사를 기록:** 기존 서비스와 연속성이 좋고 합성 PoC에서 재현 가능하다. **기본안.** DB 전체를 통제하는 관리자에게 불변성은 보장하지 못한다.
3. 이벤트 소싱을 전면 도입하고 외부 서명/WORM을 처음부터 강제: 강한 보증을 설계할 수 있지만 현재 1인 시제품에는 구현·운영비가 크다. 2번의 경계를 유지하며 외부 앵커를 후속 Gate로 도입한다.

이 선택은 평가 결과를 바탕으로 작성자가 정한 기본안이다. 실제 보험 규칙과 운영 책임은 현업·보안 담당자가 검수하기 전 확정된 정책이 아니다.

## 4. 핵심 불변식 — 구현 완료 전 승인 금지

**I-01 신원/테넌트.** 인증된 서버 actor의 tenant만 사용한다. 대상 객체의 모든 조회·갱신·외래키에 tenant를 포함한다. body의 tenant_id, role, requester_id는 권한 증거가 아니다. 다른 tenant 객체는 일관된 404, 권한 불가 작업은 403. 인증 실패는 401. 접근 통제 회귀 전 실사용 금지.

**I-02 상태와 기록.** `DRAFT → PENDING_DOMAIN_REVIEW → PENDING_RELEASE → APPROVED_FOR_DEMO` 또는 검토/승인 반려 `REJECTED`. 평가의 DRAFT 내 revision 변경도 감사에 기록. `PENDING_RELEASE`에는 해당 change와 현재 revision 계열에 대해 정확히 하나의 유효한 DOMAIN/APPROVE note와 대응 audit event가 필요하며, note.actor = `domain_reviewer_id`, 요청자/owner와 달라야 한다. 최종 승인에는 유효한 release note/event 및 서로 다른 approver가 필요하다. 누락·중복·다른 tenant·순서 역전·status/reviewer/revision 불일치는 `409 EVIDENCE_RECORD_TAMPERED` 등 구조화 오류로 fail-closed.

**I-03 이벤트 모델.** 새로운 `ChangeTransition` 또는 동일 보장 스키마를 하나의 권위 있는 전이 로그로 도입한다. 최소 필드: `id, tenant_id, change_id, revision_from, revision_to, from_state, to_state, kind, actor_id, decision_id?, evidence_hash?, occurred_at`, 스키마 버전. `revision_to=revision_from+1`; 최초 생성은 `NONE/0 → DRAFT/1` genesis 전이, DRAFT 내 평가도 `DRAFT/n → DRAFT/n+1` 전이다. tenant+change+revision_to UNIQUE, genesis부터 revision 누락·중복·비연속·허용되지 않은 전이를 차단; 복합 FK로 tenant 연결. `Change.status/revision/actor IDs`는 최신 전이의 투영이며 검증 시 재계산해 대조한다. 새 버전의 이벤트는 동일 필드를 감사 이벤트와 해시로 결박한다. DRAFT 평가, 요청 생성, 제출, 승인·반려의 행과 event 생성은 같은 트랜잭션에서 전부 commit 또는 전부 rollback.

**I-04 기존 v5.1 데이터.** 과거 event에 전이 revision 등이 없기 때문에 빈 값에 임의로 사실을 채워 '검증 완료'로 만들지 않는다. 합성 새 DB는 신규 스키마로 생성. 이전 DB를 옮길 경우 `legacy-unverified`로 격리하고 원본 백업·마이그레이션 기록을 보존한다. 과거 승인 행을 자동으로 재승인하지 않는다. 실데이터 마이그레이션은 범위 밖. 누락된 감사 기록을 추측해 만들어서는 안 된다.

**I-05 잠금·동시성.** PostgreSQL 모든 상태변경 경로는 공통 순서 `tenant audit head → change row → 관련 결정/평가 → idempotency record`로 잠금 취득을 설계한다. 순서가 다른 기존 경로도 함께 바꾼다. `SELECT ... FOR UPDATE` 후 state+revision CAS와 고유 제약으로 하나만 commit한다. SQLite는 로컬 단일 worker 한정. 다중 세션·다중 worker와 잠금 타임아웃·deadlock·재시도는 실제 PostgreSQL에서 검증하기 전 운영 지원이라 부르지 않는다. 단, 락 순서는 구현 시 SQL 실행 순서와 FK/인덱스 잠금까지 확인한다.

**I-06 증거 해시 순환 방지.** 두 단계로 나눈다. (a) `assessment_manifest_v1`: tenant/change, **최종 승인 직전 pre-approval revision**, source/dataset/evaluator/model/prompt 해시, 그 revision까지의 평가 및 **기존 DOMAIN 결정과 이벤트 참조**를 포함하고 최종 승인 전에 canonical serialization 후 해시한다. 전이 event ID 집합과 포함 순서·revision 상한은 그 시점에 고정한다. 최종 승인으로 revision이 증가하더라도 assessment는 고정된 pre-approval 스냅샷에서 재구성하며 이후 event를 섞지 않는다. (b) 최종 승인 note/event는 그 hash를 참조한다. (c) `approval_envelope_v1`: (a)의 해시와 최종 승인 note/event ID·승인자·시각·버전을 포함한다. 봉인 envelope는 자신의 해시를 입력에 포함하지 않는다. 변경 이후 재계산값과 저장값·외부 앵커를 각각 확인한다. 저장 hash만 같은 DB에 있으면 신뢰 앵커가 아니다.

**I-07 재시도.** 최초 생성, 평가, 제출, 현업결정, 최종결정에 `Idempotency-Key`를 적용한다. 최소 스코프 `(tenant_id, actor_id, endpoint_operation, key)` UNIQUE, 키 길이 12–128. canonical request fingerprint에는 HTTP method, 정규화 route template, resource/change ID(생성에는 상수), body와 의미 있는 `expected_revision`을 명시적으로 포함한다. 같은 operation에서 다른 change ID에 같은 key를 재사용하면 다른 fingerprint이므로 409다. 결과 상태/응답, 생성시간, 완료 여부를 저장한다. 인증·권한·tenant 확인 후 동일 키+동일 본문은 원 결과를 재생하고, 같은 키+다른 본문은 409. 원 요청 성공 후 응답 유실 상태에서 재시도는 stale revision보다 기존 결과 재생을 먼저 한다. replay는 과거 처리 결과이고 현재 변경 상태·증거 무결성의 최신 판정이 아니며, 응답에 `replayed=true`와 결과 revision을 표시하고 최신 GET/증거 검증을 별도로 제공한다. 동시 요청은 하나만 결과를 생성하고 나머지는 대기/기록된 결과 또는 명시적 retryable 응답. 다른 actor가 키를 추측해 결과를 얻어선 안 된다. 별도 만료/정리 정책 도입 전 운영 데이터 삭제는 금지.

**I-08 입력과 스키마.** `Decision.reason`은 필수다. 입력 원문은 Unicode code point 기준 8–500자, Python `str.strip()`으로 앞뒤 공백을 제거한 후에도 8–500자여야 한다. 정규화 문자열을 기록하며 UI는 전송 전 trim할 수 있다. JSON Schema에 required/minLength/maxLength를 표시하고 공백·정규화 검증은 설명 및 런타임 테스트로 추가한다(스키마만으로 후처리 규칙 전체를 표현했다고 주장하지 않는다). `claim_days`는 런타임에서 JSON 정수만 허용하고 `true`, `1.0`, 문자열 `"30"`, 음수·상한 초과를 거부한다. JSON Schema의 integer는 수학적으로 1.0을 포함할 수 있으므로 이 더 엄격한 정책을 OpenAPI 설명/확장에 명시하고 실제 HTTP 요청으로 별도 시험한다. `Idempotency-Key`와 `X-Expected-Revision` 필수 여부는 각 endpoint의 OpenAPI에 반영.

**I-09 사람의 역할.** 각 change는 requester/owner, domain reviewer, release approver를 서로 다른 사용자 ID로 보장한다. 동일인이 여러 role을 가져도 자기 승인 불가. 토큰 탈취에 대한 강한 신원보증은 SSO/MFA 후속 단계까지 미구현. 현재 UI의 requester-only 평가 정책을 서버에서도 일치시키는 기본안이며, 대리평가가 필요하면 위임자·승인기록·권한 모델을 별도 설계한다.

**I-10 실패 정책.** 감사·출처·평가기 불일치, 빈 근거, 미완료 평가, 미검수 고위험, 최신 revision 충돌은 승인하지 않는다. `UNKNOWN`/`INCONCLUSIVE`는 PASS가 아니고 자동으로 해제할 수 없다. 클라이언트가 409를 받으면 새로고침하여 이유를 보여준다. DB 오류는 5xx, 실제 수행 여부가 불명인 경우 idempotency 재조회로 해결한다.

## 5. 다중 테넌트·DB 목표

- **G1**에서는 기존 SQLite에서만 P0 실재 여부를 TestClient + 임시 DB로 재현하고 고친다. `live_probes.py`는 결과를 출력하는 진단 도구이며, 자동 PASS/FAIL 기준이 아님. 별도의 assert 기반 회귀를 신규 테스트에 추가한다.
- **G2**에서는 PostgreSQL을 별도 시험 인스턴스로 설치하고 migration/role/RLS를 구현한다. app role은 슈퍼유저, 소유자, `BYPASSRLS`가 아닌 별도 역할이다. 모든 tenant 테이블에 `USING`과 `WITH CHECK`를 적용하고 `FORCE ROW LEVEL SECURITY`를 소유자 보완용으로 고려한다. 슈퍼유저/BYPASSRLS는 FORCE 여부와 무관하게 우회한다.
- 트랜잭션 시작 후 인증 서버가 얻은 tenant를 `set_config('app.tenant_id', :tenant, true)` 형태의 트랜잭션 로컬 값으로 전달하는 것은 방어층의 **예시**다. `current_setting(..., true)`가 null/빈 값이거나 context 오류인 경우 fail-closed. 연결 풀 재사용·rollback 뒤 tenant 누출 시험을 필수로 한다. 사용자 제공 값을 직접 신뢰하지 않는다.
- 이 GUC는 DB가 신원을 인증하는 장치가 아니다. SQL injection이나 app role을 장악한 공격자가 임의 tenant를 세팅할 수 있는 위협은 별도 DB 역할 분리·보안 브로커·인증된 context 설계가 필요하다. RLS만으로 침해된 애플리케이션 전체를 격리한다고 주장하지 않는다. FK/unique 등 무결성 검사로 인한 존재 정보 노출 가능성도 시험한다.
- 원문: [PostgreSQL RLS](https://www.postgresql.org/docs/17/ddl-rowsecurity.html), [transaction-local set_config](https://www.postgresql.org/docs/16/functions-admin.html), [lock ordering](https://www.postgresql.org/docs/current/sql-lock.html). 실제 DB·버전은 검증 로그에 기록한다.

## 6. 규정·사실관계 모델

- 별도 `PolicyPack`/`PolicySource`/`PolicyVersion`/`RiderVersion`/`Rule`의 테넌트·상품·업무 범위를 명시한다. 최소 필드: source ID, 제공처/권리, 원문 sha256, 승인 상태·승인자·승인 시각, 상품 ID, 보장/특약 ID, 적용 시작/종료(`[start,end)`), 등록 시작/종료, 업무 기준일 종류, 우선순위, 법무/현업 확인 상태, supersedes/withdrawn 정보.
- 평가 입력은 계약 체결일, 사고일, 청구일, 상담일, 특약 가입·해지 및 **가입 특약 확인 상태**를 별도 필드로 둔다. 비어 있는 특약 목록과 '확인되어 특약 없음'을 구별한다. API에 단일 `basis_date`만 있는 현재 버전으로 실제 계약 판단을 해서는 안 된다.
- 룰이 적용할 날짜 종류와 소급 여부는 업무팩이 정한다. 누락, 정본 미승인, 불명 특약, 같은 우선순위 충돌, 다른 상품/회사 문서, 등록시점 이전 자료, 승인자 없는 근거는 `INCONCLUSIVE`. 특약 후보가 DRAFT/REVOKED이고 영향 여부가 불명일 때 기본 규정으로 무조건 대체하지 않는다. 기본안은 보류이며, 실무자가 기본 규정 적용이 안전하다고 확인한 경우에만 정책을 버전 관리해 허용.
- 반례: 계약 6/30, 사고 7/01, 청구 8/01은 세 날짜가 각각 다른 버전을 가리킬 수 있다. 어떤 날짜가 법적으로 맞는지 이 문서가 확정하지 않는다. 허가받은 약관과 보험사 현업·법무 검수 전 실제 상품 적합성은 주장하지 않는다.

## 7. 사용자 업무 화면과 실패·복구

- **분석가:** 변경 작성 → 출처 범위와 기준시점 확인 → 동일 데이터셋 평가 → BLOCK/INCONCLUSIVE 원인 및 수정 지점 표시 → 새 불변 revision에서 재평가. 기존 실패 기록 삭제 금지.
- **현업 검토자:** 상품·계약 사실/특약·시점·출처 버전과 불확실성을 확인하고 이유 필수인 승인 또는 반려. 요청자와 동일인 거부.
- **승인자:** 평가 결과·심각 결함·현업 승인자·증거 hash의 유효성 확인 후 별도 승인. 데모와 실제 출시를 시각적으로 구별.
- **감사자:** 상태 전이, 원본·평가·결정, 해시·앵커 확인; 기록 누락·불일치를 정상/실패/미검증으로 구분.
- **시정:** `REJECTED`는 terminal로 유지한다. 새 `change_id`를 발급하고 동일 tenant의 `parent_change_id`로 반려 요청에 연결한다. 이전 승인·평가를 복사해 재사용하지 않고 새 요청에서 다시 검증한다. 원본 decision과 실패 이력은 보존. 중복 전송은 같은 결과, stale 충돌은 최신 상태·재시도 안내. 장애 시 데이터 조회를 못하면 승인 잠금, 추측값으로 성공 표시 금지.
- 접근성: 키보드만으로 주요 흐름, 레이블/초점/오류 안내, 상태색에 텍스트 병기, 작은 화면, 스크린리더 확인. 사용성 통과는 실사용자 시험 전 미검증.

## 8. 실증·운영 범위

LLM 연결 전 `FakeDeterministicAdapter`로 근거 구조와 불확실성 테스트. 실제 모델 도입 시 모델/프롬프트/데이터셋/출처 버전, 요청·응답 해시, 토큰·비용·지연, 도구 허용 범위, 텍스트 안전 정책과 egress를 기록하되 민감 원문·비밀은 로그에 남기지 않는다. 프롬프트 인젝션·조작 인용은 실제 모델/문서 처리 연결 전 `N/A(미구현)`로만 기록한다.

WORM, KMS 분리, 서명, 백업/복구, SSO/MFA, 모니터링, 보안인증은 미구현. 제3자 실무·Windows 설치·모의훈련·기술리뷰는 외부인 실증 없이는 0점. 공급사 기능은 공식 라이선스·개인정보 경계 재검토 후 연결하며, `sources_table.csv`의 과거 확인 시점에 주의한다.
