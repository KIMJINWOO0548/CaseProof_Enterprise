# v5.3 구현 계약 — API·전이·증거·실험 정본

**PLANNED — 앞으로 구현할 v1 계약의 정본. 현재 baseline 코드의 기능 설명이 아니다.** 기존 v5.1 합성 서비스의 `/api`는 legacy demo이고, 아래 신규 계약은 `/api/v1`이다. v5.3 패키지의 최종 저장소 루트에는 `service/`, `reference/`, `tests/`, `prebuild/`를 둔다. `current/`라는 중간 디렉터리를 새 코드 경로로 만들지 않는다. baseline P0·입력 보강만 수행한 경우 ‘baseline hardening’으로 기록하며 G1 전체 완료와 구별한다.

## 1. 신원, ID, 문자열 및 시간

- tenant/actor는 인증 provider의 서버 결과만 사용한다. create 시 `requester_id = owner_id = actor.id`; v1에는 소유자 변경 API가 없다. reviewer와 release approver는 requester/owner 및 서로 다른 사람이다.
- API가 발급하는 object ID는 lowercase UUIDv4 문자열이다. 기존 tenant/user/synthetic pack 식별자는 등록된 ASCII 식별자이며 범위는 `[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}`이다. 동일 tenant 내 ID의 의미를 바꾸어 재사용하지 않는다.
- timestamp의 wire/hash 형식은 UTC `YYYY-MM-DDTHH:mm:ss.ffffffZ` 하나다. 입력 offset timestamp는 같은 instant의 UTC로 정규화한다. 업무 날짜는 `YYYY-MM-DD`, pack의 `business_timezone`은 필수 IANA ID다. 날짜를 임의 UTC timestamp로 변환하지 않는다.
- `Decision.reason`은 원 입력과 Python `str.strip()` 결과 각각 8–500 Unicode code point이다. 정규화 결과만 저장한다. NFC/NFD 등 추가 Unicode 정규화는 하지 않는다. surrogate code point는 거부한다. claim_days는 JSON 정수 0–9999이며 boolean/float/string을 거부한다.
- 모든 request DTO는 `extra=forbid`; duplicate JSON object key, NaN/Infinity, invalid UTF-8, lone surrogate를 422로 거부한다. body의 tenant_id/actor_id/roles/expected_revision을 권한·revision 입력으로 허용하지 않는다.

## 2. canonical bytes와 hash

규격 이름은 `caseproof.c14n.v1`이다. RFC 8785 전체 구현이라고 부르지 않는다. 허용 값은 object(string key), array, string, boolean, null, 정수 `[-9007199254740991,9007199254740991]`이며 float/decimal은 금지한다. 비용·지연의 소수는 각각 정수 micro-USD, 정수 millisecond로 기록한다.

1. object key는 Unicode code point 오름차순. 모든 protocol key는 ASCII로 고정한다. array 순서는 의미가 있으며 각 payload 아래의 정렬 규칙을 따른다.
2. UTF-8, BOM 없음, 마지막 newline 없음. JSON separator는 `,`와 `:`이며 whitespace 없음. non-ASCII는 UTF-8 원문으로 내보낸다. `"`와 `\\`, 표준 control escape(`\b\f\n\r\t`)를 escape하고 나머지 U+0000–001F는 lowercase `\u00xx`로 escape한다. slash는 escape하지 않는다. 문자열의 Unicode code point를 보존한다.
3. optional protocol field는 생략하지 않고 null을 넣는다. empty array/object는 null과 다르다. DTO default를 적용한 후 hash한다. sets는 없으며 정렬된 array를 쓴다.
4. `C(payload)`는 위 bytes이다. `H(purpose,payload) = SHA256(UTF8("caseproof:" + purpose + ":v1\n") || C(payload))`의 lowercase hex이다. purpose는 아래 계약별 고정 ASCII 값이다. 자기 자신의 hash 필드는 payload에 없다. 참조 대상의 hash는 포함할 수 있다.
5. 파일 bytes는 `SHA256(original_bytes)`로 별도 계산하고 필드 이름은 `blob_sha256`이다. normalized metadata의 `payload_sha256`과 혼용하지 않는다. evaluator code hash는 파일별 path/bytes hash를 정렬한 manifest를 hash하며 단순 파일 bytes 이어붙이기를 사용하지 않는다.

구현자는 `tests/fixtures/canonical_vectors_v1.json`에 한국어 조합형/분해형, newline, quote, reverse key order, bool/int, null/empty, UTC 변환, 서로 다른 purpose를 포함한 input/canonical_utf8_hex/hash를 한 번 고정한다. 독립 verifier가 같은 vector를 통과하기 전 다른 언어의 직렬화기로 대체하지 않는다. 이 문서는 vector 실행 완료를 주장하지 않는다.

## 3. revision과 불변 snapshot

`change.revision`은 내용 버전이 아니라 **성공적으로 commit된 workflow 전이의 연속 번호**다. genesis는 1이고 모든 전이는 `to=from+1`이다. `candidate_snapshot_id`는 평가할 candidate/model/prompt/config의 불변 내용 버전이다. submit/domain/release로 workflow revision이 증가해도 candidate가 같으면 기존 run의 내용 신원은 유지된다.

v1 change의 title, pack/product/workflow/rule scope, requester/owner, candidate/source bundle/dataset/suite/evaluator snapshot ID는 create 후 수정하지 않는다. 내용·출처·모델·프롬프트를 바꾸려면 새 change를 만든다. 교정된 답변으로 재평가하는 숫자 demo는 같은 candidate 설정 하에서 case run input이 달라질 수 있으나 각 run input 전체를 봉인하고 평가 완료 전 결과를 고치지 않는다. 실제 candidate 수정은 반드시 새 snapshot/new change이다.

