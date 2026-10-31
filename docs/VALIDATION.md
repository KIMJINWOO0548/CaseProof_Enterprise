# 검증 결과 — 5.3.0.dev4

## 5.3.0.dev4 — G1.2 불변 저장과 SQLite migration

2026-10-31 KST. Windows / Python 3.12.10 / SQLAlchemy 2.1.6 /
Alembic 1.20.1 / 임시 합성 SQLite / 단일 worker. 새 프로젝트 검증 환경과
체크아웃 밖의 별도 wheel 환경을 사용했다. [공개 실행 증거](evidence/g12/verification.json),
[전체 pytest 출력](evidence/g12/full-pytest.txt), [실제 CLI 기록](evidence/g12/migration-cli.json).

| 검사 | 관찰 결과 |
| --- | --- |
| 변경 전 manifest | 콘솔 PASS 223개; 원본 stdout 보존본으로 가장하지 않음 |
| 새 환경 hash lock 설치·pip check | exit 0; 기존 버전 유지, Alembic/Mako/MarkupSafe 추가 |
| 기존 baseline 재현 | 456 passed + 22 subtests, exit 0 |
| 신규 schema 검사 | **223 passed**, exit 0; FK·UNIQUE·정수·불변 기록·rollback·baseline 보존 |
| 최종 전체 pytest | **679 passed + 22 subtests**, exit 0, 경고 3개 |
| 실제 Alembic CLI | upgrade → check → downgrade → upgrade → check 모두 exit 0 |
| baseline smoke | **12/12**, exit 0 |
| JS 문법·실제 요청 재시도 함수 | 각각 exit 0; 새 브라우저 실행과 구별 |
| wheel/sdist·격리 wheel 설치 실행 | **5.3.0.dev4 PASS**, runtime model·migration source·Tabler notices 포함; import·seed·HTML·health·CSS 확인 |

초기 [누락 모듈 실패](evidence/g12/schema-red.txt), fixture tenant 삽입 순서 오류,
독립 검토에서 재현한 [5개 실패](evidence/g12/review-red.txt), constraint 이름 충돌로
인한 Alembic roundtrip 실패를 보존했다. DDL에 실제 BEGIN을 적용하고 immutable
PK/UNIQUE 충돌을 INSERT 전에 거부해 실패 도중 partial DDL과 OR REPLACE 우회를
차단했다. 제약 이름을 전체 열 조합으로 고정한 뒤 [최종 schema 검사](evidence/g12/schema-green.txt)가 통과했다.

전체 suite는 `scripts.windows_checks`의 소켓 초기화만 230회 재시도했다.
HTTP/assertion 재시도는 없다. 기존 Starlette deprecation 1개와 Alembic의 순환
FK 정렬 경고 2개가 남는다. Alembic 자동 diff만으로 순환 FK 전체를 검증했다고
주장하지 않으며 실제 FK 삽입·tenant 참조 거부·commit/rollback 검사와 구분한다.
체크아웃 밖 wheel 실행은 초기화 1회 재시도했다.

이번 변경은 baseline UI를 수정하지 않아 새 브라우저 실행을 하지 않았다.
G1.3 executor/이력 재구성, G1.4 HTTP, G1.5/1.6 gate/봉인 검증,
G2 PostgreSQL 권한/RLS/경합, 독립 사용자·전문가 검수와 운영 검증은 미완료다.
SQLite owner의 전체 재작성에 대한 외부 보증도 제공하지 않는다.

## 5.3.0.dev3 — Tabler 검토 화면

Windows / Python 3.12.10 / Chrome 156 / 임시 합성 SQLite. [새 로그](../reports/runs/20261030T142434Z-a01caa29/)와 [화면 범위](UI_WORKSPACE.md)를 함께 읽는다. UI 자체와 승인 기록을 실제 브라우저에서 조작했고, DB에서도 결과를 확인했다.

