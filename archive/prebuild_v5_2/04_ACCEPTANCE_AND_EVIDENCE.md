# 인수 기준·위협 시나리오·증거 매트릭스 v5.2

## 상태 용어

- `PRESENT`: 파일 또는 코드가 존재하며 해당 코드를 직접 읽었다. 동작·통과 보증은 아니다.
- `PASS`: 지정 환경에서 명령 실행 exit 0과 해당 assertion 결과가 기록됐다. 범위/조건을 반드시 붙인다.
- `FAIL`: 실제 실행에서 합격 조건을 충족하지 못했다.
- `SKIPPED`: 외부 접근·의존성·참여자 등으로 실행하지 않았다. 근거 없이 PASS로 간주하지 않는다.
- `PLANNED`: 아래 목표는 아직 수행되지 않은 계획이다.

2026-10-29 감사: 참조 unittest 49 PASS; Pydantic/JS 문법·모의 함수 공격은 제한된 단독 실행. pytest 90+22와 smoke 12/12는 **패키지의 이전 실행 기록**, 이번 감사에서는 두 명령이 의존성 문제로 SKIPPED/실행 실패였다. 코드 변경 후 과거 성적을 새로운 빌드의 통과 결과로 사용하면 안 된다.

## Gate별 실증 매트릭스

| Gate | 내용 | 완료 증거 | 미완료 시 판정 |
|---|---|---|---|
| G0 | 안전 실행·기준선 | Python/OS/패키지·demo DB 경로·input hashes·pytest·smoke log·exit | 개발 시작 전 환경 이슈 기록, 실제 결과를 추측하지 않음 |
| G1 | P0·권한·API 기본 | 실제 SQLite TestClient의 P0 적대 테스트 fail→fix→pass, 기존 회귀, OpenAPI와 idempotency | DEMO 승인 관련 변경은 미완료. 운영 차단 |
| G2 | PostgreSQL/RLS/동시성 | non-owner/NOBYPASSRLS 역할, 독립 세션, migration, pool·rollback 및 경합 증빙 | SQLite를 PG 대체 증거로 쓰지 않음 |
| G3 | 보험 업무팩 | 합성 시점·특약·충돌/미승인/혼입과 제3팩 E2E. 실제 룰은 SME 서면 검수 | 보험업무 적합성 미검증 |
| G4 | 사용자 업무 흐름 | 브라우저 클릭, 반려→시정→재평가, 접근성, 사용자 수·실패·시간 | API만으로 UI 성공 주장 금지 |
| G5 | 실제 AI·비교 | 고정 데이터·독립 검수·분리된 블라인드·paired 통계·비용·실패 결과 | 360건/정확도/경쟁 우위 미검증 |
| G6 | 운영·외부 | 독립 WORM/서명/복구; 2명 실무자, 타인 설치, 4종 훈련, 외부 리뷰, 제3팩 | 해당 보너스 0. 규제 인증은 별도 기관 사실 확인 |

## 구체 테스트 매트릭스

