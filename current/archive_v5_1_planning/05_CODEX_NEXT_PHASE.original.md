# 05. Codex 구현 지시 — v5.1 이후 미완성 Gate를 순서대로 통과

## 역할

Codex는 코드를 직접 읽고 테스트를 재현한 뒤 변경합니다. 기존 v4 문서를 보존하되 `service/`와 `docs/` v5.1의 실제 구현·계약을 우선합니다. 사용자가 원하는 것은 '멋진 데모 그림'이 아니라 금융 AI 프로젝트를 실무자에게 설명하고 실행까지 증명할 수 있는 결과물입니다. **공식 규제 준수 인증·보험사 운용을 완료했다고 절대 주장하지 않습니다.**

## 구현 우선순위 / definition of done

### G5.2 — PostgreSQL + 마이그레이션 + DB 격리
- Alembic initial + schema versioning, PostgreSQL compose local, owner/read-only roles, RLS 및 복합 FK의 동일 테넌트 제약을 실제 DB 테스트로 확인.
- 두 세션/두 worker에서 `audit_seq` 할당 및 `revision` CAS 경합 E2E. 100회 병렬 오류 없는 상태에서만 통과.
- DB corruption/임의 변경 테스트를 감사 이벤트와 DB 스냅샷에 주입하여 409 fail closed 재현.
- 단일 SQLite 데모는 계속 제공, PG는 별도 config에서 시작; test DB 자동 삭제 금지.

### G5.3 — 업무 검토의 실제 완결성
- `DRAFT`/검토 대기/반려/시정 등록/재검토 상태명세를 표준화하고 이전 승인 불변 기록 유지.
- `PATCH`는 CAS + 불변 change_version 생성, 평가 결과를 수정/삭제하지 않고 새 세대의 테스트로 분리.
- 반려 사유와 정확한 수정 담당자·기한·재검토 요청을 UI에서 추적.
- 승인자 결재에도 Idempotency-Key를 적용하여 네트워크 재시도 중복 승인 방지.

### G5.4 — 실제 AI 응답 어댑터 (Synthetic only first)
- `AIResponseAdapter` 계층: API 응답, 근거 clause IDs, 모델/프롬프트 버전, 비용, 지연, 출력 안전 필터.
- `FakeDeterministicAdapter`로 테스트한 뒤에만 외부 API 선택적으로 연결. API 키·민감 원문 절대 로그에 저장 금지.
- 근거 불충분, 역인용, 취소 약관, 인용 출처 미승인, 프롬프트 인젝션 mock 사례에서 `BLOCK/INCONCLUSIVE` 검증.

### G5.5 — 실험 프로토콜
- 360건의 정답·근거/버전/특약/난이도/위험 등급 라벨을 만들고 160/80/120 등 독립 스플릿을 **정본으로 확정**한 뒤 수정은 버전업.
- 기존 v4 문서의 360건 분할안과 불일치가 있으면 기존 정본을 검토하고 단일 스플릿만 채택. 테스트와 문서의 실험 누수 방지.
- B0(rule-only), B1(vanilla eval), B2(동일 기반 + 도메인 커스텀), T(CaseProof) 모두 같은 모델·데이터·예산·정답 기준. blind gold/stratified bootstrap, 오탐·미탐 CI, 소비자위해 치명 오류 veto. 결과 CSV와 비용 공개.
- Langfuse/Phoenix 도구를 재구현하지 않고 공식 SDK로 trace·eval 데이터 교환.

### G5.6 — 출시/운영 연습
- 외부 키로 서명한 evidence manifest와 immutable 저장소, key rotation, 사건별 로그 서명, 허용된 사용자만 보고서 조회.
- 백업/복구 RTO·RPO 정의 및 실제 수치 측정, 테스트 환경의 멀티테넌트 PII 합성 정책.
- WCAG/KWCAG 접근성, 키보드·스크린리더, 반응형, 대용량 목록과 재검색.

## 작업 규칙
1. 작업 시작 전에 해당 Gate의 현 상태와 변경 계획을 기록.
2. 완료 주장은 새 코드/테스트/실제 결과물로 증빙, 테스트 로그는 `reports/`에 저장.
3. 테스트 파일을 삭제·비활성화하는 방식으로 점수 상승 금지.
4. 검증 불가능한 외부 효과/실무자 피드백을 만들어내지 않음.
5. UI 오류/테넌트 경계/감사 무결성 문제는 새 기능보다 우선.
6. 변경 후 `CASEPROOF_DEMO_MODE=1 python -m pytest -q`와 실제 서버 스모크 재현.
7. 105점은 **항목을 다 채운 후 외부 증거로 평가**. 마케팅 문구만으로 가점 금지.
