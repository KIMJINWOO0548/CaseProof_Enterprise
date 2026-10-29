# v5.2 문서 보완 패키지 검증 기록

검사일: 2026-10-29 KST. 이 기록은 패키지 작성 시점의 확인 결과다. 제품 보안·보험업무 적합성·105점 통과 증거가 아니다.

## 원본 보존

- v5.1 원본의 `current/service`, `reference`, `tests`, `datasets`, `scripts`와 이 패키지의 동일 경로를 SHA-256으로 비교했다. **32개 파일이 모두 일치**했다. 원본 ZIP에 있던 `__pycache__`, `.pytest_cache`, `.pyc` 실행 캐시는 이 새 사본에서 제외했다.
- 현재 실행 코드는 v5.1이고 실제 P0 수정이나 신규 제품 구현은 없다. 문서·시작 경로·과거 문서 경고·패키지 manifest만 보완했다.
- 이전 독립 감사 결과와 작성자의 이전 테스트 기록을 보존한다. 감사 스텁이 공격 경로를 재현한 상태로 남아 있는 것은 정상이며 **수정이 완료되지 않았다는 표시**다.

## 이번 직접 확인

| 명령 또는 검사 | 결과 | 의미 |
|---|---|---|
| `python VERIFY_PACKAGE.py` | manifest 대상 파일 전부 일치 | 패키징 무결성. 입력 원본 안전성·제품 보안 검증이 아님 |
| `python -m scripts.verify_manifest` (`current/`) | 70/70 일치 | 현재 디렉터리 파일 무결성 |
| `PYTHONPATH=.:tests python -m unittest -q test_resolver test_answer_check test_release_impact test_v4_controls` | 49 tests, OK | 참조 엔진의 제한적 단위검사. HTTP/SQLAlchemy/브라우저는 포함하지 않음 |
| `CASEPROOF_CURRENT=<current> python independent_audit/audit_probe.py` | 격리 함수 + ORM 스텁 실험에서 기존 P0 후보, 불완전 baseline, 미승인 특약 및 반복 생성 상황을 다시 관찰 | 실제 API·SQLite/PG 재현, 결함 수정 또는 서비스 보안 PASS가 아님 |
| `python -m pytest -q` (`current/`) | exit 1, `No module named pytest` | 전체 테스트 미실행 |
| `python -m scripts.smoke` (`current/`) | exit 1, `No module named fastapi` | API/DB 스모크 미실행 |
| 경로/문서 확인 | 필수 문서 및 G0–G6, 160/80/120 계획·내부 리뷰 반영 사항 존재 | 실제 구현 또는 통합 검증이 아님 |

환경: Python 3.12.14, Linux. 현재 작성 환경에서 pytest/FastAPI 등 설치가 네트워크 제한에 막혔으므로 P0 실제 HTTP/SQL DB, 전체 테스트, 스모크, 브라우저, PostgreSQL/RLS, LLM 및 외부 검증은 미실행이다.

독립 검토는 `06_DESIGN_REVIEW.md`에 남겼다. 개발 시 `02_IMPLEMENTATION_PLAN.md`와 `04_ACCEPTANCE_AND_EVIDENCE.md`의 인수 조건을 새 환경에서 다시 실행·판정해야 한다.