`ChangeRevision`은 `(tenant_id,change_id,revision)` PK이며 매 전이마다 한 행을 추가한다. payload에는 아래 전 필드가 있다.

```text
schema, tenant_id, change_id, revision, status,
title, pack_version_id, product_id, workflow, rule_key,
requester_id, owner_id, domain_reviewer_id|null, release_approver_id|null,
candidate_snapshot_id, source_bundle_id, dataset_version_id, suite_version_id,
evaluator_version_id, active_run_id|null, active_job_id|null,
parent_change_id|null, parent_relation|null,
assessment_sha256|null, created_at, updated_at
```

`snapshot_sha256 = H("change-revision",payload)`이다. `Change`는 최신 revision의 투영 및 조회용 pointer이다. 승인 envelope hash는 Change의 별도 projection 필드로만 저장하고 ChangeRevision payload에 넣지 않는다. verifier는 genesis부터 모든 전이와 snapshot을 재구성한 뒤 최신 Change projection과 비교한다. timestamp를 순서의 근거로 사용하지 않는다.

`parent_relation`은 null, `CORRECTS_REJECTED`, `REPLACES_DRAFT`, `FOLLOWS_APPROVED` 중 하나다. parent는 같은 tenant의 기존 change이고 새 child로 방향이 정해져 cycle이 없다. parent 조회 권한을 확인한다. 어떤 관계도 과거 평가/승인을 새 change의 gate 근거로 복사하지 않는다. REJECTED/APPROVED_FOR_DEMO는 terminal이다.

## 4. 상태/행/event의 정확한 대응

| kind | from → to | actor | 필수 부속 기록 |
|---|---|---|---|
| CHANGE_CREATED | NONE/0 → DRAFT/1 | ANALYST | genesis snapshot |
| EVALUATION_RECORDED | DRAFT/n → DRAFT/n+1 | requester + ANALYST | 불변 full-suite EvaluationRun 1개 |
| SUBMITTED_FOR_DOMAIN_REVIEW | DRAFT/n → PENDING_DOMAIN_REVIEW/n+1 | requester + ANALYST | 최신 run gate PASS, 선정 run ID 고정 |
| DOMAIN_APPROVE | PENDING_DOMAIN_REVIEW/n → PENDING_RELEASE/n+1 | DOMAIN_REVIEWER | DOMAIN/APPROVE DecisionNote 1개 |
| DOMAIN_REJECT | PENDING_DOMAIN_REVIEW/n → REJECTED/n+1 | DOMAIN_REVIEWER | DOMAIN/REJECT DecisionNote 1개 |
| APPROVED_FOR_DEMO | PENDING_RELEASE/n → APPROVED_FOR_DEMO/n+1 | RELEASE_APPROVER | RELEASE/APPROVE note, assessment, envelope |
| RELEASE_REJECT | PENDING_RELEASE/n → REJECTED/n+1 | RELEASE_APPROVER | RELEASE/REJECT note 1개 |

각 전이는 정확히 ChangeRevision 1개와 ChangeTransition 1개와 AuditEvent 1개에 대응한다. 모든 kind에 integrity/state/revision 검사를 적용한다. reject도 변조된 기록 위에 정상 결정인 것처럼 쓰지 않는다. API 요청 거절 자체는 workflow 전이가 아니며 별도의 보안 운영 로그에 남긴다. tenant audit chain에 요청 거절을 append해 승인 lock을 역취득하지 않는다.

`DecisionNote` payload는 `schema,tenant_id,id,change_id,stage,decision,actor_id,input_revision,output_revision,reason,occurred_at,assessment_sha256|null`이다. `H("decision",payload)`로 hash한다. DOMAIN note는 assessment=null; release APPROVE만 고정 assessment hash를 참조한다. `(tenant,change,stage)` UNIQUE이므로 같은 단계에서 두 결정은 없다. REJECTED에서 재결정도 없다.

`ChangeTransition` payload는 `schema,tenant_id,id,change_id,revision_from,revision_to,from_state,to_state,kind,actor_id,occurred_at,previous_snapshot_sha256|null,next_snapshot_sha256,evaluation_run_id|null,evaluation_run_sha256|null,decision_id|null,decision_sha256|null,assessment_sha256|null`이다. `H("transition",payload)`로 hash한다. kind별 null/필수 필드 조합을 검증한다.

`AuditEvent` payload는 `schema,tenant_id,id,sequence,prev_hash,actor_id,occurred_at,subject_type="CHANGE",subject_id,kind,transition_id,transition_sha256`이다. `H("audit-event",payload)`로 hash한다. tenant sequence는 1부터 연속이며 최초 prev_hash는 64개의 `0`이다. event와 transition의 tenant/actor/kind/time/subject가 일치해야 한다. transition hash는 audit hash를 포함하지 않는다.

## 5. 불변 테이블과 FK/UNIQUE