| 검사 | 실제 결과 |
| --- | --- |
| 최종 전체 pytest | **456 passed + 22 subtests passed**, exit 0; 기존 deprecation 경고 1개 |
| 새 UI asset 회귀 | 페이지의 stylesheet 부재로 1 failed → 실제 경로·원본 SHA-256·라이선스·경로 탈출 차단 1 passed |
| Node 실제 요청 함수 | 중복 클릭 때 2회 전송하는 실패 관찰 → 동시 전송 공유·actor 범위·원래 키 재시도·세션 무효화 PASS |
| 실제 브라우저 승인 시나리오 | **12개 assertion PASS**: 생성→서로 다른 규정 2개→현업 검토→다른 최종 승인자→증거 |
| 응답 유실 | 실제 commit 뒤 성공 응답만 폐기; 역할 전환 후 원래 actor가 동일 key/body/revision으로 복구 |
| DB 교차 확인 | 최종 revision 6, 전이 1–6, 서로 다른 담당자 3명, 결정 2개, RELEASE note 1개 |
| 브라우저 보조 검사 | **11개 assertion PASS**: 검색·필터·라벨·live region·세션/상세/증거 응답 순서·실패 시 payload 제거 |
| XSS / 잘못된 입력 | 저장된 markup 제목을 text로 렌더링; 실제 서버 422를 표시하고 입력 폼 유지 |
| 반응형 | Tabler 최종 화면 375/768/1024/1440 viewport에서 `scrollWidth <= clientWidth` 확인; 이미지도 실제 캡처 |
| 상태 글자 대비 | upstream 작은 badge 1.97–4.04:1 관찰 → 앱 색 보정 후 녹색 6.46 / 적색 7.20 / 황색 6.33:1 |
| 외부 UI 리소스 | 해당 Chrome 실행의 외부 origin 리소스 0개; Tabler CSS는 local route에서 제공 |
| 빌드 / 배포물 내용 / 격리 설치 | 5.3.0.dev3 wheel·sdist PASS, vendor CSS·MIT notices 포함; 체크아웃 밖 seed·HTML·health·stylesheet 응답 PASS |
| 실제 GitHub CI | 코드 `e328d01`의 [실행](https://github.com/KIMJINWOO0548/CaseProof_Enterprise/actions/runs/41078723763) success; Linux 3.11/3.12/3.13·Windows 3.12·빌드/설치·JS·OSV의 7개 job 성공, push에서 PR 전용 검사 1개 skipped |

전체 suite는 `scripts.windows_checks`를 사용했고 최종 소켓 초기화 재시도는 366회였다. HTTP/assertion을 재시도한 것은 아니다. UI probe 첫 시도는 이전 mutation 완료 전에 disabled 역할 전환 버튼을 눌러 실패했다. probe가 작업 완료를 기다리도록 수정한 재실행은 통과했다. CSS 없는 `about:blank`에서 나온 대비 값은 유효 검증으로 집계하지 않았고, probe에 stylesheet 부재 거부를 추가했다. 모바일 4px overflow는 Tabler `row-cards` 배치로 수정했다.

Chrome DevTools MCP의 모바일 전체 캡처가 지연돼 중단하고, Playwright MCP로 화면 크기 검사·실제 캡처를 수행했다. 별도 Python `scripts.browser_e2e`는 Playwright 패키지 부재로 exit 1이며 **미실행**으로 취급한다. MCP 브라우저 실행과 이 CLI를 구별한다. 새 Python/npm 패키지 설치나 전역 변경은 없었다. 기본 favicon 404 및 입력 오류 시험의 422는 관찰했으며 콘솔 전체가 무오류였다고 주장하지 않는다.

이는 baseline `/api`의 UI 검증이다. 신규 v1 HTTP/DB, PostgreSQL/RLS, 완전 접근성 인증, 독립 사용자 관찰·외부 전문가 검수 및 운영 검증은 미완료다. 내부 AI 검토는 외부 검수로 집계하지 않는다. 페이지 새로고침 시 메모리의 토큰·미확인 요청 복구 정보가 사라지는 제약이 남는다.

## 5.3.0.dev2 G1.1 — 2026-10-30 KST

실행은 Windows / Python 3.12.10 / 프로젝트 가상환경이다. [이번 run](../reports/runs/20261029T154037Z-4b5b5b75/)은 10월 29일 UTC에 시작해 30일 UTC에 이어서 수행했다. v1 테스트는 DB 없이 실행하며 기존 HTTP 회귀는 임시 합성 SQLite를 사용했다.

| 검사 | 실제 결과 |
| --- | --- |
| 변경 전 manifest | 콘솔에서 204개 PASS 관찰; 원본 stdout 보존본으로 가장하지 않음 |
| 새 DTO·상태 전이 RED | 모듈 부재로 collection 오류 2개, exit 2 |
| 최초 구현 | 122 passed / 1 failed; float 거부가 TypeError로 새어 나오던 validation 경계 수정 |
| 최종 관련 검사 | **150 passed**, exit 0; 정규화 결과를 frozen JSON Schema와 대조, 44개 기존 예제 포함 |
| 최종 전체 pytest | **455 passed + 22 subtests passed**, exit 0, 기존 경고 1개 |
| baseline 보존 | 기존 코드·테스트·합성 데이터 41개 byte 일치, 변경 0개 |
| smoke | **12/12**, exit 0; 원본 JSON은 `reports/runs/20261030T140952Z-1229374d/` |
| JS 문법 / 요청 함수 재시도 / pip check | 모두 exit 0 |
| wheel/sdist build 및 내용 검사 | **5.3.0.dev2 PASS**; v1 모듈 포함 |
| 프로젝트 격리 환경에 wheel 설치, 체크아웃 밖 실행 | **PASS**, exit 0; v1 import/DTO parse, 기존 seed·HTML·health |

전체 pytest의 `scripts.windows_checks`는 소켓 초기화 오류만 1,995회 재시도했다. 개별 초기화의 최대 횟수는 64이며 HTTP 요청·assertion은 재실행하지 않았다. 설치 검사는 초기화 1회, smoke는 0회 재시도했다. 이 환경 문제를 수정했다고 주장하지 않는다.

신규 Pydantic API는 Context7의 공식 문서 조회로 확인했다. 라우터가 선택한 구현 에이전트와 읽기 검토 에이전트는 사용량 제한으로 실패했으며 코드 변경을 남기지 않았다. 구현·검증은 주 에이전트가 수행했다. 독립 외부 검수로 집계하지 않는다.

아직 하지 않은 검사: 실제 v1 HTTP/DB integration, PostgreSQL/RLS, 브라우저 E2E, 실제 모델·운영 환경. 이 구현은 내부 `TransitionChecks` 값 자체를 증거로 인증하지 않는다. 검증된 DB 이력과 gate를 생성하는 executor가 필요하며 [범위와 호출 계약](V1_FOUNDATION.md)에 명시했다. 기존 14개 canonical vector는 전체 suite에 포함된다.

코드 커밋 `0678bfa`의 [CI](https://github.com/KIMJINWOO0548/CaseProof_Enterprise/actions/runs/41070957936)는 7개 job success, PR 전용 dependency review는 skipped였다. 후속 UI 커밋과 구분한다. 코드 검증 후 변경한 README·평가표·상태/검증 문서는 기능 검사를 재실행한 것으로 보고하지 않는다.

## 5.3.0.dev1 통합 — 2026-10-30 KST

이번 결과는 Windows / Python 3.12.10 / 신규 임시 SQLite / hash lock 환경이다. 실행 로그는 [이번 run](../reports/runs/20261029T151200Z-a53be001/)에 있다. 아래 v5.3 원본의 Linux 기록은 별도 이력이다.

| 이번 검사 | 실제 결과 |
| --- | --- |
| 입력 v5.3 원본 byte manifest | 187개, 불일치 0, 입력 폴더 변경 없음 |
| 새 reference/tool 회귀 | 수정 전 11 failed / 4 passed → 수정 후 관련 기존 회귀 포함 47 passed |
| 서비스 경계 병합 | 수정 전 관찰 42 failed / 74 passed → 새 3모듈+기존 service/transition/idempotency 202 passed |
| 독립 리뷰 감사 ID 회귀 | 4 failed → 4 passed; list/dict ID를 잘못 읽어 500을 내던 진단 수정 |
| v1 canonical | import 부재 실패 → 13 passed; 고정 vector 14개와 runtime rejection 포함 |
| 최종 전체 pytest | **305 passed + 22 subtests passed**, exit 0, 기존 deprecation warning 1개 |
| 최종 smoke | **12/12**, exit 0 |
| JS 문법 / 실제 요청 함수 재시도 검사 | PASS; 브라우저 렌더링·클릭 검증과 별개 |
| pip check / hash lock 설치 | PASS, 프로젝트 환경만 변경 |
| wheel/sdist build 및 내용 검사 | PASS, 버전 5.3.0.dev1, 서비스·데이터·라이선스·canonical 모듈 포함 |
| 새 환경에 wheel 설치 후 체크아웃 밖 실행 | PASS, 임시 seed·HTML·health·canonical import, exit 0 |
| package contracts | 12 schemas / 62 examples / 14 vectors 구조 검사 PASS |

### 실제 GitHub CI

코드 커밋 `8eba9de12d7279c2784b50cc97c97dbca072c7a8`의 [CI 실행](https://github.com/KIMJINWOO0548/CaseProof_Enterprise/actions/runs/40902657873)이 **success**로 완료됐다. Linux Python 3.11·3.12·3.13, Windows Python 3.12, 배포물 빌드/체크아웃 밖 설치, JS 문법, OSV dependency audit의 7개 job이 성공했다. `Pull request dependency changes`는 push 이벤트에 적용되지 않아 skipped이며 실패를 숨긴 결과가 아니다. 이 결과는 해당 커밋의 합성 테스트 범위이며 PostgreSQL·브라우저·운영 인증 근거가 아니다.

`scripts.windows_checks`는 WinError10014 소켓 초기화만 제한적으로 재시도한다. 서비스 요청/assertion을 재실행하지 않으며, Windows 기본 서버 실행 안정성이나 PG 운영 성능을 증명하지 않는다. 로그는 최초 실패를 포함해 보존했다. 초기 배포물 검사는 이전 dev0와 dev1을 같은 dist에서 세어 실패했고, 버전별 두 파일을 격리해 정상 통과했다. 최초 설치 검사는 기능 assertion 통과 뒤 검증 wrapper가 임시 cwd 안에서 정리하려다 Windows 파일 잠금 오류가 발생했다. cwd를 먼저 복구한 재실행은 exit 0이었다.

서비스 병합 red 기록은 실행 당시 콘솔 관찰을 옮긴 요약이며 원본 stdout으로 가장하지 않는다. reference·감사 ID·canonical red/green과 전체 suite는 실제 raw 출력 파일이다.

브라우저 E2E, PostgreSQL/RLS, 외부 리뷰·실보험·운영 인증·외부 모델은 이번에 수행하지 않았다. OSV 검사는 위 실제 원격 CI에서 수행됐으며 로컬 실행과 구분한다.

---

## 입력 패키지의 이전 기록 (2026-10-29, Linux)

로컬 release-check 기록은 `docs/evidence/v5.3/`에 보존한다. 실행 환경은 Python 3.12.14, Linux x86_64, temporary SQLite, 고정 lock 의존성이다.

| 검사 | 결과 |
| --- | --- |
| `python -m pip check` | PASS |
| `python -m pytest -q` | 221 passed, 1 기존 Starlette/httpx deprecation warning, 22 subtests passed |
| `python -m scripts.smoke --output docs/evidence/v5.3/smoke.json` | PASS, 12/12 checks |
| `python -m scripts.check_ui_syntax` | PASS, 1 JavaScript file |
| `python -m scripts.check_package` | PASS, 12 schemas / 62 examples / 14 canonical vectors / 175 files |
| `pip-audit` on locked runtime dependencies | No known vulnerabilities found (OSV service; it checks hash presence, not hash validity) |
| submit-integrity regression | PASS, 3 cases; corrupted JSON now fails closed with HTTP 409 and keeps DRAFT/revision unchanged |

`pytest.log`, command metadata, lock hashes, smoke JSON and review history are bundled beside this file. Structural schema checks do not implement the planned `/api/v1` endpoints.

## 미실행 범위

- Chromium 다운로드가 손상된 ZIP으로 실패해 browser E2E를 실행하지 못했다. UI JavaScript syntax는 별도 통과했다.
- Python 3.11/3.13, Windows, macOS, Docker/PostgreSQL, remote GitHub Actions는 이 실행에서 확인하지 않았다.
- 외부 SME 검수, 비공개 holdout 연구, production 인증과 실제 보험 의사결정 적용은 수행하지 않았다.

이 결과는 기록된 로컬 실행의 증거이며 공개 저장소 CI green, 보안 인증 또는 배포 승인을 뜻하지 않는다.
