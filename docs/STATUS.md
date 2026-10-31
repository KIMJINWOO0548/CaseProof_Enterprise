# 구현 상태 — 5.3.0.dev6

2026-11-01 KST. 기존 `/api`와 독립적인 v1 작업공간을 제공한다. `python -m scripts.v1_demo`가 명시적으로 새 임시 프로필을 준비하며 앱 시작 시 DB 변환·seed를 실행하지 않는다. baseline의 멱등성과 digest bytes는 보존한다.

| 단계 | 구현·관찰 | 남은 경계 |
| --- | --- | --- |
| G1 | strict HTTP/DTO, 원자적 전이·감사·멱등성, 전체 평가, 승인 manifest/envelope, 링크 및 중첩 FK 재구성 | 전체 DB owner 재작성은 독립 보증 범위 밖 |
| G2 | 별도 frozen PG17 migration, 비소유자 role/RLS, 실제 86 FK 공격·동시 요청·교착 상태 검사 | 정확한 구현 CI의 PG460 PASS: 같은 키 100회·서로 다른 변경 경합; 운영 DB 배포 검증은 별도 |
| G3 | 3개 허구 팩, 이중 시점·rider 보류·우선순위·소급 판정, registry, 실제 세 번째 팩 API/브라우저 흐름 | 실제 보험 규정·외부 팩 검수 아님 |
| G4 | 실제 Tabler, 시정 연결·전체 모음·3인 승인·응답 유실 복구, XSS 비실행·메모리 토큰 | Langfuse·LangSmith·Dify를 참고한 병렬 목록/상세, 실제 Chrome 재검증; 독립 사용자 관찰 없음 |
| G5.1 | model/gold allowlist·연결 성분 split·정확한 NumPy PCG64 paired bootstrap | 공개 fixture만 검증; 160/80/120 비공개 연구·SME 검수 없음 |
| G5.2 | 실제 provider capability=false; 현재 adapter는 제한된 결정론적 로컬 실행 | optional 외부 job/lease 확장은 미구현·미활성, 실모델 결과 없음 |
| G6 | 새 파일만 허용하는 backup/restore, token disablement, 실제 process outage·tamper·복구 훈련 | 외부 anchor/WORM·동의받은 외부 검수·운영 검증 SKIPPED, bonus 0 |

dev6의 고정된 실행·HTTP·UI 소스에 대한 로컬 전체 회귀는 **904 passed, 1 optional Python-browser skipped, 22 subtests passed**였다. Windows socketpair 초기화만 662회 재시도했다. 이후 CLI listener를 보강했고 정확한 구현643e25f의 전체 CI·새 배포물 검사까지 통과했다(아래 참조). 초기 CLI 15초 timeout 실패와 수정 없는 단독 통과를 모두 보존한다.

