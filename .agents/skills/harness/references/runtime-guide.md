# 실행 상태·컨텍스트·통신 가이드

하네스의 실행 장부, 에이전트 재사용, 부분 재실행, 통신 기록을 구성할 때 읽는다. 아래 Python 도구는 로컬 상태와 근거를 관리한다. Codex 에이전트를 생성·중단하거나 메시지를 전달하지 않는다. 네이티브 동작에는 현재 런타임이 실제 제공하는 도구를 별도로 사용한다.

## 네이티브 실행 사전 점검

도구 목록에 spawn이 노출되어도 실제 자식 생성 전에 실패할 수 있다. 정적 검증 성공도 부모 스레드 조회나 네이티브 실행 가능 여부를 증명하지 않는다. 팬아웃 전에 다음 순서로 현재 세션의 실행 결과를 확인한다.

1. 실제 도구 스키마, 사용 가능한 역할과 동시 실행 한도를 확인한다. 알려진 실행 명령·세션 모드와 CLI 버전이 있으면 함께 기록하되, Python 상태 관리 도구가 현재 세션 모드를 자동 감지한다고 가정하지 않는다.
2. 네이티브 도구가 있으면 첫 자식 하나만 본 작업 없는 대기 지시로 생성한다. 제품 파일을 읽거나 쓰지 않고 갱신된 패킷을 기다리게 한다. 실제 생성 응답과 반환 ID를 확인하기 전에는 다음 자식을 만들거나 `run.py start`를 호출하지 않는다.
3. 성공하면 그 자식을 첫 준비된 작업의 에이전트로 재사용한다. 해당 작업에 맞는 탐색·구현·리뷰 등의 역할을 사용한다. 아래 수명 절차에 따라 실제 ID를 등록하고 최신 패킷을 준비한다. 필요한 독립 작업을 추가하면서 패킷과 실제 동료 ID를 전달한다. 사전 점검용 자식을 따로 더 만들지 않으며 실제 동시 실행 한도를 지킨다.
4. `collab spawn failed: no thread with id`처럼 부모 스레드를 찾지 못해 ID가 반환되지 않으면 추가 생성을 멈춘다. 동일한 부모 컨텍스트에서 역할마다 다시 호출하지 않는다. 원문 오류, 실행 모드·버전 중 확인한 정보, 자식 ID가 없다는 사실을 기록한다. ID가 없는 호출을 `run.py start`로 등록하거나 성공한 자식·전송을 꾸며내지 않는다.
5. 도구가 없거나 위 오류로 사용할 수 없으면 기존 메인 세션에서 같은 실질 작업과 검증을 순차 수행한다. 메인의 실제 변경·검사 근거는 별도 요약에 기록한다. 시작되지 않은 네이티브 작업은 `pending`으로 남기며, 이를 메인의 가짜 에이전트 ID로 시작하거나 네이티브 완료로 제출하지 않는다. 이 경우 네이티브 실행의 `--complete`가 통과한다고 보고하지 않는다.

과거 CLI 0.153.4에서는 일반 `codex exec`의 생성 성공과 `--ephemeral`의 위 부모 스레드 오류가 관찰되었다. 알려진 ephemeral 모드는 확인할 위험 신호이며 모든 버전·런타임의 실패를 뜻하지 않는다. 현재 세션의 실제 첫 생성 결과로 판단한다. 사용자가 선택한 기록·개인정보 선호를 유지하고, 오류를 우회하려고 `--ephemeral`을 조용히 제거하거나 영속 세션을 새로 시작하지 않는다. 모드 변경이 기존 사용자 승인 범위에 포함되면 진행할 수 있다. 포함되지 않으면 기록 방식의 차이와 변경 이유를 설명해 승인을 받고, 그동안 가능한 순차 작업은 기존 세션에서 진행한다.

일반 CLI 세션을 사용하기로 했다면 다음과 같이 대상 프로젝트에서 시작한 뒤 `$harness`와 작업 요청을 입력할 수 있다. 모델·권한 등 기존 설정을 상속한다.

```bash
codex -C /path/to/project
```

이 명령은 과거 성공이 관찰된 일반 세션의 진입 대안이며 현재 버전의 성공 보장은 아니다. 새 세션에서도 위 첫 자식 생성 점검을 수행한다.

실제 네이티브 역할·병렬 실행을 요구하는 스모크 테스트에서는 순차 대체를 통과 근거로 사용할 수 없다. 생성 오류가 발생한 네이티브 검사는 실패로, 그 뒤 실행하지 못한 검사는 미실행으로 기록하고 근거를 보존한다. 메인의 실질 작업 완료와 네이티브 실행 검증 결과를 구분해 보고한다.

## 컨텍스트와 실행 초기화

