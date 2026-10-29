# 구현 상태 — 5.3.0.dev1

2026-10-30. 사용자 제공 v5.3을 이 저장소의 추가 G1 구현과 병합했다. 아래 ‘현재’는 baseline `/api`를 뜻하며 미래 `/api/v1` route는 아직 없다. [병합 기록](V53_INTEGRATION.md), [VALIDATION](VALIDATION.md)을 함께 읽는다. 입력 패키지 당시 상태는 [보존 기록](evidence/v5.3/input_status.txt)이다.

| 기능 | 현재 | 남은 작업 |
| --- | --- | --- |
| 합성 규칙·두 tenant·숫자 검증 | 구현, 기존 정답 보존 | G3의 전체 시점·rider 사실 모델 |
| 생성/평가/제출/두 단계 승인 | 구현 | G1 target executor와 일관 API |
| 상태/revision/reviewer 감사 대조 | 전이 원장·감사 순서·담당자 교차 검증 | target immutable ChangeRevision 및 payload-ref 계약 |
| 사유 required/8–500, strict claim/revision | 이번 baseline 보강 | raw JSON duplicate/surrogate 등 target parser |
| requester-only evaluation / replay | 모든 mutation의 actor 범위 키, 원래 응답 재생, 현재 권한 재검사 | target HTTP 응답·키 형식·mutation 조회 계약 |
| 선택한 미승인 특약 보류 | 이번 baseline 보강 | 승인 이력·소급·등록시점·unknown 사실 모델 |
| 비교 기준선/후보 미완료 처리 | INVALID, 확정 통계 미출력으로 보강 | target paired CI/metadata/gold 분리 |
| smoke/browser/CLI 안전한 임시 상태 | 보강, 검증 범위는 VALIDATION | 실제 브라우저 설치·클릭 시험 |
| package/lock/CI/license/docs | hash lock 설치·wheel/sdist·체크아웃 밖 설치 확인, 공개 owner 연결 | 실제 원격 CI 결과 확인·각 플랫폼 검증 |
| 세부 계약·schema/examples/hash vectors | 제공, 구조 검증 | 미래 서버 enforcement |
| full-suite immutable run / 실패 뒤 재평가 | PLANNED | G1.5 |
| preapproval assessment / approval envelope | baseline에서 승인 직전 revision·DOMAIN 결정·감사 참조 고정 | G1.6 target payload refs·source eligibility·snapshot 계약 |
| PostgreSQL/RLS/migration/경합 | PLANNED | G2 |
| linked correction UI/완전 접근성 | PLANNED | G4 |
| 실제 LLM/RAG/parser/agent | PLANNED, 외부 호출 없음 | G5 |
| 160/80/120 독립 검수·비노출 실험 | PLANNED; 공개 20 사례와 다름 | G5 + 실제 검수자/holdout |
| SSO/MFA, 외부 WORM/signing, backup drill | PLANNED | G6 및 별도 운영 검증 |

`/api`의 생성·평가·제출·현업 결정·최종 결정은 모두 12–128자 Idempotency-Key를 요구한다. `(tenant,actor,key)`는 operation을 포함해 재사용 충돌을 검사한다. 인증·역할·담당자 분리 검사 후 과거 결과를 replay하며 최신 무결성은 GET evidence로 별도 확인한다. DRAFT에 실패 결과가 남으면 새 change로 시작한다. target full-suite run과 parent relation은 미구현이다.

G1.1의 첫 조각인 `service.domain.canonical`을 추가했다. 고정 14개 vector의 bytes/hash와 strict JSON parser의 중복 키·float·unsafe integer·surrogate·UTF-8 거부를 검사했다. baseline `digest()`는 유지한다. DTO·순수 상태기계·HTTP enforcement를 구현한 것은 아니므로 G1.1 전체 완료로 표시하지 않는다.

이번 전체 실행은 **305개 테스트와 하위 검사 22개 통과**, 스모크 **12/12**다. Windows 검증용 초기화 재시도 실행기를 사용했고 기존 Starlette 경고 1개가 남아 있다. 원본 v5.3의 Linux 221개 결과와 합산하지 않는다.

현재 bearer 토큰은 고엔트로피로 생성하고 DB에 hash만 저장하지만 expiration/rotation/revocation UI가 없다. 서버에 공유 인터넷으로 접속시키지 않는다. 기본 UI 토큰은 메모리에만 보관한다. `CASEPROOF_DEMO_MODE=1`을 명시한 로컬 데모만 허용한다.

내부 hash chain과 record projection은 감사 데이터를 통째로 재작성할 권한을 가진 공격자에 대한 독립 보증이 아니다. 최신 evidence가 유효해도 실보험 지급/계약·법규 적합성이나 실제 배포 승인을 뜻하지 않는다.
