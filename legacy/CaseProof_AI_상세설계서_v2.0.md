# CaseProof AI — 상세 제품·기술·검증 설계서 v2.0

> 작성 기준일: 2026-10-28 · 단계: **설계 및 참조 구현** · 목표: 금융권 AI·데이터·DX·IT서비스기획·SW개발 포트폴리오  
> 2026년 10월 28일 현재: 금융회사 실제 시스템과 연동하지 않았고, 모델 품질·법적 적합성·현업 구매 의향을 실증하지 않았다. 모든 계약·고객·업무규정은 합성 예시이다.

## 0. 이 문서의 정본 및 읽는 순서

- **제품명:** CaseProof AI (가칭). 기존 v1.0을 대체하는 개발 명세 정본은 본 문서다.
- **한 문장 제안:** 보험사 AI의 답변이 *해당 계약에 적용되는 약관·유효시점·특약*과 일치하는지 검증하고, 문서·모델 변경에 따른 회귀를 배포 전에 탐지하는 근거 기반 품질 게이트.
- **완전 제외:** 보험금 지급 자동 확정, 실고객 식별정보 수집, 금융규제 준수 인증, 법률 자문, 보험사 내부 시스템 무단 연결, 범용 에이전트 플랫폼/실시간 챗봇을 새로 만드는 것.
- **출시 목표:** 외부 AI/규칙형 답변을 검증하고 판정 근거를 제공하는 *연구·시연용 제품*을 공개 배포. 대기업 금융 AI 업무 과제에 맞춘 구현·평가 증거를 남긴다.
- **명세 우선순위:** `security.md`의 차단 규칙 > API·스키마 계약 > 명세서 FR/NFR > UI 디자인 > AI 구현 제안. 다를 때는 결정 기록(ADR)을 작성하고 테스트 후 수정.
- **산출물 구조:** `contracts/`는 시스템 계약, `examples/`는 합성 규정·사례, `tests/`는 참조 시험, `docs/`는 구현 지시문과 발표 스크립트. 모든 예시는 법적·보험사 실제 규정과 무관하다.

## 1. 조사 기반 문제정의 및 신뢰도

### 1.1 확인된 외부 사실

| ID | 외부 근거와 날짜 | 사실 | CaseProof 적용 | 근거 수준 |
|---|---|---|---|---|
| E01 | 금융위원회 금융 AI 가이드라인, 2026-06-18 발표 / 06-22 시행 | 거버넌스·합법성·보조수단성·신뢰성·금융안정성·신의성실·보안성 7대 원칙. 임직원의 최종 책임 강조 | 최종 승인자, 불확실한 경우 기본 차단, 증적·보안 설계 | A (공식) |
| E02 | 금융위원회, 2026-04-15 | 일부 생성형 AI 모델 변경과 관련한 혁신금융서비스 절차 간소화 발표 | 모델 변경 전후 회귀 리포트라는 제품 가설의 배경 (모든 변경이 자동 허용되는 것은 아님) | A |
| E03 | 금융보안원, 2026-08-12 | 금융 특화 AI 안전성·신뢰성 평가 프레임워크 개발, 하반기 시범 검증·2027년 평가 계획 | 품질·보안 시험 항목을 체계화 | A |
| E04 | 국가법령정보센터: 보험업감독업무시행세칙, 2026-09-10 시행본 및 과거 부칙 | 표준약관과 개정 이력, 특정 개정내용의 계약 적용례가 존재 | **효력일과 적용례를 단순 최신 문서 검색으로 대체할 수 없다** | A |
| E05 | KB손해보험 AI·데이터 신입 공고, 2026-10-23~11-01 | 업무 개선, DT 추진, IT서비스 기획, 데이터 기반 의사결정; 프로젝트 경험 우대 | 포트폴리오의 기획·측정·개발·리스크 근거 | B (공고) |
| E06 | 전자신문, 2026-09-11 | KB손해보험은 6개 AI 에이전트에 역할·권한·수행 이력을 관리하고 성과평가 계획 발표 | 검증 운영자의 실제 업무 가설 | C (보도) |
| E07 | Phoenix 공식 문서 | 추적·평가·데이터셋·실험·결정론적/LLM 평가 가능 | 자체 범용 관측 플랫폼 중복 구현 금지 | B (벤더) |
| E08 | Langfuse 공식 문서 | 평가, 고정 데이터셋, 실험, CI 내 회귀 차단 워크플로 지원 | '회귀 테스트 자체'는 차별 기능이 아님 | B |
| E09 | Ragas 공식 문서 | faithfulness, context precision 등 RAG 공통 지표 지원 | 공통 품질 기준선 B1 | B |
| E10 | OWASP 2025 LLM Top 10, NIST AI RMF GenAI Profile | 프롬프트 인젝션·정보노출·출력 검증·위험측정의 필요성 | 위협모델 및 통제 항목 | A/B |

근거 링크는 부록 A 참조. **아직 확인되지 않은 것**: 실제 보험사의 구매 의향, 규정 개정 검증 오류의 빈도, 기존 내부 솔루션의 기능 수준, 심사자가 포트폴리오에 부여할 점수. 매출·시간 절약·모델 개선 수치를 만들어 쓰지 않는다.

### 1.2 차별화와 비차별화 경계

- **비차별화(재사용):** LLM 추적, 일반적인 hallucination 검출, dataset experiment, agent orchestration, prompt registry, 토큰 사용량 차트.
- **핵심 차별화 가설 H1:** `contract_date/event_date/claim_date`와 '어떤 날짜를 적용 기준으로 삼는가'라는 규칙까지 결합해 *잘못된 약관 버전* 답변을 판별한다.
- **핵심 차별화 가설 H2:** 변경된 조항과 영향을 받는 계약/질문을 찾아내고, 변경 전후 판정을 **같은 골드셋**으로 비교해 담당자가 승인 가능성을 결정한다.
- **핵심 차별화 가설 H3:** 결과별 이유코드·근거 조항·원본 해시·승인 기록을 묶어 재현 가능한 증거 패키지를 만든다.
- **반증 조건:** Phoenix/Langfuse에 설정만으로 동일 업무 정확도·감사 추적을 구현할 수 있거나 B1 대비 B2의 품질 우위가 없으면 범용 제품 우위를 주장하지 않는다. 그 경우 '보험 업무 룰 모델링 실험' 포트폴리오로 전환.

## 2. 사용자·업무·제품 범위

### 2.1 사용자 4종과 권한 역할

| 페르소나 | 업무 목표 | 가장 필요한 화면 | 성공 신호 |
|---|---|---|---|
| 민원 담당자(REVIEWER) | 초안 답변의 오류를 빠르게 이해·수정 | 검증 상세, 검토 큐 | 주장마다 인용 근거가 명확함 |
| AI 운영 담당자(OPERATOR) | 모델/프롬프트/약관 버전 변경 시 안전 확인 | 규정 버전, 회귀 비교, 게이트 | 치명 회귀를 배포 전에 식별 |
| 리스크·감사(AUDITOR) | 누가 무엇을 승인했는지 추적 | 감사 보고서 | 해시와 근거가 일치하고 변조 탐지 가능 |
| 시스템 관리자(ADMIN) | 접근권한·비용·정책 관리 | 설정, 사용자 | 역할 분리·권한 시험 통과 |

`VIEWER`는 읽기 전용 데모 역할이며 승인·업로드 불가. 운영 기능 시뮬레이션뿐이고 금융사 업무 승인 권한을 부여하지 않는다.

### 2.2 핵심 업무 시나리오 — 수정 전후

