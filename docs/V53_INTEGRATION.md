# v5.3 병합 결정 — 2026-10-30

입력은 사용자가 지정한 `CaseProof_Enterprise_v5_3`입니다. 변경 전 전용 verifier로 **187개 파일, 해시 불일치 0**을 확인했습니다. 입력 폴더는 수정하지 않았고 [원본 manifest](provenance/v5_3_input_manifest.json)를 보존했습니다. 비교 기준 Git 커밋은 `4b8e67c`입니다.

## 반영한 내용

| 영역 | 선택 |
| --- | --- |
| 구조 | 활성 service/reference/tests/datasets/scripts를 루트로 이동. 이전 문서·감사·중복 배포물은 archive와 Git 이력에 보존. archive·로컬 도구·런타임은 배포 소스와 wheel/sdist에서 제외 |
| 서비스 | 기존 전이 원장·승인 봉인·전체 쓰기 멱등성을 유지하고 v5.3의 strict revision·extra=forbid·손상 JSON·감사 순서·제출 전 무결성 검사·CLI DB 환경변수 처리를 병합 |
| 참조 엔진 | 선택된 적용 가능 미승인 특약을 기본 규정으로 대체하지 않음. 비교 양측 중 하나라도 incomplete면 INVALID, 확정 통계 미출력 |
| 안전 도구 | 고정 DB 파일 삭제 및 import 시 서버 실행을 없앤 격리 브라우저 도구. 기존 smoke의 필수 요청 키·보고서 덮어쓰기 금지를 유지 |
| 배포 준비 | 사용자 제공 Apache-2.0/NOTICE·기여/보안 문서, hash lock, pyproject, CI, source/wheel 검사, v1 계약·예제·벡터를 반영 |

프로젝트 가상환경에 제공된 `requirements-dev.lock`을 `--require-hashes`로 설치했습니다. 전역 패키지·보안 설정·기존 DB는 변경하지 않았습니다. 종전 PostgreSQL 준비 승인은 유지되지만 새 계약의 선행 G1 작업을 확인한 후 진행합니다. 이번 병합은 PG 설치나 RLS 검증이 아닙니다.

## 충돌을 처리한 기준

1. v5.3의 `app.py`, `models.py`, `integrity.py`를 통째로 덮으면 기존 G1 전이·승인 증거·전체 재시도 기능이 사라집니다. 기존 구현을 기준으로 필요한 경계 검증을 옮겼습니다. 기존 데이터·평가기준·고정 정답을 바꾸지 않았습니다.
2. `/api`의 historical replay는 인증·역할·tenant·담당자 분리를 다시 검사한 뒤 저장된 원래 응답을 재생합니다. 최신 무결성 판정은 GET evidence로 확인합니다. 입력 패키지의 “replay 전에 현재 무결성 검사” 테스트와 충돌하는 경우, 이미 승인된 원래 응답 계약을 유지하고 **추가된 테스트만** 그 의미에 맞게 문서화했습니다. 새 `/api/v1` 계약도 auth → replay → 신규 검사 순서입니다.
3. 새 패키지의 변조 테스트 일부는 이 저장소의 강화된 복합 FK 때문에 변조 자체가 거절됩니다. FK를 끄는 대신 IntegrityError·rollback·정상 증거 보존을 검사합니다. 기존 테스트의 assertion은 삭제하지 않았습니다.
4. 기존 일반 SHA256 `digest()`는 바꾸지 않습니다. v1은 `caseproof:{purpose}:v1` 접두어를 사용하는 별도 canonical module로 시작합니다. 이미 저장된 승인·감사 해시를 새 방식으로 재작성하지 않습니다.
5. baseline의 `assessment_manifest_v1` / `approval_envelope_v1` label과 **계획 target**의 같은 label은 필드 구조가 다릅니다. label만으로 호환성을 판단하지 않습니다. baseline은 `/api` 전용이고, target은 `contracts/`와 `/api/v1`에서 별도로 구현·검증합니다.

## 재현과 증거

이번 실행 폴더는 [reports/runs/20261029T151200Z-a53be001](../reports/runs/20261029T151200Z-a53be001/)입니다. raw 로그와 원본 입력 manifest를 보존합니다. 입력 패키지의 221개/Linux 결과는 과거 입력 증거이며 이번 Windows 실행 결과와 합산하지 않습니다.

병합 및 후속 canonical 구현은 `c7d3d29`, Git LF 정규화와 manifest 정합성 수정은 `8eba9de`에 보존했다. `8eba9de`의 [실제 CI](https://github.com/KIMJINWOO0548/CaseProof_Enterprise/actions/runs/40902657873)는 7개 적용 job이 모두 성공했다. source manifest의 204개 항목을 working tree와 해당 Git blob 양쪽에서 대조했으며, 사용자 제공 원본 187개도 다시 검증했다. 기존 테스트 9개와 합성 JSON 3개는 이전 커밋의 바이트를 보존했다.

다음 순서는 `prebuild/02`의 새 G1.1 계약 기반 모듈 → 불변 schema → 공통 executor → v1 HTTP → full-suite run → target 증거 봉인입니다. 기존 `/api`의 유사 기능만으로 target 완료 체크를 하지 않습니다. PostgreSQL/RLS는 그 뒤 실제 disposable DB와 non-owner 역할에서 검증합니다.
