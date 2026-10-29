> **v5.2 우선순위/상태:** 아래 기록은 v5.1 작성 환경의 과거 실행 결과입니다. 2026-10-29 감사의 새 환경에서는 서비스 pytest 및 smoke를 재실행하지 못했습니다.

# 검증 결과 / 2026-10-29

## 직접 실행됨
- Python: `CASEPROOF_DEMO_MODE=1 python -m pytest -q --disable-warnings`
- 결과: **90 passed, 22 subtests passed**. `pytest_v5_log.txt` 원본 재현 로그.
- Node JS: `bash scripts/check_ui_syntax.sh` → **UI_JS_SYNTAX_PASS**.
- 문서: `CaseProof_Enterprise_v5_실행검증_상세보고서.docx`를 도구로 렌더링 후 시각 확인(7페이지).
- 코드는 데모 데이터 2개 조직, 7개 역할별 계정, 합성 정책 규칙으로 테스트.

## 검증 실패/제약을 숨기지 않음
- `python scripts/browser_e2e.py` 실행: 이 실행환경 Chromium 정책이 `127.0.0.1:8767` 접근을 `ERR_BLOCKED_BY_ADMINISTRATOR`로 차단. **브라우저 E2E PASS 아님**.
- Docker Compose: 작성했으나 이 컨테이너에서 실제 image build/boot 검증 안 함.
- PostgreSQL + RLS: 미구현/미측정. 운영용 DB 인증 불가.
- 외부 LLM, Langfuse/Phoenix, 금융회사 실제 API: 연동 없음.
- 360건 검수·비교, 실제 현업 사용성 실험: 아직 미실시.

## 보안 해석
로컬 DB 내부 SHA 체인은 내장 감사변조 감지 시연이며 WORM, 서명, 비가역적 증거 보존이 아님.
