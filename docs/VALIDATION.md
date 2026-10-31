# 검증 결과 — 5.3.0.dev6

## 추가 시각 개편 — 2026-11-01 KST

구현 `b0c3d64`의 [CI41226797390](https://github.com/KIMJINWOO0548/CaseProof_Enterprise/actions/runs/41226797390)는 **9 success / PR 전용1skip**이다. Linux Python3.11/3.12/3.13·Windows3.12 각각 **912 PASS,459 optional SKIP,22 subtests PASS,3 warnings**이며, 별도 실제 PG17.11은 **460 PASS/0skip**, NumPy는 **34 PASS**다. [명령·JUnit·checksum](evidence/g1-g6/ci-b0c3d64.json), [정확한 source ZIP·wheel·저장소 밖 설치·Gitleaks](evidence/g1-g6/installed-b0c3d64.json)을 기록했다. 소스 ZIP은390개 source hash+manifest를 검증했다. Gitleaks 원시 종료값은1이며, 이력23/작업 소스22 후보를 해시·합성 요청키로 분류했고 자격 증명/미해결은0이었다. 보안 인증으로 해석하지 않는다.

후속 대비 보정은 현재 단계 이외의 라벨을 기존 muted 색상으로 맞춰5.53:1로 높이고 사용되지 않는 next 색상 규칙을 제거했다.1440/390px의 실제 computed color·줄바꿈·현재 단계·화면을 재확인했다. 서버 동작과 폰트 bytes는 b0c3d64와 같으며, 최신 HEAD의 CI는 해당 SHA의 GitHub Actions 결과로 구분한다.

[설계·1차 출처](VISUAL_DESIGN.md), [Chrome 실제 동선·화면·대비](evidence/g1-g6/ui-visual-refresh.json). 검토 단계 표시는 기존 렌더러에서 RED를 확인한 뒤 실제 생성→평가→응답 유실 복구→반려→시정→분리 승인→증거 조회에서 GREEN이었다. 오류 링크 안정화 timeout은 보존했고, 선택적 smooth scroll 제거·소유 페이지 재생성 후 제한 시간 내 전체 동선을 통과했다. 이전 세션 간섭과 scroll 각각의 기여는 분리 실험하지 않았다.

최종 로컬 전체는 **913 PASS / 458 optional SKIP / 22 subtests PASS / 3 warnings**였다. 새 font MIME 회귀도 포함됐고, Windows socketpair 초기화만57회 재시도했다. 애플리케이션 요청·단언 재시도는 없다. 현재 PG 서버와 Python Playwright가 없어 관련 검사는 SKIP이며, NumPy는 설치된 환경이다. 별도 MCP Chrome156 검사는 실제 실행됐다. 관련 Python은4 PASS/1 optional SKIP, Node 원래 요청 복구·거부 이후 복구·문법 검사 PASS, baseline smoke12/12, manifest390 source/패키지 구조 검사 PASS다. 정확한 commit의 CI·설치 배포물 결과는 완료 기록에서 분리한다.

선택한 정상 텍스트 대비5.53–15.27:1, input 경계3.22:1, focus3.25:1을 측정했다.375/390/768/1024/1280/1440px 가로 넘침0, reduced-motion 전환0s, 실제 SUIT loaded/HTTP200 `font/woff2`였다. 이는 전체 WCAG 인증이나 독립 사용자/스크린리더 검수는 아니다. 외부 앵커·모델·운영 검증은 그대로 미실행이다.

## 이전 핵심 구현 `643e25f` — 2026-11-01 KST

[실제 CI41222223392](https://github.com/KIMJINWOO0548/CaseProof_Enterprise/actions/runs/41222223392), [명령·JUnit·checksum](evidence/g1-g6/ci-643e25f.json): **9 success / push의 PR 전용1skip**. Linux3.11/3.12/3.13·Windows3.12 각각 **911 passed,459 optional skipped,22 subtests,3 warnings**다. 459skip은 PG457+NumPy1+Python-browser1이며 별도 job에서 실제 PG17.11 **460 PASS/0skip**, NumPy **34 PASS**를 실행했다. 빈 collection을 성공으로 세지 않았다. OSV는 dev35/evaluation36/postgres37 dependencies에서 known vulnerability record0/skipped dependency0이었다.

[643e25f 배포물](evidence/g1-g6/installed-643e25f-wheel.json)은 새 runtime-only hash 환경·pipcheck·체크아웃 밖 설치 후 baseline assets와 실제 V2 생성→전체 평가 PASS→VALID 근거·immutable refs를 통과했다. 소켓 초기화만5회 재시도했다. wheel/sdist 내용·license notice·private/runtime 제외, 소스ZIP 내부379개 source hash와 committed manifest의 일치를 확인했다. de1fc5e와 비교한 runtime 변경은 v1 HTML/CSS/JS뿐이며 Python/reference/dataset bytes는 같다. 독립 Windows 설치로 집계하지 않는다.

[Gitleaks 최신 결과](evidence/g1-g6/gitleaks-643e25f-summary.json)는 이력23개/작업소스22개 원본 후보(exit1)를 보존했다. 각각 digest16/15개와 합성멱등성키7개로 판별했고 실제credential/미해결0이다. 예외·suppress 규칙을 추가하지 않았으며 비밀의 완전한 부재를 보증하지 않는다. 라이선스·출처의 확정 범위와 미확정 소유권은 THIRD_PARTY_NOTICES에 남긴다.

후속 완료 기록 commit은 문서/증거만 바꾸고 구현 bytes를 보존한다. 해당 HEAD의 CI도 별도로 확인하며, 이전 commit의 결과를 새 코드의 결과라고 바꾸어 기록하지 않는다.

## 후속 UI 오류 회복·라이선스 감사 — 2026-11-01 KST

[현재 화면 7단계 감사](UI_FOCUS_AUDIT.md)와 [도구/스킬 실행](evidence/g1-g6/ux-tools-skills.json)을 기록했다. UI/UX Pro Max 실제 검색, Product Design preflight, Frontend Design/Uncodixfy 검토, GitHub MCP의 고정 LICENSE 원문, Context7의 Playwright 공식 초점/Escape 문서와 IAB/Playwright 실제 관찰을 구분한다. Langfuse MIT core/상용 ee, Dify 추가 조건부 수정 Apache2, LangSmith 상용 제품을 같은 라이선스로 취급하지 않았다. 코드·자산 복제는 없었다.

공백 사유의 모달 밖 오류와 투명 배경을 이번 캡처에서 재현했다. 수정 후 실제 Chrome의 1440/390px에서 요약 초점·필드 링크·aria-invalid/describedby·정상 입력 해제·재열기·Escape·불투명 배경·잘못된 입력 POST0을 확인했다. 합성409 후 전역 오류 초점, 실제 IAB401 초점도 확인했고 같은 원래 fixture의 revision3/결정0을 보존했다. 전체 3인 반려→시정→승인과 committed-response 복구도 최신 UI에서 다시 통과했다. [Native 결과](evidence/g1-g6/ux-native-workflow.json), [표적3PASS/1선택skip](evidence/g1-g6/ux-final-target.txt). 초기 probe의 로딩 대기 누락은 실패로 보존하고 실제 업무 실패로 합산하지 않았다.

선행 최종 core `de1fc5e`의 [CI](evidence/g1-g6/ci-de1fc5e.json)는 9개 success/PR전용1skip, Linux3.11/3.12/3.13·Windows3.12 각각911 PASS/459 optional skip/22subtests, 실제 PG17.11 460 PASS, 수치34 PASS다. [fresh runtime-only wheel/sourceZIP](evidence/g1-g6/installed-de1fc5e-wheel.json)은 설치된 V2 생성·전체 평가·검증 refs까지 통과했다. [새 비밀 검사](evidence/g1-g6/gitleaks-de1fc5e-summary.json)의 이력23·작업소스22 후보는 해시/합성멱등성키로 판별했고 실제자격증명/미해결0, 원본exit1을 보존했다. 후속 UI 소스는 새 SHA의 CI/배포물 검사로 구분한다.

## dev6 실행 설정·진단·전체 회귀 — 2026-11-01 KST

[실제 로컬 전체 출력](evidence/g1-g6/ordinary-dev6-final.txt), [소스 범위와 명령](evidence/g1-g6/ordinary-dev6-final.json): **904 passed, 1 optional Python-browser skipped, 3 warnings, 22 subtests passed**, exit 0, 472.91초. 소켓 초기화만 662회 재시도했으며 테스트 본문·HTTP mutation을 반복하지 않았다. 이 실행은 마지막 CLI listener 보강 전의 고정된 V2/identity/API/UI 소스다. CLI 보강 후 최종 commit은 별도 전체 CI로 검증한다. 감독자의 이전 전체 실행 CLI TimeoutExpired(15초)는 보존했고 동일 원본 검사의 단독 실행은 사용자 보고 3.98초, 이 세션 14.64초로 각각 통과했다. timeout·기존 테스트는 변경하지 않았다.

평가 후 봉인 전 Dataset/SourceBundle을 한 행만 자체 재해시한 독립 RED 2개를 확인했다. `evaluation_run_v2`는 `run-config-v2`로 candidate/bundle/dataset/suite/evaluator/model/prompt/adapter 전체를 결합한다. V1 gold·기존 canonical bytes는 보존하며 이전 실행을 자동 변환하지 않는다. [형식과 fail-closed 경계](EXECUTION_CONFIG.md), [실행 기록](evidence/g1-g6/execution-config-verification.json), [재해시·non-null model/prompt 검사](evidence/g1-g6/tamper-config-verification.json)를 대조한다. 마지막 identity 보강 이전 V1 범위 회귀 528 PASS와 최종 전체 904 PASS를 구분한다.

증거 GET의 immutable refs 누락은 HTTP RED 후 보완했다. 관련 57 PASS 뒤 canonical identity 누락의 500을 별도로 재현했고 [RED](evidence/g1-g6/missing-identity-http-red.txt)→[200 INVALID/null refs GREEN](evidence/g1-g6/missing-identity-http-green.txt)을 확인했다. 이전 V1 기록은 인증된 조회에서 LEGACY_UNVERIFIED/null refs이며 mutation은 409다. 인증·tenant 경계와 원래 저장 요청의 역사적 replay 계약은 유지한다.

[최신 실제 Chrome 156](evidence/g1-g6/ai-ui-browser-dev6.json)은 새 V2 프로필에서 XSS 흐름과 깨끗한 캡처 흐름 두 번을 실행했다. 각 교정 변경의 DB에는 revision/transition/event 5개, decision 2개, V2 run과 VALID 증거가 있었다. 서버 성공 commit 후 응답 abort→원래 키 복구, 3인 승인, 1280/1440/390/375px, Escape, WebStorage 비사용과 이전 형식 UI 차단을 확인했다. 캡처는 실제 V2 데이터다. 이 Windows 재검증은 기본 서버 시작의 10014 실패 뒤 명시적 loopback listener와 프로세스 내 SelectorEventLoop로 실행했다. 정상 실행기 보강의 별도 결과를 후속 기록한다.

`651a5bc`의 [실제 CI 증거](evidence/g1-g6/ci-651a5bc.json)는 9개 성공/PR 전용 1개 skip, 일반 각 868 PASS, 실제 PG17.11 460 PASS, NumPy 평가 34 PASS다. [격리 wheel](evidence/g1-g6/installed-651a5bc-wheel.json)은 runtime-only 환경에서 실행했다. 후속 dev6 전체 CI/새 설치를 이전 결과로 대체하지 않는다.

Gitleaks 8.30.1 공식 바이너리의 게시 SHA-256 확인 후 Git 전체 이력과 작업 소스를 redaction 모드로 검사했다. 각각 원본 후보 20개(exit 1)를 보존하고 해시 기록 14개·합성 멱등성 키 6개로 판별했으며 실제 credential/미해결 후보는 0개였다. [명령·출처·판별 근거](evidence/g1-g6/gitleaks-summary.json). suppress/allowlist를 추가하지 않았으며 완전한 유출 부재 보증으로 표현하지 않는다. 라이선스·출처의 확인된 범위와 미확정 소유권은 THIRD_PARTY_NOTICES를 따른다.

최종 CLI 시작은 기본 ProactorEventLoop와 명시적 loopback listener를 사용한다. 실제 시작 실패 RED 후 Windows 10014의 첫 listen만 최대 128회·20ms로 제한해 재시도하고 실패 소켓을 닫는다. 다른 OS/오류는 즉시 실패한다. [실제 CLI·제한 검사 5 PASS](evidence/g1-g6/demo-startup-verification.json), [실행 출력](evidence/g1-g6/demo-startup-verified.txt). 테스트는 인증 200·무인증 401·HTML/JS 200·DB 파일 hash 보존·소유 process 정리를 확인했다. HTTP나 mutation 재시도는 없다. 10014의 운영체제 원인은 확정하지 않았다.

보강한 실행기로 [새 V2 복구 훈련](evidence/g1-g6/recovery-drill-dev6.json)을 다시 실행해 service outage·token theft·rollback/restore·evidence tampering의 **4개 PASS, exit 0**을 확인했다. 기본 실행기를 사용했고 controller의 socketpair 초기화 재시도는 0회였다. 관찰된 RTO/RPO와 초기화 시도는 해당 JSON의 로컬 환경 수치다.

## AI UI 및 후속 인수 검증 — 2026-11-01 KST

Langfuse·LangSmith·Dify의 공식 자료를 조사하고 [적용 범위](AI_UI_REFERENCES.md)를 기록했다. 목록과 상세를 병렬 배치하고 닫힌 native dialog의 Tabler 표시 충돌을 수정했다. [Chrome 156 native 실행](evidence/g1-g6/ai-ui-browser.json)은 반려→시정→3인 승인·증거 VALID, 성공 commit 뒤 response abort와 같은 key 복구, XSS title/reason 비실행·WebStorage 비사용·Escape 초점 복귀를 통과했다. 1280/1440px 정렬과 390/375px 가로 넘침을 검사했다. [실측 대비/44px 표적](evidence/g1-g6/ai-ui-metrics.json), [GET 오류·로딩·빈 상태](evidence/g1-g6/ai-ui-error-states.json)는 각 검사 범위를 구분한다. 임의 GET 응답을 주입한 화면 시험을 서버 권한 검증으로 세지 않는다. 도구 setup 실패와 과거 click timeout은 PASS에 합산하지 않았다.

추가 HTTP route/resource/expected-revision key 충돌·원본 replay 표적은 **33 passed**, exit 0이었다. Windows 소켓 초기화만 52회 재시도했다. 새 PG 서로 다른 변경 경합 검사는 수집했고 후속 CI를 기다린다. 선택적 Python Playwright는 여전히 미설치 skip이며 실제 MCP 실행과 구분한다.

백엔드 커밋 `e9b67ac`의 [CI](https://github.com/KIMJINWOO0548/CaseProof_Enterprise/actions/runs/41214934555)는 **9개 job success, PR 전용 1개 skipped**다. Linux Python 3.11/3.12/3.13·Windows 3.12, PG17 **459 passed**, 수치 통계·OSV·UI 문법·격리 배포물 설치를 실제 실행했다. 별도 로컬 fresh runtime-only wheel 설치도 exit 0이며 소켓 초기화 6회만 재시도했다. 후속 UI/검사 소스는 새 commit/CI로 별도 검증한다.

## G1–G6 로컬 구현 — 2026-10-31 KST

[비 PG 전체 출력](evidence/g1-g6/ordinary-pytest.txt): 862 passed, 1 optional Python-browser skipped, 3 warnings, 22 subtests passed, exit 0. 실제 Chrome 156 MCP의 3인 반려→시정→승인, committed response 유실 뒤 같은 key 복구, XSS 비실행, WebStorage 비사용, 375px 및 focus 검사를 별도 실행했다. 후속 native-click 재실행 timeout은 성공에 합산하지 않는다. UI/UX Pro Max 검토와 AI 제품 레이아웃 조사는 후속 화면 변경으로 구분한다.

[복구 훈련](evidence/g1-g6/recovery-drill.json)은 실제 임시 server process 중지/재시작, token disablement, 변조 거부, 새 DB 복구의 4개 PASS다. 기존 target 덮어쓰기·손상 hash·빈 tenant head 이상·Windows connection close 회귀를 추가했다. 결과의 RTO/RPO는 해당 로컬 합성 환경의 측정이며 운영 보장 수치가 아니다.

실제 PG17.11 표적 459 PASS 뒤, 물리 backend를 barrier 전 반환하는 시험 결함을 재현해 연결을 유지하도록 수정했다. 이후 Windows PG startup/socket 10014/timeout 실패를 보존했으며 최종 PG CI는 아직 확인 전이다. 초기화만 재시도하고 SQL mutation/assertion을 재실행하지 않는다. 기존 단위 시험과 원본 gold 답은 변경하지 않았다.

OpenAPI Bearer 선언과 실제 HTTP/작업공간/수치 평가 표적 회귀는 **61 passed**, exit 0이다. 응답 유실 뒤 권한 거부가 와도 원래 미확정 키를 보존하도록 Node RED→GREEN 회귀를 추가했다.

NumPy 2.4.6·psycopg 3.3.6은 승인된 프로젝트 환경에 별도 hash lock으로 설치했다. 공개/비공개 artifact 경로 거부, 모델 allowlist, split 연결 성분, paired/불완전 비교, 전체 case 모음 및 최신 incomplete veto를 검사했다. 외부 모델은 연결하지 않았다.

재현 실패도 보존한다: 누락 모듈 RED, 기록-link와 중첩 FK 변조 재현, adapter timeout/UUID source bridge RED, 테스트 모듈 이름 충돌, private path RED, socket 초기화 64회 제한 재현. [초기화 회귀 RED](evidence/g1-g6/windows-initialization-red.txt) 후 128회·20ms의 bounded 초기화만 허용했고 다른 오류·module 재실행은 거부했다.

G5.2 optional external job mode, 외부 anchor/독립 key custodian, 동의받은 보험 검수자와 독립 설치·사용자 관찰·운영 검증은 미실행이다. 사용자가 현재 자료·인프라가 없음을 확인했으며 외부 검수 bonus는 0이다.


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
| 실제 GitHub CI | 코드 `fdac40d`의 [실행](https://github.com/KIMJINWOO0548/CaseProof_Enterprise/actions/runs/41164118260) success; Linux 3.11/3.12/3.13·Windows 3.12·배포물·JS·OSV의 **7개 job 성공**, push의 PR 전용 1개 skipped |

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
