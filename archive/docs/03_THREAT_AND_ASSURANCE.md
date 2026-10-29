> **v5.2 우선순위/상태:** 아래는 v5.1 당시 위협 설명입니다. 상태 행만 바뀌어도 현업 승인 기록 누락을 감지하지 못할 수 있는 P0 후보를 감사에서 추가 발견했습니다. 우선순위는 ../../prebuild/02_IMPLEMENTATION_PLAN.md를 따릅니다.

# 03. 위협 모델 / 증거 무결성 / 실제 보안 격차

## 범위

공개 OWASP API Top 10 2023의 API1(객체 접근), API2(인증), API3(객체 속성) 및 OWASP LLM 2025의 프롬프트 인젝션·민감정보·에이전트 과권한 문제를 참고합니다. 다만 CaseProof v5는 LLM을 실행하지 않으므로 **LLM 공격을 막았다고 주장할 수 없습니다.**

| 위협 | 현재 통제 | 자동 반례 | 운영 전 미완료 |
|---|---|---|---|
| 다른 보험사 리소스 ID 대입 | tenant scope 조회 + composite FK | 타사 접근 404, 타사 FK 쓰기 실패 | DB RLS·DB 계정 분리 |
| 탈취/무권한 토큰 | SHA-256 토큰 해시, 역할 확인 | 401/403 | MFA, SSO, 회전·폐기, 접근 로그 |
| 동일인의 자기 승인 | 요청/현업/최종 승인자 ID 분리 | 동시 다역할이어도 403 | 조직도 연계, 대리 결재 |
| 패키지 데이터셋·평가기 위조 | 서버 계산 원본 3 해시 대조 | 틀린 해시 409 | 서명된 빌드·배포 보증 |
| 평가 응답 DB 위조 | audit event 결박된 request/result SHA | 조작 뒤 승인 409 | 외부 신뢰 앵커·저장 불변성 |
| 감사 이벤트 자체 변경 | 이벤트 SHA-256 체인 | 수정/비정상 JSON 발견 | 독립 WORM·서명·주기 앵커 |
| 승인사유 변경 | DecisionNote 원문 해시와 audit 비교 | 조작 후 승인 409 | 승인자 서명·증빙 권한분리 |
| 동시 덮어쓰기 | revision CAS | 오래된 revision 409 | 다중-worker PostgreSQL 경쟁 테스트 |
| 프롬프트 인젝션 | **없음(LLM 미연결)** | 없음 | 악성 RAG 조각/Tool-output red-team |
| 개인정보 유출·보존 | 합성 데이터만 사용 | 실정보 외부 연계 없음 | DLP·암호화·마스킹·TTL·삭제권 |
| 과도한 API 호출 | 없음 | 없음 | rate-limit/비용 한도/DoS 방어 |

## 감사의 한계

v5.1에서 감사 이벤트 해시 체인만 검사할 경우 **감사 체인은 멀쩡하지만 `Evaluation.result_json`이 수정된 상황**을 놓칠 수 있었습니다. 이제 평가 이벤트에 요청 해시와 결과 해시를 기록하고, `submit`, 현업 결정, 최종 결정 전에 DB 행과 이벤트를 맞대조합니다. 승인 후에는 `GET /evidence`가 `record_integrity_verified` 및 `matches_approval`을 별도 반환합니다.

*변조 탐지와 변조 방지는 별개*입니다. DB 관리자 권한으로 기록·감사 이벤트·체인 head를 모두 재작성하는 공격을 방지하려면 별도 서명 키·외부 타임스탬프/immutable storage에 대한 anchoring이 필수입니다. 따라서 `external_trust_anchor: false`를 강제 표기합니다.

## 우선 보강해야 할 것

P0: PostgreSQL 운영·RLS 테스트, DB 계정 권한 최소화, 인증 수명/회전, 승인 기록 불변 저장, 복구형 change revision.

P1: 관측성·로그에서 민감정보 마스킹, 접근 감사, 보안 스캐너, rate-limit, SAST·Dependency Scan, 마이그레이션/DR 리허설.

P2: LLM 연결 후 Prompt Injection/PII leakage/Excessive agency 정량 레드팀, 외부 평가 제품 비교.

출처: https://api-security.owasp.org/editions/2023/en/0x11-t10/ ; https://genai.owasp.org/llm-top-10/