독립 작업에는 목표, 프로젝트 루트, 입력, 결정, 필요한 스킬, 쓰기 소유권, 의존성, 완료 기준이 포함된 작은 패킷을 전달한다. 전체 대화 복제나 특정 fork 옵션을 기본값으로 가정하지 않는다. 같은 주제의 후속 작업은 에이전트를 재사용하되 갱신된 `input.md`와 변경된 계약·스킬을 다시 읽게 한다. 독립 리뷰에는 런타임이 지원하면 새 컨텍스트를 사용하고, 구현자의 결론 대신 요구사항·diff·검증 기준을 제공한다.

계획 파일의 각 작업에 다음 필드를 둔다. 이 예제의 경로·목표는 실제 프로젝트에 맞춰 작성한다.

```json
{
  "objective": "확정된 계약으로 프로필 응답을 변환한다",
  "tasks": [{
    "id": "adapter",
    "role": "harness_worker",
    "dependencies": [],
    "ownership": ["src/profile/adapter.ts"],
    "inputs": ["docs/profile-contract.md"],
    "context": {
      "decisions": ["응답의 profile 키와 기존 오류 형식을 유지한다"],
      "skill_paths": []
    },
    "acceptance": ["소비 코드가 확정된 응답 계약을 처리한다"],
    "required": true
  }]
}
```

- `inputs`는 계약·명세·참조처럼 작업 중 바꾸지 않는 입력이다. 해당 작업이 수정하는 제품 파일은 `ownership`에 넣고 `inputs`와 겹치게 지정하지 않는다.
- `context.decisions`에는 메인이 확정한 판단을, `skill_paths`에는 자식이 실제 읽을 스킬 경로를 쓴다. 스킬 파일도 입력 지문에 포함된다.
- 선행 작업의 산출물은 `dependencies`로 연결한다. 아직 생산되지 않은 결과 경로를 초기 `inputs`에 넣지 않는다. `start`가 승인된 선행 결과와 산출물의 경로·지문을 패킷에 추가한다.
- 디렉터리 입력의 지문은 일반 실행 잡음인 `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.DS_Store`, `.pyc`·`.pyo`를 제외한다. 이 파일을 명시적인 파일 입력으로 지정하면 지문에 포함한다. 테스트 실행으로 생성된 일반 캐시가 스킬 디렉터리를 불필요하게 무효화하지 않도록 하는 규칙이다.

```bash
python3 .agents/skills/harness/scripts/run.py --project . init \
  --plan-file /absolute/path/to/project-plan.json --run-id profile-v1
python3 .agents/skills/harness/scripts/run.py --project . ready --run profile-v1
```

`init`은 `.harness/runs/profile-v1/plan.json`에 `schema_version: 2`, 절대 `project_root`, 입력·계약 지문, 작업 상태를 기록하고 작업별 `input.md`를 만든다. 경로는 대상 프로젝트 기준이다. 메인이 실행 도구를 통해 상태를 갱신하며 자식이 장부를 직접 편집하지 않는다.

## 작업과 에이전트 세션의 수명

작업 완료와 네이티브 에이전트의 유휴·중단·종료는 서로 다른 사실이다. 위 사전 점검을 통과한 첫 자식을 재사용하고, 추가 네이티브 에이전트도 먼저 작업 지시를 기다리는 상태로 생성한다. 이 최초 지시에는 아직 제품 파일을 읽거나 쓰지 말고 최신 패킷을 기다리라고 명시한다. 실제 반환된 ID를 레지스트리에 연결한 뒤 본 작업을 전달한다. 다음 명령의 `ACTUAL_AGENT_ID`는 실제 도구가 반환한 값으로 바꾼다.

```bash
python3 .agents/skills/harness/scripts/run.py --project . start \
  --run profile-v1 --task adapter --agent-id ACTUAL_AGENT_ID
```

메인은 ready 확인 → 네이티브 대기 에이전트 생성 → start로 실제 ID 등록·최신 input.md 준비 → 실제 후속 도구로 작업 패킷 전달 순서를 따른다. 기존 유휴 에이전트도 start로 새 계약을 등록하고 갱신된 패킷을 읽게 한 뒤 실제 후속 실행 도구를 사용한다. start가 실패하면 본 작업을 전달하지 않고 원인을 해결한다. 최신 패킷에 실제 동료 ID·역할·담당 경계·메인 ID 목록을 함께 제공한다. 로컬 장부가 에이전트를 생성하거나 메시지를 전달한다고 가정하지 않는다.

결과를 받으면 메인이 실제 결과를 파일에 저장하고 등록한다.

```bash
python3 .agents/skills/harness/scripts/run.py --project . result \
  --run profile-v1 --task adapter --result-file /absolute/path/to/adapter-result.json
```

