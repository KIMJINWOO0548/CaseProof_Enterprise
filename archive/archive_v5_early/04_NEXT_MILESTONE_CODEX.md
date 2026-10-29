# Codex handoff — v5 이후 개발 지시 정본

## 현재 상태(절대 재구현하거나 과장하지 말 것)

- `service/`: 실제 FastAPI + SQLAlchemy DB와 승인 API. 오프라인으로 실행 가능.
- `reference/`: 결정론적 합성 규정 엔진과 평가/해시/paired 벤치마크.
- `tests/`: 90개 pytest + 22 subtests 통과.
- `service/static/index.html`: 실제 API를 호출하는 UI 작성. 브라우저 정책으로 이 환경에서는 자동 E2E 미완료.
- 실제 운영 보험사·LLM·RAG/Promptfoo/Phoenix/Langfuse 연동 **없음**.

## 다음 개발 순서 (순서 변경 전 명시적 ADR 작성)

### Gate 2 → 실제 브라우저 통합 검증

1. 깨끗한 Windows PC에서 `README.md`대로 설치하고 `python scripts/browser_e2e.py` 경로를 로컬 정책에 맞게 수정하지 말고 실행(Chromium 경로만 환경 설정화).
2. Playwright 계정 3개로 `create → PASS 2종 → domain review → release approve → manifest` 자동 E2E 추가. 스크린샷·로컬 서버 로그, 실패시 HAR(토큰·개인정보 제거) 저장.
3. JavaScript lint, TypeScript 또는 React로 UI 단계적 리팩터링하되 API JSON 계약은 유지.
4. WAI-ARIA 키보드 접근성과 200% 줌, Korean error labels, 빈 상태·타임아웃·중복클릭, 비동기 상태를 점검.

### Gate 3 → 변경 전후 paired evaluation + 영향 그래프

1. 현재 `reference/paired_benchmark.py`, `reference/impact.py`를 서버의 읽기 전용 서비스로 연결.
2. TestRun / TestCase / SourceSnapshot / ArtifactVersion 테이블을 추가.
3. Baseline↔candidate `dataset_sha256`, `evaluator_sha256`, `case_id` 정합성 검사를 DB 트랜잭션으로 보장.
4. 신규 CRITICAL 또는 미실행 테스트가 하나라도 발생하면, 평균 성능이 좋아도 전환 불가. `NEEDS_DOMAIN_REVIEW` 별도.
5. 외부 평가 엔진과의 비교 측정 없이 자체 제품 우위 선언 금지.

### Gate 4 → 실제 Postgres+RLS 보안 테스트

1. Alembic migration 생성. 신규 SQLite 개발 시드와 PG 스키마 동일 데이터 계약 검증.
2. `policy_rules`/`evaluations`/`changes`/`decision_notes`/`audit_events` RLS 활성화·강제.
3. DB에 actor tenant context를 트랜잭션 단위 `SET LOCAL`로 설정하고 누락 시 fail-closed. connection pool contamination 음성 검사.
4. worker 2개 이상의 동시 승인 시 한쪽만 200, 나머지 409. 재시도시 Idempotency 결과 확인.
5. 별도 서비스에 감사 head anchor를 기록하고 변조 시 알림/승인 중지.

### Gate 5 → 보험 업무팩 재사용성

1. 손보 AUTO-101·생보 LIFE-201 외 제3 가상 업무팩을 코어 로직 변경 없이 schema+fixture로 추가.
2. 특약 중첩, 소급 개정, 기준일 변경, 복수 상품·문서 충돌, 미승인 문서·만료 출처 경계 사례를 늘림.
3. 공통 core에 insurer-name 문자열 분기가 0인지 AST/린트로 확인.

### Gate 6 → 실측 경쟁 비교

1. B0 수작업, B1 범용 RAG, B2 기존 평가도구+동일 도메인 규칙, T CaseProof를 동일 데이터·모델·문서·평가자로 비교.
2. 360건은 아직 목표. 180 train/90 validation/90 holdout으로 버전·결정 사유와 전문가 검수를 기록.
3. 실험이 없으면 결과표를 비워 두고 성과 수치 임의 생성 금지.

## 금지

- SQL 스키마를 바꾸면서 API/테스트/README 갱신 누락 금지.
- 고객정보를 로그·감사 이벤트·프롬프트 원문에 기록 금지.
- 임의 공개 웹에서 추출한 보험 약관을 실제 지급 판단에 사용하는 기능 금지.
- `APPROVED_FOR_DEMO`를 `DEPLOYED`로 표기 금지.
- 기본 100점 만점 또는 추가 5점을 코드가 생성됐다는 이유만으로 선언 금지.

## 인수조건

모든 PR/작업에는 (A) 해당 요구사항 ID, (B) 변경 파일, (C) 양/음 테스트, (D) 전후 API 계약(diff), (E) 위험·리스크, (F) 실패시 롤백, (G) 실행 로그를 남길 것. 테스트 커버리지 수치와 외부 실무 채택 증거를 구분할 것.