| ID / 우선순위 | 입력·사전조건 | 실행 | 기대 결과 | 현 상태 / 후속 |
|---|---|---|---|---|
| T01 P0 | 본문과 감사 정상, `PENDING_DOMAIN_REVIEW` | SQLite에서 status만 `PENDING_RELEASE`로 수정, 별도 승인자 POST | 409; release note/event 없음. 누락된 DOMAIN 승인이 드러나야 함 | ORM 스텁 재현만; 진짜 DB 미실행 |
| T02 P0 | 현업 APPROVE 생성 | DOMAIN decision/event를 삭제·교체·복제·순서 변경 | 409, 누락/불일치 이유 | PLANNED, 실제 DB 시험 |
| T03 P0 | 평가 두 개와 승인 근거 | request/result/verdict 중 한 필드 변경 또는 삭제 | 이후 승인 409, 승인 후 evidence false | 테스트 코드가 있으나 이번 pytest 미실행 |
| T04 P0 | 동일 사람이 REQUESTER와 REVIEWER 권한 모두 보유 | 자기 domain approve | 403; 감사에는 거부 기록 정책에 따른 결과 | 참조 로직 단위 PASS; API 미실행 |
| T05 P0 | reviewer와 release 권한을 동일 계정에 부여 | 같은 사람이 두 단계 승인 | 403; release note 없음 | API 미실행 |
| T06 P0 | tenant A 요청 ID | tenant B로 read/evaluate/submit/decision/evidence | 404, 응답 본문에서 A 정보 0 | 참조 권한 테스트만 PASS |
| T07 P1 | 요청 본문과 idempotency key 고정 | 동일 actor 같은 POST 두 번; 두 번째는 응답 유실 후 재시도 | 같은 객체·결정·이벤트, 과거 결과 replay 표시; 같은 key 다른 change ID·method·본문·expected_revision 409, 최신 무결성 별도 조회 | 생성 경로의 원본 함수+스텁에서는 중복 생성 관찰 |
| T08 P1 | 동일 revision / 사용자 둘 | 동시에 별도 DB 연결로 승인 2건 | 정확히 한 승인; 다른 요청은 명시적 충돌/정상 replay, 부분 기록 0 | SQLite 및 PostgreSQL 실제 동시성 미실행 |
| T09 P1 | PG RLS app role, A tenant context | B 행 select/update/delete/insert 및 FK 조합 | 데이터 미노출·변경 차단; integrity error는 최소 정보 | PLANNED |
| T10 P1 | PG 연결 풀, A 트랜잭션 rollback | 같은 연결에서 B 요청과 미설정 요청 | A context 누출 없음; 미설정 fail-closed | PLANNED |
| T11 P1 | 필수 승인 사유 없음·빈값·공백 8개 | OpenAPI/schema 및 POST | 스키마 required/minLength/maxLength; 서버 422. 입력과 strip 결과 각각 8–500 Unicode code point를 검증하고 스키마가 표현 못 하는 trim 규칙을 spec에서 설명 | Pydantic 단독에서 현 불일치 확인 |
| T12 P1 | claim_days true, 문자열 30, 1.0, -1, 10000 | API evaluation | 런타임 엄격 타입·범위에 따른 422. JSON Schema의 integer만으로 1.0 거부를 표현할 수 없음을 별도 설명 | Pydantic 단독 bool→1 관찰, HTTP 미실행 |
| T13 P1 | 동일 업무팩의 published 기본 룰, DRAFT 특약 | 해당 특약 가입/unknown 상태 입력 | 영향이 불명확하면 INCONCLUSIVE | resolver 단독 기본 룰로 RESOLVED 관찰; 실제 보험법상 정답 미확인 |
| T14 P1 | 기준선 한 항목 `complete=false` | paired comparison | INVALID/INCOMPLETE; 확정 정확도/CI 미출력 | 참조 함수에서 비교 허용 재현 |
| T15 P1 | 실행 중 오류 또는 network 응답 끊김 | 변경 요청 재조회 및 같은 키 재전송 | 동일 기록 혹은 명시적 실패, 중복/허위 성공 없음 | PLANNED |
| T16 P2 | 승인 전 assessment manifest와 final envelope | 도메인 결정 삭제/사유 변경, 서명·외부 hash 검증 | 바뀐 근거 또는 외부 앵커 불일치 탐지, 자기 참조 없음 | PLANNED |
| T17 P2 | prompt injection 텍스트 포함한 합성 출처 | 모델/RAG 연결 후 정상 정책·출처검증 우회 시도 | 권한 밖 동작 방지, 불신 입력 처리·결과 기록 | 현재 LLM 없음, N/A(미구현) |
| T18 P2 | 모델이 존재하지 않는 clause/version 인용 | source validator | 미승인/다른 tenant/없는 출처는 PASS 금지 | PLANNED |
| T19 P2 | 세 번째 가상 업무팩 | 코어 무변경으로 등록→UI/API/DB·격리 E2E | core hash 동일, 결과 정상, 외부인 시험 시 B05 검토 | PLANNED |
| T20 P2 | 외부 장애·탈취·감사변조·롤백 모의훈련 | 운영 절차 실행·수정·재시험 | 4개 결과와 증거 보존; 외부 수행 시 B03 검토 | PLANNED |

