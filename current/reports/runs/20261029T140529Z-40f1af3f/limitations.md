# 실행 범위

- PASS는 신규 합성 SQLite, 단일 worker, 해당 입력과 실제 assertion에 한정한다.
- 기본 Windows Python에서 socketpair 초기화 WinError10014가 재현됐다. 두 Python 실행기와 Windows MCP PowerShell에서도 재현됐다. 원인인 OS/보안 소프트웨어는 특정하지 않았다. 전역 네트워크·보안 설정을 변경하지 않았다.
- 검증 실행기의 초기화 재시도와 정상 서비스 실행은 별개다. HTTP 검사는 같은 검증 실행기를 통해 uvicorn을 시작했다. 기본 실행이 안정적이라고 주장하지 않는다.
- Starlette가 기존 httpx TestClient 사용에 deprecation warning을 출력한다. httpx2 설치나 의존성 변경은 이번 범위에서 하지 않았다.
- 평가 외 mutation endpoint에는 전체 멱등성 계약이 아직 없다. 응답 유실·동시 재전송·route/revision fingerprint는 G1 Task1.3 후속 작업이다.
- 신규 컬럼/전이 테이블이 있는 새 DB만 검증했다. 실제 v5.1 DB 스키마를 업그레이드하는 경로는 없다. 기존 DB는 보존하고 새 경로에서 합성 시연해야 한다.
- PostgreSQL/RLS/다중 worker/운영 동시성, 브라우저 E2E·접근성, 실제 LLM/보험 규정·외부 검수·360건 실험·WORM·SSO·백업/복구는 SKIPPED 또는 미구현이다.
- 내부 DB hash·전이 원장은 DB 전체와 모든 hash를 다시 쓰는 관리자 공격을 막는 외부 신뢰 앵커가 아니다.
- 과거 점수·감사 결과·이전 pytest/smoke 로그를 신규 성공으로 사용하지 않았다. 이번에는 점수를 다시 산정하지 않았다.
- SQL 데이터 변조는 fail-closed 승인 차단을 검증했으며 모든 임의 DB 손상에 대한 조회 복구를 포괄적으로 검증한 것은 아니다.
