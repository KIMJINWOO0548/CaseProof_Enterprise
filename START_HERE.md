# CaseProof v5.3 — Codex 구현·오픈소스 공개 준비 패키지

> **2026-10-30 업데이트:** 현재 `5.3.0.dev2`는 v5.3 병합에 이어 v1 DTO·순수 상태기계를 추가했습니다. 기존 전이 원장·승인 봉인·전체 요청 재시도 기능을 보존했으며 `/api/v1` HTTP·DB 연결은 후속 작업입니다. [통합 기록](docs/V53_INTEGRATION.md), [현재 상태](docs/STATUS.md), [이번 검증](docs/VALIDATION.md)을 먼저 확인하세요. 공개 저장소는 [KIMJINWOO0548/CaseProof_Enterprise](https://github.com/KIMJINWOO0548/CaseProof_Enterprise)입니다.

이 폴더 자체가 Git 저장소 루트입니다. 이전 `current/`, `legacy/`, 중복 ZIP 중심 구조를 없애고 **실행 코드와 앞으로 구현할 계약을 구분**했습니다. 새 원격 저장소를 만들거나 GitHub에 게시한 상태는 아닙니다.

## 이번 수정의 의미

- 실행 가능한 기존 합성 데모를 유지하며 승인 상태·revision·담당자 변조 검증, 입력 계약, 평가자 권한, 미완료 비교실험 처리와 검증 스크립트를 보완합니다. 실제 실행 결과는 [VALIDATION.md](docs/VALIDATION.md)가 정본입니다.
- `/api`는 현재 시제품 API입니다. `/api/v1`은 향후 구현 계약입니다. 전이 테이블, 전체 쓰기의 idempotency, PostgreSQL/RLS, 완전한 평가 run, 모델 어댑터는 계획으로 명시합니다.
- 오픈소스 기본 파일, GitHub CI, 의존성 잠금, 예제 계약, 구현 계획과 인수 기준을 제공합니다. 실보험 업무·보안 인증·360건 외부 검증 완료를 주장하지 않습니다.

## 바로 넘기는 방법

1. 압축을 풀어 `CaseProof_Enterprise_v5_3` 폴더를 Codex 작업 폴더로 엽니다.
2. [AGENTS.md](AGENTS.md), [상태표](docs/STATUS.md), [구현 계약](prebuild/08_IMPLEMENTATION_CONTRACTS.md)을 읽게 합니다.
3. [05_CODEX_KICKOFF.md](prebuild/05_CODEX_KICKOFF.md)의 전문을 붙여넣습니다. G0 재검증 후 G1의 첫 미완료 작업부터 시작하면 됩니다.
4. 구현 후 [PUBLISHING.md](docs/PUBLISHING.md)의 절차로 GitHub에 게시합니다. 이 패키지 자체는 개발용 pre-release로 공개할 수 있도록 구성했습니다.

Codex에는 `이 폴더의 AGENTS.md와 prebuild/05_CODEX_KICKOFF.md를 읽고, G0 검증 뒤 첫 미완료 작업부터 구현해 주세요. 기존 테스트와 합성 데이터의 정답을 보존하고, 각 Gate의 실제 실행 결과를 reports/runs에 남겨 주세요.`라고 전달하셔도 됩니다.

## 문서 우선순위

| 질문 | 정본 |
| --- | --- |
| 지금 실제로 무엇이 동작하는가 | 코드 + 이번 실행 기록 + [STATUS](docs/STATUS.md) |
| 다음 버전은 정확히 무엇을 구현해야 하는가 | [08 계약](prebuild/08_IMPLEMENTATION_CONTRACTS.md) → [01 설계](prebuild/01_TARGET_DESIGN.md) → [02 계획](prebuild/02_IMPLEMENTATION_PLAN.md) |
| 예제 JSON이 올바른가 | `contracts/` 스키마·샘플; 현재 API와 혼동 금지 |
| 과거의 19/105·80/105·90 테스트는 무엇인가 | [PROVENANCE](docs/PROVENANCE.md); 새 버전 점수나 검증 결과가 아님 |
| 공개/배포 가능한 범위는 무엇인가 | [STATUS](docs/STATUS.md), [SECURITY](SECURITY.md), [PUBLISHING](docs/PUBLISHING.md) |

문서 사이의 충돌을 발견하면 숨기지 말고 해당 계약과 테스트를 같이 수정합니다. 하위 문서의 오래된 문장을 근거로 상위 계약을 우회해서는 안 됩니다. 도구·외부인이 없으면 확인되지 않은 것을 확인했다고 만들지 않습니다.

## 로컬 실행과 환경

Windows에서도 활성화 스크립트 없이 `.venv\Scripts\python.exe`를 직접 실행할 수 있습니다. 플랫폼별 정확한 명령은 [README](README.md)에 있습니다. 저장소 밖의 운영 DB, 실고객 자료, 외부 모델 키는 필요하지 않습니다. 원본 ZIP은 본 패키지에 중복 포함하지 않았으며 원본 파일 해시와 제외 내역은 [PROVENANCE](docs/PROVENANCE.md)에 기록합니다.