1. 가상 손해보험 상품 `DEMO-HOME-A`의 규정 2개 버전(v1/v2)을 등록한다. 각 버전은 *적용 기준 날짜와 유효기간*, 조항, 예외, 출처 해시를 갖는다.
2. 가상 계약 `C-0007`이 v1 적용 기간에 체결되었다. 문의 접수일은 v2 시행 이후다.
3. 외부 AI의 답변 초안은 v2 기준의 '20일'을 제시한다. v1 규정에 정한 답 '30일'과 상충한다. **숫자는 합성 데이터**다.
4. CaseProof의 `PolicyResolver`는 해당 규정에서 선택한 `CONTRACT_START` 기준으로 v1을 선택한다.
5. `ClaimExtractor`는 답변에서 `claim=접수기한(20 DAY)`을 구조화한다. `RuleValidator`가 v1의 `30 DAY` 규칙과 충돌하는지 확인한다.
6. **사전 정책상 결정론적 충돌은 LLM 판정으로 PASS에 뒤집을 수 없다.** `BLOCK(VERSION_MISMATCH)`로 출력한다.
7. 담당자는 오류근거와 원문 비교를 보고 초안을 수정, 다시 검증한 뒤 승인 여부를 결정한다.
8. 새 정책/모델 릴리스 전, 고정된 사례로 B1과 B2를 재실행하여 기준선 대비 악화된 건을 보여준다.

### 2.3 필수/후속/제외 범위

| 등급 | 범위 | 조건 |
|---|---|---|
| P0 | 합성 약관 2버전, 12개 핵심 사례, 규정선택/주장검증 API, 한 화면 | 가장 먼저 작동해야 함 |
| P1 | 100건 이상의 라벨 데이터, 3개 비교 기준, 회귀 비교·메트릭 | P0 테스트 전부 통과 후 |
| P2 | 역할·승인·감사 export, UX 6개 화면, 배포 | P1 베이스라인 재현성 통과 후 |
| P3 | 240건 블라인드 평가, 외부 reviewer 검수, 문서 파싱 개선 | 검증 데이터 충분할 때 |
| 제외 | 보험금 지급 결론/자동 발송/실기관 MCP/Graph DB/K8s/실제 고객 PDF | 연구·시연 프로젝트 범위 밖 |

## 3. 판정의 가장 중요한 전제: 시간과 규정은 다르다

### 3.1 시점 모델 (bitemporal)

- **valid time:** 규정이 적용되는 업무상 시점 (`valid_from` 포함 / `valid_to` 제외), 예: 2026-01-01 ≤ t < 2026-06-01.
- **recorded time:** CaseProof가 그 규정을 시스템에 알게 된 시점 (`recorded_at`) 및 정정 이력. 동일한 과거 시점 규정이 사후 업로드·수정되는 경우 대비.
- **basis_date:** 해당 조항의 *명시적* 적용기준(`CONTRACT_START`, `EVENT_DATE`, `CLAIM_RECEIVED`, `QUESTION_DATE`)을 따라 계산한 날짜. 상품·조항마다 다를 수 있으므로 하나의 질문 날짜를 모든 조항에 적용하지 않는다.
- **applicability rule:** 문서/규정에 선언된 JSON 기반 규칙. 근거가 없는 '최신 약관 우선' 로직 금지.
- **우선순위:** 동일 업무에 특약이 일반약관보다 우선하는지 여부는 선언된 `priority`로만 처리. 같은 우선순위의 서로 다른 정답은 `INCONCLUSIVE(POLICY_CONFLICT)`.
- **명시적 버전 입력:** 사용자가 지정한 `policy_version_id`가 계산된 적용 버전과 충돌하면 무시하지 않고 `INCONCLUSIVE(VERSION_INPUT_CONFLICT)`.
- **문서 입력 결손:** 기준일·상품·특약 범위 등이 빠져 판단할 수 없으면 `INCONCLUSIVE`와 `required_fields[]` 반환. 자동으로 오늘 날짜 대입 금지.

### 3.2 resolver 결정 테이블

| 조건 | 기대 처리 | 이유 코드 |
|---|---|---|
| 상품ID 없음 | INCONCLUSIVE | MISSING_PRODUCT |
| 적용 기준일 없음 | INCONCLUSIVE | MISSING_BASIS_DATE |
| 유효기간에 정확히 1개 버전 매칭 | 선택 성공 | POLICY_RESOLVED |
| 기간 경계 `t = valid_to` | 이전 버전 **제외** | HALF_OPEN_BOUNDARY |
| 여러 동순위 유효 버전이 다른 결론 | INCONCLUSIVE | POLICY_CONFLICT |
| 요구 특약 없거나 적용 조건 불명 | INCONCLUSIVE | MISSING_RIDER_CONTEXT |
| 입력된 고정 버전과 계산된 버전 불일치 | INCONCLUSIVE | VERSION_INPUT_CONFLICT |
| 규정 변경 PDF가 일부 파싱 실패 | INCONCLUSIVE | PARSE_UNCERTAIN |
| 과거 상태 재현 시 기록된 날짜 이전 문서만 참조 | 포함 또는 미포함 | AS_OF_RECORDED_TIME |

### 3.3 정책 DSL (리스크와 구현 절충)

DSL은 임의 Python/JS 스크립트를 실행하지 않는다. 허용 필드는 `rule_key, product_id, date_basis, valid_from, valid_to, priority, riders, facts, exceptions`로 화이트리스트. `facts`의 값은 단위 포함 타입값 (`{value:30, unit:'DAY'}`)으로 저장. v1에서는 중첩 예외식·임의 관계식은 금지하고 문자열 동일·숫자 비교·AND 조건만 지원. 복잡하면 자동 PASS 대신 REVIEW/INCONCLUSIVE.

## 4. 도메인 동작 계약: 모듈과 인터페이스

### 4.1 처리 파이프라인

```
웹 입력/시연 사례
  -> CaseValidator (JSON schema, idempotency key, PII guard)
  -> PolicyResolver (상품+특약+적용기준일+효력일)
  -> ClaimExtractor (타입화 주장 추출: mock 또는 LLM)
  -> EvidenceRetriever (해당 규정 버전만 필터, clause locator)
  -> RuleValidator (날짜/숫자/예외/출처 ID 결정론적 검사)
  -> OptionalJudge (근거의 의미상 지지 여부 보조)
  -> VerdictAggregator (결정론적 차단 최우선)
  -> EvidenceRecorder (span, hash, 설정, 실행 이력)
  -> Reviewer UI (수정 -> 재검증 -> 승인)
```

데모 핵심은 **LLM API 없이도** 규정선택·VERSION_MISMATCH 테스트가 완성되어야 한다. LLM은 구조화가 어려운 한국어 자유서술 답변의 주장 추출에만 우선 사용하고, 위험 판단을 단독 맡기지 않는다.

### 4.2 타입·판정 결과

- `PolicyResolution`: `RESOLVED | INCONCLUSIVE`; 선택된 `policy_version_id[]`, 각 규칙의 선택근거, `required_fields`, reason codes.
- `ClaimVerdict`: `SUPPORTED | CONTRADICTED | UNSUPPORTED | UNKNOWN`, severity `CRITICAL | MAJOR | MINOR | INFO`, source evidence span, reason codes.
- `EvaluationVerdict`: `PASS | REVIEW | BLOCK | INCONCLUSIVE`. `BLOCK`은 결정론적 고위험 충돌이나 금지행위, `INCONCLUSIVE`는 필요한 데이터·파싱·적용규정이 불명확, `REVIEW`는 해석 불확실·중간위험, `PASS`는 현재 검증 범위의 필수 검사 통과.
- **판정 우선순위:** `BLOCK > INCONCLUSIVE > REVIEW > PASS`. BLOCK과 INCONCLUSIVE가 동시 존재하면 BLOCK을 표시하되 보조 원인코드 모두 보존한다.
- `UNKNOWN`/파싱 오류를 `SUPPORTED`로 취급하지 않음. 유효한 검색 출처가 없어도 답이 그럴듯하다고 PASS 금지.

