# v5.3 계약 검토 — 구현 전에 고정할 사항

상태: **설계 검토 / 제안. 구현·테스트 완료 보고가 아님.** 검토 범위는 v5.2 `prebuild/01_TARGET_DESIGN.md`–`04_ACCEPTANCE_AND_EVIDENCE.md`, v5.1 `service/{app,models,schemas,db,seed}.py`, `reference/{evidence_pack,paired_benchmark}.py`이다. 이 검토는 기존 파일을 수정하지 않았다. 아래 P0/P1은 설계 결정의 구현 차단 우선순위이며 새 취약점 실증 등급이 아니다.

## 핵심 결론

방향은 타당하지만 서로 다른 구현자가 동일 동작을 만들기에는 신원 부트스트랩, 해시 입력, revision, 평가 재실행, 재시도 범위가 충분히 고정되지 않았다. `08_IMPLEMENTATION_CONTRACTS.md`는 아래 결정을 정확한 계약으로 제안한다. 현재 `/api`는 legacy 합성 데모로 남기고 미래 계약을 `/api/v1`로 분리한다. baseline의 P0·입력 개선을 미래 Gate 전체 완료로 표시하면 안 된다.

| 우선순위 / ID | 발견과 근거 | 결정 및 인수 조건 |
|---|---|---|
| P0 C01 | I-07의 UNIQUE `(tenant,actor,endpoint_operation,key)`와 Task 1.3/T07의 다른 경로·method에서 같은 key이면 409 요구가 모순된다. | 모든 mutation의 UNIQUE를 `(tenant_id,actor_id,key)`로 통일한다. fingerprint는 method/정규화 route/resource/정규화 DTO/expected_revision을 포함한다. 다른 endpoint·resource·revision으로 재사용하면 409. 다른 actor는 자기 별도 key 공간만 사용하며 남의 응답을 읽지 못한다. |
| P0 C02 | I-05의 idempotency 마지막 잠금과 I-07의 stale revision 이전 replay 순서는 구현 절차가 없다. 먼저 행을 만들거나 예약을 별도 commit하면 빈 예약·부분 성공·잠금 역전이 생긴다. | 인증/현재 권한/객체 tenant 확인 → tenant head → change → 관련 행 → idempotency 순서. 잠금 후 authoritative replay 판정을 하고, 신규 요청만 integrity/state/revision 검사를 한다. 성공 결과와 모든 업무 기록을 한 commit에 저장한다. 실패 예약은 남기지 않는다. rollback 뒤 같은 key 재시도 가능. |
| P0 C03 | I-03/I-06에 정렬·문자·시간·숫자·전체 필드·snapshot 보존 방식이 없어 manifest의 재구성 결과가 구현마다 달라진다. 현재 `evidence_content()`는 현재 rule 행을 다시 읽고 결정·전이도 포함하지 않는다. | 버전 있는 canonical bytes, immutable revision snapshot, event/transition/decision의 비순환 해시 DAG를 고정한다. pre-approval revision 및 tenant audit checkpoint까지를 봉인한다. 이후 관계없는 이벤트·정상적인 새 source version 추가는 기존 승인 hash를 바꾸지 않는다. 삭제·원문 변경은 검출해야 한다. |
| P0 C04 | ‘현재 revision 계열’과 평가가 의미하는 revision이 불명확하다. 모든 평가가 revision을 올리므로 마지막 평가만 현재 revision과 일치한다는 검사로는 최소 2건 요건과 충돌한다. | workflow revision은 전이 번호, candidate snapshot ID는 평가 대상 내용의 식별자다. 모든 평가 case가 같은 candidate/source/dataset/evaluator snapshot을 참조한다. submit/review의 revision 증가는 평가를 자동 무효화하지 않는다. |
| P0 C05 | UI는 실패를 수정하고 재평가한다고 하지만 현재 submit/release는 모든 과거 evaluation이 PASS여야 한다. 실패 보존과 수정 후 진행이 동시에 불가능하다. 필수 coverage의 case identity도 없다. | 불변 `EvaluationRun`에 필수 suite 전체 결과를 담고 최신 commit된 run 하나로 gate를 계산한다. 최신 run이 INCOMPLETE/BLOCK이면 이전 PASS로 fallback 금지. 과거 실패 run은 삭제하지 않고 assessment에 hash 참조로 포함한다. |
| P0 C06 | RLS를 User에도 적용하면 현재 `get_actor()`의 tenant 미설정 token_hash 전역 조회가 막힌다. 인증 우회를 위해 User를 무심코 RLS에서 제외할 위험이 있다. | 합성 v1은 서버 소유 token-digest→tenant/actor registry를 DB 외부에서 검증한 후 transaction-local context를 세팅한다. 이어 같은 tenant User의 enabled/roles를 조회한다. body/header tenant는 사용하지 않는다. registry 누락·중복은 startup 오류; unknown token 401. SSO는 별도 adapter이며 이 demo 방식이 SSO라는 주장은 금지한다. |
| P1 C07 | `X-Expected-Revision`과 body expected_revision이 섞이고 새 schema의 endpoint/status/error/replay body가 정해지지 않았다. | 미래 `/api/v1` mutation은 create 외 모두 header만 사용한다. body revision은 extra field로 422. 성공 응답은 `result_revision`, `replayed`, 불변 result를 갖는다. 오류별 code/retryable을 표준화한다. current `/api` 호환성 변경과 별도 작업으로 관리한다. |
| P1 C08 | source의 DRAFT/PUBLISHED/REVOKED, valid/recorded time, 승인 시점 현재 철회 여부가 혼합되어 과거 검증과 현재 승인 가능성을 구별하기 어렵다. | frozen source/승인이력으로 역사적 증거 integrity를 검증한다. 현재 source withdrawal은 새 승인 gate를 차단하지만 이미 봉인한 과거 envelope를 hash mismatch로 만들지 않는다. 응답에 integrity와 current eligibility를 별도 필드로 제공한다. |
| P1 C09 | 360건 최소 record 하나에 모델 input과 expected answer/rationale/citation gold가 섞인다. open-source 배포물에 holdout labels를 넣으면 미래 blind 주장이 성립하지 않는다. | `CaseInput`/`GoldRecord`/`CaseMetadata`를 분리한다. model adapter allowlist만 전달하고 private gold 경로를 주지 않는다. 공개 합성 예시는 dev/demo로 표시한다. 외부 custodian의 private holdout이 없으면 blind=SKIPPED. 공개한 holdout은 노출된 것으로 전환한다. |
| P1 C10 | `critical`이 사례 심각도와 실제 실패를 혼용하며, incomplete·분모·paired CI 방법이 아직 선택지다. 현재 비교는 baseline incomplete를 보지 않는다. | `severity`는 고정 gold, `critical_failure`는 rubric 기반 결과다. 어느 쪽이 incomplete여도 headline accuracy/delta/CI는 null. exact paired case set, family bootstrap algorithm/seed/replicates, 0 분모 처리와 budget 비교를 사전 고정한다. |