| 대상 | 최소 key/제약 | 변경 정책 |
|---|---|---|
| TenantAuditHead | tenant PK; sequence>=0, 64hex head | app는 sequence/head만 갱신 |
| Change | `(tenant,id)` UNIQUE; latest revision FK | projection 갱신; DELETE 금지 |
| ChangeRevision | `(tenant,change,revision)` PK | INSERT/SELECT만 |
| ChangeTransition | `(tenant,id)` UNIQUE; `(tenant,change,revision_to)` UNIQUE; next revision FK | INSERT/SELECT만 |
| AuditEvent | `(tenant,id)` UNIQUE; `(tenant,sequence)` UNIQUE; `(tenant,transition_id)` UNIQUE | INSERT/SELECT만 |
| DecisionNote | `(tenant,id)` UNIQUE; `(tenant,change,stage)` UNIQUE | INSERT/SELECT만 |
| EvaluationRun | `(tenant,id)` UNIQUE; `(tenant,change,recorded_revision)` UNIQUE | INSERT/SELECT만 |
| Source/Policy/Candidate/Dataset/Suite/Evaluator snapshots | `(tenant,id)` UNIQUE, explicit schema/hash | INSERT/SELECT만; 새 version으로 변경 |
| Assessment/ApprovalEnvelope | `(tenant,change)` UNIQUE 각각; hash와 canonical bytes 보관 | INSERT/SELECT만 |
| IdempotencyRecord | `(tenant,actor,key)` UNIQUE | 성공 결과와 같은 tx에서 INSERT; 보관 정책 전 삭제 금지 |

모든 tenant 간 참조는 대상의 `(tenant,id)` 또는 전체 PK를 쓰는 복합 FK이다. actor FK도 동일하다. `Change.latest_revision`과 revision/transition의 참조로 생기는 INSERT 순환은 신규 Change skeleton → snapshot/transition/side rows → Change pointer 순서 및 필요한 명시적 deferred FK로 처리한다. SQLite/PG의 실제 DDL과 flush 순서를 검증한다. skeleton에는 승인 가능 status를 두지 않고 transaction 밖으로 commit하지 않는다. 더 간단하게 latest_revision FK를 생략할 경우 그 생략을 migration에 명시하고 verifier 및 원자성 테스트로 같은 invariant를 검증한다. 두 방식을 구현자가 임의 혼합하지 않는다.

기본 선택은 **latest_revision FK를 생략**하고 Change에 `(tenant,id)`를 먼저 insert한 뒤 모든 child의 FK를 Change에 건다. Change의 revision/status projection 정합성은 매 mutation verifier와 CHECK/UNIQUE로 검사한다. 이를 완전한 DB-only invariant라고 주장하지 않는다. app role에는 불변 표의 UPDATE/DELETE를 주지 않는다. owner/migrator로 그 권한을 우회한 전체 재작성은 외부 앵커 이전에는 막았다고 주장하지 않는다.

## 6. 평가 run과 승인 gate

`EvaluationRun`은 한 full-suite 실행의 immutable 결과다. 필드: `schema,id,tenant_id,change_id,recorded_revision,actor_id,created_at,candidate_snapshot_id,source_bundle_id,dataset_version_id,suite_version_id,evaluator_version_id,adapter_version_id,run_input_sha256,run_config_sha256,case_results,completion,gate_summary`이다. case_results는 case_id 오름차순이고 duplicate 금지. source/dataset/evaluator/model/prompt hashes는 해당 immutable snapshot을 통해 전부 해소 가능해야 한다.

suite manifest는 `required_case_ids`, 각 case의 approved source/version 범위, required coverage labels, `minimum_distinct_policy_versions`를 버전 관리한다. 기존 synthetic scope를 승계하는 suite는 최소 2개의 서로 다른 approved policy_version ID를 요구한다. 규정 row ID 개수를 policy version 수로 대신하지 않는다. 새 pack에서 1개 version만 존재하면 2를 무조건 요구하지 않고 **검토된 별도 suite version**으로 coverage를 명시한다.

case result는 `case_id,input_sha256,output_sha256,source_refs,resolution_status,verdict,complete,error_code|null,critical_failure|null`을 갖는다. complete=false면 verdict는 INCONCLUSIVE, critical_failure는 null이고 원인을 기록한다. 성공 판정으로 채워 넣지 않는다. `completion=COMPLETE`는 모든 required case가 정확히 한 번 있고 모두 complete=true일 때뿐이다. `gate_summary=PASS`는 complete, coverage 충족, 모든 required verdict PASS, critical_failure 없음, 검수 veto 없음, 모든 snapshot/권한/source 유효성을 동시에 만족할 때뿐이다.

선정 규칙은 `recorded_revision`이 가장 큰 committed run 하나다. 그 run이 INCOMPLETE/BLOCK이면 이전 PASS를 선택할 수 없다. 새 run은 suite 전체를 다시 실행한다. 오래된 실패를 지우거나 일부 PASS만 모아서 suite를 합성하지 않는다. submit 시 selected_run_id를 snapshot에 고정하고 이후 평가 API는 상태 오류다. approval의 hash에는 선정 run뿐 아니라 해당 change의 이전 run ID/hash도 포함한다.

G1의 `/evaluation-runs`는 `FakeDeterministicAdapter`의 제한된 동기 실행만 지원한다. 입력은 `{suite_version_id, case_inputs}`이고 case_inputs는 suite의 case_id를 정확히 한 번씩 포함하는 typed input 목록이다. 모델·프롬프트·source·evaluator는 Change snapshot에서 결정된다. target 숫자 합성 adapter에서 각 input은 `case_id,claim_days,case_context`; G3에서 context는 계약/사고/청구/상담 날짜·rider facts·recorded_as_of를 포함한다. 예상 정답은 이 DTO에 없다. 실패 결과도 run으로 commit되면 HTTP 201이며 run.completion/gate_summary로 표시한다. HTTP 성공과 평가 PASS를 혼용하지 않는다.

### 6.1 dev6 execution-config version boundary

