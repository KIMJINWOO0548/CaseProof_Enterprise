# 인수 기준·증거 매트릭스 v5.3

현재 실행 결과는 [VALIDATION](../docs/VALIDATION.md), 현재/미래 기능 구분은 [STATUS](../docs/STATUS.md), target 계약은 [08](08_IMPLEMENTATION_CONTRACTS.md)가 정본이다. 이 문서는 **다음 구현에서 통과시킬 인수 기준**이다. 원본의 과거 점수를 새 결과로 재사용하지 않는다.

## 상태와 출시 단계

- PRESENT: 파일/코드가 있음. PASS와 다르다.
- PASS: 명시된 환경·입력·명령 exit 0와 assertion 증거가 있음.
- FAIL: 실행했지만 조건 미충족. 환경 설치 실패도 실패 사실을 기록한다.
- SKIPPED: 기능/인프라/참여자 미확보로 해당 검증을 수행하지 않음.
- PLANNED: 아직 구현되지 않은 목표.

| 공개 수준 | 필요한 사실 | 허용 표현 |
| --- | --- | --- |
| 현재 5.3.0.dev0 | baseline 회귀 + 정직한 제한 + 코드/라이선스/재현 절차 | synthetic local prototype / implementation handoff |
| v1 local demo | G1+G3+G4 실제 로컬 흐름과 브라우저 증거 | tested synthetic demo |
| PostgreSQL demo | 위 조건 + G2 실제 비소유 app role/RLS/경합 | tested PG synthetic demo |
| 비교실험 발표 | G5 실제 독립 검수/비노출 holdout/paired 원자료 | 해당 데이터·모델·환경으로 한정된 결과 |
| 운영 서비스 | G6 및 실제 배포의 보안/개인정보/책임 검증 별도 | 현재 패키지는 여기에 해당하지 않음 |

## Target 필수 인수 사례

| ID | 공격/실패 또는 정상 사례 | 기대 결과 | 소유 task |
| --- | --- | --- | --- |
| A01 | status만 PENDING_RELEASE로 변조 | 409, release note/transition/audit 0 증가 | G1.3 |
| A02 | reviewer/revision/approval hash 개별 변경 | integrity invalid; 새 승인 거부 | G1.3 |
| A03 | note/snapshot/run/transition/event 누락·복제·역순 | 재구성 불일치, fail closed | G1.3/G1.6 |
| A04 | requester가 DOMAIN/RELEASE 역할 동시 보유 | 자기 승인 403 | G1.3 |
| A05 | DOMAIN reviewer가 RELEASE도 보유 | 동일인 최종 승인 403 | G1.3 |
| A06 | A tenant ID를 B actor로 모든 경로 접근 | 404, A 자료/존재 정보 없음 | G1.4/G2.2 |
| A07 | 같은 key, 같은 정규화 요청 | 객체·이벤트 1개, 원 status/result revision replay | G1.4 |
| A08 | 같은 actor key, 다른 endpoint/resource/body/revision | 409 IDEMPOTENCY_CONFLICT | G1.4 |
| A09 | commit 뒤 응답 유실, 이후 상태 진전 | 같은 key로 원 결과; 최신 integrity는 별도 | G1.4/G4 |
| A10 | 사용 중지·권한 회수 뒤 기존 key 조회 | 인증/권한 거부, 이전 결과 유출 없음 | G1.4/G2.2 |
| A11 | 각 write 경계에 예외 | 모든 행/head/key rollback, 부분 승인 0 | G1.3 |
| A12 | 동시 session 동일 revision 승인 | effect 최대 1, 허용 conflict/replay 외 오류 0 | G2.3 |
| A13 | tenant head 경합·timeout/deadlock | 전체 rollback + 503, bounded retry | G2.3 |
| A14 | context 누락/빈 값/rollback→다른 tenant | fail closed, pool 누출 0 | G2.2 |
| A15 | RLS app role이 owner/superuser/BYPASSRLS | 시험 자체 실패; 유효한 보안 결과로 인정 금지 | G2.1 |
| A16 | reason 누락/공백/trim후 7자/501자 | 422; required/min/max 설명과 HTTP 일치 | G1.1/G1.4 |
| A17 | claim_days bool/float/string/out of range | 422; schema integer의 1.0 한계 별도 검증 | G1.4 |
| A18 | raw JSON duplicate key/surrogate/NaN | 422; 서버 예외·불일치 fingerprint 없음 | G1.4 |
| A19 | run BLOCK→full PASS, 최신 INCOMPLETE | 실패 보존, 최신 incomplete veto | G1.5 |
| A20 | 필요한 case/버전 coverage 누락·중복 | submission 차단; 부분 PASS 조합 금지 | G1.5 |
| A21 | 승인 후 다른 change event·새 source version | 과거 seal 불변 | G1.6 |
| A22 | 봉인 source bytes/DOMAIN reason 변경·삭제 | historical integrity invalid | G1.6 |
| A23 | 사후 source withdrawal | 과거 무결성과 현재 eligibility 분리 | G1.6/G3 |
| A24 | 계약/사고/청구일이 서로 다른 버전, rider UNKNOWN | 정책에 맞는 근거 또는 INCONCLUSIVE | G3 |
| A25 | 선택된 DRAFT/REVOKED 특약·상충 우선순위 | unsafe base fallback 금지 | G3 |
| A26 | 반려→새 linked change→새 full run | old decisions 보존; 승인 재사용 없음 | G4 |
| A27 | XSS text, 키보드/초점, 네트워크 unknown | 안전한 text 표시·복구·역할별 안내 | G4 |
| A28 | gold field를 model request에 섞음 | allowlist 거부; public bundle에 private gold 없음 | G5.1 |
| A29 | baseline 또는 candidate incomplete | target INCOMPLETE + 확정 metrics null | G5.1 |
| A30 | paired set/hash/group 불일치, 0분모 | INVALID 또는 명시적 null/reason | G5.1 |
| A31 | job 중복 완료·worker crash·취소 경합 | terminal run 하나, 잔여 불완전성 보존 | G5.2 |
| A32 | DB/head 전체 재작성과 외부 checkpoint 비교 | 독립 anchor가 있을 때 탐지 실증 | G6 |

