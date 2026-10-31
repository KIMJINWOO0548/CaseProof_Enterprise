# AI 제품 UI 조사와 CaseProof 적용

2026-11-01. 실제 변경 검토 화면의 목록·상세 배치를 개선했다. 기존 로컬 Tabler 1.7.3을 사용하며 새로운 UI 패키지는 추가하지 않았다.

## 공식 자료·관찰·적용 결정

2026-11-01 KST에 공식 문서를 다시 읽고 GitHub MCP로 두 프로젝트의 `main` commit을 조회한 뒤 그 commit에 고정된 LICENSE 원문을 확인했다. 아래의 장점은 문서 또는 화면에서 관찰한 작업 방식이며 CaseProof에서의 사용성 효과는 별도 설계 가설이다. 세 제품을 모두 같은 라이선스의 오픈소스로 분류하지 않는다.

| 제품·공식 URL | 관찰한 장점과 확인 수준 | CaseProof 적용 파일·구역 | 제외한 아이디어·이유 | 라이선스 분류·확인 원문 |
| --- | --- | --- | --- | --- |
| **Langfuse** — [Sessions](https://langfuse.com/docs/observability/features/sessions), [공식 화면](https://langfuse.com/images/docs/session.png) | 목록과 넓은 검사 영역이 함께 보여 선택 대상을 유지한다. 2026-10-31 조사에서 원본 PNG를 직접 시각 확인했고 이번에는 공식 설명을 재확인했다. | [v1.html](../service/static/v1.html)의 `.workspace-grid` 작업함/`.review-grid` 상세, [v1.css](../service/static/v1.css)의 병렬 grid와 모바일 단일 열, [v1.js](../service/static/v1.js)의 `renderQueue`·`syncSelectedRow` | 채팅 replay·토큰 비용·public share·아이콘 전용 전역 sidebar는 현재 변경 승인 업무에 없고 추가 권한/데이터가 필요해 제외한다. | core **SPDX `MIT`**, enterprise 경로와 제3자 구성요소는 별도. [고정 LICENSE](https://github.com/langfuse/langfuse/blob/c96575bb34e9683885f94935604d3fc2064b14bc/LICENSE), [enterprise LICENSE](https://github.com/langfuse/langfuse/blob/c96575bb34e9683885f94935604d3fc2064b14bc/ee/LICENSE) |
| **LangSmith** — [Observability](https://www.langchain.com/langsmith/observability), [Manage a trace](https://docs.langchain.com/langsmith/manage-trace) | 상세에서 관련 로그로 이동할 때 Trace ID 문맥을 유지한다. 공식 문서 텍스트만 확인했다. 이전 AVIF는 표시되지 않아 세부 시각 근거로 사용하지 않는다. | [v1.js](../service/static/v1.js)의 `render` 제목·상태·revision·역할별 결정 및 `syncSelectedRow`, [v1.html](../service/static/v1.html)의 `#detail` | trace tree·실행 비교·공개 공유·상용 UI 코드/자산을 가져오지 않는다. 현재 API가 제공하지 않는 기능이며 상용 제품의 문서 참조를 재배포 허가로 해석할 수 없다. | **상용 proprietary 제품**, UI에 오픈소스 SPDX를 부여하지 않음. [공식 Terms](https://www.langchain.com/terms-of-service), 갱신일 2026-06-02, §§2.4·4.1. LangChain/LangSmith SDK 라이선스를 hosted UI에 전용하지 않음. |
| **Dify** — [Logs / Inspect a Run](https://docs.dify.ai/en/cloud/use-dify/monitor/logs) | 한 실행의 결과·입출력·상태를 구분하고 관련 trace를 확인한다. 공식 문서 텍스트만 확인했다. 이전 그림 CDN 403으로 세부 화면을 관찰했다고 주장하지 않는다. | [v1.js](../service/static/v1.js)의 `#run-result` 결과 표와 `#load-evidence` 처리, [v1.html](../service/static/v1.html)의 `#evidence` 역사 무결성/현재 적격성/앵커 구역 | workflow 편집 캔버스·Test With Params·thumbs-up 승인은 제외한다. 전체 모음 재평가와 사람 승인 계약을 우회하거나 없는 기능을 표시하지 않기 위해서다. 제품 외형·컴포넌트도 복제하지 않는다. | **수정 Apache-2.0 + 추가 조건**, plain `Apache-2.0`로 표시하지 않음. 로컬 식별 설명 `LicenseRef-Dify-Additional-Terms`는 공식 SPDX 목록 등록 주장 아님. [고정 LICENSE](https://github.com/langgenius/dify/blob/4c521a3c0a1f60607c8a7bcf90792f34adcf18d0/LICENSE) |

## 라이선스·버전 기록

버전 tag를 추측하지 않고 실제 조회한 commit과 원문을 기록했다. Git blob SHA-1과 아래 SHA-256은 서로 다른 식별자다. SHA-256은 GitHub MCP가 반환한 LICENSE 문자열을 줄바꿈 등 추가 정규화 없이 UTF-8로 인코딩한 값이며 upstream이 별도로 공표한 checksum이라고 주장하지 않는다.

| 대상 | 조회 commit / 약관 버전 | LICENSE 텍스트 SHA-256 |
| --- | --- | --- |
| Langfuse root LICENSE | `c96575bb34e9683885f94935604d3fc2064b14bc` | `9ee6ca42e813fb58bcad18bed834438503bcc997da3b452d3f9ad4af4292b6b3` |
| Langfuse ee/LICENSE | 같은 commit | `760f5202be4f31f9f8ca43a3c558bebaa5187fa7d7eccad6a32de8392cdccee6` |
| Dify LICENSE | `4c521a3c0a1f60607c8a7bcf90792f34adcf18d0` | `232cf91474932d5110ed304e53b6b742a58463857c571fae803fdf2ac36d7bb3` |
| LangSmith | 공식 Terms 갱신일 `2026-06-02`; hosted UI commit/tag는 확인하지 않음 | 고정 LICENSE 파일을 제공받지 않았으므로 기록하지 않음 |

Langfuse root LICENSE는 `ee/`, `web/src/ee/`, `worker/src/ee/`, `packages/shared/src/server/ee/`를 MIT 범위에서 제외하고 `ee/LICENSE`로 연결한다. 제3자 구성요소도 각 원 라이선스를 유지한다. enterprise 원문은 해당 계약·유효한 Enterprise License 아래의 사용을 규정하므로 프로젝트 전체를 일괄 MIT로 부르지 않는다.

확인한 Dify LICENSE는 Dify 소스를 이용한 다중 tenant 운영에 서면 허가/상용 라이선스 조건을 두며, Dify frontend를 사용할 때 로고·저작권 정보를 제거하거나 바꾸지 못하게 한다. contributor의 약관 조정·상업 이용 조건과 interactive design에 대한 appearance patent 주장도 포함한다. 이는 원문의 범위를 요약한 것이며 특허 유효성·적용 범위나 재사용 권리 확보를 검증한 결과는 아니다.

LangSmith 공식 Terms는 platform과 documentation의 사용 제한 및 LangChain/licensor의 권리 유보를 명시한다. 공개 설명을 읽었다는 사실만으로 상용 UI 코드·문서·화면의 복제 권한을 확보했다고 기록하지 않는다.

이번 적용은 일반적인 목록/상세·선택 문맥·결과 분리 방식의 참고에 한정한다. 세 제품의 코드·CSS·로고·스크린샷·색 토큰·SDK를 저장소나 배포물에 복사하지 않았고 연동·제휴도 추가하지 않았다. 기존 vendored **Tabler 1.7.3 MIT**의 파일·해시·완전한 notice는 [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES.md)와 해당 vendor 디렉터리에 보존한다. 이 조사 자체는 별도 법률 검수나 포괄적인 권리 clearance가 아니다.

## 구현한 범위

- 992px 이상에서는 왼쪽 작업함과 오른쪽 변경 상세가 같은 높이에서 시작한다. 긴 작업 목록이 상세를 화면 아래로 밀지 않는다.
- 작업함은 기본 HTML 표를 유지한다. 각 요청의 제목, 실제 상태, 팩, revision을 한 행에 모으고 현재 선택에 `aria-current`와 행 표시를 유지한다.
- 상세의 상태와 revision을 함께 배치하고 역할별 결정 버튼을 참조 정보보다 먼저 표시한다. 최신 평가와 증거 조회는 기존 동작을 유지한다.
- 좁은 화면에서는 작업함·상세·증거를 순서대로 배치한다. 모바일 44px 버튼·입력, 키보드 초점, reduced motion과 기본 dialog를 유지한다.

토큰·권한·상태 전이·요청 복구 로직과 증거 조회 API는 변경하지 않았다. 외부 추적 SDK, 가짜 차트나 실행 수치, 제공하지 않는 메뉴는 추가하지 않았다. UI/UX Pro Max의 기존 검토 및 focus 지침과 Frontend Design을 설계에 사용하고 Uncodixfy로 장식적 요소를 최종 점검했다. 기존 팔레트와 접근성 조건을 스킬의 일반적인 스타일 선호보다 우선했다.

## 검증 경계

`scripts/v1_ui_probe.js`는 1280/1440px 병렬 배치, 390px 순서와 가로 넘침을 검사한다. 이 검사와 실제 브라우저·업무 흐름의 실행 결과는 [VALIDATION](VALIDATION.md)에 별도로 기록한다. 함수가 존재하는 것만으로 브라우저 PASS를 주장하지 않는다.

목록과 내용을 함께 보는 배치의 유용성은 설계 가설이며 독립 사용자 연구 또는 외부 전문가 검수를 대신하지 않는다. 외부 모델·앵커·실제 보험 판단은 이 화면 개편의 검증 범위가 아니다.