새 runtime 실행은 `evaluation_run_v2`이며 `H("run-config-v2", {schema:"execution_config_v2", candidate_snapshot, source_bundle, dataset, suite, evaluator, model, prompt, adapter})`로 평가 당시 전체 snapshot을 고정한다. source/policy는 bundle member의 ID/hash와 실제 bytes를 대조해 결합한다. V1 저장 bytes와 원본 schema/예제는 보존하고 신규 승인에 재사용하지 않는다. V1 history는 409 `EXECUTION_CONFIG_UNVERIFIED`, 인증된 조회는 `LEGACY_UNVERIFIED`와 null immutable refs를 반환한다. 자동 재해시·형식 변환·DB 삭제는 없다. [명시 경계와 새 프로필 절차](../docs/EXECUTION_CONFIG.md)를 따른다.

## 7. assessment와 approval envelope의 비순환 계약

release APPROVE에서 tenant head와 change를 잠근 뒤 승인 직전 revision을 `p`, tenant audit head의 sequence/hash를 `a`로 고정한다. 다음 순서 외에는 허용하지 않는다.

1. `p`까지 integrity 및 full-suite gate, DOMAIN note/event, source의 현재 신규 승인 가능 여부를 검증한다.
2. assessment payload를 만든다. 필드: `schema="assessment_manifest_v1",tenant_id,change_id,preapproval_revision=p,preapproval_snapshot_sha256,tenant_audit_checkpoint={sequence,head_sha256},candidate_snapshot_ref,source_bundle_ref,dataset_ref,suite_ref,evaluator_ref,model_ref|null,prompt_ref|null,selected_run_id,run_refs,decision_refs,transition_refs,source_eligibility_snapshot_ref`.
3. ref는 ID와 해당 immutable payload SHA-256의 쌍이다. run_refs는 recorded_revision/ID, decision_refs는 output_revision/ID, transition_refs는 revision_to 순이다. transition ref에는 transition ID/hash와 대응 audit event ID/sequence/hash를 포함한다. 해당 change의 모든 1..p 전이를 포함하고 p 이후는 제외한다. source bundle의 내용은 당시 고정한 version/bytes만 사용한다.
4. `assessment_sha256 = H("assessment",payload)`를 저장한다. 새 release DecisionNote, p+1 snapshot, transition, audit event는 이 hash를 참조한다. 각각의 ID와 동일 occurred_at은 hash 계산 전에 서버가 발급한다.
5. envelope payload는 `schema="approval_envelope_v1",tenant_id,change_id,preapproval_revision=p,approved_revision=p+1,assessment_sha256,release_decision_ref,release_transition_ref,release_event_ref,approved_snapshot_sha256,approver_id,approved_at`이다. `H("approval-envelope",payload)`를 계산한다. envelope 자신의 hash는 포함하지 않는다. release event 역시 envelope hash를 참조하지 않는다.
6. 모든 행, Change projection, tenant head, 성공 idempotency 응답을 한 transaction으로 commit한다. envelope 외부 앵커는 후속 단계이며 실패 시 존재하지 않는 앵커를 ‘verified’로 표시하지 않는다.

`GET evidence`는 저장 bytes를 다시 hash하는 것만으로 검증하지 않는다. 고정 범위의 실제 source/run/decision/snapshot/transition/event를 재구성하여 저장 manifest와 비교한다. 누락/추가/중복/순서/field 변경을 검출한다. 결과는 `historical_integrity=VALID|INVALID|LEGACY_UNVERIFIED`, `current_approval_eligibility=ELIGIBLE|BLOCKED|NOT_APPLICABLE`, `external_anchor=NOT_CONFIGURED|UNVERIFIED|VERIFIED|FAILED`로 구분한다. 승인 전에는 approved_revision/envelope hash가 null이다. 관련 없는 후속 tenant event나 새 source version의 존재만으로 봉인 hash가 바뀌지 않는다.

현재 source가 철회되면 신규 승인은 BLOCKED이며 기존 envelope의 historical integrity는 별개다. source status history는 append-only이고 assessment의 `source_eligibility_snapshot_ref`는 승인 시점의 검사 결과 및 적용한 policy version을 고정한다. 사후 철회를 과거 payload에 덮어쓰지 않는다.

## 8. `/api/v1` endpoint/DTO

모든 mutation에 `Idempotency-Key`가 필수다. `[A-Za-z0-9_-]{12,128}` ASCII로 제한하며 case-sensitive이고 trim하지 않는다. create를 제외한 mutation은 `X-Expected-Revision` ASCII 양의 십진 정수(leading zero 금지)가 필수다. create에 이 header를 보내면 422이다. 공통 mutation 응답은 `{data,result_revision,replayed}`이다. data는 당시 결과의 snapshot이며 replay에서 최신 상태로 바꾸지 않는다.

| method/path | body | 성공 |
|---|---|---|
| POST `/api/v1/changes` | title, pack_version_id, product_id, workflow, rule_key, candidate_snapshot_id, source_bundle_id, dataset_version_id, suite_version_id, evaluator_version_id, parent_change_id?, parent_relation? | 201, DRAFT revision 1 |
| POST `/api/v1/changes/{change_id}/evaluation-runs` | suite_version_id, case_inputs | 201, run summary + DRAFT revision n+1 |
| POST `/api/v1/changes/{change_id}/submit` | `{}` | 200, PENDING_DOMAIN_REVIEW n+1 |
| POST `/api/v1/changes/{change_id}/domain-decision` | decision: APPROVE\|REJECT, reason | 200, PENDING_RELEASE 또는 REJECTED n+1 |
| POST `/api/v1/changes/{change_id}/release-decision` | decision: APPROVE\|REJECT, reason | 200, APPROVED_FOR_DEMO 또는 REJECTED n+1 |
| GET `/api/v1/changes/{change_id}` | 없음 | 200, 현재 projection 및 최신 run; integrity 상태 별도 |
| GET `/api/v1/changes/{change_id}/evidence` | 없음 | 200, 검증 결과와 immutable refs; INVALID도 진단 data로 반환 |
| GET `/api/v1/mutations/{key}` | 없음; 현재 actor key 공간만 | 200, committed 결과와 original_status; 없음 404 |

