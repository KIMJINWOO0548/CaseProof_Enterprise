# 공개 저장소 관리와 배포물 준비

공개 Git 저장소는 [KIMJINWOO0548/CaseProof_Enterprise](https://github.com/KIMJINWOO0548/CaseProof_Enterprise)이며 기존 `main`과 `origin`을 사용합니다. 새 저장소 초기화나 remote 재생성은 필요하지 않습니다. 현재 개발 소스는 **`5.3.0.dev6`**이고 PyPI 업로드·GitHub 패키지 release·서비스 배포는 수행하지 않았습니다.

dev6 구현 `643e25f`의 [실제 CI](https://github.com/KIMJINWOO0548/CaseProof_Enterprise/actions/runs/41222223392)는 9개 job 성공, push의 PR 전용 1개 skip을 확인했습니다. [격리 wheel·소스 ZIP 검사](evidence/g1-g6/installed-643e25f-wheel.json)도 실행했습니다. 후속 문서-only HEAD는 같은 구현을 유지하며 CI를 별도로 확인합니다. 변경한 코드는 해당 SHA의 새 결과로 검증하고 [VALIDATION](VALIDATION.md)에 기록합니다.

## 변경 전후의 Git 확인

기존 저장소에서 경로·branch·remote와 변경을 먼저 확인합니다. 사용자 변경이나 기존 기록을 reset하지 않습니다.

```bash
git status -sb
git remote -v
git log -5 --oneline
git diff --stat
git diff --check
```

검증된 작은 변경 묶음을 stage한 뒤 실제 내용을 검토하고 commit합니다. 이 작업에서는 사용자가 지속적인 commit·push를 명시 승인했습니다. 일반적인 기여자는 저장소의 권한·review 절차를 따릅니다. public push는 패키지 공개나 운영 배포를 대신하지 않습니다.

```bash
git diff --cached --stat
git diff --cached --check
git diff --cached
```

공개 전에는 `.env`, 로컬 DB, 토큰 출력, credential registry, private gold, 사용자 자료와 runtime 디렉터리가 stage되거나 배포물에 포함되지 않았는지 확인합니다. 실제 토큰이나 개인정보를 검토 로그에 복사하지 않습니다. Git 기록을 바꾸어 이미 공개한 비밀을 숨기려 하지 말고 비밀을 폐기·교체합니다.

## 최종 소스 검증

지원 Python의 프로젝트 가상환경에서 실행합니다. 신규 패키지 설치나 lock 변경은 해당 작업의 승인 범위를 따릅니다.

```bash
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip check
python -m pytest -q
python -m scripts.smoke
python -m scripts.check_ui_syntax
python -m scripts.check_package
python VERIFY_PACKAGE.py
```

영향받는 Windows 호스트에서는 pytest·smoke의 진입점에 `python -m scripts.windows_checks pytest -q` 또는 `python -m scripts.windows_checks scripts.smoke`를 사용할 수 있습니다. 이 도구는 `WinError 10014`의 socketpair 초기화만 제한적으로 재시도하며 요청·mutation·검사를 반복하지 않습니다. v1 실행기는 별도로 명시적 loopback listener를 준비하고 Windows 10014 초기화만 제한적으로 재시도합니다. 초기 실패를 보존한 뒤 실제 CLI의 인증·UI·DB 보존 검사와 V2 복구 훈련을 실행했습니다. 이 범위를 일반적인 운영 가용성 보장으로 확대하지 않습니다.

NumPy 통계, 실제 PostgreSQL, 브라우저 검사는 선택 의존성과 실행 환경이 필요합니다. [PostgreSQL 안내](G2_POSTGRES.md), [통계 계약](G51_METRICS.md), [UI 범위](G4_WORKSPACE.md)를 따르고 미실행·실패를 구분합니다. PostgreSQL은 disposable DB와 비소유자/NOBYPASSRLS role을 사용하며 SQLite로 대체하지 않습니다. GitHub CI의 job·artifact에서도 최종 commit SHA와 실제 exit 결과를 대조합니다.

## wheel·sdist·source ZIP

소스 변경을 마친 뒤 새 출력 경로에 빌드하고 내용·라이선스·runtime 자산을 검사합니다. 기존 검증 배포물을 덮어쓰지 않습니다.

```bash
python -m build --no-isolation --outdir dist/dev6-final
python -m scripts.check_distribution dist/dev6-final
python -m scripts.release_package --output ../CaseProof_Enterprise_5.3.0.dev6_source.zip
python VERIFY_PACKAGE.py
```

source ZIP 출력은 저장소 밖의 존재하지 않는 파일이어야 합니다. 생성 명령은 source byte manifest를 갱신하므로 `PACKAGE_MANIFEST_SHA256.json` diff를 검토하고 최종 소스와 함께 기록합니다. manifest는 바이트 일치만 검사하며 작성자 신원·안전성·런타임 보증을 인증하지 않습니다. Git 줄바꿈 변환 후의 바이트와 원본 ZIP을 구분합니다.

wheel은 실행 코드·합성 dataset·UI를 포함하고 sdist/source ZIP은 각 배포 규칙에 따라 문서·계약·테스트·migration을 포함합니다. `.runtime`, `.venv`, 로컬 DB·자격 증명·private gold·검증 run 출력은 배포 대상이 아닙니다. archive 검사를 통과한 wheel도 새 가상환경에 `requirements.lock`의 hash로 runtime 의존성을 설치한 뒤 `--no-deps`로 설치하고 `pip check`를 실행합니다. 체크아웃 밖에서 해당 환경의 Python으로 `scripts/check_distribution.py --installed`를 실행하여 source tree import에 가려지지 않는지 확인합니다. 자동화의 실제 명령은 [CI workflow](../.github/workflows/ci.yml)에 있습니다.

에이전트가 운영한 격리 설치는 독립 Windows 설치 검수가 아닙니다. dev6는 `evaluation_run_v2`의 완전한 실행 설정 digest를 사용하며 기존 v1 기록은 `LEGACY_UNVERIFIED`로 보존합니다. [형식 경계](EXECUTION_CONFIG.md)를 확인하고 기존 프로필의 자동 변환·삭제를 release 절차에 넣지 않습니다.

## 공개 설정과 남은 경계

- LICENSE·NOTICE·THIRD_PARTY_NOTICES·PROVENANCE를 보존하고 원본 코드·합성 자료의 배포 권한을 확인합니다. 외부 상용 문서나 브랜드 자산을 복사해 재라이선스하지 않습니다.
- private vulnerability reporting·secret scanning·branch rules의 실제 활성 상태는 GitHub 설정에서 확인합니다. 확인하지 않은 보호 설정을 활성이라고 문서화하지 않습니다. [SECURITY](../SECURITY.md)의 신고 경로도 실제 동작 여부를 확인합니다.
- required checks는 현재 workflow의 실제 job 이름과 일치시킵니다. fork PR에 secret을 전달하거나 `pull_request_target`으로 신뢰하지 않는 PR 코드를 실행하지 않습니다.
- 외부 모델 job/lease 확장은 미구현·미활성입니다. 독립 anchor/WORM·보험 전문가 검수·비공개 360건 연구·독립 Windows 설치·사용자 관찰은 SKIPPED, 외부 검수 bonus 0입니다. 로컬 복구 훈련의 RTO/RPO를 운영 SLA로 해석하지 않습니다.

패키지 이름 확보, 공개 release, PyPI 업로드와 배포는 별도 작업입니다. 이 절차를 실행했다고 자동으로 수행하지 않습니다. 최종 release 조건은 [readiness checklist](operations/RELEASE_READINESS.md)에서 확인합니다.

## Docker와 의존성 갱신

Docker 검증은 Docker가 있는 환경에서 따로 실행합니다. 검증하지 않은 image 빌드나 startup을 성공으로 기록하지 않습니다. 기존 compose 데모는 baseline 프로필이며 v1/PG 검증과 구분합니다. volume 삭제는 복구 절차나 일반 종료에 포함하지 않습니다.

lock은 uv universal resolution으로 플랫폼 marker와 파일 hash를 보존합니다. 지원 Python은 3.11–3.13이며 실제 플랫폼 실행 증거를 별도로 기록합니다. `requirements.lock`, `requirements-dev.lock`, `requirements-browser.lock`, `requirements-evaluation.lock`, `requirements-postgres.lock`의 관계를 유지하고 변경한 선택 환경도 다시 설치·회귀·audit합니다. hash는 파일 신원만 확인하며 취약점 부재를 의미하지 않습니다. uv나 외부 서비스 계정은 데모 실행의 필수 조건이 아닙니다.
