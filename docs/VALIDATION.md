# 검증 결과 — 5.3.0.dev0

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