source/model/etc ID는 같은 tenant의 승인된 snapshot이어야 한다. unknown/tampered/revoked는 아래 error 계약을 따른다. list/get의 모든 본문은 현재 actor에게 권한 있는 tenant 자료만 포함한다. 원문 gold/credential이나 다른 tenant 존재 여부는 반환하지 않는다. GET evidence의 `INVALID`와 mutable endpoint의 409 차이는 의도된 진단 계약이다.

## 9. idempotency, 트랜잭션과 잠금

fingerprint payload는 `schema,method,route_template,resource_id,body,expected_revision`이다. method는 uppercase, route_template은 위 표의 고정 path, create resource_id는 literal `NEW`, 나머지는 UUID, create expected_revision은 null이다. body는 DTO 검증/정규화/default 적용 후 object이다. query parameter는 해당 mutation에서 허용하지 않는다. `H("request",payload)`를 사용한다. 동일 payload의 JSON whitespace/key 순서 차이는 같은 요청이고, trim으로 같은 reason이 된 입력도 같은 요청이다.

IdempotencyRecord의 필드는 `tenant_id,actor_id,key,request_sha256,method,route_template,resource_id,response_status,response_data_json,result_revision,created_at,completed_at,completion="COMMITTED"`이다. UNIQUE는 **(tenant_id,actor_id,key)** 이며 operation을 추가하지 않는다. 최초 응답은 replayed=false, replay는 나머지 status/data/result_revision을 보존하고 replayed=true만 바꾼다. HTTP 201도 재생한다. token 값 자체는 key/fingerprint에 넣지 않는다.

mutation의 authoritative 처리 순서:

1. 서버 token 인증 및 현재 actor.enabled/role 확인. tenant context를 설정한 transaction에서 resource가 현재 tenant에 있는지와 현재 actor의 객체 권한을 확인한다. 실패는 idempotency 조회 전에 끝낸다.
2. tenant audit head → change(creation은 새 ID) → 관련 source/job/run/decision 행의 table/PK 오름차순 → idempotency record 순서로 잠금한다. 최초 비잠금 read는 최적화일 뿐 결과 판단 근거로 쓰지 않는다. 한 tenant의 mutation은 head lock으로 직렬화한다.
3. 해당 key의 committed record가 있으면 fingerprint 비교 후 replay 또는 409 IDEMPOTENCY_CONFLICT. 이 검사는 state/revision freshness보다 먼저다. replay는 원 처리 결과이며 현재 evidence 유효성을 새로 보증하지 않는다. audit head row의 이상은 별도 evidence 진단으로 보고한다.
4. 신규 key이면 integrity → 상태/role separation → expected revision → gate를 확인한다. DB current revision과 request revision 및 update CAS가 모두 맞아야 한다. 잘못된 state/revision은 성공 record를 만들지 않는다.
5. G1 fake deterministic 계산과 모든 부속 row/hash 생성 후 CAS, tenant audit append, 성공 record를 같은 transaction에 넣고 commit한다. 그 뒤 response를 전송한다. 중간 오류는 모두 rollback한다. reservation만 먼저 commit하지 않는다.

실패한 401/403/404/409/422/5xx는 IdempotencyRecord에 성공 결과처럼 보관하지 않는다. 실패에도 HTTP audit/trace가 필요하면 별도 운영 로그로 기록한다. successful commit 후 socket 유실은 같은 key로 복구한다. commit 여부를 서버도 모르는 DB 연결 오류는 503 OUTCOME_UNKNOWN이고 새 key 사용을 권하지 않는다. 불변 key를 GET 또는 POST 재전송으로 재조회한다.

lock timeout/deadlock은 transaction 전체 rollback 후 503 RETRYABLE_CONFLICT, `Retry-After: 1`을 반환한다. 서버 내부 무제한 재실행은 하지 않는다. 클라이언트는 같은 key/body/revision으로 제한된 재시도(1s,2s,4s 후 사용자 안내)를 한다. stale revision 후 사용자가 새 현재 상태에 대한 새 동작을 선택할 때만 새 key를 발급한다. SQLite는 single worker synthetic 한정이며 PG lock 보장의 대체 증거가 아니다.

tenant lock은 성능상 강한 직렬화다. scale 보장으로 홍보하지 않는다. 외부 모델 호출/네트워크 I/O를 이 transaction 안에서 수행하지 않는다. G5 job extension이 구현되기 전 실제 provider adapter는 활성화하지 않는다.

## 10. 오류 표준과 우선순위

body: `{error:{code,message,retryable,request_id,details}}`; details는 allowlist이고 DB SQL/credential/다른 tenant ID/민감 원문은 금지한다. 같은 tenant의 STALE_REVISION에는 current_revision을 포함할 수 있다.

| HTTP | code | retryable / 의미 |
|---|---|---|
| 401 | UNAUTHENTICATED | false; unknown/disabled token 동일 외부 설명 |
| 403 | FORBIDDEN, REQUESTER_ONLY, SEPARATION_OF_DUTIES | false; 인증됨, 작업 권한 없음 |
| 404 | NOT_FOUND | false; 존재하지 않거나 다른 tenant 객체 |
| 409 | IDEMPOTENCY_CONFLICT | false; 같은 actor key의 의미가 다름 |
| 409 | AUDIT_INTEGRITY_FAILURE, EVIDENCE_RECORD_TAMPERED | false; 자동 복구/승인 금지 |
| 409 | INVALID_STATUS, STALE_REVISION | false; 현재 상태를 읽고 사용자 동작을 다시 결정 |
| 409 | EVALUATION_INCOMPLETE, RELEASE_GATE_BLOCKED, SOURCE_NOT_ELIGIBLE, SNAPSHOT_MISMATCH | false; 원인 수정 또는 새 change/run 필요 |
| 422 | INVALID_REQUEST | false; DTO/header/JSON 유효성 실패; fields allowlist |
| 503 | RETRYABLE_CONFLICT | true; 전체 rollback이 확인됨 |
| 503 | OUTCOME_UNKNOWN | true; 동일 key 조회/재전송으로 확인 |
| 500 | INTERNAL_ERROR | false; request_id만 노출, 운영자 조사 |