결과 파일은 `run_id`, `task_id`, `status`, `summary`, `artifacts`, `checks`, `issues`를 포함한다. 완료 결과에는 최소 한 개의 필수 검사가 통과해야 하며, 필수 검사 모두에 실제 근거가 있어야 한다. 읽기 전용 검토는 파일·행·관찰 결과를 근거로 기록할 수 있다. 명령이 없었던 검토에 가짜 명령을 쓰지 않는다.

```json
{
  "run_id": "profile-v1",
  "task_id": "adapter",
  "status": "completed",
  "summary": "실제 수행한 변경을 적는다",
  "artifacts": ["src/profile/adapter.ts"],
  "checks": [{
    "name": "관련 계약 검증",
    "status": "passed",
    "required": true,
    "command": "실제로 실행한 명령으로 교체",
    "evidence": "실제 출력 요약 또는 근거 파일 경로로 교체"
  }],
  "issues": []
}
```

이 JSON은 작성 형식의 예이며 통과 결과가 아니다. 미실행 검사는 `not_run`으로 기록한다. 필수 검사가 실패·미실행이면 작업을 완료로 제출하지 않는다.

승인된 result의 artifacts는 해당 실행에서 변하지 않는 인계 결과로 취급한다. 후속 작업이 같은 파일을 수정하면 생산자의 산출물 지문과 소비자의 의존 지문이 오래된 상태가 된다. 단계마다 별도 출력 경로를 사용하고 공용 파일 변경은 메인의 명시적인 통합 작업으로 배정한다. 통합이 승인된 산출물을 바꿨다면 이전 결과를 유효한 완료로 유지하지 말고 관련 작업·소비자를 다시 검증한다.

artifacts에는 개별 결과 파일이나 `task-<id>/outputs/` 같은 전용 출력 디렉터리를 기록한다. `plan.json`, `agents.json`, `result.json`을 포함하는 실행·작업 디렉터리 전체를 산출물로 반환하지 않는다. 결과 등록이나 수명주기 기록 자체가 그 디렉터리를 변경해 지문을 무효화할 수 있다.

결과 등록 후에도 네이티브 에이전트는 실행 중일 수 있다. 실제 유휴 또는 중단 응답을 확인한 뒤 다음과 같이 별도 기록한다.

```bash
python3 .agents/skills/harness/scripts/run.py --project . agent \
  --run profile-v1 --agent-id ACTUAL_AGENT_ID --state idle \
  --evidence '실제 네이티브 완료 응답 또는 유휴 상태 관찰로 교체'
python3 .agents/skills/harness/scripts/run.py --project . status --run profile-v1
```

같은 에이전트를 재사용할 때에는 새로운 패킷을 전달하고 실제 후속 실행 도구를 사용한다. 단순 메시지가 유휴 세션을 깨운다고 가정하지 않는다. 소유권을 다른 에이전트로 넘길 때에는 `stop_requested`를 기록하고 네이티브 중단을 요청한 뒤, 실제 중단 응답을 근거로 `stopped`를 기록하거나 실제 종료 응답을 근거로 `closed`를 기록한다. `stop_requested` 이후에는 `idle`로 전이하지 않는다. 작업이 정상 완료되어 유휴 상태를 관찰했다면 `running`에서 바로 `idle`로 기록한다. `stop_requested`만으로 쓰기 소유권을 회수하지 않는다. 로컬 상태 변경이나 기다림만으로 슬롯이 반환되지는 않는다.

## 적극적인 협업과 통신 기록

중요한 발견을 최종 응답까지 미루지 않는다. 영향을 받는 동료에게 먼저 알리고, 필요한 사실은 짧고 구체적으로 질문한다. 질문을 받으면 근거와 함께 신속하게 답한다. 메인에게 의존성과 계약 변경을 함께 알린다.

| 종류 | 전달할 내용 |
| --- | --- |
| `discovery` | 다른 작업에 영향을 주는 발견, 파일·행, 영향 |
| `question` / `answer` | 필요한 사실 하나와 정확한 요청 / 근거가 있는 답 |
| `contract` / `decision` | 변경 제안과 소비자 영향 / 메인이 확정한 결정 |
| `blocker` | 막힌 이유, 필요한 입력·담당자, 계속 가능한 작업 |
| `handoff` | 준비된 산출물, 사용 조건, 검사 근거 |
| `progress` | 중요한 이정표나 계획을 바꾸는 새 정보 |
| `completion` / `ack` | 실제 결과 / 특정 메시지 수신·이해 확인 |
| `lifecycle` | 실제 중단·유휴·종료 관찰과 영향 |

동료가 직접 대화할 수 있는 런타임이면 실제 메시지 도구를 사용한다. 그렇지 않으면 메인이 전달한다. 동료 간 토론은 작업 소유권이나 계약을 변경하지 않는다. 최종 결정과 재배정은 메인만 수행한다. 새로운 정보가 없는 주기적 생존 보고나 반복 질문은 보내지 않는다.