### 4.3 상태 머신을 세 가지로 분리

1. **실행 상태(run_status):** `QUEUED → RUNNING → COMPLETED | FAILED | CANCELLED`. 재시도는 새 `attempt_id`에 연결. 실패는 평가 PASS를 뜻하지 않음.
2. **품질 판정(verdict):** COMPLETED 실행에서만 `PASS/REVIEW/BLOCK/INCONCLUSIVE` 중 하나. FAILED일 때 UI는 `처리 실패` 표시, 기본 배포 차단.
3. **승인 상태(review_status):** `NOT_REQUESTED → PENDING → APPROVED | REJECTED | CHANGES_REQUESTED`; `CHANGES_REQUESTED`는 수정 후 새로운 평가 실행을 생성. 과거 증적을 덮어쓰지 않음.
4. **릴리스 게이트(release_status):** `DRAFT → EVALUATING → BLOCKED | READY_FOR_REVIEW → APPROVED_FOR_DEMO`. 결과가 PASS여도 승인 기록 없으면 자동 릴리스 불가.

**상태 불변식:** ① `verdict != PASS`인 실행을 운영 승인의 근거로 직접 사용할 수 없다. ② BLOCK은 동일 실행에서 임의 수동 승인 불가; 수정 후 새 평가 실행이 필요. ③ 본인이 만든 high-risk 변경을 본인이 승인하지 못하게 2인 승인 정책을 선택적으로 켤 수 있다(개인 데모는 별도 가상 계정 두 개). ④ 모든 전이는 서버측 권한검사, 기록, 원자적 DB transaction.

### 4.4 오류코드 카탈로그

| 코드 | 트리거 | severity | 기본 판정 | 담당자 조치 |
|---|---|---|---|---|
| VERSION_MISMATCH | 효력기간 밖 문서/규정에서 추출한 값 | CRITICAL | BLOCK | 올바른 버전 근거로 수정 |
| FACT_CONTRADICTION | 적용 규정의 수치·조건과 상충 | CRITICAL | BLOCK | 문장 수정/근거 재확인 |
| UNSUPPORTED_CITATION | 조항·페이지 인용 존재하지 않음 | MAJOR | REVIEW | 근거 재검색 |
| MISSING_EXCEPTION | 예외 조건 누락 | MAJOR/CRITICAL | REVIEW/BLOCK | 필수 예외 명시 |
| POLICY_CONFLICT | 둘 이상의 유효 규정 충돌 | CRITICAL | INCONCLUSIVE | 규정 관리자 확인 |
| MISSING_BASIS_DATE | 적용 기준일 부족 | MAJOR | INCONCLUSIVE | 계약/사고/청구일 입력 |
| DOCUMENT_PARSE_ERROR | 문서 조항 추출 오류 | MAJOR | INCONCLUSIVE | 문서 재확인 |
| PII_LEAKAGE | 개인정보 또는 테스트용 금지 토큰 노출 | CRITICAL | BLOCK | 원문 제거/비식별화 |
| PROMPT_INJECTION | 문서가 실행 정책·권한 변경을 지시 | CRITICAL | BLOCK | 해당 문서 격리 |
| PROVIDER_UNAVAILABLE | LLM API 실패, 반복 제한 도달 | MAJOR | INCONCLUSIVE/FAILED | 재시도 또는 MOCK 모드 |
| EVIDENCE_MISSING | 핵심 주장에 확인 가능한 원문 근거 없음 | MAJOR | REVIEW | 근거 보완 |

본 카탈로그의 트리거는 **프로젝트 정의**이며 보험사·법적 표준 분류가 아니다.

## 5. UI: 화면·상태·클릭 동작을 구체적으로 정의

### 5.1 정보구조 및 공통 디자인

- PC 1440px 우선 반응형(1280/1024/768 대응), 콘텐츠 `max-width: 1440px`, 좌측 내비 232px, 상단 도구막대 64px.
- 정보 밀도는 B2B 제품 수준. 배경 중립 회색, 상태 색상 외에 텍스트·아이콘·이유 코드를 항상 제공. 색상만으로 상태 표시 금지.
- 타이포: 한국어 가독성 최우선; 긴 약관은 14px 본문/1.55 line-height, 데이터 라벨은 12–13px, 테이블 정렬.
- 공통 상단: `DEMO·합성 데이터` 표시, 데이터셋 버전, 실행환경 `MOCK | API`, 계정 역할, 사용자 안내.
- loading/error/empty/permission-denied/partial-data를 모든 화면에서 직접 설계. 버튼에 실제 액션이 없으면 노출 금지.
- API 비용 유발 작업은 확인 모달 + 예상 건수/예산 표시. 작업 취소는 서버 `CANCEL_REQUESTED` 후 완료 보장 여부 명시.

### 5.2 S1 개요 `/overview`

상단 KPI 4개: 실행 건수, `BLOCK+INCONCLUSIVE` 비중(분모 명시), 버전 충돌 건수, 최신 회귀 배치 상태. 중간 시간별 추세와 위험 상위 5개 원인코드; 아래 최신 검토 목록. KPI 클릭→해당 필터된 상세 목록. 빈 상태는 샘플 데이터 생성 액션. 실패 시 통계를 0으로 표시하지 않고 ‘집계 실패’ 명시.

### 5.3 S2 검증 상세 `/evaluations/:id`

3열 레이아웃: **좌 30%** 입력 문의·AI 초안·상품·날짜, **중 30%** claim 카드/검증 verdict/이유코드, **우 40%** 근거 조항 diff/원본 PDF 페이지·버전·시점. claim을 클릭하면 관련 evidence를 스크롤·형광 강조한다. `BLOCK`의 경우 수정 버튼→새 실행 ID 생성; 기존 결과는 읽기 전용. `PASS`라도 ‘법률 검증 아님’ 표기. 증거가 없으면 근거 패널을 비우지 말고 `EVIDENCE_MISSING` 이유 표시.

### 5.4 S3 규정 라이브러리 `/policies`

상품별 v1/v2, 원문 SHA256 앞 12자리, 업로드일, 효력일, 정정일, 상태(초안/검토완료/폐기), 파싱 품질. 새 버전 등록 시 valid interval 겹침 경고, 적용 기준 날짜 변경 확인 필수. 변경조항별 ADD/MODIFY/DELETE와 동일성(조항번호 재배치) 검토 기능. diff 자체는 *법적 적용 확정*을 하지 않음. 정정본은 별도 버전으로 기록한다.

### 5.5 S4 회귀 실험 `/experiments/:batchId`

상단 Baseline B1 / Candidate B2, 동일 데이터셋 SHA, 모델·prompt·문서 버전/토큰 예산 표시. 지표는 recall/precision/FPR/FNR, 95% Wilson CI, false blocks, paired disagreed cases. 좌측 filters(`changed`, `critical`, `regressed`, `improved`), 우측 변경 케이스 비교. 샘플수가 적으면 신뢰구간 경고. 실제 실행이 없으면 빈 상태와 '실험 전' 안내, 임의 차트 금지.

### 5.6 S5 승인 대기함 `/reviews`

위험도→접수시간 순. 기본적으로 `BLOCK/INCONCLUSIVE`는 승인 버튼 비활성화 및 명확한 사유 표시. `REVIEW`는 수정요청만 가능하도록 v1 정책 적용(후속엔 예외승인 ADR 필요). `PASS`는 승인 가능하나 검토 사유·규정버전 확인 체크 필수. 동시 승인 충돌은 `409 REVIEW_VERSION_CONFLICT`로 처리. 감사자는 버튼 자체 숨김 + 서버 403.