서버/프레임워크가 HTTP envelope를 파싱할 수 있어야 인증한다. resource 유효성 판정은 인증→같은 tenant 조회→권한→idempotency→integrity→state→revision→gate 순서를 따른다. 일반 input validation이 먼저 반환되는 경우에도 tenant 존재를 유추할 내용을 포함하지 않는다. 타 tenant 접근은 state·role·hash 오류를 반환하지 않고 404이다.

## 11. RLS와 인증 부트스트랩

G2 합성 기본안은 `DemoTokenAuthenticator`다. CLI가 고엔트로피 demo token을 발급할 때 별도 서버 소유 registry에 `token_sha256 -> {tenant_id,actor_id}`를 기록한다. registry는 untracked local secret 파일이고 예제 파일에는 fake values만 둔다. app role의 tenant User 테이블 전역 조회를 인증 부트스트랩으로 사용하지 않는다.

1. Authorization Bearer token digest를 registry에서 찾는다. 누락은 401. registry의 duplicate digest/unknown format/빈 값은 startup 실패다.
2. DB transaction을 시작하고 registry에서 얻은 tenant만 transaction-local `app.tenant_id`로 설정한다. request body/header/query tenant는 세팅하지 않는다.
3. 같은 tenant의 User id를 조회해 enabled와 역할을 검증한다. registry가 가리킨 User가 없거나 disabled면 401. role은 registry나 token claim이 아니라 현재 DB User에서 읽는다.
4. 정상 요청만 scoped read/write를 수행한다. 모든 종료 경로에서 transaction을 commit/rollback하고 session을 닫는다. 이 설정을 connection/session 수명 전체의 tenant로 유지하지 않는다.

User를 포함한 모든 tenant 표는 non-owner/NOBYPASSRLS app role 기준 USING과 WITH CHECK가 필요하다. 미설정/null/빈 context는 read 0행/write 거부이다. migration/seed는 별도 owner 자격으로 빈 disposable DB에만 실행하고 런타임 자격과 섞지 않는다. table owner/FORCE/BYPASSRLS 및 GUC 위협 한계는 기존 설계를 유지한다. 이 demo registry는 SSO/MFA/침해된 app role에 대한 DB 인증 경계가 아니다. SSO adapter는 검증된 외부 subject→tenant membership 매핑을 내보내도록 이후 별도 구현한다.

필수 G2 테스트: 정상 인증, unknown token, disabled user, registry 누락/중복, context 미설정 SELECT/INSERT, A→rollback→B 동일 connection, A→예외→context 없음, 전 표의 cross-tenant FK/UPDATE/DELETE, replay role 회수, owner가 아닌 app role 확인. 최소 SQL/DB 버전/role/worker 수를 로그에 남긴다.

## 12. G3 source/time 판정의 최소 결정

pack은 business_timezone, query/workflow별 required date fields와 date_basis, retroactivity_policy_id, versioned priority rule을 필수로 가진다. `[valid_from,valid_to)`는 업무 날짜, `[recorded_from,recorded_to)`와 source approval history는 UTC instant이다. end=null은 무한대이다. from>=to는 등록 실패다.

case_context는 `contract_date,incident_date,claim_date,consultation_date,rider_context_status,riders,recorded_as_of`를 구분한다. rider에는 code/enrolled_from/enrolled_to 및 확인 근거 ID가 있다. `CONFIRMED + []`는 확인된 무특약, UNKNOWN은 불확실이다. 필수 날짜 또는 rider 맥락이 없거나 contradiction이면 INCONCLUSIVE이다. 알 수 없는 rider나 영향 불명 DRAFT/REVOKED 상위 특약을 제외하고 base rule로 내려가지 않는다.

정본 candidate 선택 순서는 tenant/pack/product/workflow → recorded_as_of 때 알려진 source/status → versioned date_basis의 business date → 가입 rider와 적용 범위 → 승인된 우선순위이다. 같은 최고 우선순위의 상충 후보, 소급 정책 미검수, 단일 date basis 미확정은 INCONCLUSIVE/POLICY_CONFLICT이다. 판단 기록에는 후보 집합·제외 사유·선택 source/version/clause ID와 as-of를 남긴다. 이 알고리즘은 합성 업무 규격이며 실제 보험 약관 법적 해석을 확정하지 않는다.

## 13. 공개 데이터와 private blind 경계

고정 목표는 개발 160/검증 80/private blind 120이다. 공개 저장소가 이 360건을 모두 갖춘다고 가정하지 않는다. 공개 dev/demo fixtures 수와 실제 independently reviewed/blind 수를 따로 기록한다. private holdout과 custodian이 없으면 blind 결과는 SKIPPED이고 120건을 임의 생성하여 완료로 세지 않는다.