쓰기 가능한 에이전트는 중요한 발신 메시지를 먼저 기록한다. 발신자·수신자 ID와 본문은 실제 내용으로 바꾼다.

```bash
python3 .agents/skills/harness/scripts/communication.py --project . --run profile-v1 log \
  --sender worker-api --recipient worker-client --kind question --task adapter \
  --body 'profile이 null일 때 소비자가 요구하는 오류 형식과 근거 파일을 알려주세요.' \
  --delivery recorded
```

1. 위 명령이 반환한 이벤트 ID를 보관한다.
2. 현재 런타임의 실제 메시지 도구로 본문과 이벤트 ID를 전달한다. 네이티브 도구가 없으면 메인에게 전달을 요청한다.
3. 실제 전송 결과를 별도 이벤트로 기록한다. `--reply-to`에는 원래 이벤트 ID를 넣고, 도구 성공 응답이 있으면 `sent`, 실패하면 `failed`를 쓴다. `sent`는 수신자의 이해나 작업 완료를 뜻하지 않는다.
4. 수신자는 답변 또는 수신 확인을 원래 이벤트 ID와 연결한다. 메인이 받은 실제 답을 대신 기록하면 `--delivery received`를 사용한다. 수신 확인은 계약 승인이나 소유권 이전이 아니다.

긴 본문은 `--body-file /absolute/path/to/message.txt`를 사용한다. `--body`와 함께 쓰지 않는다. 읽기 전용 역할은 로그 파일이나 내보내기를 작성하지 않고 메인에게 실제 메시지·전송 결과를 제공하여 기록을 요청한다. 역할의 샌드박스를 로그 작성 때문에 완화하지 않는다.

로그는 `_workspace/communications/profile-v1.jsonl`에 추가된다. 공유 JSONL은 직접 편집하지 않고 잠금을 사용하는 도구로만 추가한다. Markdown 보기는 별도로 생성할 수 있다.

```bash
python3 .agents/skills/harness/scripts/communication.py --project . --run profile-v1 view \
  --format markdown --output _workspace/communications/profile-v1.md
```

이 로그는 하네스가 명시적으로 기록한 사건이다. Codex 내부 대화 전체를 자동 수집하지 않으며 로컬 로그 작성이 네이티브 메시지를 보내지도 않는다. 전송·수신·응답이 확인되지 않았으면 해당 사실을 꾸며 기록하지 않는다. 기록 도구가 준비되지 않았으면 메인이 근거를 보존하고 미기록 범위를 알린다.

## 변경 감지와 완료 검증

이미 선언된 입력 파일의 내용만 바뀌었다면 기존 계획으로 재개한다.

```bash
python3 .agents/skills/harness/scripts/run.py --project . resume \
  --run profile-v1 --new-run profile-v2
python3 .agents/skills/harness/scripts/run.py --project . ready --run profile-v2
python3 .agents/skills/harness/scripts/validate.py --project . --run profile-v2 --complete
```

`decisions`, `ownership`, `acceptance`, 목표(`objective`)나 작업 구성이 바뀌었다면 새 계획 템플릿을 작성하고 선택적 `--plan-file`로 전달한다. 작업 추가·제거 시 의존성도 함께 갱신한다. 과거 `.harness/runs/<run-id>/plan.json`을 수정해서 계약을 바꾸지 않는다.

```bash
python3 .agents/skills/harness/scripts/run.py --project . resume \
  --run profile-v1 --new-run profile-v2 \
  --plan-file /absolute/path/to/revised-project-plan.json
```

두 예시는 같은 이전 실행에서 선택하는 대안이며 같은 새 run ID로 연속 실행하지 않는다. `resume`은 새 실행을 만들고 이전 실행을 보존한다. 입력·계약·결과가 바뀐 작업과 영향을 받는 하위 작업은 pending으로 돌리고, 추가된 작업도 새로 실행한다. 제거된 작업은 새 계획에서 제외된다. 계약·입력·승인 결과가 그대로인 작업만 재사용한다. 메인은 다시 준비된 작업과 갱신된 패킷을 확인한다. 읽기 전용 조사에서 읽었던 소스가 뒤 단계에서 변경됐다면 다음 실행에서 그 조사 결과가 무효화되는 것은 정상이다.

기본 `validate.py --project .`는 구조를 검사한다. `--run ... --complete`는 해당 실행의 필수 결과, 산출물, 검사 근거와 최신성을 추가로 확인한다. 이것도 실제 네이티브 전송·샌드박스 적용·동시 실행을 증명하지 않는다. 명령 실행 결과와 런타임 관찰을 구분해서 보고한다.
