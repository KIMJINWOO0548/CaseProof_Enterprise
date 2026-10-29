# CaseProof 개발 상태 — 2026-10-29

이번 작업은 v5.2 계획 중 G0 실행 환경 확인, G1 승인 무결성·입력·재시도 계약을 진행했다. **운영 준비 완료를 뜻하지 않는다.** 현재 지원·검증 범위는 신규 합성 SQLite DB와 단일 worker다.

## 후속 개발 — 요청 재시도 계약

공개 저장소: [KIMJINWOO0548/CaseProof_Enterprise](https://github.com/KIMJINWOO0548/CaseProof_Enterprise), 기본 브랜치 `main`. 재시도 계약 구현 커밋은 `0f7ed2e`다. GitHub CLI 인증은 사용자가 직접 완료했다.

- 생성·평가·제출·현업 결정·최종 결정 모두 `Idempotency-Key` 12–128자를 필수로 요구한다. OpenAPI와 실제 요청으로 검사했다.
- tenant·actor·key 고유 제약과 operation을 저장한다. I-07의 최소 스코프보다 강하게, 같은 사용자·tenant가 다른 operation에 같은 키를 쓰는 것도 409로 거부한다. 이 선택은 구현 계획의 “같은 키·다른 경로는 충돌” 조건을 만족시키기 위한 것이다.
- fingerprint에는 POST, 정규화 route, change ID, 정규화 본문, expected revision을 포함한다. 인증·역할·tenant·요청자·승인자 분리를 검사한 후 원래 status/body/revision을 `replayed=true`로 재생한다. 현재 상태·무결성 판정은 별도 GET 조회다.
- 실제 변경과 완료 응답을 한 번에 commit한다. 응답 유실·중간 실패·동시 동일 키·다른 변경의 동시 감사 기록·SQLite 잠금 경합을 검사했다. SQLite writer 예약은 다섯 mutation POST에만 적용하고 경합은 재시도 가능한 409로 반환한다.
- 화면은 연결 오류·5xx·재시도 가능한 충돌·불완전한 성공 응답에서 키를 유지한다. 본문이나 expected revision 변경은 새 키를 쓰고, 로그아웃하면 대기 키를 비운다. 자동으로 변경 요청을 반복 전송하지는 않는다.
- **전체 157개 + 하위 검사 22개 통과, 스모크 12/12**, Node 요청 처리 검사와 실제 localhost/OpenAPI 확인을 완료했다. [새 실행 증거](current/reports/runs/20261029T142554Z-0b8c51e9/), [전체 로그](current/reports/runs/20261029T142554Z-0b8c51e9/pytest_full.txt)를 참고한다. 그 아래 142개 기록은 직전 실행 이력이다.

새 스키마에도 기존 DB 자동 마이그레이션은 없다. 실제 PostgreSQL·브라우저 조작·운영 환경 검증은 남아 있다. 기존 테스트의 assertion은 보존하고 공통 인증 헬퍼에 새 필수 요청 키만 추가했다.

## 구현·검증한 변경

- 실제 TestClient + SQLite에서 상태만 `PENDING_RELEASE`로 바꾸면 DOMAIN 승인 없이 최종 승인 200이 발생하는 결함을 재현했다. 회귀 테스트를 먼저 실패시킨 뒤 차단했다.
- 생성부터 평가·제출·현업 결정·최종 결정까지 `ChangeTransition`을 기록한다. genesis, 연속 revision, 합법적 전이, 테넌트 FK, 결정 및 감사 이벤트와의 연결을 검사하고 현재 상태·담당자와 대조한다.
- 상태·revision·결정·감사·전이 기록을 같은 트랜잭션에서 저장한다. 각 변경 경로에서 감사 기록 직후 예외를 주입해 전체 rollback을 확인했다.
- 최종 승인 직전 revision, DOMAIN 결정, 전이 및 감사 이벤트를 assessment에 고정하고 별도의 approval envelope로 최종 승인을 연결한다. 손상된 envelope는 무결성 실패로 반환하고 승인 일치로 표시하지 않는다.
- 요청자만 평가를 실행할 수 있다. 같은 사람에게 여러 역할을 부여해도 자기 승인과 검토·최종 승인 겸임은 허용하지 않는다.
- `claim_days`는 0–9999 범위의 JSON 정수만 허용한다. `true`, `false`, `1.0`, `"30"`은 422다. 승인 사유는 필수이며 원문과 `str.strip()` 결과 모두 Unicode code point 기준 8–500자로 검증한다. OpenAPI에도 계약을 표시한다.
- 스모크 결과는 매번 새로운 실행 폴더에 저장한다. `--output`으로 지정할 수 있으며 기존 파일은 덮어쓰지 않는다.

## 실제 실행 증거

새 결과: [G1 실행 폴더](current/reports/runs/20261029T140529Z-40f1af3f/), [환경](current/reports/runs/20261029T140529Z-40f1af3f/environment.json), [명령·종료 코드](current/reports/runs/20261029T140529Z-40f1af3f/commands.txt).

| 검사 | 이번 실행 결과 |
|---|---|
| 최초 패키지 검증 | 106개 파일, 해시 불일치 0 |
| 변경 전 승인/평가/증거 회귀 | 3개 실제 실패, [원본 로그](current/reports/runs/20261029T140529Z-40f1af3f/transition_red.txt) |
| 입력 계약 | 5개 실패 → 19개 통과 |
| 독립 리뷰 후 envelope 회귀 | 2개 실패 → 2개 통과 |
| 최종 전체 pytest | **142 passed + 22 subtests passed**, exit 0, [로그](current/reports/runs/20261029T140529Z-40f1af3f/pytest_verified.txt) |
| 최종 스모크 | **12/12**, exit 0, [결과](current/reports/runs/20261029T140529Z-40f1af3f/smoke_final.json) |
| 실제 localhost HTTP | health·HTML·OpenAPI 응답 확인, exit 0, [로그](current/reports/runs/20261029T140529Z-40f1af3f/http_wrapped_check.txt) |
| 정적 UI JavaScript 문법 | Node `--check`, exit 0 |
| 원본 보존 | 기존 datasets·reference·tests 16개 파일의 원본 SHA 일치. 과거 감사·테스트 보고서는 변경하지 않음 |

Windows Python 소켓 초기화에 `WinError 10014`가 간헐적으로 발생했다. 원래 pytest는 85개 통과·5개 setup 오류였고, 중간 실행도 141개 통과·1개 setup 오류였다. 이 실패 기록을 보존했다. 검증 전용 `scripts.windows_checks`는 해당 소켓 초기화만 최대 64회, 10ms 간격으로 재시도한다. HTTP 요청·테스트 assertion·서비스 트랜잭션은 재시도하지 않는다. 최종 142개 통과는 이 실행 방식의 결과이며 기본 Windows 서버 실행 안정성을 증명하지 않는다. Starlette의 기존 httpx 사용에 관한 deprecation warning 1개도 남아 있다.

## 재실행

프로젝트 `current/`에서 실행한다. 사용자 승인으로 만든 `.venv`를 사용하며 설치된 정확한 버전은 [패키지 스냅샷](current/reports/runs/20261029T140529Z-2794b92a/installed_requirements.txt)에 있다. 해시가 있는 재설치 lockfile이나 제3자 설치 검증은 아직 없다.

```powershell
$env:CASEPROOF_DEMO_MODE = '1'
$env:CASEPROOF_DATABASE_URL = 'sqlite://'
.\.venv\Scripts\python.exe -m scripts.windows_checks pytest -q
.\.venv\Scripts\python.exe -m scripts.windows_checks scripts.smoke
```

스모크는 자체 임시 SQLite를 사용한다. 수동 시연에는 이전 DB를 보존하고 **존재하지 않는 새로운 합성 SQLite 파일 경로**를 지정한 뒤 `service.cli init-demo`를 실행한다. 기존 v5.1 DB에 대한 자동 스키마 마이그레이션은 없다. 새 스키마에서 전이 이력이 없는 행은 `legacy-unverified`로 거부하며 과거 이력을 생성해 재승인하지 않는다.

## 남은 순서

1. **G2:** 실제 PostgreSQL, 마이그레이션, non-owner RLS, 연결 풀·잠금·동시성 검증. SQLite 결과를 대체 근거로 사용하지 않는다.
2. **G3–G6:** 보험 업무팩 보완, 브라우저 E2E·접근성·시정 흐름, AI 비교실험, 독립 보존·운영·외부 검증. 이번에는 미실행이다.

개발 도구로 Auto Model Router를 실제 실행해 승인 무결성 구현을 Astra/low 에이전트에 배정했고 별도의 읽기 전용 리뷰를 받았다. Context7 MCP로 Pydantic의 엄격한 필드 검증 문서를 확인했다. 제품 자체에 실제 LLM을 연결한 것은 아니다. 원본은 `1ab3d43`, 입력 계약은 `38c306d`, 승인 무결성과 증거는 `9a42368` 커밋에 보존했다. 이후 커밋 작성자는 저장소 로컬 설정 `Kimjinwoo <wlsdn8176@naver.com>`이다. 기존 자체 점수·독립 감사 점수는 재채점하지 않았다.
