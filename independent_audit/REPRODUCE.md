# CaseProof Enterprise v5.1 감사 재현 안내

기준일: 2026-10-29 KST. 본 디렉터리는 원본과 별도인 감사 산출물이다. 모든 데이터는 합성값이며 실제 보험사 정보·고객정보·운영 DB를 사용하지 않는다. `live_probes.py`는 감사 당시 실행하지 않았으므로 실행 결과를 보장하지 않는다.

## 1. 원본 확인 및 복사

원본 ZIP SHA-256:

```text
e1ad52fc13fc700e697b816ed280a9a4d1547b6df29da5bbeab9e8814c6ebaec
```

압축 해제 전 절대경로·`..`·역슬래시·중복 파일명·심볼릭 링크와 크기를 점검했다. 107개 항목이었고 총 압축해제 바이트는 1,466,957였다. `PACKAGE_MANIFEST_SHA256.json`은 자기 자신을 제외한 106개 파일을 포함하며, 파일 106/106의 해시 일치, 추가 파일 0개. 별도로 첨부된 CSV와 ZIP의 `SCORECARD_105.csv`는 바이트까지 일치했고 두 SHA-256은 `ceeb649c29c79e5796565e949ae3c39eaff23165b71c35195b46702c55a2e7a9`이다. `legacy/` 내부 ZIP은 압축 해제하여 현재 소스에 섞지 않았다.

테스트는 원본을 보호하기 위해 패키지를 별도 임시 폴더에 풀고 `CaseProof_Enterprise/current`의 실행 사본에서 한다. `scripts/smoke.py`는 성공 시 `reports/integration_smoke.json`을 새로 쓰므로 원본에서 직접 실행하지 않는다. `scripts/browser_e2e.py`는 고정된 테스트 DB 경로를 실행 전 삭제하므로 실행 전 코드를 검토하고 **버려도 되는 사본**만 사용해야 한다.

## 2. 이번 환경 및 결과

- OS: Linux; Python `3.12.14`; Node `v24.22.1`; Pydantic `2.14.1`.
- 누락: pytest, FastAPI, SQLAlchemy, httpx, uvicorn, Python Playwright. PostgreSQL 서비스·실제 보험사 DB는 사용하지 않음.
- `requirements-dev.txt` 설치를 별도 venv에서 시도했으나 패키지 다운로드 프록시 연결 제한으로 실패. `logs/dependency_install.txt` 참조.
- 이번 `pytest`와 smoke는 실패했으나 이전 작성자의 `current/evidence/pytest_v5_log.txt` 기록은 **90 passed + 22 subtests / 4.38초**, `reports/PACKAGING_VALIDATION.md`는 **90 + 22 / 3.52초와 smoke 12/12**라고 보고한다. 그 과거 결과는 이번 독립 재실행 결과가 아니다.

## 3. 이번에 실제 실행한 명령

아래에서 현재 디렉터리는 복사본의 `CaseProof_Enterprise/current`였다. `PYTHONDONTWRITEBYTECODE=1`과 `PYTEST_ADDOPTS='-p no:cacheprovider'`를 사용했다. 현재 평가 환경에선 `python`이 `/opt/codex/runtimes/codex-primary-runtime/dependencies/python/bin/python`이다.

```bash
CASEPROOF_DEMO_MODE=1 python -m pytest -q
# exit 1: No module named pytest

CASEPROOF_DEMO_MODE=1 python -m scripts.smoke
# exit 1: No module named fastapi

PYTHONPATH=.:tests python -m unittest -v \
  test_resolver test_answer_check test_release_impact test_v4_controls
# Ran 49 tests ... OK
```

20개 기준 사례는 `test_resolver.py`의 `subTest`로 검사했다. 2개 데이터/평가자 불일치 분기 역시 subTest다. `unittest` 요약은 subTest 수를 별도로 출력하지 않으므로 22개는 소스 구조상 확인된 분기 수다. 서비스 연동 테스트 `tests/test_service.py`의 41개 함수는 실행하지 못했다. 소스 AST로 테스트 함수 90개(49 + 41)를 세었지만 이것은 통과 건수가 아니다.

`service/static/index.html`에서 단일 `<script>` 내용을 별도 `evaluation/logs/ui_script_0.js`에 추출한 뒤 `node --check .../ui_script_0.js`를 실행했다. 종료코드 0. 이것은 문법 검사이지 브라우저 E2E가 아니다. 3개 데이터 JSON 파싱, 10개 룰·20개 정답 사례 고유 ID, 날짜 범위와 source_state의 기본 구조를 확인했다. 26개 Python 소스는 AST 파싱만 했다.

