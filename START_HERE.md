# CaseProof v5.3 — 시작 안내

현재 개발 버전은 **`5.3.0.dev6`**입니다. 합성 보험 규칙을 평가하고 요청자·현업 검토자·최종 승인자의 결정을 불변 기록과 연결하는 로컬 연구용 서비스입니다. 공개 저장소는 [KIMJINWOO0548/CaseProof_Enterprise](https://github.com/KIMJINWOO0548/CaseProof_Enterprise)이며, 이 폴더가 Git 저장소 루트입니다.

## 실행 프로필

- 기존 `/api` baseline은 기존 SQLite 데이터·API·digest 계약을 유지합니다.
- 명시적으로 실행하는 `/api/v1` 작업공간은 원자적 revision·전체 사례 평가·모든 변경 요청의 멱등성·반려 시정 연결·분리된 검토자 승인·assessment/envelope 재구성을 제공합니다. 세 개의 등록된 허구 팩을 사용합니다.
- PostgreSQL role/RLS·동시성, NumPy paired 통계, 로컬 복구 훈련은 별도 시험과 증거로 구분합니다. UI는 로컬 Tabler와 실제 AI 제품의 목록/상세 검사 패턴을 사용합니다. [참고 자료와 적용 범위](docs/AI_UI_REFERENCES.md)를 확인하세요.

실제 동작과 실행 결과는 [현재 상태](docs/STATUS.md), [검증 기록](docs/VALIDATION.md)이 정본입니다. 구현 파일이나 계획 문서만으로 검증 완료를 판단하지 않습니다.

## 처음 실행하기

저장소 루트에서 Windows PowerShell로 실행합니다. 기존 가상환경이 있다면 새로 만들지 않고 사용할 수 있습니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.lock
$env:CASEPROOF_DEMO_MODE = '1'
.\.venv\Scripts\python.exe -m scripts.windows_checks scripts.v1_demo --port 8766
```

`http://127.0.0.1:8766/v1`을 엽니다. 명령이 만든 새 임시 프로필의 경로가 표시됩니다. 역할별 토큰은 Git에서 제외된 `profile.json`에서 직접 확인하고 공개하지 않습니다. 앱은 토큰을 브라우저 메모리에만 보관합니다. DB 초기화·seed는 명시적 준비 단계에서만 실행되며 앱 시작 때 자동 수행하지 않습니다.

같은 버전의 기존 합성 프로필을 재개하려면 `--profile <profile.json 경로>`를 사용합니다. **dev6 이전 실행은 그대로 보존하세요.** dev6의 새 실행은 전체 설정을 묶는 `evaluation_run_v2`를 기록합니다. 기존 `evaluation_run_v1`은 자동 변환하지 않으며 `LEGACY_UNVERIFIED`로 표시하고 평가·승인 동작을 제공하지 않습니다. 새 실행을 하려면 `--profile` 없이 새 임시 프로필을 준비합니다. 정확한 경계와 과거 요청 replay는 [실행 설정 계약](docs/EXECUTION_CONFIG.md)에 설명되어 있습니다.

이 Windows 호스트의 초기 `WinError 10014`를 재현해 실행기가 loopback listener를 먼저 준비하도록 보강했습니다. Windows의 해당 소켓 초기화만 최대 128회·20ms 간격으로 재시도하며 다른 오류와 HTTP 요청은 반복하지 않습니다. 실제 CLI 인증·UI·DB 보존 검사와 새 V2 복구 훈련을 실행했습니다. socketpair 초기화용 `scripts.windows_checks`와 listener 초기화의 범위는 [검증 기록](docs/VALIDATION.md)에서 구분합니다.

다른 플랫폼의 실행과 baseline 데모는 [README](README.md), v1 역할별 흐름은 [작업공간 안내](docs/G4_WORKSPACE.md)를 따릅니다. 운영 DB·실고객 자료·외부 모델 키는 필요하지 않습니다.

## 검증과 후속 개발

실행 가능한 CI는 이미 존재합니다. dev6 구현 `643e25f`의 [실제 CI](https://github.com/KIMJINWOO0548/CaseProof_Enterprise/actions/runs/41222223392)는 9개 job 성공, push의 PR 전용 1개 skip을 확인했습니다. 새 환경의 wheel 설치·V2 평가·근거 조회도 통과했습니다. 후속 문서 변경은 같은 구현을 유지하며 commit별 최종 검증은 [VALIDATION](docs/VALIDATION.md)에서 확인합니다.

개발을 이어갈 때는 [AGENTS.md](AGENTS.md), [구현 계약](prebuild/08_IMPLEMENTATION_CONTRACTS.md), [진행 체크리스트](prebuild/02_IMPLEMENTATION_PLAN.md)를 읽고 첫 미완료 인수 항목부터 진행합니다. 원본 테스트·합성 정답·기존 기록을 보존하고 새 결과는 `reports/runs/<run-id>/`에 남깁니다. 선택적 도구나 외부 검수 자료가 없으면 해당 검사를 SKIPPED로 기록합니다.

외부 모델과 optional job/lease 확장은 미활성·미구현입니다. 독립 앵커/WORM·보험 전문가 검수·비공개 360건 연구·독립 Windows 설치·사용자 관찰은 확보되지 않았으며 외부 검수 bonus는 0입니다. 로컬 PASS나 `APPROVED_FOR_DEMO`는 실제 보험 판단·운영 배포 승인이 아닙니다.

## 문서 우선순위

| 질문 | 정본 |
| --- | --- |
| 지금 구현·검증된 범위 | 코드, [STATUS](docs/STATUS.md), [VALIDATION](docs/VALIDATION.md) |
| API·데이터·hash의 계약 | [08 계약](prebuild/08_IMPLEMENTATION_CONTRACTS.md), [dev6 형식 경계](docs/EXECUTION_CONFIG.md), [실제 OpenAPI](docs/api/v1-openapi.json) |
| 다음에 검증할 항목 | [02 구현 계획](prebuild/02_IMPLEMENTATION_PLAN.md) |
| 스키마·구조 예제의 의미 | [contracts 안내](contracts/README.md); 예제 자체는 실행 증거가 아님 |
| 출처·라이선스·과거 자료 | [PROVENANCE](docs/PROVENANCE.md), [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md) |
| Git 관리와 배포물 준비 | [PUBLISHING](docs/PUBLISHING.md), [SECURITY](SECURITY.md) |

문서가 충돌하면 현재 계약·코드·실행 증거를 함께 대조합니다. Git commit과 push는 이 작업에서 별도로 승인되었지만 패키지 공개 release나 배포는 수행하지 않았습니다.