### 5.7 S6 감사 보고서 `/audits/:id`

한 건의 input→선택 문서→주장→판정→수정→재판정→승인 lineage 그래프. JSON export는 ① manifest, ② hashed records, ③ evidence excerpt, ④ reviewer attestation의 참조 묶음. 인증서/전자서명으로 오인되는 표현 금지. SHA256은 무결성 **확인용**이며 자체적으로 변경 불가능한 저장소를 보장하지 않는다.

### 5.8 화면 구현 완료 체크리스트

각 페이지: 디자인 규격, 로딩/실패/권한없음/데이터없음, 키보드 포커스, 테이블 검색·정렬, 1024px 이하 재배치, API 연동, Playwright happy/edge 테스트를 모두 만족해야 '완료'로 표시.

## 6. 기술 스택과 선택 배경 (1인 개발 현실성 우선)

| 계층 | v2 확정 | 선택 이유 | 유보/제외 |
|---|---|---|---|
| Frontend | React + TypeScript + Vite + TanStack Query + Tailwind | 안정적 화면/데이터 캐시·독립 배포 | Next.js SSR 필요 없음 |
| UI | shadcn/ui 구성요소, Radix 접근성 기본, 자체 토큰 | 일관성·빠른 구현·편집 가능 | 시각 효과 과잉 금지 |
| Backend | Python 3.12+ / FastAPI / Pydantic v2 / SQLAlchemy 2 / Alembic | AI 및 정형 API 구현 용이 | 마이크로서비스 분할 금지 |
| DB | PostgreSQL 16+, SQLAlchemy / pgvector P2부터 선택 | 날짜 필터·복합 제약·버전 관리에 유리 | 초기엔 벡터 인덱스 필요 없음 |
| Background | 1차 inline→P1에서 Redis + RQ | P0 단순성, 회귀 작업은 비동기 | Kafka 불필요 |
| Document | 초기 JSON+텍스트; PDF는 검수 후 Docling 파서 | PDF가 핵심 검증 실패원인 되지 않도록 분리 | OCR GPU 필수 아님 |
| LLM | Provider adapter + JSON Schema 출력 + deterministic mock | 모델교체/비용 예산 관리 | 직접 학습/파인튜닝 제외 |
| Tracing | OpenTelemetry + Phoenix (P1) | 기능 중복 제거 | Phoenix와 Langfuse 동시 구축 안 함 |
| Tests | pytest / hypothesis / Playwright / Ruff / mypy | 규칙 로직 회귀·UI 품질 증거 | 높은 e2e 비중보다 단위 테스트 |
| Deploy | Docker Compose + GitHub Actions, 합성데모만 공개 | 재현 가능한 실행 | Kubernetes 필요 없음 |

기술 버전은 코드 설치 시 안정 릴리스를 확인하고 `uv.lock` / `package-lock.json` 고정. 본 문서의 버전은 제품에 필요한 최소 계열이므로 특정 최신 패치가 검증되었다는 뜻은 아니다.

## 7. 데이터 스키마: 관계·불변식·인덱스

### 7.1 주요 테이블

- `organization(id, name, demo_only)` — 최초 P0는 하나의 조직. org_id는 미래 확장 대비, 아직 다중테넌트 보안이 검증됐다고 주장하지 않음.
- `policy_document(id, org_id, product_id, title, source_url, content_sha256, mime, storage_key, ingestion_status, recorded_at)` — 파일 원본 식별과 파서 상태.
- `policy_version(id, document_id, version_tag, valid_from, valid_to, recorded_at, supersedes_id, reviewer_status, parse_quality)` — 반개구간 (`valid_to IS NULL` = 무기한), `valid_from < valid_to` DB CHECK.
- `policy_rule(id, policy_version_id, rule_key, date_basis, priority, value_json, exceptions_json, riders_json, text_excerpt, clause_ref, page, content_hash)` — 동일 버전 내 `rule_key+priority` 유일성 기본, 조건부 규칙은 별도 rule_id.
- `case_record(id, org_id, product_id, contract_start, event_date, claim_received, question_date, rider_codes_json, sanitized_question, expected_policy_id, dataset_split)` — 입력 검증.
- `answer_candidate(id, case_id, text, source_model_ref, prompt_version, generated_at)` — 외부 AI 초안은 명확히 별도 보관.
- `evaluation_run(id, case_id, answer_id, policy_version_id, run_status, verdict, policy_resolution_json, model_config_sha, dataset_sha, source_snapshot_sha, started_at, finished_at, cost_tokens, error_json)` — **상태 3가지 분리**.
- `atomic_claim(id, run_id, claim_key, raw_span_start, raw_span_end, normalized_value_json, verdict, severity, reason_codes_json)` — sentence-level 분할이 아니라 의미 단위.
- `evidence_link(id, claim_id, rule_id, source_sha256, page, char_start, char_end, role)` — 원문을 다시 열 수 있는 정확한 locator.
- `review_action(id, run_id, reviewer_id, prior_state, new_state, reason, created_at, optimistic_version)` — 수정/승인 이력 immutable append-only.
- `replay_batch(id, dataset_sha, baseline_config_sha, candidate_config_sha, run_status, threshold_config_sha, created_at)` / `replay_case_result(id, batch_id, case_id, baseline_run_id, candidate_run_id, change_type)`.
- `audit_event(id, aggregate_type, aggregate_id, actor_role, action, prev_hash, event_hash, happened_at, immutable_payload_json)` — 체인형 해시만으로 법적 불변성이 증명되지는 않음.

### 7.2 필수 제약조건

- 모든 PK는 UUID, 타임스탬프 UTC `timestamptz`, 날짜는 `DATE`로 명시. UI만 KST로 변환하며 날짜 시차로 하루 밀림 금지.
- 규정 유효기간은 `[valid_from, valid_to)` 반개구간. 같은 상품·rule_key·조건·우선순위의 겹침은 입력 시 경고+검수 필요, 자동 최신 선택 금지.
- 외래키 org_id 일치 검사 및 row-level authorization은 서비스 공통 helper로; P2 다중조직 시험 전 공개 데모는 단일 조직만 제공.
- `evaluation_run` 결과 변경 금지. 재평가 시 새 행 생성, `parent_run_id`로 lineage 연결.
- 감사 `event_hash = SHA256(canonical_JSON(event_payload) + prev_hash)`. external anchor나 전자서명 없는 해시 체인은 DB 관리자 변조를 막는다고 주장하지 않음.
- `source_sha256`, `schema_version`, `resolver_version`, `ruleset_version`, `model_provider+model_id`는 매 실행 필수 수집(미사용 모델은 `MOCK`).
- 원문 전체 텍스트를 LLM trace/외부 텔레메트리에 기본 전달하지 않음.

### 7.3 구체적인 인덱스

`(product_id, valid_from, valid_to)`, `(policy_version_id, rule_key)`, `(case_id, started_at DESC)`, `(run_id, severity)`, `(replay_batch_id, change_type)`, `(org_id, happened_at DESC)`; 예외 조건과 특약은 초기 규모에 맞춰 JSONB로 보관하되 조회 병목을 측정한 뒤 정규화.

## 8. API 계약: 버전, 요청/응답, 실패까지 규정

### 8.1 공통

