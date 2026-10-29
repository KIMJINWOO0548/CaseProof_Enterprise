# 사전등록 실험 설계 (Preregistered Protocol) — 실행 전 계획

## 1. 질문과 비교군 정의

**RQ-1 정확성**: 같은 데이터셋에서 CaseProof의 시간·특약 검증이 단순 LLM 답변 평가보다 신규 치명적 오류를 더 많이 찾아내는가?

**RQ-2 시간**: 도메인 검토자가 오류의 원인을 찾고 수정 요청하는 시간(초)이 기존 도구 단독 대비 줄어드는가?

**RQ-3 운영**: 2인 승인·근거 해시·변경 영향 테스트가 릴리스 승인 실패를 안전하게 차단하는가?

**RQ-4 다기업**: 공통 코어 코드를 수정하지 않고 손보·생보 가상팩 2개를 적용할 수 있는가?

### 비교군 (최소 4개)

| 그룹 | 구성 | 시험 목적 | 외부제품 실연동 상태 |
|---|---|---|---|
| B0 | 사람이 자료 검색해 정정 | 실무 시간 기준선 | 계획 |
| B1 | 범용 RAG + LLM 품질평가 | 기술 최소 비교군 | 미구현 |
| B2 | Langfuse/Phoenix 중 1개 + 동일 도메인 검증 플러그인 | 동일 도메인 기능 추가 시 우위 여부 | 미구현 |
| T | CaseProof + 동일 LLM/API/문서 + 전용 시점 검증·UI | 주장할 실제 제품의 효과 | 참조 로직만 구현 |

**매우 중요:** B1과 T만 비교하면 '도메인 규칙을 추가했으니 좋아졌다'는 자명한 결과일 수 있다. 가장 중요한 공정 비교는 **B2 vs T**다. B2가 동등하거나 좋으면 CaseProof 독립제품 가치에 의문이 있다는 결론을 인정한다.

## 2. 데이터셋 설계 (목표 360, 아직 구축·검수되지 않음)

| 구간 | 건수 목표 | 사용 목적 | 재사용 정책 |
|---|---:|---|---|
| Development | 180 | 로직 작성·프롬프트 튜닝 | 자유 |
| Validation | 90 | 임계값·심각도 검수 | 튜닝 제한 |
| Blind holdout | 90 | 최종 공개 지표 | 최종까지 미공개·튜닝 금지 |
| **합계** | **360** |  |  |

**데이터 출처:** 공개되고 재사용 조건이 확인된 약관·가이드, 사람이 직접 작성한 가상 규칙, 비실제 인물의 합성 사례. 공개 약관 전문을 임의 재배포하지 않고 원문 URL·허용된 인용·조항 메타데이터로 검증한다.

**분포 제안(혼합 가능, 총 건수는 중복제거 ID 기준):** 적용 시점/경계 80, 특약·우선순위 50, 출처/문서 승인 40, 문서 검색 실패/환각 45, 보안/테넌트 45, 모델/프롬프트 회귀 40, 정상 사례 60 = 360. 반드시 각 그룹별 표본 수와 비율을 최종 결과에서 함께 공개.

**라벨 필드:** `case_id`, `tenant_pack`, `product`, `contract_start_date`, `incident_date`, `claim_received_date`, `rule_key`, `gold_rule_version`, `gold_decision`, `expected_reason`, `severity`, `evidence_source_id`, `gold_labeler_1`, `gold_labeler_2`, `adjudicator`, `split`, `case_hash`.

## 3. 라벨링·평가자 독립성

- 라벨 2인 독립 검토, 불일치에 대해 조정자 결정. 실제 보험 전문가가 참여하지 않으면 '비전문가 합성 검수'라 명시.
- 모호하거나 원문 근거 없는 사례는 정답 강제 금지, `UNRESOLVED`로 별도 표기하고 분모·제외사유 공개.
- 평가자 모델·프롬프트·정답 라벨 동일 스냅샷에 봉인. 비교 모델에 홀드아웃 ID/정답 유출 금지.
- 무작위 순서를 고정 시드로 재현; 같은 사례의 유사한 개정 문장을 train/holdout에 나눠 넣지 않도록 문서군 단위 분할.
- 사전 지정 임계값 변경 시 실험 버전 갱신, 최종 홀드아웃을 본 후 임의 튜닝 금지.

