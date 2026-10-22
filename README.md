# else-if

막힌 프로젝트에서 다음에 시험할 변경 하나를 고르는 Codex 스킬입니다. 현재 대화의 AI가 근거와 대안 원인을 검토해 실험을 제안하고, Python 보조 프로그램이 계획과 정량 결과를 검증합니다.

## 대화에서 사용

설치 후 새 대화에서:

```text
$else-if 디자인을 여러 번 수정했는데 방향이 계속 어긋난다.
요청과 결과, 피드백을 보고 다음에 무엇을 시험할지 추천해 줘.
```

후속 요청:

```text
첫 번째 실험을 선택할게. 30분, 추가 지출 없이 비교할 계획을 만들어 줘.
실험 결과를 가져왔어. 유지할지 기각할지, 다음에 뭘 해야 할지 검토해 줘.
```

발견되지 않는 현재 대화에서는 `skills/else-if/SKILL.md`의 **절대 경로**를 제공하고 그 스킬을 사용해 달라고 요청할 수 있습니다. 설치 폴더의 내용은 스킬 선택 시 로드되며 실험은 기존 호스트 도구로 수행합니다.

## 설치·비활성화·제거

저장소를 내려받아 설치합니다. 같은 이름의 스킬이 이미 있으면 덮어쓰지 않습니다.

```sh
git clone https://github.com/Raunplaymore/else-if.git
cd else-if
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
ln -s "$PWD/skills/else-if" "${CODEX_HOME:-$HOME/.codex}/skills/else-if"
```

자동 선택을 끄려면 `skills/else-if/agents/openai.yaml`에 다음을 추가합니다. 명시적인 `$else-if` 호출은 유지됩니다.

```yaml
policy:
  allow_implicit_invocation: false
```

훅을 설치했다면 먼저 아래 명령으로 else-if 항목만 제거합니다. 다른 훅은 유지됩니다. 그 다음 설치한 **심볼릭 링크만** 확인하고 해제합니다.

```sh
python3 scripts/install_continuity.py --remove
test -L "${CODEX_HOME:-$HOME/.codex}/skills/else-if" && unlink "${CODEX_HOME:-$HOME/.codex}/skills/else-if"
```

새 대화부터 반영합니다. 이미 열린 대화에 로드된 지침은 제거만으로 지워지지 않으므로 사용 중단을 요청하세요. 백그라운드 실행·후속 예약은 없습니다. 프로젝트에 저장된 `next-experiment-runs` 기록은 남으며 필요할 때 사용자가 따로 삭제합니다. 설치 원본 저장소를 이동하면 링크를 다시 연결해야 합니다.

## 대화 이어가기 훅

스킬 설치 후 저장소 루트에서 등록합니다.

```sh
python3 scripts/install_continuity.py
```

이 명령은 사용자 `hooks.json`을 백업하고 `UserPromptSubmit`와 `SessionStart`에 else-if 항목을 추가합니다. 기존 훅과 신뢰 설정을 변경하지 않습니다. **새 훅은 Codex의 훅 검토 화면에서 신뢰 확인을 해야 실행됩니다.** CLI에서는 `/hooks`로 두 `else-if-continuity-v1` 항목을 확인합니다. 새 항목이 표시되지 않으면 Codex를 다시 시작해 설정을 불러옵니다. [공식 훅 문서](https://learn.chatgpt.com/docs/hooks)

등록·신뢰 확인 후 `$else-if …`로 시작하면 현재 대화와 작업 폴더에 체크포인트를 만듭니다. 다음 메시지나 대화 재개·맥락 압축 후 저장된 상태를 다시 전달합니다. 시작·단계 변경 때만 `else-if · 결과 검토`처럼 단계를 보여 주도록 스킬에 지시합니다. 매 응답을 검사하는 배지는 아닙니다.

`$else-if 종료` 또는 `$else-if stop`을 메시지 전체로 보내면 훅이 체크포인트를 삭제합니다. 자연어 종료나 다른 작업으로 전환할 때는 에이전트가 상태를 해제합니다. 일반 대화와 단순 언급은 자동으로 활성화하지 않습니다. 스킬을 자연어로 호출하면 에이전트가 체크포인트를 저장해 시작할 수 있습니다.

기록 위치는 현재 작업 폴더의 `next-experiment-runs/.else-if-sessions/`입니다. 전체 대화 대신 목표·가설·직전 결과·다음 행동·단계만 저장합니다. 다른 대화·분기·작업 폴더에는 자동 승계하지 않습니다. API 호출·응답 차단·자동 재실행은 없습니다. 내용 갱신과 자연어 종료 처리는 에이전트에 의존하며, 훅은 지침 준수를 보장하지 않습니다. 상세 동작은 [이어가기 지침](skills/else-if/references/continuity.md)에 있습니다.

## 실행 가능한 예시

Python 3.9 이상만 필요하며 추가 패키지·API 키가 필요하지 않습니다. 다음 자료는 **전부 합성 예시**입니다. 실제 두구두구 성과가 아닙니다.

```sh
python3 skills/else-if/scripts/experiment.py check examples/design-plan.json
python3 skills/else-if/scripts/experiment.py review examples/design-plan.json examples/design-results.json
python3 -m unittest discover -s tests -v
```

스킬은 근거 확인 → 최대 세 후보 → 추천 하나 → 선택한 실험 → 결과 회고를 지원합니다. 파일 기록이 필요할 때 사용하는 전체 계약은 [record-format.md](skills/else-if/references/record-format.md)에 있습니다.

## 실제 제공 범위

- 출처와 가설을 구분하도록 안내하는 대화 흐름.
- 사용자가 원하는 대상·범위·방향을 유지하고, 이전 결과물과 새 결과물을 직접 비교하는 흐름.
- 기술 수치와 사용자 평가를 구분하고, 부분 개선·남은 불만에 따라 다음 가설로 전환하는 회고.
- 출처 ID 참조, 계획 버전, 고정된 평가 기준, 예상 실행 목록 검증.
- 대응되는 기준선·후보 측정값 비교, 누락·실패·조건 변경·예산 초과 표시.
- 후보 결과가 좋아도 보존 조건을 위반하면 채택하지 않는 판정.

현재 버전은 스킬 기반입니다. 별도 UI·자체 모델·실험 자동 실행기·실시간 예산 차단·정책 자동 적용·대화 자동 수집은 없습니다. 정량 비교 프로그램은 입력 두 파일만 읽고 네트워크·셸 명령·파일 쓰기를 수행하지 않습니다. 이어가기 프로그램은 해당 대화의 체크포인트만 읽고 저장·삭제합니다. 호스트 AI의 도구 사용까지 이 프로그램들이 통제하지는 않습니다.

원문 진위와 조건의 실제 동등성은 사람이 확인해야 합니다. `criteria_met`는 제출된 데이터의 기준 충족만 뜻합니다. 실제 효과, 통계적 유의성, 인과관계는 별도 검증 대상입니다. 스킬 사용은 호스트 구독/모델 사용량을 소비할 수 있으며, 전달한 자료에는 호스트의 데이터 처리 정책이 적용됩니다.