- Prefix `/api/v1`. 모든 POST는 `Idempotency-Key` UUID(업로드/평가/배치/승인)에 대해 같은 키·같은 본문 재요청이면 동일 결과, 같은 키·다른 본문은 409.
- 오류 응답: `{ "error": { "code": string, "message": string, "retryable": bool, "details": {}, "trace_id": string } }`. 일반 사용자에겐 서버 내부 경로·토큰 비노출.
- ISO 8601 UTC 시각, 입력 날짜 `YYYY-MM-DD`. 커서 페이지네이션 `limit <= 100`, `next_cursor`.
- 작업 시작은 HTTP 202 + `{job_id, status:"QUEUED", status_url}`; 작업 상세 GET. P0 동기 평가 API는 200 가능하나 P1에서 202로 전환하는 ADR 필요.
- 모든 엔드포인트에 역할·소유조직 권한 체크. URL ID만 변경하여 타조직 조회 시 404 또는 권한 정책에 따라 403(정책 통일).

### 8.2 HTTP 엔드포인트 및 수락조건

| Method | Endpoint | Body 핵심 | 성공 | 예외/권한 |
|---|---|---|---|---|
| GET | `/health/ready` | 없음 | 200 의존성 상태 | 장애 503 |
| POST | `/policies` | product, version, validity, rule JSON | 201/202 | 검수 없는 입력 422 |
| GET | `/policies/{id}` | 없음 | 200 immutable revision | 404 |
| POST | `/policies/resolve` | product_id, dates, rider_codes, record_as_of | 200 RESOLVED/INCONCLUSIVE | 허용하지 않는 date_basis 422 |
| POST | `/cases` | sanitized_question, product, dates, candidate_answer | 201 | PII guard 422 |
| POST | `/evaluations` | case_id, answer_id, config_id | 202 + job_id | 중복키 409, 비용 429 |
| GET | `/evaluations/{id}` | 없음 | 200 full verdict+evidence | 404 |
| POST | `/replays` | frozen_dataset_sha, baseline, candidate | 202 + batch_id | 예상예산 초과 422 |
| GET | `/replays/{id}` | 없음 | 200 paired metrics+CI | 404 |
| POST | `/reviews/{run_id}` | action, reason, version | 200 appended review event | 권한 403/충돌 409 |
| GET | `/audits/{run_id}/export` | format=json | 200 downloadable archive | 409 incomplete lineage |

### 8.3 필수 JSON 예시

```json
{
  "product_id": "DEMO-HOME-A",
  "contract_start": "2026-04-10",
  "question_date": "2026-08-01",
  "claim_received": null,
  "rider_codes": [],
  "candidate_answer": "이 가상 상품의 접수 기한은 20일입니다.",
  "source_model_ref": "MOCK"
}
```

```json
{
  "run_id": "DEMO-RUN-0007",
  "run_status": "COMPLETED",
  "verdict": "BLOCK",
  "reason_codes": ["VERSION_MISMATCH", "FACT_CONTRADICTION"],
  "resolved_policy": {"version_tag":"v1", "date_basis":"CONTRACT_START", "valid_from":"2026-01-01", "valid_to":"2026-06-01"},
  "claims": [{"claim_key":"claim_deadline", "value":{"value":20,"unit":"DAY"}, "verdict":"CONTRADICTED", "severity":"CRITICAL", "evidence_rule_id":"DEMO-HOME-A:v1:CLAIM_DEADLINE"}],
  "review_status": "NOT_REQUESTED",
  "trace_id": "DEMO-TRACE-0007"
}
```

**기술적 주의:** `VERSION_MISMATCH`는 단순히 정답 값이 다른 경우 자동으로 붙이지 않는다. 답변이 v2에서만 확인되는 값/출처를 인용했다는 증거가 있거나 지정한 버전 참조가 분명할 때 붙인다. 그렇지 않으면 `FACT_CONTRADICTION`만 사용해 이유코드 오남용을 방지한다.

## 9. 문서 수집·검색·주장 분석

### 9.1 문서 신뢰 파이프라인

P0에서 검수된 JSON clause set만 사용 → P1에서 소규모 공개 PDF/텍스트 파싱 → P2에서 PDF OCR 필요조건 검토. 수집 시 출처/이용조건, 원본 해시, 파일 크기, MIME/magic, 파서 버전, 페이지 수, 누락 범위 기록. 테이블 파손 또는 조항 식별 실패 시 문서 `QUARANTINED`, 자동 사용 금지.

### 9.2 검색과 버전

1. `PolicyResolver`로 해당 상품·계약·특약 및 기준일에 유효한 **문서 버전**을 먼저 특정.
2. 해당 문서 버전의 rule_key와 조항 텍스트에 SQL FTS 검색 수행.
3. 다수 candidate 문서 내에서만 임베딩 유사도(필요 시)를 적용; FTS exact 조항 번호 매칭 우선.
4. 검색 후보가 없으면 `EVIDENCE_MISSING`, 임베딩 점수가 높다는 이유로 다른 유효기간의 문서를 선택 금지.
5. source locator의 문서 해시와 글자 범위를 확정한 후 evidence link 작성. 검색 텍스트는 프롬프트 지시가 아닌 **검증 대상 데이터**로 주입.

### 9.3 한국어 주장 구조화

`AtomicClaim {claim_key, subject, predicate, normalized_value, unit, qualifier, exception, span_start, span_end, cited_version, cited_clause}`. 하나의 문장에 '20일 이내'와 '예외 있음'이 동시에 있으면 주장 2개로 분리. 추출 실패 시 미검증 주장 때문에 PASS 금지. LLM JSON 형식 유효성 재검증, 1회 자동 교정 재시도, 실패 시 INCONCLUSIVE.

### 9.4 LLM evaluator 의존성 제한

`LLM judge`는 수치의 진위를 최종 판정하지 않고, 출처 조항과 자연어 주장 간의 의미상 지지 여부만 평가한다. 출력 enum은 `SUPPORTS/REFUTES/INSUFFICIENT`; 필수 근거 span 외 자유 설명은 참고용. 온도 낮음/동일 모델로 반복하고 결과 분산 기록, 원본/프롬프트/모델 버전 보존. 한국어 형태소·부정문·예외구문에 대해 사람이 검수한 사례로 보정한다.

## 10. 실험 설계 및 통계 — 과장 없는 포트폴리오

### 10.1 데이터셋 목표 240건(현재 본격 수집/전문가 검수: 미완료)

| 분류 | 개발 | 검증 | 블라인드 | 합계 |
|---|---:|---:|---:|---:|
| 정상 안내 | 34 | 8 | 8 | 50 |
| 규정 버전/시점 오류 | 34 | 8 | 8 | 50 |
| 조건·예외 누락 | 26 | 7 | 7 | 40 |
| 근거 위조·없음 | 23 | 6 | 6 | 35 |
| 간접 prompt injection | 17 | 4 | 4 | 25 |
| 정보 노출/PII | 13 | 3 | 4 | 20 |
| 다른 조직·권한 우회 | 13 | 4 | 3 | 20 |
| **합계** | **160** | **40** | **40** | **240** |

같은 계약·약관 템플릿에서 생성한 문장 변형은 반드시 같은 split으로 배정하여 누출을 방지한다. 전문가 독립 검수 전에는 `SYNTHETIC_AUTHOR_LABEL`로만 표기. 최소 20%를 사람이 중복 라벨링하여 의견 차이를 기록(혼자라면 별도 날짜/블라인드로 자기 재검수하고 한계를 명시). 정답 판정의 버전/조항 ID는 문제 생성과 분리해 만든다.

### 10.2 동일 예산의 비교군

