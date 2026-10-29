> **v5.1 과거 패키징 기록:** 아래 결과는 이 설계 보완판에서 다시 실행된 결과가 아닙니다.

# 통합 패키지 실제 재검증

- 검사 시각(UTC): 2026-10-28T22:24:31.538757+00:00
- Python: 3.13.5 / OS: Linux
- 위치: `current/` (원본 v5.1 ZIP에서 동일 코드 추출)
- 외부 금융사 DB·실제 LLM·브라우저 UI E2E는 이번 검사에 포함되지 않았습니다.

## PYTEST: PASS
- exit code: `0`
- command: `/opt/pyvenv/bin/python -m pytest -q --disable-warnings`
```text
.................................................. [ 55%]
........................................                                 [100%]
90 passed, 22 subtests passed in 3.52s
```

## SMOKE: PASS
- exit code: `0`
- command: `/opt/pyvenv/bin/python -m scripts.smoke`
```text
Synthetic E2E smoke: 12/12 checks passed; report=reports/integration_smoke.json
```

## 패키징 메모
- `current/README.md`의 옛 폴더명 `CaseProof_Enterprise_v5_WorkingMVP` 표기는 통합 패키지 경로와 달라, **실행 시 `current/`로 이동**해야 합니다.
- 구버전 자료는 수정 없이 `legacy/`에 보존하며 실행 정본으로 취급하지 않습니다.
- v5.1 소스의 기존 테스트 결과(과거 로그)와 이번 재실행 결과를 분리했습니다.