Pydantic `service.schemas`의 `model_json_schema` 및 `model_validate`를 별도 실행했다. `Decision`에는 reason이 required로 나오지 않지만 런타임에서는 reason 8자 미만을 거부했고, `EvalRequest`의 `True`는 `1`로, 문자열 `'30'`은 `30`으로 변환됐다. `logs/schema_validation.txt`가 출력이다. 전체 FastAPI `/openapi.json`은 생성하거나 확인하지 못했다.

## 4. 독립 격리 모의 실험

다음 명령에서 `CASEPROOF_CURRENT`는 원본과 분리해 압축 해제한 current/의 절대경로다. Python 표준 라이브러리만 사용한다.

```bash
CASEPROOF_CURRENT=/absolute/path/CaseProof_Enterprise/current \
  PYTHONDONTWRITEBYTECODE=1 python /absolute/path/evaluation/audit_probe.py
```

PowerShell:

```powershell
$env:CASEPROOF_CURRENT = 'C:\audit-copy\CaseProof_Enterprise\current'
$env:PYTHONDONTWRITEBYTECODE = '1'
python C:\audit-output\evaluation\audit_probe.py
```

`audit_probe.py`는 원본 함수 코드를 AST로 추출하고 가상 ORM, 가상 트랜잭션·scope/evidence helper를 주입한다. 정상 감사 event·평가 두 건을 구성한 후 상태값만 바꾸고 실제 `release_review` 함수 본문을 호출한 결과 `APPROVED_FOR_DEMO`, `audit_ok=True`, `record_integrity=True`, DOMAIN 승인 건수 0이 관찰됐다. 이것은 **실제 HTTP/DB 공격이 아니라 코드 격리 실험**이다. 같은 스크립트는 중복 생성, 기준선 incomplete, DRAFT 특약 fallback도 실험한다. 출력: `logs/independent_probes.txt`.

## 5. 실제 SQLite/TestClient 후속 실험 — 이번에는 미실행

별도 사본에서 가상환경을 만들고 `requirements-dev.txt`를 설치한 뒤, 아래 테스트를 실행한다. 이미 설치 가능한 환경에서만 수행한다. 패키지 버전은 미고정이므로 해시 잠금·환경 차이를 별도로 기록한다.

```bash
cd /absolute/path/CaseProof_Enterprise/current
python -m venv /absolute/path/caseproof-audit-venv
/absolute/path/caseproof-audit-venv/bin/python -m pip install -r requirements-dev.txt
export CASEPROOF_CURRENT="$PWD"
export CASEPROOF_DEMO_MODE=1
/absolute/path/caseproof-audit-venv/bin/python -m pytest -q
/absolute/path/caseproof-audit-venv/bin/python -m scripts.smoke
/absolute/path/caseproof-audit-venv/bin/python /absolute/path/evaluation/live_probes.py
```

`live_probes.py`는 매 시나리오별 OS 임시 디렉터리에 SQLite 샘플 DB를 만들고 테스트 토큰을 사용한다. 잘못된 토큰·다른 테넌트·자기 승인, 상태 행 변조 후 출시 승인, change POST/evaluation POST 재전송, 평가 결과 변조, 감사 체인 변조, 동시 승인을 시험하도록 작성했다. `raise_server_exceptions=False`이므로 결과에 500이 있으면 성공으로 치지 말고 원인을 확인해야 한다. 이 파일은 AST 문법 확인만 받았으며 예측 출력이 아닌 **현장 실행 결과**를 기록해야 한다.

PostgreSQL RLS, DB 권한 탈취, 네트워크 경계, 독립 WORM은 SQLite 시험으로 대체되지 않는다. 별도의 격리된 PostgreSQL 테스트 인스턴스·제한된 app role과 복수 세션이 필요하다. 브라우저는 Playwright와 Chromium 설치 후 합성 DB만을 대상으로 실행하며 로그인만 검사하는 `browser_acceptance.py`와 전체 `browser_e2e.py`를 구분한다.

## 6. 파일 변경 사항

- 사용자 제공 원본 ZIP/CSV: 변경 없음. 패키지 추출본의 106개 해시 일치.
- 감사용 사본: `audit_execution/current/`에 복사; 실패한 smoke는 보고서 파일을 쓰기 전에 종료됨.
- 별도 감사 산출물: `REPORT.md`, `SCORECARD_FILLED.csv`, `sources_table.csv`, `REPRODUCE.md`, `audit_probe.py`, `live_probes.py`, `logs/`.
- 평가용 가상환경은 패키지 코드에 설치하지 않았고 기본 의존성 설치가 실패했다.