- **B0:** 단순 키워드/정규식 검사(적용 문서 유효일 미반영).
- **B1:** 검색+일반 faithfulness RAG judge(Phoenix/Ragas 사용), 같은 입력문서 저장소이지만 시점별 엄격 필터를 적용하지 않은 기준선.
- **B2:** CaseProof 적용 규정 선택 + 결정론적 검사 + 동일 예산 LLM judge.
- **공정성 보완:** B1도 사용자에게 제공 가능한 최신 문서와 동일한 모델·토큰·테스트 케이스를 사용; B2만 정답 규정ID를 별도 특권으로 받지 않음. B1에게도 계약일 정보를 포함한 질문을 제공한다. B2는 *선언된 룰을 해석하는 모델*이라는 추가 개발량을 차별점으로 공개.
- **케이스 페어링:** 각 case_id에서 B0/B1/B2 판정을 비교. 모델 생성과 평가를 분리하고 고정된 candidate_answer를 평가해 평가기 자체의 효과와 생성 품질을 혼동하지 않음.

### 10.3 주요 지표와 보고

- `critical_recall = critical 오류를 BLOCK한 건 / 전체 gold critical 오류`; `false_block_rate = 정상인데 BLOCK / 전체 gold 정상`.
- `version_error_recall = 버전 오류 발견 / gold 버전 오류`; `citation_exact = 맞는 정책 버전+조항을 정확히 찾은 건 / 근거 대상 건`.
- `abstention_rate = (REVIEW + INCONCLUSIVE) / 전체 평가`; `unsafe_pass_rate = gold 오류임에도 PASS / gold 오류`.
- 배포 판단은 전체 accuracy가 아니라 critical FN, false blocks, 유형별 recall, 승인 위반 건수, p95, 입력 100건당 실측 비용.
- 이항비율은 Wilson 95% CI; 비교는 같은 사례의 discordant pair를 사용하여 bootstrap CI/필요시 McNemar 검정. 40건 blind의 작은 분모를 결과표에 노출.
- **사전 등록 실험 목표(실측 아님):** 버전 오류 recall B2-B1 +15%p 이상, 정상 오차 차단률 상승 +5%p 이하, blind critical 미탐지 0건, 자료 분리 무결성 100%. 목표 미달이면 실패로 기록.
- 각 실행은 `dataset_sha`, `policy_sha`, `prompt_sha`, `model_ref`, `code_commit`, `cost`, `timestamp`, raw confusion counts, CI, sample list를 포함한다.

### 10.4 실험 결과 표 양식

| Metric | B0 측정 | B1 측정 | B2 측정 | 단위·분모 | 판정 |
|---|---|---|---|---|---|
| 버전 오류 탐지 recall | 미측정 | 미측정 | 미측정 | TP / gold version errors | 미평가 |
| critical false negative | 미측정 | 미측정 | 미측정 | misses / gold critical | 미평가 |
| false block rate | 미측정 | 미측정 | 미측정 | FP / gold normal | 미평가 |
| 평가 100건 비용 | 미측정 | 미측정 | 미측정 | 결제화폐·실제 토큰 사용량 | 미평가 |
| p95 latency | 미측정 | 미측정 | 미측정 | wall clock / 동일 HW | 미평가 |

**절대 금지:** 사례에서 보기 좋게 숫자 만들기, 정상과 오류 분모 혼동, 실패 케이스 제거, 같은 LLM으로 정답 생성·채점 후 객관적이라고 주장, blinding 후 프롬프트 수정하면서 같은 blind 반복 사용.

## 11. 보안·프라이버시·거버넌스

### 11.1 위협모델 STRIDE 간이 버전

| 위협 | 공격 경로 | 방어 | 테스트 |
|---|---|---|---|
| Prompt injection | 규정 PDF에 '이전 지시 무시' | 문서=untrusted data, tool 없고 판정 규칙 우선 | SEC-01 |
| BOLA/IDOR | `/evaluations/{id}` 타기관 ID 열람 | 서버 org+role 검증, uniform 404 | SEC-02 |
| 정보노출 | 외부 trace에 이메일/계약번호 포함 | 합성 데이터, PII 검사·로그 redaction | SEC-03 |
| 권한 상승 | reviewer가 admin API 직접 호출 | 토큰 role 서버검사 | SEC-04 |
| 조항 위조 | 문서 내용은 변경하면서 원본 hash 재사용 | upload sha 검증/immutable revision | SEC-05 |
| 부적절 출력 | 약관 HTML 안의 스크립트 | 텍스트 렌더링/HTML sanitization/CSP | SEC-06 |
| 자원 고갈 | 평가 10만 건 반복/큰 PDF | 2MB/초기, 작업 수 제한, budget/cancel | SEC-07 |
| 감사기록 수정 | 기록 삭제/수정 | append-only, hash chain, 백업·권한 분리 | SEC-08 |

### 11.2 최소 권한·데이터정책

P0는 단일 데모 테넌트. P2부터 서버 RBAC(ADMIN/OPERATOR/REVIEWER/AUDITOR/VIEWER), 조직 격리 테스트, CSRF/CORS, rate limiting, SECRET env 관리, object storage 경로 검증. 외부 LLM 요청 시 고객 원문 전송 금지(합성 텍스트만), IP·이메일 로그 보존정책 명시. 접근 토큰/키 Git 반입 금지; `.env.example`만 저장.

### 11.3 장애 정책

LLM timeout·DB 장애·파싱 실패 시 `PASS`로 실패를 숨기지 않는다. API는 상태 `FAILED`와 이유 반환; UI는 '잠시 후 재시도'와 비용 발생 가능성 표시. 재시도 최대 2번/지수 백오프+지터, 동일 idempotency key, 중복 과금 가능성은 provider 특성에 따라 기록. 외부 의존 불안정시 규칙형 MOCK 시연은 계속 가능해야 한다.

## 12. 운영·비용·성능

- 개발과 시연은 Docker Compose API/Web/PostgreSQL 3개를 기본으로 시작, Redis/worker/Phoenix는 P1 이후 프로필로 선택.
- 예산 설정: `MAX_DAILY_LLM_SPEND`와 `MAX_TOKENS_PER_JOB`, `MAX_CONCURRENT_JOBS`, `MAX_RETRIES=2` 등. 실제 환율/모델별 단가는 실측 시점 설정 파일로 입력; 사전 비용을 사실처럼 제시하지 않는다.
- 메트릭: HTTP 5xx, DB pool, job success rate, timeouts, `verdict` 분포, per-category confusion, p50/p95, input+output tokens, provider errors, 월간 비용.
- 경보는 slack/email 실전 연동 대신 로컬 관리자 이벤트·대시보드 표시로 충분. 알림이 없다고 실서비스 보안 관제를 완성했다고 주장하지 않음.
- CI: `lint → unit → schema → integration → regression (mock) → security smoke → frontend build → e2e smoke`; 민감정보 검사와 dependency audit는 P2부터.

## 13. 수용 테스트: 구현자가 임의 판단하지 못하도록

