<!-- codex-harness:start -->
## Codex Harness

For creating, extending, auditing or maintaining this project's agent team,
use the `harness` skill at `.agents/skills/harness/SKILL.md`.

For substantial work, proactively delegate bounded independent subtasks to
available Codex subagents when this improves speed or verification. The main
session owns dependencies, shared configuration and final integration. Give
each writer explicit, disjoint file ownership; tell workers they are not alone
and must preserve others' changes. Use read-only exploration/review in parallel;
run dependent implementation and QA in ordered waves. Reuse agents, respect the
runtime concurrency limit, and avoid recursive delegation by default. Product
fixes belong to workers; QA verifies them.

Use only the tools exposed by the current runtime. If custom roles are not yet
available, use an available built-in role with the relevant instructions, and
report that fallback. Required failed tasks remain unresolved until fixed;
completion requires actual verification of the integrated result.

Give children refreshed input packets and actual peer IDs. Proactively share
findings, ask focused peer questions, answer promptly, and announce blockers and
handoffs. The parent confirms contracts and scope. Record important exchanges
under `_workspace/communications/` using the communication helper; native
message delivery is a separate action. Read-only agents ask the parent to log.
Follow `.agents/skills/harness/references/runtime-guide.md` for context refresh,
run state, observed session lifecycle, correlated messages, and completion checks.
<!-- codex-harness:end -->

<!-- codex-harness:domain:start -->
## SF 소설 프로젝트
한국어 SF 소설의 구상·세계관·플롯·집필·수정·이어쓰기에는 `.agents/skills/sf-novel-orchestrator/SKILL.md`를 읽는다.
하네스 자체의 구축·점검·동기화에는 `.agents/skills/harness/SKILL.md`를 읽는다.
<!-- codex-harness:domain:end -->
