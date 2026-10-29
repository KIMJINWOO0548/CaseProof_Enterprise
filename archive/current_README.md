> **개발 업데이트 / 2026-10-29:** 실제 SQLite/API에서 승인 우회를 차단하고 G1 승인 무결성·입력·재시도 계약을 구현했습니다. 이번 전체 검증은 Windows 검증 전용 실행기에서 157개와 하위 22개 통과, 스모크 12/12입니다. 최신 증거·실행법·제약은 [개발 상태](../DEVELOPMENT_STATUS.md)를 먼저 읽으세요. 모든 변경 POST는 Idempotency-Key를 요구합니다. 신규 합성 DB만 검증했으며 기존 DB 자동 마이그레이션은 없습니다. 아래 v5.1 설명·과거 실행 기록과 구분하세요.

# CaseProof Enterprise v5.1 — 실제 API·DB·UI를 연결한 합성 데이터 MVP

> **정본 / 2026-10-29.** 이 버전은 보험사에 납품 가능한 제품이 아닙니다. **합성 규정에 대한 결정론적 숫자 주장 검증 서비스**입니다. 실제 AI LLM 연결, 실상품 적합성 판단, 실제 보험금 지급 결정, 개인신용정보 취급, 법규 인증을 지원하지 않습니다. v4의 폭넓은 설계와 달리 **v5 서비스 구현에서 작동하는 좁은 기능**만 구현 완료로 표시합니다.

## 실행 상태
- FastAPI HTTP API / SQLAlchemy 관계형 모델 / SQLite 로컬 DB / 실제 서버에 연결되는 정적 웹 UI.
- 보험사 이름 대신 **가상 AURORA_NONLIFE, HORIZON_LIFE** 두 테넌트와 가상 상품/특약 사용.
- 서버에서 발급한 토큰으로 역할 선택, 서버에 있는 데이터셋·평가자·규정 파일 해시를 고정, 변경 생성→두 버전 평가→현업 검토→별도 승인→증거 확인.
- 감사 이벤트 SHA-256 체인 **+ 감사 내용과 DB의 평가 결과/승인근거를 교차 검증**. WORM/외부 신뢰 앵커/전자서명은 미구현.
- 1인 로컬 시연용 SQLite 실행만 실제 통합 검증. PostgreSQL/SSO/운영 인프라는 후속 검증 대상.

## 바로 시작하기 (Windows PowerShell)

```powershell
cd .\CaseProof_Enterprise\current
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
$env:CASEPROOF_DEMO_MODE = '1'
python -m service.cli init-demo
# 출력된 토큰을 외부에 공유하거나 저장소에 올리지 마세요.
python -m uvicorn service.app:app --host 127.0.0.1 --port 8000 --workers 1
```

브라우저에서 `http://127.0.0.1:8000/`을 엽니다. `init-demo` 출력의 토큰을 하나씩 입력해 화면의 역할을 바꿉니다. **같은 브라우저에서 역할 변경은 연결 해제 후 다시 로그인**합니다. 서버 토큰은 브라우저 메모리에만 두며 새로고침하면 재로그인이 필요합니다.

## macOS / Linux

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements-dev.txt
export CASEPROOF_DEMO_MODE=1
python -m service.cli init-demo
python -m uvicorn service.app:app --host 127.0.0.1 --port 8000 --workers 1
```

`sqlite:///./caseproof_demo.sqlite3` 파일은 실행 위치에 저장됩니다. 초기화한 토큰을 잃어버렸다면 **가상 데이터가 담긴 로컬 DB 파일을 삭제한 뒤** `init-demo`를 다시 수행하세요. 운영 데이터는 절대 삭제하지 마세요.

## 자동 검증

```bash
# 합성 통합 테스트 + 기존 v4 참조 테스트
CASEPROOF_DEMO_MODE=1 python -m pytest -q
# Windows PowerShell: $env:CASEPROOF_DEMO_MODE='1'; python -m pytest -q

# 사람 없이 3자 검토와 감사증거까지 재현
python -m scripts.smoke
```

`reports/`에 생성된 결과를 참고하되 **테스트 성공은 실제 LLM 정확도나 보안 인증을 의미하지 않습니다.** 버전별 실행 결과와 코드 변경은 Git에서 별도로 보존하세요.

