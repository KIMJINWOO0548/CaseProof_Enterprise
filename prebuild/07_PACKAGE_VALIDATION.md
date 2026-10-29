# 패키지 검증 진입점

현재 실행 결과와 한계는 [docs/VALIDATION.md](../docs/VALIDATION.md), 원본 및 수정 내역은 [PROVENANCE](../docs/PROVENANCE.md), 기능별 현재 상태는 [STATUS](../docs/STATUS.md)에서 관리한다. 이 파일에 과거 숫자를 중복 복사하지 않는다.

압축을 푼 원본에서 `python VERIFY_PACKAGE.py`로 해시·파일 집합을 검사한다. 코드 수정 후 manifest 불일치는 예상되는 현상이다. 새 release를 만들 때만 검증 후 `python -m scripts.release_package --output <새 ZIP 경로>`로 manifest와 ZIP을 생성한다. 기존 출력 파일은 덮어쓰지 않는다.

`python -m scripts.check_package`는 schema/examples와 내부 링크·필수 구성·공개 대상 파일을 검사한다. 이것은 악성코드 탐지나 비밀 유출 전수 감사를 대신하지 않는다. Git push 직전 tracked diff와 실제 CI 결과를 사람이 확인한다.
