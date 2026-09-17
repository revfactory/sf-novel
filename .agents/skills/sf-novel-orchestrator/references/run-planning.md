# 실행 계획과 결과 계약

복수 산출물 집필·위임·부분 재실행을 계획할 때 읽는다. 모든 명령은 프로젝트 루트에서 실행한다. `PLAN.json`, `RUN_ID`, `ACTUAL_AGENT_ID`는 실제 경로/값으로 바꾼다. CLI는 기록만 관리하며 실제 에이전트 호출은 따로 한다.

## 계획 만들기

`_workspace/plans/`에 이번 요청의 계획 JSON을 쓴다. 새 run ID를 먼저 정하고 존재하는 입력만 넣는다. 선행 출력은 dependencies로 연결한다. 리뷰가 읽고 판단할 안정된 파일을 빠짐없이 inputs에 포함한다. 메인이 만든 통합본·정본·문체 계약도 예외가 아니다. 입력 목록에 없는 파일의 변경은 resume이 알아서 감지하지 않는다. 예를 들어 확정 장면 카드가 있으면 draft → editor/continuity 병렬 검토 → 새 버전 수정 순서로 구성한다. 검토 전에는 수정 필요 여부를 알 수 없으므로 수정 작업은 개정 계획으로 추가한다.

```json
{
  "objective": "확정된 첫 장면 카드를 한국어 초안으로 작성한다",
  "tasks": [{
    "id": "draft",
    "role": "sf_writer",
    "dependencies": [],
    "ownership": [".harness/runs/RUN_ID/task-draft/outputs/"],
    "inputs": ["novel/brief.md", "novel/canon/", "novel/outline/plot.md"],
    "context": {
      "decisions": ["이 실행의 실제 시점·범위·분량 기준으로 교체한다"],
      "skill_paths": [".agents/skills/sf-novel-draft/SKILL.md"]
    },
    "acceptance": ["지정 장면 카드의 목표·장애·선택·변화가 드러난다", "정본과 시점 인물의 지식에 모순이 없다"],
    "required": true
  }]
}
```

위 예제는 미정 브리프를 자동 확정하지 않는다. 실제 집필 전에 필요한 전제와 장면 카드가 준비됐는지 확인하고 미정이면 먼저 설계한다. 리뷰 작업은 `dependencies: ["draft"]`, 읽기 전용 `ownership: []`로 추가한다. 검토자가 쓸 수 없으므로 메인이 결과를 저장한다. 원고 2차 수정은 다른 출력 경로를 사용한다.

```bash
python3 .agents/skills/sf-novel-orchestrator/scripts/check_inputs.py --project . --plan PLAN.json
python3 .agents/skills/harness/scripts/run.py --project . init --plan-file PLAN.json --run-id RUN_ID
python3 .agents/skills/harness/scripts/run.py --project . ready --run RUN_ID
python3 .agents/skills/harness/scripts/run.py --project . start --run RUN_ID --task draft --agent-id ACTUAL_AGENT_ID
```

입력 검사 명령이 실패하면 init/배정을 진행하지 않는다. 재개·재사용 때에도 갱신된 plan의 입력을 다시 검사한다. 검사기는 경로 존재·빈 파일 여부를 확인하며, 실제 설정 내용의 충분성은 메인이 읽고 판단한다. 선행 산출물은 inputs에 미리 넣지 말고 dependencies로 전달한다.

`start` 전에 네이티브 대기 자식의 실제 생성 성공과 ID가 필요하다. 등록 후 준비된 `.harness/runs/RUN_ID/task-draft/input.md`와 동료 ID·역할·소유권을 전달하여 실제로 작업을 재개한다. 작업의 불변 입력과 수정 대상은 겹치지 않게 한다.

## 결과 등록과 세션 상태

메인은 실제 반환 결과를 별도 JSON으로 저장한다. `status`는 completed/blocked/failed, checks 상태는 passed/failed/not_run이다. 검토 명령이 없으면 command를 생략하고 파일·장면 위치와 관찰을 evidence에 쓴다.

```json
{
  "run_id": "RUN_ID",
  "task_id": "draft",
  "status": "completed",
  "summary": "실제 완료 범위로 교체",
  "artifacts": [".harness/runs/RUN_ID/task-draft/outputs/scene-v1.md"],
  "checks": [{"name": "장면 계약 대조", "status": "passed", "required": true, "evidence": "실제로 대조한 장면 위치·규칙 ID·관찰로 교체"}],
  "issues": []
}
```

예시 문자열을 통과 근거로 제출하지 않는다. 필수 검사가 실패/미실행이면 완료가 아니다. 읽기 전용 리뷰의 artifacts는 빈 배열로 반환해도 된다. 실제 근거 없이 사용자 만족·문학적 우수성을 보증하지 않는다.

```bash
python3 .agents/skills/harness/scripts/run.py --project . result --run RUN_ID --task draft --result-file RESULT.json
python3 .agents/skills/harness/scripts/run.py --project . agent --run RUN_ID --agent-id ACTUAL_AGENT_ID --state idle --evidence '실제 네이티브 완료·유휴 응답으로 교체'
python3 .agents/skills/harness/scripts/validate.py --project . --run RUN_ID --complete
```

완료 응답과 유휴 확인은 별도 사실이다. 실행 상태를 실제 도구에서 확인한 후 기록한다. 자식이 없는 상황에 메인을 가짜 자식으로 등록하지 않는다.

## 후속 수정

```bash
python3 .agents/skills/harness/scripts/run.py --project . resume --run OLD_RUN --new-run NEW_RUN
```

계약/작업 구성이 바뀌면 `--plan-file REVISED_PLAN.json`을 추가한다. 이전 plan.json을 직접 고치지 않는다. 이전 원고·리뷰는 보존하고 새 결과는 새 버전으로 작성한다. 완성된 원고를 `novel/manuscript/`로 통합할 때 메인은 source run/task, 파일, 정본 버전을 기록하고 내용 일치를 확인한다.

## 운영 검증 사례

- 정상: 공통 전제로 독립 자료 2개 작성 → 메인 통합 → 독립 리뷰. 실제 생성/수신 ID와 파일을 기록한다.
- 오류: 필수 입력 누락 또는 규칙 위반을 발견하면 blocked/failed. 선행 결과가 없는 소비 작업은 ready가 아니어야 한다.
- 후속: 입력 하나 또는 task 결정 하나를 바꾸고 resume하여 해당 작업과 소비자만 pending, 무관한 결과는 completed로 재사용되는지 확인한다.
- 자동 선택: 명시 호출 실행과 새 세션에서 관찰한 자동 선택은 따로 기록한다. 관찰하지 않은 것은 not_run.
