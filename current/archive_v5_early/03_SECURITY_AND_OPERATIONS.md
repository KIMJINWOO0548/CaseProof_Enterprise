# 보안·운영 준비도와 실제 미해결 위험

## 이미 처리한 위험

| 위험 | v5 방어 | 재현 검증 |
|---|---|---|
| API 객체 ID 변경으로 타사 접근 | 모든 객체에 인증 사용자 tenant 조건; 404 | cross_tenant_object_404 |
| 관계 참조로 타사 객체 주입 | tenant_id+id 복합 FK, SQLite foreign_keys=ON | composite_fk_prevents_cross_tenant_evaluation |
| 자기 요청 자기 승인 | 역할·서로 다른 실제 사용자 ID 검증 | same_requester / approver_separation |
| 검증 결과 1건만 PASS한 출시 | 서로 다른 2개 적용 규정 버전 PASS 필수 | one_pass / duplicate_version |
| 검증 요청 중복·변조 | Idempotency-Key + payload SHA; revision CAS | idempotency / stale_revision |
| 소스 변경 은폐 | 정책 payload SHA 재검산, 스냅샷 비교 | tamper_source |
| 감사 수정 은폐 | sequence + prev_hash + event_hash 연결 후 검증 | tamper_audit |
| 미승인 자료의 숫자 답변 | RESOLVER → INCONCLUSIVE, 제출 불허 | unapproved_source |
| 사용자가 임의 해시 입력 | 서버가 확정한 소스/데이터/평가자 SHA 요구 | snapshot_mismatch |

## 이 코드를 운영용으로 배포하지 말아야 할 이유

1. **SSO/MFA 없음:** 로컬 장기 bearer 토큰(해시 저장)만 지원. 1회 발급·재발급, 회수·만료·속도제한·세션 안전 미구현.
2. **배포/외부노출 금지:** 데모는 127.0.0.1 / SQLite / 단일 worker 기준. TLS·CSRF/보안 헤더·API WAF·운영 secret 관리 미완료.
3. **Postgres RLS 미검증:** 복합 FK와 application-layer tenant filter는 구현했지만 실제 DB RLS/마이그레이션/격리 테스트는 없음.
4. **감사 증빙의 한계:** 동일 DB 관리자 공격자가 event+hash+head를 함께 수정하면 SHA 체인은 독립적인 위변조 방지책이 아님. 외부 append-only 앵커/키 기반 서명/독립 보관 필요.
5. **동시성:** PG tenant row `FOR UPDATE` 기반 로직을 설계했으나 실제 PG 부하 테스트 없음; SQLite는 단일 worker 데모 제한.
6. **데이터:** 모든 약관은 가상. 진짜 약관 해석·법률 자문·실보험 소비자 결정을 지원하지 않음.
7. **평가:** AI 연결/자연어 claim extraction 없음. 손해보험사의 실제 고객정보, 상담·의료서류 업로드 기능도 없음.
8. **업무 승인:** `APPROVED_FOR_DEMO`는 **출시 승인 UI 모형**이며 실제 배포 권한 또는 감사 인증이 아님.
9. **재해복구:** 운영 백업, restore, incident response, 취약점 스캔, PII/DLP 정책 미검증.
10. **브라우저 E2E:** 테스트 스크립트는 준비했지만 이 컨테이너 정책이 localhost를 차단해 실제 UI 자동 실행을 증명하지 못했음.

## 우선 구현할 운영기능 — 도입 게이트

- SSO/OIDC+MFA, tenant claims 서버 검증, 토큰 회수, 보안 세션.
- Postgres DB migration, RLS `USING/WITH CHECK`, 변경 시나리오별 교차 권한, 동시 승인 경쟁.
- 표준화된 이벤트 outbox, external immutable log anchoring / KMS 서명, retention·삭제 정책.
- 작업 큐 DLQ/재시도·회로차단·Kill switch, 생애주기 이벤트 관찰성.
- 업로드를 만든다면 먼저 바이러스 검사, MIME/크기, OCR 품질, PII 마스킹, 악성 PDF 안전 격리.
- 최소권한 권한 부여/회수 화면, 변경 이유와 원문 증거의 독립 보존.

참고: OWASP API1:2023 Broken Object Level Authorization 등은 객체 경계 검증을 권고함. https://api-security.owasp.org/editions/2023/en/0xa1-broken-object-level-authorization/
