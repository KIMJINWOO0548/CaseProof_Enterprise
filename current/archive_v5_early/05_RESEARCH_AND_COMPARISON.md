# 공개 근거·경쟁제품과의 비교 원칙

## 실무 문제를 확인할 때 참고할 공개 자료

- OWASP API Security Top 10 2023, 특히 API1 객체 수준 권한 오류, API5 기능 수준 권한 오류: https://api-security.owasp.org/editions/2023/en/0x11-t10/
- SQLite composite foreign keys 원문: https://www.sqlite.org/foreignkeys.html
- 미국 NIST AI RMF 및 GenAI Profile: https://airc.nist.gov/AI_RMF_Knowledge_Base/AI_RMF
- Langfuse: https://langfuse.com/docs
- Arize Phoenix: https://arize.com/docs/phoenix
- Promptfoo: https://www.promptfoo.dev/docs/
- 한국 금융위원회와 금융보안원의 발표는 v4.0 패키지에서 검토한 공식 보도자료가 출발점이며, 수치·항목 구분이 바뀌면 원문을 새로 대조해야 한다.

이 원칙과 표는 공개 지침·제품 문서에서 **검증해야 할 요구사항을 도출**한 것이다. 각 제품이 이 보험 도메인 시나리오에서 약한지 강한지는 실제 동일 조건 실험 전까지 결정할 수 없다.

## 경쟁제품 대조

| 비교 지점 | 이미 검증된 오픈소스가 제공하는 기능 | CaseProof의 개발·검증 대상 |
|---|---|---|
| OpenTelemetry/trace | Langfuse, Phoenix 등 | 기존 엔진 재활용; 별도 tracer 자체 구현 금지 |
| 프롬프트 버전/데이터셋 관리 | 범용 도구에서 지원 | 도메인 규정 시점과 연결한 버전 선택 |
| 보안 프롬프트 테스트 | Promptfoo 등 | 규정·승인·소비자 위험에 따른 검증 결과 활용 |
| 업계별 적용 일자 | 범용 도구에 사용자 정의 구현 가능 | 적용 시점·특약·개정시점 resolver |
| 정식 승인·사후 감사 | 기존 도구별 검증 필요 | 업무 책임자와 QA, 감사 증거를 이어주는 UX |

**차별성 가설:** 실제 보험 담당자가 기존 도구+B2와 동일한 규정 엔진을 써도 CaseProof가 더 빠르고 안전한가? 과제 수행시간, 오류 탐지율, 잘못된 승인 시도, 유지비를 동일한 환경에서 측정한다. 불리한 결과가 나오면 제품 포지셔닝을 축소할 수 있다.

## 현재 확인된 것과 미확인

- 확인: 기존 오픈소스가 범용 tracing/eval/experiment 기능을 제공한다는 점(각 공식 문서).
- 확인: v5 합성 범위에서 권한 분리·시점 규칙을 재현 테스트할 수 있다는 점(직접 코드 실행).
- 미확인: 실제 보험사 내부 업무 절차와 전체 약관 적용 규칙 적합성.
- 미확인: CaseProof가 기존 제품보다 비용·정확도·조치시간에서 우수한지.
- 미확인: 금융사 AI·DX 채용 평가자가 이 구현물을 몇 점으로 평가할지.
