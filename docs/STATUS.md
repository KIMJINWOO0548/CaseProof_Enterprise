# 구현 상태 — 5.3.0.dev4

2026-10-30. 사용자 제공 v5.3을 이 저장소의 추가 G1 구현과 병합했다. 아래 ‘현재’는 baseline `/api`를 뜻하며 미래 `/api/v1` route는 아직 없다. [병합 기록](V53_INTEGRATION.md), [VALIDATION](VALIDATION.md)을 함께 읽는다. 입력 패키지 당시 상태는 [보존 기록](evidence/v5.3/input_status.txt)이다.

| 기능 | 현재 | 남은 작업 |
| --- | --- | --- |
| 합성 규칙·두 tenant·숫자 검증 | 구현, 기존 정답 보존 | G3의 전체 시점·rider 사실 모델 |
| 생성/평가/제출/두 단계 승인 | 구현 | G1 target executor와 일관 API |
| 상태/revision/reviewer 감사 대조 | baseline 전이 원장·감사 순서·담당자 교차 검증; 분리된 v1 불변 테이블 | G1.3 target 이력 재구성·payload-ref 대조 |
| 사유 required/8–500, strict claim/revision | 이번 baseline 보강 | raw JSON duplicate/surrogate 등 target parser |
| requester-only evaluation / replay | 모든 mutation의 actor 범위 키, 원래 응답 재생, 현재 권한 재검사 | target HTTP 응답·키 형식·mutation 조회 계약 |
| 선택한 미승인 특약 보류 | 이번 baseline 보강 | 승인 이력·소급·등록시점·unknown 사실 모델 |
| 비교 기준선/후보 미완료 처리 | INVALID, 확정 통계 미출력으로 보강 | target paired CI/metadata/gold 분리 |
| smoke/browser/CLI 안전한 임시 상태 | Chrome MCP에서 실제 3인 승인·응답 유실 복구·DB 확인, 임시 합성 상태만 사용 | 독립 Playwright CLI·사용자 관찰 시험 |
| package/lock/CI/license/docs | hash lock·vendor MIT notices·wheel/sdist 설치, `fdac40d`에서 Linux 3.11/3.12/3.13·Windows 3.12 포함 CI 7개 job 성공 | 후속 커밋의 CI 지속 확인, 운영 검증 별도 |
| 세부 계약·schema/examples/hash vectors | 제공, 구조 검증; G1.1 입력·레코드 DTO와 순수 상태 전이 검증 | 미래 서버 enforcement |
| v1 불변 저장·신규 SQLite migration | 분리된 metadata·tenant FK·제약·불변 trigger·명시적 disposable migration | G1.3 executor 및 실제 기록 의미 검증 |
| full-suite immutable run / 실패 뒤 재평가 | PLANNED | G1.5 |
| preapproval assessment / approval envelope | baseline에서 승인 직전 revision·DOMAIN 결정·감사 참조 고정 | G1.6 target payload refs·source eligibility·snapshot 계약 |
| PostgreSQL/RLS/권한·경합 | PLANNED | G2; SQLite migration과 별개 |
| 검토 UI / linked correction / 접근성 | Tabler 1.7.3 표·폼·승인창·증거 요약, 라벨/초점/상태 대비 검사 | G4의 linked correction·완전 접근성·사용자 관찰 시험 |
| 실제 LLM/RAG/parser/agent | PLANNED, 외부 호출 없음 | G5 |
| 160/80/120 독립 검수·비노출 실험 | PLANNED; 공개 20 사례와 다름 | G5 + 실제 검수자/holdout |
| SSO/MFA, 외부 WORM/signing, backup drill | PLANNED | G6 및 별도 운영 검증 |

`/api`의 생성·평가·제출·현업 결정·최종 결정은 모두 12–128자 Idempotency-Key를 요구한다. `(tenant,actor,key)`는 operation을 포함해 재사용 충돌을 검사한다. 인증·역할·담당자 분리 검사 후 과거 결과를 replay하며 최신 무결성은 GET evidence로 별도 확인한다. DRAFT에 실패 결과가 남으면 새 change로 시작한다. target full-suite run과 parent relation은 미구현이다.

G1.1의 canonical·DTO·순수 상태기계 체크리스트를 구현·검증했다. strict command/header 및 case context, ChangeRevision·DecisionNote·EvaluationRun 타입, 불변 command context, 안전한 오류 형식과 7종 전이를 추가했다. 입력 날짜·사유·기본값을 정규화하고, 저장 레코드는 정규형 그대로인지 검사한다. 고정 14개 canonical vector와 기존 `digest()`는 보존한다. [모듈 경계](V1_FOUNDATION.md)를 함께 읽는다.

이번 전체 실행은 새 프로젝트 검증 환경에서 **679개 테스트와 하위 검사 22개 통과**, 스모크 **12/12**다. v1 저장·migration 검사는 223개이며 실제 CLI의 빈 DB upgrade/downgrade/upgrade도 통과했다. Windows의 소켓 초기화만 230회 재시도했고 HTTP/assertion은 재시도하지 않았다. 기존 Starlette 경고 1개와 Alembic의 순환 FK 정렬 경고 2개를 기록했다. 후자는 실제 FK 삽입·거부 시험과 구분한다. [검증 기록](VALIDATION.md)과 기존 [UI 검증](UI_WORKSPACE.md)을 함께 읽는다. 원본 v5.3의 Linux 결과와 합산하지 않는다.

G1.2는 [분리된 불변 저장과 disposable SQLite migration](G12_SCHEMA.md)을 추가한다. 기존 baseline DB의 자동 승격·승인 이력 생성은 거부한다. 다음은 G1.3의 원자적 executor와 전체 이력 재구성이다. 현재 v1 상태기계는 DB를 쓰지 않으며, 전달받은 내부 검증 결과를 현재 snapshot/run hash에 결합한다. full-suite gate 계산은 G1.5, `/api/v1` HTTP enforcement는 G1.4의 별도 검증 대상이다.

현재 bearer 토큰은 고엔트로피로 생성하고 DB에 hash만 저장하지만 expiration/rotation/revocation UI가 없다. 서버에 공유 인터넷으로 접속시키지 않는다. 기본 UI 토큰은 메모리에만 보관한다. `CASEPROOF_DEMO_MODE=1`을 명시한 로컬 데모만 허용한다.

내부 hash chain과 record projection은 감사 데이터를 통째로 재작성할 권한을 가진 공격자에 대한 독립 보증이 아니다. 최신 evidence가 유효해도 실보험 지급/계약·법규 적합성이나 실제 배포 승인을 뜻하지 않는다.
