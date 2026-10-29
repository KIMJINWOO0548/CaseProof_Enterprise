# 공개 저장소와 release 절차

이 패키지는 로컬 개발용 source handoff다. 실제 원격 저장소·CI 실행·공개 release는 아직 생성하지 않았다. 최초 공개 이름은 `caseproof`, 버전은 `5.3.0.dev0`와 같이 pre-release임이 드러나게 사용한다.

## 공개 전에 확인할 구체 항목

- README/STATUS가 실제 동작과 일치하고 future `/api/v1`을 구현됐다고 표시하지 않는다.
- LICENSE는 Apache-2.0 기본값이다. 원본 사용자 제공 코드·합성 데이터에 배포 권리가 있는지 maintainer가 확인한다. 외부 문서/기업 자료를 복사해 재라이선스하지 않는다. NOTICE/THIRD_PARTY_NOTICES/PROVENANCE를 함께 보존한다.
- GitHub 저장소를 만든 뒤 **private vulnerability reporting**을 켜고 SECURITY의 실제 신고 경로를 확인한다. 가짜 이메일이나 존재하지 않는 badge URL을 넣지 않는다.
- `.env`, local DB, token output, credential registry, private blind gold, 사용자 자료·과거 APK/ZIP은 commit하지 않는다. `git diff --cached`를 읽고 secret scanning을 활성화한다.
- lock 설치, pytest, smoke, JS syntax, package checks, source+wheel 빌드와 설치를 실행한다. browser/PG/Windows 체크는 해당 환경에서 별도로 실행한다. CI 정의 파일만 보고 green badge를 붙이지 않는다.

## 첫 Git 저장소

원격이 없는 새 작업 폴더에서 다음을 실행한다. 이미 Git 저장소라면 init을 반복하거나 기존 remote/branch를 덮지 않는다.

```bash
git init -b main
git add .
git diff --cached --stat
git diff --cached --check
git status --short
```

stage 목록과 내용을 검토한 뒤 로컬 commit:

```bash
git commit -m "Initial CaseProof synthetic prototype and implementation handoff"
```

GitHub에서 소유자·공개 여부·저장소명을 확인하여 빈 저장소를 만든 다음, 실제 제공된 URL로 remote를 연결하고 push한다. 이 문서는 `OWNER/REPO`를 실제 저장소처럼 제시하지 않으며 인증/권한을 추측하지 않는다. 사용자 허가 없이 public repo 생성·push를 실행하지 않는다.

CI가 실제 통과하면 branch protection/ruleset에서 테스트 matrix, package build, dependency audit 등 실제 job 이름을 required checks로 선택한다. fork PR에 secret을 전달하거나 `pull_request_target`으로 PR 코드를 실행하지 않는다. maintainer 권한을 최소화하고 신뢰하지 않는 artifact를 배포 job에서 실행하지 않는다.

## 재현과 배포물

```bash
python -m pip install --require-hashes -r requirements-dev.lock
python -m pip check
python -m pytest -q
python -m scripts.smoke
python -m scripts.check_ui_syntax
python -m scripts.check_package
python -m build --no-isolation
python -m scripts.check_distribution dist
python -m scripts.release_package --output ../CaseProof_Enterprise_v5_3_source.zip
```

source ZIP 생성은 byte manifest를 갱신한다. 변경 후에는 새 manifest diff를 검토하고 필요한 release commit/tag에 포함한다. Git ignore한 build/dist/reports는 source ZIP에 포함하지 않는다. source ZIP은 Codex용 docs/contracts/tests를 포함하고, wheel은 실행 코드와 합성 dataset/UI를 포함한다. 패키지 소유권/이름을 확보하지 않았으므로 PyPI upload는 자동 수행하지 않는다.

## Docker 로컬 데모

Docker 자체가 있는 환경에서 별도로 검증해야 한다. 기본 image tag는 변경 가능하므로 재현 가능한 release에서는 검토한 base image digest로 고정한다. 이미지를 검증하지 않았는데 빌드 성공이라고 기록하지 않는다.

```bash
docker compose build
docker compose run --rm --no-deps caseproof-demo python -m service.cli init-demo --database sqlite:////data/caseproof.sqlite3
docker compose up caseproof-demo
```

초기화 토큰은 one-off 명령의 현재 터미널에만 출력한다. 로그를 저장소에 올리지 않는다. host port는 127.0.0.1에만 바인딩되며 container는 non-root이다. 종료는 `docker compose down`; 데이터를 보존하려면 `-v`를 추가하지 않는다. volume 삭제는 별도 의도 확인 없이 자동화하지 않는다.

## 의존성 갱신

현재 lock은 uv universal resolution으로 Python3.11 이상 및 플랫폼 marker를 포함한다. 실제 지원은 pyproject의 3.11–3.13이고 각 플랫폼 실행 증거는 별도다. uv는 lock 유지보수 도구이며 사용자 실행 필수 dependency가 아니다.

```bash
uv pip compile requirements.txt --universal --python-version 3.11 --generate-hashes -o requirements.lock
uv pip compile requirements-dev.txt --universal --python-version 3.11 --generate-hashes -c requirements.lock -o requirements-dev.lock
uv pip compile requirements-browser.txt --universal --python-version 3.11 --generate-hashes -c requirements-dev.lock -o requirements-browser.lock
```

정기 업데이트는 lock·설치·회귀·audit 결과를 한 PR에 둔다. hash는 배포 파일의 신원만 확인하며 취약점 부재를 의미하지 않는다. 선택적 browser 의존성을 갱신하면 실제 설치 버전·브라우저 버전을 기록하고 UI E2E를 다시 수행한다.

`VERIFY_PACKAGE.py`와 source manifest는 원본 source ZIP의 byte 집합을 검사한다. wheel/sdist에는 build metadata가 추가되므로 그 검증은 `scripts.check_distribution`을 사용한다. sdist에는 source-ZIP manifest를 넣지 않는다. Git checkout의 줄바꿈 변환 후 byte hash가 달라질 수 있으므로 원본 ZIP 검증 결과와 구분한다.
