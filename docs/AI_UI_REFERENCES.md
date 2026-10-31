# AI 제품 UI 조사와 CaseProof 적용

2026-11-01. 실제 변경 검토 화면의 목록·상세 배치를 개선했다. 기존 로컬 Tabler 1.7.3을 사용하며 새로운 UI 패키지는 추가하지 않았다.

## 공식 자료와 확인 범위

| 제품 | 확인한 공식 자료 | 적용한 작업 방식 |
| --- | --- | --- |
| Langfuse | [Sessions 설명](https://langfuse.com/docs/observability/features/sessions), [실제 공식 화면](https://langfuse.com/images/docs/session.png). 원본 PNG를 직접 시각 확인했다. | 왼쪽 목록과 오른쪽 검사 영역을 함께 표시하고 선택 표시를 유지한다. |
| LangSmith | [Observability](https://www.langchain.com/langsmith/observability), [Manage traces](https://docs.langchain.com/langsmith/manage-trace). 공식 문서의 상세 검사·관련 로그 이동을 확인했다. AVIF 그림의 세부 시각은 검증하지 않았다. | 선택한 변경의 제목·상태·revision·결정을 같은 문맥에 유지한다. |
| Dify | [Logs](https://docs.dify.ai/en/cloud/use-dify/monitor/logs). 실행 결과·입출력·상태를 나누는 공식 문서 내용을 확인했다. 그림 CDN은 403이어서 세부 화면을 확인하지 못했다. | 최신 평가 결과와 승인 증거를 구분하고, 증거의 세 가지 판정을 각각 표시한다. |

로고·제품 화면·CSS·소스 코드·색상 토큰을 복사하지 않았다. 자료는 정보 배치의 근거로 사용했으며 해당 제품과의 연동이나 제휴를 뜻하지 않는다.

## 구현한 범위

- 992px 이상에서는 왼쪽 작업함과 오른쪽 변경 상세가 같은 높이에서 시작한다. 긴 작업 목록이 상세를 화면 아래로 밀지 않는다.
- 작업함은 기본 HTML 표를 유지한다. 각 요청의 제목, 실제 상태, 팩, revision을 한 행에 모으고 현재 선택에 `aria-current`와 행 표시를 유지한다.
- 상세의 상태와 revision을 함께 배치하고 역할별 결정 버튼을 참조 정보보다 먼저 표시한다. 최신 평가와 증거 조회는 기존 동작을 유지한다.
- 좁은 화면에서는 작업함·상세·증거를 순서대로 배치한다. 모바일 44px 버튼·입력, 키보드 초점, reduced motion과 기본 dialog를 유지한다.

토큰·권한·상태 전이·요청 복구 로직과 증거 조회 API는 변경하지 않았다. 외부 추적 SDK, 가짜 차트나 실행 수치, 제공하지 않는 메뉴는 추가하지 않았다. UI/UX Pro Max의 기존 검토 및 focus 지침과 Frontend Design을 설계에 사용하고 Uncodixfy로 장식적 요소를 최종 점검했다. 기존 팔레트와 접근성 조건을 스킬의 일반적인 스타일 선호보다 우선했다.

## 검증 경계

`scripts/v1_ui_probe.js`는 1280/1440px 병렬 배치, 390px 순서와 가로 넘침을 검사한다. 이 검사와 실제 브라우저·업무 흐름의 실행 결과는 [VALIDATION](VALIDATION.md)에 별도로 기록한다. 함수가 존재하는 것만으로 브라우저 PASS를 주장하지 않는다.

목록과 내용을 함께 보는 배치의 유용성은 설계 가설이며 독립 사용자 연구 또는 외부 전문가 검수를 대신하지 않는다. 외부 모델·앵커·실제 보험 판단은 이 화면 개편의 검증 범위가 아니다.