| ID | Given | When | Then | 우선순위 |
|---|---|---|---|---|
| ACC-001 | 2026-04-10 계약, v1=30일, v2=20일, 계약일 기준 | 20일 안내 평가 | BLOCK + v1 조항 근거 | P0 |
| ACC-002 | 위와 동일 | 30일 안내 평가 | PASS(검증범위 내) | P0 |
| ACC-003 | 2026-06-01 계약(경계) | 시점별 규정선택 | v2 선택 | P0 |
| ACC-004 | 계약일 없음 | 선택 요청 | INCONCLUSIVE + missing field | P0 |
| ACC-005 | 동순위 충돌 규정 2개 | 선택 요청 | INCONCLUSIVE(POLICY_CONFLICT) | P0 |
| ACC-006 | v2 문서에 권한 상승 지시 문자열 | 검증 | 지시 무시·안전차단 | P1 |
| ACC-007 | 출처 없는 답변 수치 | 검증 | REVIEW/EVIDENCE_MISSING, PASS 금지 | P0 |
| ACC-008 | 이전 RUN에 BLOCK | 사용자가 승인 API 강제 호출 | 409/403, 감사 로그 | P2 |
| ACC-009 | R1·R2 동일 case_id | 재평가 | 새 run_id, R1 불변 | P1 |
| ACC-010 | 원문 해시 바뀜 | 기존 증거 참조 | 감사 manifest mismatch 경고 | P2 |
| ACC-011 | 블라인드 동일 계약의 문장 변형 | 분할 | 같은 split 배정 | P1 |
| ACC-012 | 평가 도중 모델 API 실패 | 실행 | FAILED/INCONCLUSIVE + 자동 배포 차단 | P1 |
| ACC-013 | VIEWER 역할 | 승인 요청 | 서버 403 | P2 |
| ACC-014 | 악성 HTML in 약관 | 화면 렌더링 | 스크립트 비실행 | P2 |
| ACC-015 | 동일 POST idempotency key/body | 재요청 | 중복 실행/결제 없음(서비스측) | P2 |
| ACC-016 | 실측 결과 없고 최신 배치 없음 | 대시보드 | '미측정', 임의 그래프 없음 | P0 |

### 13.1 테스트 피라미드 및 DoD

- 파서·resolver·결정·상태머신은 **순수 단위 테스트**와 property-based 경계 tests.
- DB 제약/업로드/승인/작업 큐는 integration; 브라우저 e2e는 주요 6개 user journey만.
- PR 머지: `ruff/format`, `mypy`(핵심 모듈), `pytest`, `web build`, `OpenAPI schema check` 통과; P1 이후 regression smoke PASS.
- P0 완료는 `pytest tests/test_policy_resolver.py`, `docker compose up --build`, UI에서 정상/차단 2건, `GET /evaluations/:id`가 근거를 반환한다는 **실제 실행 증거**가 있어야 한다.
- v2 부록에 넣은 코드는 **규정선택 참조 모형**일 뿐, FastAPI 서버·웹 화면을 이미 구현했다는 뜻이 아니다.

## 14. 단계별 개발 백로그: 주차가 아닌 실행 게이트

### Gate 0 — 문제·자료·규정 승인

- I-001 공식 출처 원장 최신화와 이용조건 기록 / 확인 URL·조회일·관찰 사실을 분리 / 출처 8건 이상.
- I-002 합성 도메인 규정 v1/v2와 유효기간·기준일 스펙 / JSON Schema 검증.
- I-003 16개 골든 케이스 정답 라벨(왜 그런지 정답 근거 포함) / 수정자·검수자 기록.
- I-004 ADR-001: 단일 조직, P0에 LLM 미사용 결정 / 범위 증가 요구 거절 규칙.

### Gate 1 — 위험 오류를 실제 차단하는 vertical slice

- I-010 Python 정책 resolver(무자격 날짜 자동선택 금지) / ACC-001~005 pytest.
- I-011 규칙 검증(기간·수치·단위) + reason code aggregation / ACC-001/002/007.
- I-012 `/policies/resolve`, `/evaluations` FastAPI route/JSON schema / 계약 스냅샷 테스트.
- I-013 React 검증 상세 S2 좌/중/우 배치 및 상태/증거 하이라이트 / Playwright 2개.
- I-014 Compose 로컬 부팅·Mock mode·seed 데이터/README / PC 재현 실행.

### Gate 2 — 근거·정량 평가

- I-020 claim extractor(JSON 기반 → LLM 어댑터 선택) / 오류 시 INCONCLUSIVE.
- I-021 100개 검증 케이스 생성·독립검수·split 누출 검사 / data card.
- I-022 B0/B1/B2 공정 비교기, 혼동행렬/Wilson CI/페어 비교 / runner CLI.
- I-023 Phoenix OTEL trace + 민감정보 마스킹 / 한 개 run으로 추적 링크 확인.
- I-024 규정 diff 및 변경영향 case candidate 매칭 / 완전 회귀셋 병행.

### Gate 3 — 금융 운영 통제

- I-030 RBAC/조직 경계와 403/404 부정 시나리오 / ACC-008/013.
- I-031 review workflow/optimistic locking/immutable revision / 동시 승인 409.
- I-032 감사 JSON export와 checksum 검증 CLI / 일부 증적 누락 시 거부.
- I-033 S1/S3/S4/S5/S6 완료·한국어 UX/키보드 / 브라우저 e2e 6개.
- I-034 보안 공격 8종·비용 제한·rate limit / 위험 기계식 차단.

### Gate 4 — 독립 평가 및 출시 검토

- I-040 240개 frozen dataset + 40 blind / 데이터 사용 기록과 hash.
- I-041 B1 vs B2 paired experiment 반복·실제 비용·한계 보고 / 위반 지표 공개.
- I-042 릴리스 게이트, critical misses/FP 제어 / 실패하면 데모 전용 표시.
- I-043 공개 데모·GitHub·2분/10분 시연영상·포트폴리오 / 실제 실험 재현법.

**Munder Difflin/Codex 역할 분리:** 작업 계획·이슈 분배·테스트 자동화는 개발 에이전트에 위임 가능. 코드 통합, 평가 분할 잠금, 보안·약관 의미·비용 상한 결정은 사람 최종 승인. 자동 에이전트 수가 늘어난다고 포트폴리오 가치가 늘지 않음.

## 15. 100점 평가 루브릭 및 증거 정책

### 15.1 평가 원칙

- 공개근거는 **필요성·기술 중복·위험 기준**을 뒷받침하지만, 구매수요/기술효과/합격확률은 별도 실험/인터뷰로만 확인 가능.
- 점수는 '외부기관 공식점수'가 아니라 **설정한 기준에 따라 근거와 미확인을 분리한 프로젝트 평가**다.
- 현재 제품 실측 성능: **미평가**. 구현 없는 상태에서 성능 100점 표시 금지.
- 설계 문서의 조항·계약·API와 테스트의 일관성은 정적 검사로 평가 가능. 외부 검증이 필요한 항목은 **미확인**으로 감점한다.

### 15.2 고정 평가표(합계 100)

| 영역 | 배점 | v1 설계 | v2 설계 | 채점 근거 | 만점 조건 |
|---|---:|---:|---:|---|---|
| 현업수요·채용 정합성 | 15 | 14 | 14 | E01/E03/E05/E06; 구매수요 인터뷰 없음 | 실제 금융 DX 실무자 복수 검토 |
| 대체재 대비 차별성 | 15 | 12 | 12 | E07/E08/E09; 시점 룰의 추가 가치 미실증 | 동등 조건 비교로 개선 검증 |
| 도메인 명세·모순 제거 | 15 | 13 | 15 | 적용 기준일, 반개구간, bitemporal, 상태 3중 분리, 예외 정책 명시 | 모순 0·도메인 시험 검증 |
| 기술 아키텍처·실행 상세 | 15 | 14 | 15 | 스키마·API·불변식·화면 이벤트·이슈 DoD 명시 | 구현 시 충돌 없는 계약 확인 |
| 정량평가·재현성 | 15 | 12 | 13 | 분할 세부표·비교실험·CI·통계 지정; 최종 측정 없음 | 사람이 검수한 평가/반복실측 |
| 보안·위험 통제 | 10 | 9 | 9 | E01/E03/E10 대응 테스트 계획, 실제 침투시험 없음 | 공격/권한/유출 테스트 성공 |
| 1인 구현 실현성 | 10 | 9 | 9 | P0→P2 범위 제한, 실제 통합 구축 미확인 | 실제 도커/CI/비용 검증 |
| 포트폴리오 설득력 | 5 | 3 | 3 | 시연 플롯은 마련; 영상·배포·측정 미완료 | 실제 시연 및 재현 리포트 |
| **총계** | **100** | **86** | **90** | **문서 수준 자체 채점; 성능점수 아님** | 검증 증거 확보 시에만 갱신 |

