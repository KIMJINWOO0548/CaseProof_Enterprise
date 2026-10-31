# 구현 상태 — 5.3.0.dev5

2026-10-31 KST. 기존 `/api`와 독립적인 v1 작업공간을 제공한다. `python -m scripts.v1_demo`가 명시적으로 새 임시 프로필을 준비하며 앱 시작 시 DB 변환·seed를 실행하지 않는다. baseline의 멱등성과 digest bytes는 보존한다.

| 단계 | 구현·관찰 | 남은 경계 |
| --- | --- | --- |
| G1 | strict HTTP/DTO, 원자적 전이·감사·멱등성, 전체 평가, 승인 manifest/envelope, 링크 및 중첩 FK 재구성 | 전체 DB owner 재작성은 독립 보증 범위 밖 |
| G2 | 별도 frozen PG17 migration, 비소유자 role/RLS, 실제 86 FK 공격·동시 요청·교착 상태 검사 | 강화한 물리 연결 고정 시험의 최종 CI 확인 진행 중 |
| G3 | 3개 허구 팩, 이중 시점·rider 보류·우선순위·소급 판정, registry, 실제 세 번째 팩 API/브라우저 흐름 | 실제 보험 규정·외부 팩 검수 아님 |
| G4 | 실제 Tabler, 시정 연결·전체 모음·3인 승인·응답 유실 복구, XSS 비실행·메모리 토큰 | AI 제품 UI 조사 후 목록/상세 배치 개편 진행 중; 독립 사용자 관찰 없음 |
| G5.1 | model/gold allowlist·연결 성분 split·정확한 NumPy PCG64 paired bootstrap | 공개 fixture만 검증; 160/80/120 비공개 연구·SME 검수 없음 |
| G5.2 | 실제 provider capability=false; 현재 adapter는 제한된 결정론적 로컬 실행 | optional 외부 job/lease 확장은 미구현·미활성, 실모델 결과 없음 |
| G6 | 새 파일만 허용하는 backup/restore, token disablement, 실제 process outage·tamper·복구 훈련 | 외부 anchor/WORM·동의받은 외부 검수·운영 검증 SKIPPED, bonus 0 |

비 PostgreSQL 전체 실행은 **862 passed, 1 optional Python-browser skipped, 22 subtests passed**였다. 실제 Chrome MCP 흐름은 별도로 실행했다. 이후 OpenAPI 보강의 표적 회귀를 별도 실행한다. Windows socketpair 초기화만 253회 재시도했으며 애플리케이션 요청/검사를 반복한 것이 아니다. 외부 browser CLI의 skip을 MCP 실행 성공과 혼동하지 않는다.

PG17.11의 표적 실행에서는 459개 검사가 통과했다. 후속 재실행에서 동시성 시험이 barrier 전에 풀 연결을 반환할 수 있음을 발견해 물리 연결을 끝까지 유지하도록 보강했다. 이 보강 뒤 로컬 Windows 재시작은 socket 10014/timeout으로 실패했으며 성공으로 세지 않는다. 별도 Linux PG17 CI가 최종 코드를 검증한다.

실행 증거와 실패는 [VALIDATION](VALIDATION.md), [로컬 복구 결과](evidence/g1-g6/recovery-drill.json)에 기록한다. 내부 AI 검토는 외부 전문가/사용자 검수로 집계하지 않는다. 합성 데모의 PASS·승인은 실제 지급/계약 결정이나 운영 배포 승인이 아니다.