`651a5bc`의 [CI](https://github.com/KIMJINWOO0548/CaseProof_Enterprise/actions/runs/41216084641)는 일반 각 868 PASS, PG17.11 **460 PASS**, 수치 통계 34 PASS, OSV·JS·배포물까지 **9개 job 성공**이었다. 과거 결과는 별도로 보존하며 아래643e25f에서 후속 dev6도 재검증했다. 실제 PG role/RLS/물리 연결 경합을 SQLite 검사와 구분한다.

새 실행은 완전한 설정을 묶는 `evaluation_run_v2`다. 평가 후 어댑터·데이터셋·출처 묶음의 부분 재작성과 canonical identity 누락을 독립 재현 후 보강했다. V1 저장 bytes는 보존하며 `LEGACY_UNVERIFIED`로 조회하고 재승인을 차단한다. [실행 형식 경계](EXECUTION_CONFIG.md), 검증된 `immutable_refs`의 공개 범위를 따른다.

실행 증거와 실패는 [VALIDATION](VALIDATION.md), [로컬 복구 결과](evidence/g1-g6/recovery-drill.json)에 기록한다. 내부 AI 검토는 외부 전문가/사용자 검수로 집계하지 않는다. 합성 데모의 PASS·승인은 실제 지급/계약 결정이나 운영 배포 승인이 아니다.

후속 AI UI는 Chrome 156의 native clicks로 반려→시정→별도 검토자 승인·증거, committed response 유실 복구, 1280/1440px 병렬 배치·390/375px 넘침·닫힌 dialog·Escape 복귀를 검사했다. 합성 GET 403/404/409/422·로딩·빈 목록도 별도 관찰했다. 주요 텍스트 대비는 6.32 이상이며 모바일 표적은 44px였다. [최신 V2 실행 범위](evidence/g1-g6/ai-ui-browser-dev6.json), [화면 측정](evidence/g1-g6/ai-ui-metrics.json).

실제 CLI의 Windows 10014 시작 실패를 독립 재현한 뒤 초기화만 제한적으로 보강했다. [CLI 5개 검사](evidence/g1-g6/demo-startup-verification.json)와 [새 V2 복구 4개 훈련](evidence/g1-g6/recovery-drill-dev6.json)이 통과했다. 최종 구현 CI와 격리 배포물의 실제 결과를 아래에 기록한다.

후속 [결정 흐름 UX 감사](UI_FOCUS_AUDIT.md)로 모달 투명 배경과 모달 밖 오류를 재현·수정했다. 1440/390px 요약/필드 초점·Escape·오류 초기화·잘못된 입력 POST0, 전체 3인 시정 승인 흐름을 실제 Chrome으로 재검증했다. [de1fc5e CI](evidence/g1-g6/ci-de1fc5e.json)는 9개 성공, 일반 각 911 PASS·PG460 PASS였으며 후속 UI643e25f도 아래의 별도 CI·배포물 검사에서 통과했다.

## dev6 핵심 구현 검증

구현 commit `643e25f`의 [CI](https://github.com/KIMJINWOO0548/CaseProof_Enterprise/actions/runs/41222223392)는 **9개 job success / PR 전용 1개 skipped**다. Linux Python3.11/3.12/3.13·Windows3.12 각각 **911 PASS**, 실제 PG17.11 **460 PASS**, NumPy 평가 **34 PASS**를 확인했다. 일반 job의 선택 의존성 skip과 실제 PG/NumPy 별도 실행을 구분한다. [정확한 결과와 명령](evidence/g1-g6/ci-643e25f.json).

[새 runtime-only wheel](evidence/g1-g6/installed-643e25f-wheel.json)은 체크아웃 밖 설치·V2 생성/평가·VALID 근거/immutable refs까지 통과했다. 소스 ZIP과 내부379개 source hash도 검증했다. 후속 완료 기록 변경은 문서·증거만 갱신하며 같은 구현을 유지한다. 실제 최신 브랜치 CI는 GitHub Actions에서 commit SHA별로 확인한다.

현재 UI는 합성 검토 데모로 캡처·native 동선 검증을 마쳤다. 스크린리더 발화·독립 사용자/전문가·설치 검수, 비공개360연구, 외부 provider/job·anchor/WORM·운영 검증은 완료하지 않았다. 해당 외부 검수 bonus는0이다.

## 추가 시각 개편

잉크·아이리스·피치 색상, 로컬 SUIT 글꼴, 실제 현재 검토 단계와 넓은 화면의 독립 증거 패널을 적용했다. [설계·출처](VISUAL_DESIGN.md), [실제 화면·측정](evidence/g1-g6/ui-visual-refresh.json)을 기록했다. Chrome156에서 전체 반려/시정/승인·원래 요청 복구·오류 초점을 통과했고,375/390/768/1024/1280/1440px 가로 넘침0과 모션 감소를 확인했다. MIME 회귀는 RED→GREEN, 관련 Python4 PASS·선택 브라우저1 SKIP이다. 앞선 핵심 검증과 새 변경의 최종 CI는 SHA를 구분해 [VALIDATION](VALIDATION.md)에 기록한다.