| DTO / 저장 위치 | 내용 | adapter 접근 |
|---|---|---|
| CaseInput / public 또는 custodian runner | opaque case_id, query, context_snapshot, source_bundle_id, business_as_of, recorded_as_of | allowlist 필드만 허용 |
| CaseMetadata / evaluator manifest | scenario_family, document_family, contract/incident group, split, pack/product, versions | model prompt 제외 |
| GoldRecord / evaluator-private | case_id, ground_truth_status, expected_claim_or_constraint, expected_reason, allowed_citation_spans, severity, risk_present, rubric_version, annotator/adjudicator evidence | 절대 전달 금지 |

dataset_manifest는 세 payload의 version/hash와 split/group 정의를 별도로 묶는다. private file path, gold content/hash의 역추정 가능한 case별 단순 commitment, 정답 annotation을 model/일반 UI/공개 repo에 내보내지 않는다. hash는 접근 통제·비밀성 자체가 아니다. blind custodian은 gold와 실행 전 frozen manifest를 별도 관리하고 실행자는 모델 입력과 익명화된 system 설정만 받는다. 독립 검수자 2명 이상 및 불일치 조정 이력이 없으면 SME reviewed=false다.

group split은 공유 문서 원본/상품 가족/계약·사고/시나리오 파생형 관계의 연결 성분을 하나의 group으로 묶어 어느 split에도 중복 배치하지 않는다. 고정 160/80/120이 이 원칙과 충돌하면 group을 쪼개지 말고 추가 사례를 확보하여 수를 맞춘다. split 전에 group manifest를 봉인한다. 블라인드 사례/정답/상세 오류를 보고 수정에 사용하면 exposed_at을 기록하고 다음 confirmatory 결과에는 새 holdout을 쓴다. 공개 사례를 미래의 genuinely blind 데이터라고 다시 부르지 않는다.

필수 자동검사: repo/package private-gold exclusion, adapter payload allowlist, source/case group disjointness, source hash 일치, public manifest와 private manifest ID 정합성. 사람이 gold를 보지 않았다는 주장은 자동검사만으로 증명하지 않는다.

## 14. 비교 지표의 정확한 계산

paired run의 case IDs는 duplicate 없는 동일 비어 있지 않은 집합이어야 한다. input/source/dataset/gold/rubric/evaluator hashes, budget/timeout/retry 정책을 비교한다. B0/B1/B2/T의 의도된 차이는 사전 등록 `comparison_spec.allowed_differences`에만 허용한다. 모델 사용 여부 자체가 다른 B0에 동일 model을 요구하는 식의 모순된 비교를 하지 않는다. 모델/version/temperature/seed/max tokens/권한/인프라/측정 구간은 기록하고 고정할 수 없는 provider 요인은 한계로 밝힌다.

case result는 `complete:boolean, correct:boolean|null, critical_failure:boolean|null, risk_flagged:boolean|null`이다. severity와 risk_present는 GoldRecord에서 읽고 양측 결과가 수정할 수 없다. complete=false면 해당 결과 판단값은 null이다. critical_failure는 사전 rubric의 치명 실패 조건에 실제 해당하는 경우이며 severity=CRITICAL 자체와 같지 않다.

어느 쪽이든 incomplete가 있으면 `status=INCOMPLETE`, 양측 attempted/completed/timeout/error 수와 원자료는 반환하지만 `accuracy`, `accuracy_delta_pp`, `paired_ci95`, recall/FPR headline 값은 null이다. snapshot/case/group 계약 불일치는 INVALID이다. 완전 비교에서 critical regression이나 사전 gate 위반은 BLOCKED, 그 외 ELIGIBLE_FOR_HUMAN_REVIEW이며 자동 승인 뜻이 아니다.

- accuracy = correct/N, delta_pp = 100*(candidate_correct-baseline_correct)/N.
- risk recall = TP/(TP+FN), FPR = FP/(FP+TN). 분모 0은 null + `NO_POSITIVE_CASES` 또는 `NO_NEGATIVE_CASES`; 0%로 위장하지 않는다.
- `new_critical_ids`는 candidate.critical_failure=true이고 baseline.critical_failure=false인 case IDs이다. severity가 양측에서 달라지는 비교는 INVALID이다.
- paired CI 기본값: scenario_family가 독립 group. NumPy `Generator(PCG64(seed=20261028))`, 10,000 replicate, group ID를 lexicographic 정렬, 매 replicate에 M개 group을 균등 복원추출하고 선택 group의 **양측 동일 case 전체**를 함께 포함한다. 각 replicate의 case-weighted accuracy delta_pp를 계산하고 `quantile([0.025,0.975],method="linear")`를 사용한다. NumPy 버전/lock/hash를 결과에 기록한다. M<2는 CI=null/INSUFFICIENT_CLUSTERS. 독립성 가정과 군집 수를 보고한다.
- 비용은 모델 token/API 청구, infrastructure, human review를 구분한다. 누락 비용은 null+사유이고 0이 아니다. latency는 모델, 전체 처리, 사람 검토를 별도로 보고한다.

이 수치 방법은 등록할 기본 분석 규격이지 360건의 검정력이 충분하다는 보장이 아니다. rare critical 분모와 source/group 수를 함께 공개한다. 공개할 수 없는 private 원자료는 접근 가능한 검증자와 재현 범위를 명시한다.

## 15. 실제 모델 도입 시 G5 job extension

이 절은 optional 구현 범위지만 **활성화 조건은 필수**다. 실제 network adapter를 켜려면 동기 tenant-lock 계산 대신 아래 job 경계와 테스트를 먼저 추가한다.