## 4. 지표 정의

| 지표 | 분자 | 분모 | 판정 목적 |
|---|---|---|---|
| Critical recall | 탐지된 실제 CRITICAL | 라벨된 실제 CRITICAL 전체 | 소비자 위해 탐지 |
| Critical precision | 실제 CRITICAL인 경보 | 모델의 CRITICAL 경보 전체 | 과도한 경고 관리 |
| False negative rate | 놓친 위험 | 실제 위험 전체 | 위험 누락 |
| False positive rate | 정상 사례 중 오경보 | 실제 정상 전체 | 현업 피로 |
| Abstention coverage | INCONCLUSIVE로 처리한 건 | 전체 대상 사례 | 불확실성 표시 |
| Unsupported citation rate | 근거 출처가 없는 주장 | 검증 대상 전체 주장 | 근거 충실성 |
| Rule date accuracy | 올바른 기준일·약관 선택 | 정답 확정된 해당 사례 | 시점 검증 |
| New critical regression | candidate에서만 실패한 CRITICAL | 신규 발생 건수 | **0건 목표**, 배포 게이트 |
| Paired accuracy delta | (후 성공-전 성공)/N | 동일 N개 평가쌍 | 순개선 |
| Review time | 업무 완료까지 초 | 완성된 작업 수 | 직원 효용 |
| Time-to-detect | 오류 발생~경보 수신 초 | 오류 사례 수 | 운영 대응 |
| Cost per reviewed case | 총 API+클라우드+검토인건비 | 완료 케이스 수 | 사업성 |
| Release evidence completeness | 필수 증빙이 모두 있는 승인 | 승인 시도 전체 | 감사 준비도 |

표본이 작거나 치명 오류 건수가 적으면 실제 지표와 Wilson 신뢰구간, 건수 분포를 함께 보고하고 우수하다는 주장을 제한한다. 평균 대신 중앙값/P90/P95도 사용.

## 5. 사전 성공 기준(사업·규제 기준이 아닌 프로젝트 목표)

- S1 핵심 날짜 적용 엔진: 라벨 확정 사례의 rule-version 선택 정확도 목표 >= 98%; INCONCLUSIVE를 무단 PASS로 변환한 사례 0.
- S2 치명적 회귀: **새로운 CRITICAL 0**에서만 인간 승인 단계 진입 가능. 정상판정이 많다는 이유로 override 불가.
- S3 보안 음성 테스트: 교차 tenant 접근/무권한 승인/도구 범위 확장 성공 0.
- S4 조치시간: 사전 정한 8~12개 과제의 사용자 실험에서 B2 대비 중앙 처리시간 20% 감소 **목표**. 통계적·실무적 차이 없으면 '미입증'.
- S5 다기업성: 공통 코어의 tenant-specific 분기 코드 0, 2개 가상팩에 대해 같은 API와 Gate 경로 통과.
- S6 포트폴리오 재현: Windows+Docker 기동, 설정·데이터·스크립트만으로 누구나 같은 합성 결과 확인. API 키 없이 결정론적 slice 동작.

## 6. 위험한 평가 설계 금지

- 실험 전 생성된 49개 단위 테스트를 실제 AI 정확도 점수로 사용하지 않음.
- 합성 데이터로 측정한 처리시간을 보험사 현업 인건비 절감률로 환산해 홍보하지 않음.
- 모델 답변을 동일 LLM이 채점하면서 맹목적으로 '객관적 정확도'로 홍보하지 않음.
- 완성되지 않은 작업을 분석에 넣을 때 반드시 denominator 및 censoring 여부 기록.
- A/B가 다른 모델·문서·평가자·API 비용을 쓰면 먼저 비교 불가로 선언.

## 7. 결과 보고 양식 (실험 전)

```yaml
experiment_id: EXP-YYYY-NNN
status: NOT_RUN
preregistration_version: v4.0
run_at: null
dataset_snapshot_sha256: null
evaluator_sha256: null
baseline_revision: null
candidate_revision: null
cases_total: 0
cases_completed: 0
critical_tp: null
critical_fp: null
critical_fn: null
critical_tn: null
wilson_95: null
paired_time_delta_seconds: null
operator_n: 0
failures_and_exclusions: []
limitations:
  - No live insurance customer dataset
  - No carrier production integration
```