Baseline에 유사 테스트가 있어도 v1 task 통과로 자동 계산하지 않는다. API·DB 구조가 다르므로 target 경로와 실제 runtime role로 재실행한다.

## 결과 보관 형식

신규 `reports/runs/YYYYMMDDTHHMMSSZ-xxxxxxxx/`를 만든다. 기존 경로 덮어쓰기 금지.

- `run.json`: run_id, recorded_at UTC, input/source archive/commit hash, command list, exit_code, duration, status.
- `environment.json`: Python/OS, dependency lock hash, installed versions, DB type/version/role/isolation, workers, browser version. 비밀번호/토큰/DSN 전체는 제외.
- 실제 `pytest.log`, `smoke.json`, `browser.log`, `pg.log` 등. 실행하지 않았다면 파일을 꾸며내지 말고 run.json에 SKIPPED/reason.
- `limitations.md`: 실패/미실행, 이전 상태와 차이, source/SME/model/운영 한계.
- 외부 검수/비공개 원자료는 consent/권리/접근 범위를 기록한다. 공개 repo에 고객 정보나 private blind gold를 넣지 않는다.

release evidence는 내용/비밀을 검토한 뒤 `docs/evidence/<release>/`에 필요한 것만 복사한다. SHA manifest는 byte 변화만 확인하며 안전성·저자·외부 검증을 보증하지 않는다.

## 평가표

[자체 105점 rubric](../docs/SCORECARD_105.csv)은 연구용 평가표다. 구현 gate 통과 수와 105점은 동일하지 않다. R01–R09는 실제 해당 증거로만 평가하고 B01–B05(외부 SME·타인 Windows·훈련·외부 기술리뷰·외부 제3팩)는 실제 외부 증거 없이는 0이다. 이 패키지에서 내부 agent가 수행한 검토를 ‘독립 외부 전문가 인증’으로 계산하지 않는다.
