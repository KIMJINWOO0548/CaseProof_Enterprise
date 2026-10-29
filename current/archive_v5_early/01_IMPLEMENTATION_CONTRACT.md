# v5.0 구현 계약 / 상태와 불변식

## 실제 사용자와 작업

- `ANALYST`: 가상 약관 변경검증 요청을 등록하고 검증 데이터를 저장. 자신이 생성한 요청만 제출.
- `DOMAIN_REVIEWER`: 요청자 및 소유자와 다른 ID로 현업 적합성을 검토. 승인/반려 사유 필수.
- `RELEASE_APPROVER`: 요청·소유·현업검토와 다른 ID로 데모 출시 승인. 자동으로 모델을 운영환경에 배포하지 않음.
- `AUDITOR`: 테넌트별 감사 해시 체인 검사. 그 외 사용자는 이 엔드포인트에 접근 불가.

## 상태 전이 (하나의 요청 단위)

```text
DRAFT --(2 versions PASS + human submit)--> PENDING_DOMAIN_REVIEW
PENDING_DOMAIN_REVIEW --(domain approve)--> PENDING_RELEASE
PENDING_DOMAIN_REVIEW --(domain reject)--> REJECTED
PENDING_RELEASE --(release approve)--> APPROVED_FOR_DEMO
PENDING_RELEASE --(release reject)--> REJECTED
```

`PASS`는 **수치 주장과 합성규정 비교 결과**에 불과하며 업무 승인·보장판단이 아니다. `INCONCLUSIVE`, `BLOCK`가 존재하는 요청은 제출 불가. 수정 이후 검증 결과를 덮어쓰지 않으며 새로운 변경을 생성하게 한다.

## DB와 데이터 흐름

| DB 엔티티 | 핵심 컬럼/제약 | 사용 목적 |
|---|---|---|
| tenants | id / audit_seq / audit_head | 테넌트 격리와 로컬 감사 head |
| users | tenant_id + id 복합 유니크; token_hash unique | 신원·권한. 비밀 토큰 원문 DB에 저장하지 않음 |
| policy_rules | tenant_id / payload_json / source_sha256 | 적용일·기록시점·특약 스냅샷. 시연용 seed만 쓰기 허용 |
| changes | tenant_id + id 유니크; request/owner/approver 복합 FK; revision | 작업 변경과 승인 상태 |
| evaluations | tenant_id + change_id 복합 FK; 멱등성 유니크 | 변경 요청에 속한 검증 기록 |
| decision_notes | 테넌트·요청·행위자 복합 FK | 담당자의 승인/반려 사유 |
| audit_events | tenant_id + sequence 유니크; prev_hash/hash | 변조 감지용 로컬 체인 |

모든 데이터 조회에서 `authenticated_actor.tenant_id` 조건을 사용하며, API body에서 테넌트를 신뢰하지 않는다. `GET /api/changes/{id}`는 다른 테넌트의 객체도 **404**를 반환.

## 주요 REST API

| 엔드포인트 | 역할 | 동작 / 실패 코드 |
|---|---|---|
| `GET /api/me` | 인증 사용자 | 토큰의 사용자 ID·테넌트·역할 확인 |
| `GET /api/scopes` | 인증 사용자 | 서버 고정 규정/데이터셋/평가자 해시 제공 |
| `POST /api/changes` | 분석가 | 인가된 scope와 서버 해시 불일치 시 409 |
| `GET /api/changes` | 인증 사용자 | 해당 테넌트 목록만 조회 |
| `GET /api/changes/{id}` | 인증 사용자 | 검사·결정 사유 함께 읽기 |
| `POST /api/changes/{id}/evaluations` | 분석가 | `X-Expected-Revision`, `Idempotency-Key` 필수. 409 충돌/스냅샷/멱등성 |
| `POST /api/changes/{id}/submit` | 최초 분석가 | 2개 규정 버전 PASS + 차단 0 + 체인 정상 |
| `POST /api/changes/{id}/domain-decision` | 현업 검토자 | 8자 이상 근거, 자기검토 거절 |
| `POST /api/changes/{id}/release-decision` | IT 승인자 | 자기승인 거절, 소스 해시/증거/체인 확인 |
| `GET /api/changes/{id}/evidence` | 인증 사용자 | manifest, approval digest 매칭, 체인 결과 |
| `GET /api/audit/verify` | 감사 | 로컬 테넌트 감사 체인 검증 |
| `GET /api/fixture-regression` | 분석가 | 지정 합성 사례의 DB-backed 규정 회귀 검사 |

실제 OpenAPI JSON은 서버가 `/openapi.json`, Swagger는 `/docs`에서 자동 생성.

## 승인 인수조건 (현재 구현)

1. 역할을 가진 계정 3개가 서로 다른 신원이어야 한다.
2. 약관 시점·특약·적용 규정이 단일 의미로 `RESOLVED`되어야 한다.
3. 서로 다른 두 규정 버전에서 최소 2개 PASS. 실패/미결정 검증이 0개.
4. 모든 소스 항목의 실제 payload SHA가 저장된 SHA와 일치하고, 생성 시점 source hash와 현재 snapshot이 같아야 한다.
5. 데이터셋·평가자 구현의 서버 고정 SHA와 요청의 고정 SHA가 같아야 한다.
6. 테넌트 감사 체인이 순서·직전 해시·이벤트 해시에서 유효해야 한다.
7. `expected_revision` == 현재 revision. 변경 불일치 409.
8. 승인 근거 사유 최소 8자, 이후 사유 텍스트와 해시의 이벤트가 남는다.
9. 최종 상태는 실제 배포가 아니라 `APPROVED_FOR_DEMO`.

## 문서 기반의 현재 제한

- 클라이언트가 AI가 주장한 일수를 정수로 입력한다. 자연어 주장 자동 파싱은 없음.
- 서로 다른 시점 기준이 섞인 스코프는 안전을 위해 422 반환.
- 외부 문서 파싱, OCR 신뢰도, 의료정보·실제 고객정보 처리는 다루지 않는다.
- 승인 지표는 하나의 변경 안에 등록된 모든 개별 평가 `PASS`를 요구하므로 **과거의 차단 검증을 수정해 통과로 바꿔치기 할 수 없다**. 새 변경 건을 만들어 평가해야 한다.
- PostgreSQL 운영용 마이그레이션·RLS·분산 감사 잠금·백업은 미검증.
