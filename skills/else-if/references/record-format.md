# 실험 기록 계약 v1

자연어 상담에는 이 형식을 요구하지 않는다. 선택된 실험을 보존하거나 정량 비교할 때 사용한다. Python 3.9 이상, 표준 라이브러리만 필요하다.

## 계획

최상위 필드는 모두 필수이며 추가 필드는 거절한다.

| 필드 | 값 |
|---|---|
| `schema_version` | `next-experiment/1` |
| `id`, `project_id` | 실험과 프로젝트 식별자. 변경된 기준은 새 실험 ID로 보존 |
| `data_origin` | `synthetic` 또는 `project`. 원문 진위를 증명하는 값은 아님 |
| `problem`, `goal`, `scope` | 문제·목표·유효 범위를 나타내는 문자열 |
| `sources` | 최대 50개. 각 항목: `id`, `locator`, `excerpt`, `status` |
| `candidates` | 1~3개. 아래 후보 필드 사용 |
| `selected` | 사용자가 선택한 후보 ID. 실행 권한 부여와는 별개 |
| `controls` | 동일하게 유지할 조건의 중복 없는 문자열 배열, 최소 1개 |
| `budget` | `minutes`(양수), `model_calls`(0 이상 정수), `extra_cost`(0 이상 수), `currency`(통화 문자열) |
| `expected_pairs` | 사전에 정한 과제/반복 ID 문자열 배열. 중복 없이 1~100개 |
| `criteria` | 지표 1~5개. 주요 지표 정확히 하나, 나머지는 보존 조건 |

출처의 `status`: `checked`(호스트가 원문 확인), `user_report`(사용자 보고), `unverified`(미확인), `synthetic`(합성). 프로그램은 이 선언의 진위를 검사하지 않는다. `locator`는 파일/대화 ID와 위치를 표시하는 문자열이며 프로그램이 열지 않는다. 비밀값이나 불필요한 원문을 기록하지 않는다.

후보의 필수 필드:

```text
id, mode, hypothesis, source_refs, change, procedure,
alternative, uncertainty, stop, rollback
```

`mode`는 `step_up` 또는 `breakthrough`, `source_refs`는 계획에 존재하는 출처 ID 배열이다. 근거가 전혀 없으면 빈 배열을 허용하되 경고한다. 나머지는 비어 있지 않은 문자열이다. `procedure`에는 실제 비교 절차, `stop`에는 자원 상한과 중단 조건을 넣는다.

지표의 필수 필드:

```json
{"id":"time","label":"준비·실행·재시도·평가를 포함한 시간","unit":"minutes","direction":"lower","role":"primary","minimum_delta":4}
```

- `direction`: `lower` 또는 `higher`. 개선 방향을 양수로 환산한다.
- `role: primary`: 모든 예정 쌍의 평균 개선량이 양수인 `minimum_delta` 이상이어야 한다.
- `role: guardrail`: **모든 쌍**이 각각 `minimum_delta` 이상이어야 한다. 0이면 악화 금지, -1이면 해당 단위로 1까지 악화 허용이다. 허용 폭은 결과를 보기 전에 정한다.
- 단위와 평가 루브릭은 고정한다. 주관적 점수는 사람 평가임을 명시한다. 순서형 점수의 차이를 엄밀한 인과 효과로 해석하지 않는다.

```text
python3 <스킬 경로>/scripts/experiment.py check <계획.json>
```

반환된 `plan_sha256`를 결과에 복사한다. 지문은 JSON 키 순서나 공백에는 무관하다. 계획 변경 탐지 수단이며 시간 증명·서명·승인 증명이 아니다. 결과를 본 뒤 계획과 지문을 함께 바꾸는 부정행위를 이 프로그램이 막아주지는 않는다. 사전 계획은 별도 기록/버전 관리로 보존한다.

## 결과

```json
{
  "schema_version": "next-experiment/1",
  "plan_sha256": "check가 반환한 값",
  "deviations": [],
  "usage": {"minutes":30,"model_calls":2,"extra_cost":0},
  "pairs": [
    {
      "id":"사전에 정한 과제/반복 ID",
      "baseline":{"status":"completed","metrics":{"time":20},"evidence_refs":["실행 결과의 위치"]},
      "candidate":{"status":"completed","metrics":{"time":15},"evidence_refs":["실행 결과의 위치"]}
    }
  ]
}
```

`usage`는 양쪽 조건·준비·실패·평가를 합친 전체 사용량이며 비용 단위는 계획의 통화다. 모르는 값은 `null`로 둔다. 값이 누락되거나 예산을 초과하면 합격 판정을 하지 않는다. 예산은 이 도구가 자동 집행하지 않으며 실행 중 호스트/사용자가 확인해야 한다.

각 실행의 `status`는 `completed`, `failed`, `missing` 중 하나다. 실패도 로그 참조를 남긴다. 누락 실행은 빈 metrics/evidence_refs를 사용할 수 있다. 없는 측정값은 `null` 또는 키 생략으로 남겨 판단 유보를 유도한다. 실패·재시도를 성공한 마지막 실행으로 교체하지 않는다. 계획 밖 추가 실행은 새 계획에서 수행한다.

```text
python3 <스킬 경로>/scripts/experiment.py review <계획.json> <결과.json>
```

| 판정 | 의미 |
|---|---|
| `criteria_met` | 제출된 모든 실행이 완료되고 사전 기준·예산 조건 충족 |
| `not_supported` | 후보 실행 실패 또는 주요 지표/보존 조건 미충족 |
| `inconclusive` | 누락, 기준선 실패, 비교 조건 변경, 사용량 미확인, 예산 초과 |

판정은 통계적 유의성·인과관계·실사용 효용의 입증이 아니다. `data_origin: synthetic` 결과는 항상 합성 예시로 표시한다. 오류 입력은 stderr JSON과 종료 코드 2, 유효한 입력의 판정은 stdout JSON과 종료 코드 0을 반환한다. 코드 0이 실험 성공을 뜻하지 않는다.

각 파일은 최대 1 MiB, 문자열은 최대 10,000자, 숫자는 유한한 ±1e12 범위다. 경로·로그 문자열은 실행하지 않는다. 출력 파일은 만들지 않는다. 보고서 저장은 호스트가 지정 산출물 위치에 별도로 수행한다.