**90점은 100점 선언이 아님.** 추가 10점(1+3+2+1+1+2)은 실제 시장·제품 실증으로 채워야 한다. 점수를 올리려면 '실험 로그/현업 피드백/실제 시연'이 제출돼야 하며 문서를 길게 쓰는 것만으로 추가 점수 없음.

### 15.3 만점 조건의 실험 증거 파일

- `research/interviews.md` (현업 니즈 인터뷰, 역할·날짜·편향 기록), `benchmark/paired_results.csv`, `benchmark/manifest.json`, `benchmark/confusion.json`, `security/test_report.md`, `demo/recording.mp4`, `docs/adr/*.md`, `ci/test_logs/`.
- 실측 성능은 점수와 별도 표로 관리: `N`, `TP/FP/TN/FN`, Wilson CI, 회귀 의사결정, 공급자 모델명, seed/설정, 환경, 실패사례.

## 16. 리스크 레지스터 및 피벗 조건

| 위험 | 가능성/영향(추정) | 얼리워닝 | 차단/대안 |
|---|---|---|---|
| 단순 Langfuse 대시보드 복제 | 높음/높음 | 기능 목록이 trace만 가득 | resolver + 영향 분석만 P0로 |
| 실제 약관 해석 복잡도 | 높음/높음 | 적용 기준일을 단정 불가 | 합성 DSL, INCONCLUSIVE 기본 |
| 가짜 정답·자기검증 편향 | 높음/높음 | 골드셋을 같은 모델이 생성/채점 | 규칙 독립 작성, 블라인드 잠금 |
| 허위 100점·성과 숫자 | 중간/높음 | 실측 없이 성과 차트 게시 | 미측정 표시, CI 데이터 연결 |
| 단독 개발 범위 팽창 | 높음/높음 | RBAC/Graph DB부터 시작 | Gate 1 실패 동안 확장 금지 |
| API 비용/개인정보 | 중간/높음 | 외부 요청·로그에 원문 등장 | mock default, 합성 데이터만 |
| 제품 연관성 약화 | 중간/중간 | 면접에서 '무슨 문제' 설명 곤란 | 2분 데모: 틀린 약관 차단 중심 |

**중단 규칙:** B2가 B1보다 실질적으로 안전하지 않거나 버전 오류 시점 모형을 설명할 수 없다면 전체 플랫폼 개발을 중단하고 연구·회귀 시험 프로젝트로 좁힌다.

## 17. 포트폴리오·면접 발표 구조

### 17.1 2분 데모 스토리보드

- 0~20초: 문제 — 보험 AI가 구약관 적용 계약에 신약관으로 답할 위험.
- 20~45초: 같은 계약·같은 질문에 2개의 답변 후보 입력.
- 45~75초: CASE-0007은 `VERSION_MISMATCH`, 원문 v1 조항과 적용기준일 표시, BLOCK.
- 75~100초: 규정 업데이트 후 회귀 케이스별 개선/악화표 및 사람 승인 시뮬레이션.
- 100~120초: 공정 비교 수치(실제 측정 후), 한계(합성 데이터/법률자문 아님), 다음 단계.

### 17.2 인사·현업 질문 대비

- **왜 Munder Difflin 말고?** 범용 협업 에이전트가 아니라 보험 도메인의 버전·시점 판단과 배포 차단에 집중해 중복을 줄였다.
- **왜 일반 RAG 평가가 부족?** 문장 수준 근거 충실도와 '해당 시점 계약에 효력이 있는 문서인가'는 별개의 조건이다.
- **왜 Python?** 규칙·데이터 평가와 실험 재현성이 우선. React/TS로 실서비스 수준 관리 UI도 함께 구현한다.
- **정확도 몇 %?** 테스트가 완료되기 전에는 어떤 성능 수치도 주장하지 않는다. 지표와 실험 프로토콜만 정했다.
- **법적 정확성?** 법률 해석을 자동 확정하지 않는다. 검수된 합성 규정으로 사용성을 검증하고 불명확하면 INCONCLUSIVE 처리한다.
- **개발자가 아닌 AI·DX 업무에 강점은?** 업무 모델·전후 비교·예산/보안 통제·담당자 승인 UX를 한 패키지로 기획하고 구현한다.

## 18. 문서·코드의 일치 검증 규칙

1. 모든 FR/ACC/I 티켓은 코드 테스트와 스크린샷 또는 `미구현` 라벨 중 하나에 연결.
2. UI의 KPI·비용·개선율은 실제 DB/benchmark 결과만 표시. 데모 시뮬레이션 데이터는 상단 `합성 데이터`를 고정.
3. 문서/DB/API의 `verdict`는 동일 enum을 사용하며 `status`와 혼동하지 않는다.
4. 날짜·효력일은 UTC timestamp가 아닌 calendar DATE; 기준일 결손 시 기본값 금지.
5. 정책 규칙 정의 변경 시 금지 전이·경계 날짜·답변 판정 unit test 업데이트.
6. `AGENTS.md`와 ADR이 이 명세의 범위와 우선순위를 준수하며 리팩터링 시 마이그레이션 전략 포함.
7. 로컬 데모와 공개 배포 설정을 분리; 실고객 데이터 업로드 옵션이 자동 활성화되지 않게 함.

## 부록 A. 검색 출처와 공식 문서

1. E01 금융위원회, 2026-06-18, https://www.fsc.go.kr/no010101/87142
2. E02 금융위원회, 2026-04-15, https://www.fsc.go.kr/po010103/86712
3. E03 금융보안원, 2026-08-12, https://www.fsec.or.kr/bbs/detail?bbsNo=12031&menuNo=69
4. E04 국가법령정보센터, 보험업감독업무시행세칙, https://www.law.go.kr/LSW/admRulInfoP.do?admRulSeq=2200000108939
5. E05 KB손해보험 AI·데이터 2026 하반기 공고(공고 미러), https://www.bzpp.co.kr/biz/businessDetailView/BR261023A00496
6. E06 전자신문, 2026-09-11, https://www.etnews.com/20260911000048
7. E07 Arize Phoenix 공식 문서, https://arize.com/docs/phoenix/
8. E08 Langfuse 공식 평가, https://langfuse.com/docs/evaluation/overview
9. E09 Ragas 지표, https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/
10. E10 OWASP LLM Top 10, https://genai.owasp.org/llm-top-10/ ; NIST GenAI Profile https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence
11. 보완 자료: 금융보안원 2026 핵심 AI 전략, https://www.fsec.or.kr/bbs/detail?bbsNo=11872&menuNo=69
12. 보완 자료: 국가법령정보센터 별표 15 표준약관, https://www.law.go.kr/admRulBylInfoPLinkR.do?admRulNm=%EB%B3%B4%ED%97%98%EC%97%85%EA%B0%90%EB%8F%85%EC%97%85%EB%AC%B4%EC%8B%9C%ED%96%89%EC%84%B8%EC%B9%99&bylNo=0015

> **v2 핵심 변화**: 문장 설명에 그치지 않고 bitemporal 적용 시점, 세 개의 분리된 상태 모델, 원자적 주장 데이터, reason code, 명시적 오류 응답, ID별 테스트, 공정 비교 절차와 실패 시 중단조건을 구현 가능한 계약으로 정했다. 여전히 제품 성능·법적 적합성·금융사 채택은 검증되지 않았다.
