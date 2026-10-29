> **v5.2 우선순위/상태:** 아래의 설계·실행 설명은 v5.1 이력입니다. 서비스는 변경되지 않았고 승인 전이 결함 후보가 있습니다. 신규 목표와 게이트는 ../../prebuild/01_TARGET_DESIGN.md 및 ../../prebuild/02_IMPLEMENTATION_PLAN.md가 우선합니다.

# 01. 실행 아키텍처와 API 계약 v5.1

## A. 실제 실행 컴포넌트

브라우저 UI (`service/static/index.html`) → HTTP Bearer 보호 API (`service/app.py`) → SQLAlchemy 세션 (`service/db.py`) → 관계형 모델 (`service/models.py`). 평가기는 `reference/resolver.py`, `reference/verify_answer.py`를 호출합니다. 두 실제 구현 팩 `datasets/synthetic_rules.json`을 `service/seed.py`에서 DB에 로딩합니다. `datasets/resolver_test_cases.json`과 평가자 코드 SHA-256을 읽어 **평가 실행 시 서버 측 스냅샷과 비교**합니다.

별도 AI 모델 호출은 존재하지 않습니다. 현재 확인 가능한 기술 깊이는 도메인 규칙의 시간선택, 역할·경계 검증, 트랜잭션, 감사 무결성, 오류 경로입니다.

## B. 변경 요청 상태 머신

`DRAFT` → `PENDING_DOMAIN_REVIEW` → `PENDING_RELEASE` → `APPROVED_FOR_DEMO`; 현업 또는 최종 승인에서 `REJECTED`로 분기. 반려된 변경을 새 요청으로 이관하는 `REOPEN` 기능은 아직 없습니다. 상태 전이 때 revision CAS를 사용합니다. 외부 도구 실행/보험금 지급/실시스템 배포는 수행하지 않습니다.

## C. 객체 권한

| API | 역할 | 강제 조건 | 거부 코드 |
|---|---|---|---|
| `GET /api/me` | 로그인 사용자 | 유효 Bearer | 401 |
| `GET /api/scopes` | 인증 사용자 | 자신의 tenant 데이터 | 401 |
| `POST /api/changes` | ANALYST | 등록된 스코프·3개 해시 일치 | 403/409 |
| `POST /api/changes/{id}/evaluations` | ANALYST | 자신의 tenant + DRAFT + 예상 revision + 멱등키 | 404/409 |
| `POST /api/changes/{id}/submit` | ANALYST 요청자 | PASS 두 버전·원본/감사 무결성 | 403/409 |
| `POST /api/changes/{id}/domain-decision` | DOMAIN_REVIEWER | 본인 요청 금지·사유 8자 이상 | 403/409/422 |
| `POST /api/changes/{id}/release-decision` | RELEASE_APPROVER | 요청자·현업검토자와 다른 계정, 증거 무결성 | 403/409 |
| `GET /api/changes/{id}/evidence` | tenant 사용자 | tenant 격리·근거 보존 여부 표시 | 404 |
| `GET /api/audit/verify` | AUDITOR | tenant별 감사 체인 검사 | 403 |
| `GET /api/fixture-regression` | ANALYST | 합성 20건 중 자신의 tenant 정답 검사 | 403 |

PostgreSQL RLS는 **미구현**; 현재 API·복합 FK로 다중 테넌트의 논리적 격리를 시험합니다. 응용 계층 인증만으로 실제 금융기관 테넌트 분리 설계를 완성했다고 말하지 않습니다.

## D. 고정 불변식과 실패 정책

1. Tenant ID는 Bearer 토큰으로 찾은 사용자 소속에서 결정; 변경 생성 요청은 tenant ID 필드 자체를 갖지 않음.
2. 모든 객체 조회는 tenant ID를 함께 비교; 다른 회사의 객체 ID를 알아도 404.
3. 변경 생성 때 데이터셋·평가기·규정 출처 3개 해시를 서버 계산값과 비교.
4. 평가 때 멱등키와 입력 본문 SHA-256을 비교; 같은 키로 다른 입력은 409.
5. 동시 수정은 revision CAS로 다른 사람의 변경을 덮지 않음.
6. 검증 결과에는 요청/결과/판정을 묶은 audit event를 append.
7. 검토·승인 이전에 감사 이벤트 해시 체인과 **실제 DB 평가·승인·원본 레코드**를 교차 검증.
8. `PASS` 판정만으로 승인하지 않음. 서로 다른 규정 버전의 PASS 두 건과 두 명의 서로 다른 승인 주체가 필요.
9. 충돌, 승인되지 않은 출처, 알 수 없는 특약은 `INCONCLUSIVE`; numeric mismatch는 `BLOCK`.
10. 감사·데이터 불일치 시 `APPROVED_FOR_DEMO`가 아닌 409 fail-closed 반환.

## E. 계약상 누락/제약

- 평가기는 **숫자 일수(claim_days)** 하나만 검사, 자유형 문서 생성 AI를 검증하지 않음.
- 고객계약·특약·접수일의 실서비스 사실관계 수집이 아니라 평가 호출 시 입력된 합성 기준일로 판단.
- 실제 법령·약관 버전 관리, 배포 후에만 적용되는 규정의 예외와 변경이력의 bitemporal DB 모델은 계획 단계.
- UI는 실제 API에 연결되지만 정식 디자인 시스템, 접근성, 대량 데이터 페이지네이션·검색 기능 없음.
- v5는 로컬 SQLite 단일 프로세스에 최적화. PostgreSQL 동시성·성능/분산 환경에서 별도 검증이 필수.