## 로그 및 증거 수집 규격

`current/reports/runs/<UTC-run-id>/`에 다음을 둔다. Windows 경로를 위해 ID는 `YYYYMMDDTHHMMSSZ-<8자리 16진수>` 형식을 사용하며 콜론을 쓰지 않는다. 경로는 신규로 작성하며 기존 `reports/` 과거 파일을 수정·교체하지 않는다.

1. `environment.json`: 실행 시각 UTC/KST, OS, Python/Node, 패키지 버전 및 lockfile/hash, DB 종류/버전/격리수준/role(비밀 제외), 브라우저 버전, worker 수, demo mode.
2. `commands.txt`: 실제 작업 디렉터리, 명령, exit code. 토큰·인증정보는 포함 금지.
3. `pytest.log`, `smoke.log`, `browser.log`, `security_scenarios.json`, `migration.log`: 실제 실행된 항목만 기록. 경쟁 비교·외부 검수 미실행은 가짜 로그를 만들지 않는다.
4. `artifact_hashes.json`: 코드 커밋 또는 원본 SHA, 테스트·데이터·평가기·모델/프롬프트 버전, 실험 seed, 결과 hash. SHA만으로 타인 검증·불변성을 증명하지 않는다.
5. `limitations.md`: 비실행·실패·원인·영향, 외부 의존, 이전과 신규 결과의 차이, 실제 보험사·법률 적용의 한계.

스모크 스크립트는 기본 경로를 덮어쓰므로 실행 전 사본 또는 안전한 출력경로로 바꾼다. 브라우저 스크립트의 고정 경로 삭제를 제거하기 전에는 원본 디렉터리에서 실행하지 않는다. 보관·서명·WORM은 구현·실증 전 PLANNED다.

## R01–R09와 B01–B05 연결

| 코드 | 점수를 높이기 위한 독립 증거 | 대응 Gate |
|---|---|---|
| R01 | 시점/특약/충돌 실DB 재현, 실약관·실무자 검수와 한계 | G3, G5, G6 |
| R02 | 독립 업무팩, tenant isolation 비소유 DB role, 제3팩 E2E | G2, G3 |
| R03 | 최신 기능·라이선스와 동일 질문/정답/모델/지표·TCO 비교 | G5 |
| R04 | 실제 UI/API/DB/마이그레이션·브라우저 E2E·배포/복구 | G1, G2, G4, G6 |
| R05 | 전문가 검수 데이터, 오류/미탐/오탐·blind 비교·구간/비용 | G5 |
| R06 | 공식 자료 원문·위협 모델, 실제 인가·감사, LLM red-team | G1, G2, G5, G6 |
| R07 | 실제 역할별 사용자 시험과 반려/시정/복구·접근성 | G4 |
| R08 | 제3자 설치, CI·관측·유지보수 | G0, G4, G6 |
| R09 | 재현 가능한 시연, 실제 ROI 근거, 역할별 설명 및 본인 기여 | G4–G6 |
| B01 | 보험 실무자 2명 이상 서면·개선 반영 | G6 |
| B02 | 제3자 Windows 신규 설치·해시·실행 | G6 |
| B03 | 장애/탈취/감사변조/롤백 4종의 외부 수행·수정·재시험 | G6 |
| B04 | 외부 기술 리뷰·실질 피드백 반영 | G6 |
| B05 | 제3자 독립 업무팩 코어 무수정 E2E·DB 격리 | G3, G6 |

대상 항목의 세부 배점은 `../SCORECARD_105.csv`가 정본. 진척 상태와 점수는 독립 재평가로 다시 결정한다. 대략적 예상 점수를 성공으로 기재하지 않고, 각 보너스는 실제 외부 자료 없으면 0이다.
