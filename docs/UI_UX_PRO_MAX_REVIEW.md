# UI/UX Pro Max — v1 검토 화면 적용 기록

2026-10-31. 범위는 `service/static/v1.html`과 `v1.css`의 기존 작업 화면이다. 기능, API 계약, 상태 값, DOM ID와 JavaScript 동작은 변경하지 않는다.

## 조사와 선택

사용자가 지정한 로컬 `ui-ux-pro-max/SKILL.md`를 읽었다. 이 작업의 coordinator가 실제 로컬 CLI 검색을 수행하고 전달한 결과를 아래와 같이 적용했다. 아래 검색은 이 문서 작성자가 별도로 재실행한 것으로 집계하지 않는다.

| 검색 | 확인된 결과 | 판단 |
| --- | --- | --- |
| `review workbench information hierarchy`, UX domain | `ColorOnly`, `HeadingHierarchy` | 상태를 글자로 유지하고 제목 계층을 보존한다. 함께 나온 breadcrumb 권고는 평면 작업 화면에 맞지 않아 적용하지 않는다. |
| `insurance review operations dashboard`, design system | `Hero + Features + CTA` marketing pattern | 운영 검토 흐름과 맞지 않아 거부한다. 결과 전체를 디자인 정본으로 저장하지 않는다. |
| `enterprise dashboard compact readable`, style domain (좁힌 재검색) | `Data-Dense Dashboard`, id `data-dense-dashboard` | 중립 배경, 읽기 쉬운 표, 일정한 간격, 기능적인 hover/focus만 채택한다. |

기존 HTML/Tabler 구성과 `v1.js`가 생성하는 표·평가 폼·증거 정의 목록을 읽고 스타일 적용 범위를 확인했다. 신규 UI 라이브러리나 프레임워크는 필요하지 않다.

## 적용한 다섯 가지 조정

1. 합성 데이터와 외부 연결 한계 안내를 계속 상단에 표시하되 중립 배경과 작은 본문으로 낮춘다. 흰색 앱 헤더와 작업 제목이 본 작업의 시작을 구분한다.
2. 본문과 표를 14px 기준으로 맞추고 카드·표·폼에 일정한 12/16/20/24px 간격을 적용한다. 기존 시스템 글꼴과 로컬 Tabler 1.7.3을 사용한다.
3. 작업함은 검색/필터와 표 머리를 구분하고, 행 hover와 키보드 `focus-within` 표시를 제공한다. 상태 글자는 그대로 유지한다. 통합 과정에서 현재 선택 데이터의 `aria-current`와 행 표시를 추가했으며 CSS가 선택 상태를 추정하지 않는다.
4. 상세와 증거 영역은 같은 제목 계층을 사용하고 정의 목록의 레이블과 값을 정렬한다. 평가 폼과 결과에는 구분선을 두고 원본 JSON은 접힌 상세 영역을 유지한다.
5. 작은 화면에서는 한 열 배치, 44px 이상 버튼·입력·역할 전환, 16px 입력 글자와 줄바꿈을 적용한다. 키보드 초점 테두리를 유지하고 `prefers-reduced-motion`을 지원한다.

## 보존한 것과 검증 경계

`h1 → h2 → h3`의 기존 순서, 모든 DOM ID/선택자와 영문 업무 상태, 메모리 전용 토큰, 요청 복구/역할 분리/승인/증거 조회 동작을 보존한다. 로컬 Tabler 배포물과 MIT 고지는 변경하지 않는다. 새 CDN·폰트·패키지·차트·KPI·사이드바는 추가하지 않았다.

이 기록은 적용 근거와 소스 변경을 설명한다. 브라우저 시각 검사, 실제 렌더링 대비 수치, 모바일 viewport, 키보드/업무 시나리오와 전체 회귀 결과는 coordinator의 새 실행 증거로 별도 확인해야 한다. 코드의 색상 선언이나 CSS 최소 높이만으로 접근성 인증 또는 실행 통과를 주장하지 않는다. 외부 사용자/전문가 검토나 운영 승인으로 집계하지 않는다.

The integration adds truthful `aria-current` and a persistent selected-row marker from the current record; candidate/source/suite IDs move into a native details disclosure while requester/reviewers remain visible. Browser checks are recorded by the coordinator.

## 2026-11-01 — AI 제품 자료를 참고한 후속 배치

[공식 조사와 적용 기록](AI_UI_REFERENCES.md)에 Langfuse·LangSmith·Dify의 확인 범위와 채택한 작업 방식을 기록했다. 후속 HTML/CSS와 최소 DOM 렌더링 변경으로 데스크톱 작업함·상세를 병렬 배치하고 상태와 revision을 묶었다. 기본 표·텍스트 노드·선택 표시·메모리 토큰·요청 복구 동작은 유지한다. 실제 브라우저에서 발견한 닫힌 native dialog 표시 충돌도 명시적 `dialog:not([open])` 규칙으로 수정했다. 실행 결과는 별도 검증 기록을 따른다.