## 반드시 추가할 회귀

1. tenant A actor의 같은 key를 create→submit, change X→Y, expected_revision n→n+1로 바꾸면 각각 409; 같은 요청은 원 result_revision으로 replay한다.
2. 성공 commit 후 응답을 잃고 나서 상태가 진전되어도 원 결과를 replay한다. actor가 비활성화되거나 현재 접근 권한을 잃으면 replay를 반환하지 않는다.
3. 상태·decision·transition·snapshot·event·idempotency 쓰기 각 경계에 실패를 넣어 모두 rollback되는지 확인한다. 이미 commit된 결과와 응답 전송 실패는 같은 key로 복구한다.
4. DRAFT run1 BLOCK → run2 PASS(필수 case 전체) → submit 성공; run3 INCOMPLETE면 run2로 돌아가지 않고 submit 차단한다. 과거 실패가 assessment에 남아 있어야 한다.
5. Unicode 조합형 문자열, 개행, null/누락, UTC timestamp, hash 목적별 test vector를 고정한다. 같은 canonical payload는 같은 bytes/hash이고, schema 또는 목적이 다르면 hash가 다르다.
6. 승인 이후 다른 change 이벤트·정상 source 새 version을 추가해도 기존 assessment/envelope hash가 같다. 봉인한 source bytes/DOMAIN reason/전이를 바꾸거나 삭제하면 invalid다.
7. context가 없는 app role은 tenant row를 읽지 못한다. 정상 token 인증 후 해당 User만 조회되며 pool 재사용·rollback 뒤 이전 tenant가 남지 않는다.
8. adapter spy로 gold/expected/citation answers가 model request에 들어가지 않음을 확인한다. 공개 ZIP에 private holdout/gold/개인정보/실제 token이 없는지 검사한다.
9. 기준선 또는 후보 하나라도 incomplete이면 두 경우 모두 동일하게 INCOMPLETE이고 headline metric은 null이다. critical severity는 같고 critical_failure만 다른 정상 비교를 검증한다.

## 적용 순서

먼저 C01–C07의 API·schema·해시 vector를 contract test로 고정하고 G1/G2의 구현 목록을 갱신한다. C08–C10은 G3/G5 진입 조건으로 삼는다. 실제 외부 모델을 연결하기 전에는 tenant 잠금 안에서 network I/O를 수행하지 않는 job/completion 경계를 구현해야 한다. 본 검토에는 실제 DB 경합·RLS·브라우저·SME 검수를 실행한 결과가 없다.


## v5.3 반영 결과

C01–C10의 선택을 08 구현 계약과 02 작업 계획, contracts/ schema·예제로 반영했다. baseline의 P0/입력/미완료 비교/특약 fallback은 별도로 수정·회귀 검증하며 결과는 docs/VALIDATION.md에 기록한다. 이 문서의 내부 설계 검토는 외부 B04 점수 근거가 아니다. 실제 v1 구현과 PostgreSQL·모델·private holdout 실증은 아직 계획이다.
