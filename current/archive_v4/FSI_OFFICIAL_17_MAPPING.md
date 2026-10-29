# 금융보안원 공식 보도자료 17개 항목 × CaseProof v4 매핑

- 공식 출처: [금융보안원, 금융분야 AI 에이전트 보안 평가기준 마련](https://www.fsec.or.kr/bbs/detail?bbsNo=12122&menuNo=69), 기획부 2026-10-08.
- **문헌 정합성 이슈:** 원문 서두는 **6개 분야·17개 점검항목**이라고 기재. 본문에서 번호가 붙은 분류표는 **1~5개 범주**로 나타남. CaseProof는 서두에 기재된 6개라는 수와 각 17개 항목의 원문 이름을 기록하고, 분류 개수가 완전히 조정되었다고 주장하지 않음.
- ★ 항목은 공식 원문에서 신규 에이전트 특화 위험 표시.
- 아래 '상태'는 v4의 Python 참조 일부 테스트까지 포함하되 실제 금융보안원 보안평가 통과와 무관.

| ID | 공식 발표문 점검 항목 이름 | CaseProof 대응 요구 | 테스트/예정 | 상태 |
|---|---|---|---|---|
| 01 | 인터페이스 보안 | API 인증·스키마·테넌트 경계 | SEC-01; API negative | PARTIAL_REFERENCE |
| 02 | 환각·오정보 대응 | source/provenance/date 검증 | resolver + gold set | PARTIAL_REFERENCE |
| ★03 | 목표 무결성 | 업무 목표/수정 범위 hash 고정 | 변경 스냅샷 검증 | PLANNED |
| ★04 | 연쇄적 실패 대비 | 재시도/차단/격리 | queue fault injection | PLANNED |
| ★05 | 취약한 도구 사용금지 | tool allowlist, source review | tool injection | PLANNED |
| ★06 | 도구 권한 제어 | actor scope, 기본 read-only | forbidden write tests | PLANNED |
| ★07 | 샌드박스 환경구축 | 업로드 파서 격리 | malformed upload | PLANNED |
| 08 | 메모리 오염 방지 | 문서 명령 무시, memory TTL | prompt injection | PLANNED |
| 09 | 메모리 격리 | no cross-session context | scope isolation | PLANNED |
| 10 | 데이터 유출 방지 | 합성/민감정보 마스킹·egress | PII canary | PLANNED |
| ★11 | 에이전트 간 통신보안 | agent-to-agent 연결은 비활성/장래 auth | message spoofing | OUT_OF_SCOPE_INITIAL |
| 12 | 공급망 보안 | 라이브러리 고정·SBOM·hash | dependency audit | PLANNED |
| ★13 | 인적 승인체계 구축 | SoD + CAS + review; client 우회 불가 | `test_v4_controls.py` | PARTIAL_REFERENCE |
| ★14 | 인적 개입 과부하 방지 | 중복 경보 통합·우선순위 | workload user test | PLANNED |
| 15 | 자원 고갈 방지 | token/call/time budget | runaway job simulation | PLANNED |
| 16 | 킬스위치 구현 | 평가/승인 분리 중단 | unit gate + service E2E | PARTIAL_REFERENCE |
| 17 | 로깅 및 감사체계 구축 | 증거 manifest, hash chain, external anchor | `test_v4_controls.py`; storage drill | PARTIAL_REFERENCE |

**중요:** 이 표는 통제 요구사항을 공식 명칭에 연결한 사전 계획이다. `PARTIAL_REFERENCE`는 순수 Python 합성 참조 코드의 특정 테스트만 통과한 상태이며 실제 인프라의 보안 기준 만족을 뜻하지 않는다.
