# 구현 전 계획 검토 기록

검토일: 2026-10-29. 설계 문서의 내부 검토이며 외부 보험 실무자 검수·보안 인증·B04 외부 기술 리뷰가 아니다. 서비스 코드를 구현하거나 실제 SQLite/PG 테스트를 실행한 증거로 사용하지 않는다.

## 반영한 설계 충돌

| ID | 독립 검토에서 발견한 문제 | 계획에 반영한 해결 | 실제 코드 상태 |
|---|---|---|---|
| D01 | 동일 actor의 같은 key가 다른 change의 결과를 재생할 위험 | method·route·resource/change ID·본문·expected revision을 fingerprint에 포함, 동일 key·다른 대상 409. 재생 결과와 현재 무결성 판단을 구분 | 미구현 |
| D02 | 최종 승인 시 revision이 바뀌면 사전 승인 manifest를 현재 상태로 재구성할 때 정당한 hash도 달라지는 위험 | pre-approval revision과 해당 시점 event 집합·정렬을 동결, 이후 event는 분리. 최종 approval envelope는 자기 hash를 포함하지 않음 | 미구현 |
| D03 | 최초 생성 revision=1과 전이 규칙 `from+1`의 시작점 불명확 | `NONE/0 → DRAFT/1` genesis, 평가 시 `DRAFT/n → DRAFT/n+1`, revision 결번·중복 거부 | 미구현 |
| D04 | 반려 뒤 새 revision과 후속 요청 중 선택되지 않아 상태 정본 충돌 | REJECTED는 terminal, 새 change_id와 동일 tenant parent_change_id로 연결하고 평가 새로 수행 | 미구현 |
| D05 | JSON Schema integer만으로 1.0을 거부할 수 없고 trim 길이도 스키마만으로 완전히 기술되지 않음 | schema required/min/max와 설명·확장, 런타임 strict HTTP 시험 분리. 입력 원문과 strip 결과 각각 code point 8–500 | 미구현 |
| D06 | gold hash가 자신의 hash를 포함하는 순환 위험 | hash 제외한 정규화 payload, 정렬·UTF-8·버전 고정 후 hash 산출 | 미구현 |
| D07 | 이전 smoke가 기존 보고서 파일을 고정 경로에 덮어쓰는 문제 | 출력 경로 옵션을 구현하거나 별도 실행 사본을 사용하고, 신규 run_id 경로에 저장 | 기존 스크립트는 여전히 고정 경로에 씀 |

## 미해결 검증

- 위 설계가 실제 SQLite·PostgreSQL에서 안전하게 작동하는지 아직 시험하지 않았다.
- 임시 SQLite/TestClient의 P0 재현은 최초 개발 작업이다. 스텁에서 관찰된 결과를 실제 HTTP·DB 성공으로 바꿔 말하지 않는다.
- 현업 약관 해석, 규정 소급 여부, 특약에 대한 안전한 fallback은 보험 실무자 검수 전 확정하지 않는다.
- RLS tenant context는 app role이나 SQL injection이 장악된 상태에서 보안 경계가 되지 않을 수 있다. 이를 포함한 위협 모델과 실제 DB role 시험이 필요하다.
- 360건의 목표 분할·외부 평가·보너스는 계획이며 결과물이 아니다.