- requester의 `/evaluation-runs` 요청은 short transaction에서 `EvaluationJob=QUEUED`, `active_job_id`, `EVALUATION_REQUESTED` DRAFT/n→DRAFT/n+1 및 202 idempotency 결과를 저장한다. fake adapter도 이 모드에서는 worker로 수행한다. job state는 QUEUED/RUNNING/SUCCEEDED/INCOMPLETE/CANCELLED이다.
- worker의 모델 호출은 DB transaction/tenant lock 밖에서 한다. network 호출 전후 attempt trace를 별도 기록하고 원문/secret을 숨긴다. provider 호출 비용의 exactly-once는 보장하지 않는다. 외부 업무 실행 tool은 허용하지 않는다.
- 하나의 tenant service actor가 최초 requester와 job ID를 명시하여 completion을 기록한다. `EVALUATION_COMPLETED` DRAFT/n+1→DRAFT/n+2, immutable full-suite run, active_job_id=null을 단일 transaction으로 저장한다. completion idempotency key는 `job_<uuid>_complete_v1`이고 동일 job의 completion은 한 번이다. actor의 인가된 서비스 역할은 인간 DOMAIN/RELEASE 권한과 분리한다.
- active job 중 다른 evaluate/submit/approve는 409 EVALUATION_INCOMPLETE. 취소는 requester만 할 수 있고 남은 case를 incomplete로 한 terminal run과 같은 completion 전이를 남긴다. 취소와 성공 completion이 경합하면 먼저 commit된 terminal outcome 하나만 남는다. terminal job에 두 번째 completion은 원 결과를 조회하며 새 전이를 만들지 않는다.
- lease timeout/worker crash/watchdog는 재시도 제한 후 INCOMPLETE terminal run을 기록한다. pending job을 삭제하거나 오래된 PASS run으로 되돌리지 않는다. lease interval/max attempts/provider timeout은 adapter config의 필수 고정값이며 초기 demo 기본값은 30s lease, 최대 2 attempts, case당 10s timeout이다. provider 제약이 다르면 config version을 바꾸어 비교 조건을 기록한다.

추가 인수는 queue acceptance 후 응답 유실, worker crash 전/후, 동일 job 중복 completion, cancel/complete race, 동일 tenant의 다른 change 진행, app 재시작 복구, provider timeout/비용 실패, latest incomplete veto이다. 이 job extension을 구현하지 않은 빌드의 real-model capability는 false로 고정한다.

## 16. 구현 작업 단위와 증거

1. contract DTO/error/canonical vectors와 state table 테스트를 먼저 작성한다. baseline와 v1의 결과를 별도 기록한다.
2. schema/migration, immutable snapshot과 validator, atomic transition helper, idempotency helper, RLS bootstrap을 순서대로 구현한다. mutable endpoint마다 helper를 우회한 경로가 없는지 검사한다.
3. full-suite run/coverage/current run policy를 구현한 후 assessment/envelope reconstruction을 연결한다. 이전 failed runs와 source versions 보존을 시험한다.
4. 실제 PG 독립 session으로 lock order/race/timeout/pool/RLS를 검증한다. 단일 worker SQLite 결과를 PG 증거로 재사용하지 않는다.
5. private blind boundary 및 paired metrics를 별도 G5 테스트로 검증한다. 실제 holdout/SME/외부 실행 증거가 없으면 목표 숫자·외부 보너스는 미완료다.

모든 task 보고에는 changed files, 실제 명령/exit, DB/role/worker/버전, assertions, 실패/미실행, run artifact hash를 포함한다. 이 계약의 문서 존재는 구현·보안 검증·실보험 적합성 PASS가 아니다.

## 17. v5.3 schema 구체화 결정

`contracts/`의 schema label과 nested ref 구조는 다음으로 고정한다. 미래 서버를 이 구조에 맞추어 구현하고 변경 시 schema version을 올린다.

- schema labels: `change_revision_v1`, `change_transition_v1`, `decision_note_v1`, `audit_event_v1`, `evaluation_run_v1`, `mutation_fingerprint_v1`. assessment/envelope 이름은 §7 그대로다.
- `PayloadRef={id,payload_sha256}`; RunRef는 recorded_revision, DecisionRef는 output_revision, EventRef는 sequence를 추가한다. TransitionRef는 revision_to 및 audit_event_ref를 추가한다. envelope의 release decision/transition ref는 PayloadRef, release event ref는 EventRef다.
- EvaluationRun hash purpose는 `evaluation-run`이다. `active_run_id`는 DRAFT의 최신 run이며 submit 이후 승인 대상 run으로 동결한다. 별도 snapshot.selected_run_id 필드를 만들지 않는다; assessment.selected_run_id에 같은 ID를 쓴다.
- evaluation/submit 전이만 run ref를 갖고, decision 전이만 decision ref를 갖는다. assessment hash는 release APPROVE에서만 들어간다. schema의 kind별 required/null 제약을 따른다.
- tenant/actor/pack/product/workflow/rule/case는 RegisteredId, API가 생성한 snapshot/adapter ID는 UUID다. rider 확인 근거 key는 `confirmation_evidence_id`다. 누락 context의 날짜/asof=null, status=UNKNOWN, riders=[] default를 적용한 뒤 hash하고, 필수 사실이 없으면 평가를 보류한다.
- case verdict는 PASS/FAIL/INCONCLUSIVE, run completion은 COMPLETE/INCOMPLETE, gate_summary는 PASS/BLOCK이다. case FAIL과 run gate BLOCK을 혼동하지 않는다.
- 오류 details는 기본 `{}`이며 STALE_REVISION에는 current_revision, INVALID_REQUEST에는 허용된 fields만 노출한다.

스키마 구조 예제의 valid=true는 해당 레코드의 서명/업무 적합성/완전한 FK 연결/승인 가능성을 의미하지 않는다. raw JSON strict type·duplicate key·Unicode·시간 정규화와 레코드 간 관계는 별도 HTTP/domain 테스트가 필요하다.
