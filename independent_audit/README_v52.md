# 이 디렉터리에 보관한 독립 감사에 관하여

2026-10-29 감사의 `REPORT.md`, `REPRODUCE.md`, 점수표, 출처표, 격리 실험, 로그를 원래 내용 그대로 보존했다. 이 복사본 디렉터리명은 `independent_audit/`이고, 과거 재현서에 보이는 `evaluation/` 경로는 당시 출력 폴더명이므로 현재 경로로 바꾸어 읽는다.

표준 라이브러리만 사용하는 격리 함수 스텁 실험은 패키지 루트에서 다음과 같이 실행할 수 있다. 이 실험의 PASS는 취약점이 고쳐졌다는 뜻이 아니다. `CASEPROOF_CURRENT`는 임시 사본의 `current/`를 가리켜야 한다.

```bash
CASEPROOF_CURRENT="$PWD/current" PYTHONDONTWRITEBYTECODE=1 python independent_audit/audit_probe.py
```

`live_probes.py`는 FastAPI·SQLAlchemy가 있는 환경의 임시 DB/TestClient용 후속 테스트 도구이며 당시 실행하지 않았다. 수행한 결과에 따라 해석해야 한다.