## 화면에서 수행할 작업
1. `aurora-analyst` → 약관 범위 선택, 변경 요청 생성.
2. 2026-06-30 기준 **30일**, 2026-07-01 기준 **20일**의 합성 규정을 검증. 성공 시 서로 다른 두 규칙 버전에 대한 PASS 기록 2개가 쌓입니다.
3. **현업 검토 요청** → `aurora-reviewer`로 접속 → 근거를 기록하며 현업 승인.
4. `aurora-approver`로 접속 → 다른 담당자의 검토 이력 확인 → **데모 출시 승인**.
5. `aurora-auditor` 접속 → 감사 체인 검증. 권한/회사 경계 위반, 같은 사람이 요청과 승인을 수행하면 서버에서 차단됩니다.

**중요:** BLOCK 또는 INCONCLUSIVE가 하나라도 있으면 이 시연 버전은 해당 변경을 제출할 수 없습니다. 재검증을 위해 검증 이력을 지우는 기능도 없습니다. 실제 제품에서는 변경 수정, 오류 시정, 재검증 버전 생성이라는 별도 workflow가 필요합니다. 이것을 완성된 시정 절차라고 주장하지 마세요.

## 디렉터리 정본

| 경로 | 의미 | 상태 |
|---|---|---|
| `service/` | 실제 동작 FastAPI·DB·정적 UI | 로컬 테스트 완료 |
| `reference/` | 시점 규정 결정론 엔진·평가기·참조 통제 | 테스트 완료 |
| `datasets/` | 가상 보험업무팩과 20개 규정 정답 사례 | 합성 데이터만 |
| `tests/` | 통합·참조 단위·권한·변조 테스트 | 로컬 pytest 통과 |
| `docs/01~05` | 구현 아키텍처·계약·위협 모델·현업 수용·점수 | 설계 문서 |
| `archive_v4/` | 이전 범위가 넓은 계획서의 참고본 | 런타임 정본 아님 |
| `reports/` | 로컬 검증 로그와 스모크 기록 | 실행 결과 |

**충돌 우선순위:** v5.1 실제 서비스 코드·v5.1 명세 > v4 예시 설계 > 이전 버전. 코드와 문서가 다르면 구현 완료가 아니라 `미일치`로 등록하고 수정해야 합니다.

## 당장 구현되지 않은 주요 기능

실제 LLM/RAG, OCR/PDF 문서 처리, 360건 블라인드 실험, 소비자위해 자동 탐지, AI 모델 전후 동등 비교, 실제 상품 약관 등록, 운영자 승인 workflow 재시도, SSO/MFA, RLS·PostgreSQL 통합 시험, 실사용자 조사, 외부 WORM 앵커, 백업/복구 게임데이, 접근성 검증, 보안 침투테스트, Langfuse/Phoenix 벤치마크, 타인 Windows 설치 재현.

## 브라우저 UI 검증

실제 브라우저 localhost 클릭을 이 컨테이너에서도 시도했지만 Chromium 접근 정책(`ERR_BLOCKED_BY_ADMINISTRATOR`)으로 수행할 수 없었습니다. **따라서 브라우저 합격이라고 기록하지 않았습니다.** 사용자 PC에서 `pip install playwright`, `python -m playwright install chromium`, `CASEPROOF_TEST_ANALYST_TOKEN` 환경변수 지정 후 `python -m scripts.browser_acceptance`로 다시 실행하세요. API TestClient 통과와 브라우저 합격은 별개입니다.

## 보안 한계
- 로컬 데모의 Bearer 토큰은 SaaS 인증 구현이 아닙니다. 실고객 데이터 입력 **금지**.
- SHA-256 체인은 DB 내부 조작의 일부를 탐지할 뿐, DB 전체를 제어하는 관리자 공격자에게 변조 불가능한 증거를 제공하지 않습니다.
- 개인 신용정보 처리·보존·파기·전송·로그 마스킹과 규정 준수는 범위 밖입니다.
- 이 코드의 `APPROVED_FOR_DEMO`는 실제 소프트웨어 배포 승인이 아닙니다.

## 근거
- OWASP API Security Top 10 2023 (특히 객체 수준 인증/인증 체계): https://api-security.owasp.org/editions/2023/en/0x11-t10/
- NIST AI RMF / 금융권 AI 가이드라인 / 금융보안원 AI 에이전트 보안 평가 기준: `archive_v4/` 연구 노트를 참고하되 최신 공식 원문을 재검증할 것.
- 프로젝트 점수는 공개자료를 바탕으로 고안한 **자체 평가표**이지 금융사 채용기관의 공식 점수가 아닙니다.
