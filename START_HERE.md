# CaseProof Enterprise — v5.2 구현 전 보완 패키지

> **2026-10-29 개발 진행:** 원본 기준선을 Git에 보존한 뒤 G1 승인 무결성·입력 계약을 일부 구현·검증했다. 최신 결과와 남은 작업은 [DEVELOPMENT_STATUS.md](DEVELOPMENT_STATUS.md)를 먼저 읽는다. 아래 원본 패키지 설명과 과거 감사 결과는 당시 기록이다.

**먼저 확인:** v5.2는 설계·구현계획·인수기준의 버전이다. 포함된 실행 코드는 **v5.1 합성 시제품 그대로**이며 P0 수정·실제 제품 구현을 완료했다는 뜻이 아니다. 실고객 데이터나 보험금 지급·계약 승인·금융기관 실운영에 사용하지 않는다.

## 1. 이 패키지의 목적

2026-10-29 독립 감사에서 발견한 승인 무결성 위험과 API/업무 규칙·경쟁검증·운영 공백을 구현 전에 수정 가능한 계약으로 정리했다. 우선 실제 임시 SQLite에서 P0 후보를 재현하고 fail-closed로 고친 다음 PostgreSQL·보험 업무팩·UI·AI 비교실험을 진행한다.

- `prebuild/01_TARGET_DESIGN.md`: 제품 범위, 승인·감사 불변식, 동시성, 출처·특약·UI 목표.
- `prebuild/02_IMPLEMENTATION_PLAN.md`: G0~G6 순서, 파일별 작업·테스트·합격 조건.
- `prebuild/03_INSURANCE_AND_EXPERIMENT.md`: 보험 모델과 360건·160/80/120 비교실험 계약.
- `prebuild/04_ACCEPTANCE_AND_EVIDENCE.md`: 공격 시나리오 20개, 미실행 범위, 증거와 점수 연결.
- `prebuild/05_CODEX_KICKOFF.md`: 구현을 시작할 때 Codex에 전달하는 전체 실행 프롬프트.
- `prebuild/06_DESIGN_REVIEW.md`: 내부 설계 검토에서 발견한 충돌과 반영 결과.
- `prebuild/07_PACKAGE_VALIDATION.md`: 원본 보존과 이 패키지에서 실제 확인한 결과.
- `independent_audit/`: 2026-10-29 감사 보고·점수·출처·실험 스크립트와 당시 로그.
- `current/`: 실행 코드·합성 데이터·기존 테스트 **v5.1**. 변경하지 않은 기준선이다.
- `legacy/`, `current/archive_v4/`, `current/archive_v5_early/`, `current/archive_v5_1_planning/`: 과거 설계·프롬프트. 현재 구현 또는 최신 목표의 증거가 아니다.

## 2. 정본과 모순 해결

1. **현재 동작 여부:** `current/service`, `reference`, `datasets`, `tests`와 이번 환경에서 실제 실행한 결과가 우선. 계획 문서는 구현 완료의 증거가 아니다.
2. **앞으로 만들 목표:** `prebuild/01`~`04`가 우선. 옛 `current/docs/05`와 `current/prompts/CODEX_V5_1_MASTER.md`는 최신 문서로 연결하며 원본은 archive에 보존한다.
3. **점수 기준:** `SCORECARD_105.csv` 배점, 이후 독립 평가의 증거 기준. 옛 80/105는 자체 평가다. 2026-10-29의 19/105는 미실행 항목을 0으로 처리한 해당 환경의 보수적 점수다. 이후 개발 결과를 반영한 점수가 아니다.
4. **데이터셋 계획:** 옛 문서의 다른 분할이 있으면 `prebuild/03`의 160 개발·80 검증·120 블라인드(총 360)를 계획 정본으로 삼는다. 이는 아직 만들어지거나 검수·봉인된 데이터가 아니다.
5. **테스트 이력:** 패키지 작성자의 과거 pytest 90개+하위 22개, smoke 12/12와 2026-10-29 감사의 49 unittest 통과·전체 pytest/smoke 미실행은 별개다. 새 환경에서 직접 실행하기 전 통과를 확정하지 않는다.

## 3. 현재 출시 차단 위험

`current/service/app.py`의 원본 함수를 ORM 스텁에 주입한 격리 실험에서 DB 상태값만 바꾸면 실제 현업 결정 기록 없이 `APPROVED_FOR_DEMO`에 도달하면서 행 무결성이 True로 보일 수 있었다. **실제 HTTP/SQL DB에서의 공격 성공은 아직 확인하지 못했다.** 따라서 개발 첫 단계는 임시 SQLite/TestClient에서 재현하고 승인 기록·상태·revision·감사를 같은 트랜잭션으로 검증하는 것이다. DB 관리자 전체 조작에 대한 안전성은 외부 신뢰 앵커와 별도 실험이 필요하다.

## 4. 구현 시작 전 실행 방법

1. 전체 ZIP을 풀고 **별도 작업 복사본**을 만든다. 원본 자료 및 평가 로그는 보존한다.
2. `prebuild/05_CODEX_KICKOFF.md`의 전문을 Codex에 전달하고 G0부터 진행한다.
3. Windows 예시(압축을 푼 위치에서):

```powershell
cd .\CaseProof_Enterprise\current
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
$env:CASEPROOF_DEMO_MODE='1'
python -m pytest -q
python -m scripts.smoke
```

`python -m scripts.smoke`는 성공 시 `reports/integration_smoke.json`을 덮으므로 원본이 아닌 사본에서만 실행한다. `scripts/browser_e2e.py`는 고정된 샘플 DB 파일을 삭제하는 코드가 있어 수정 전에는 실행하지 않는다. 실제 DB URL, 토큰, 외부 전송과 삭제 대상은 매번 먼저 확인한다.

`CASEPROOF_CURRENT`에 current의 절대 경로를 지정하면 `independent_audit/audit_probe.py`의 표준 라이브러리 격리 실험을 재현할 수 있다. `independent_audit/live_probes.py`는 실제 SQLite/API 검증용으로 작성되었지만 2026-10-29에는 실행하지 못한 **후속 검증 도구**다.

## 5. 무결성

압축을 풀고 패키지 루트에서 `python VERIFY_PACKAGE.py`를 실행하면 패키징 당시의 파일 해시와 추가/누락 파일을 검증한다. 해시가 맞아도 코드의 보안·보험 정확성·외부 검증이 증명되는 것은 아니다. 테스트나 코드를 수정하면 원래 manifest는 더 이상 일치하지 않을 수 있으므로 원본을 따로 보관하고 별도 실행 증거를 남긴다.
