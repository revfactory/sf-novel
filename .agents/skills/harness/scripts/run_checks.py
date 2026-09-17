"""Validate recorded run results and completion without executing agent work."""

from __future__ import annotations

from pathlib import Path

from run_support import checked_id, load_json, project_path, run_path, snapshot_inputs


RESULT_STATUSES = {"completed", "failed", "blocked"}
CHECK_STATUSES = {"passed", "failed", "not_run"}


def _strings(value: object, label: str, errors: list[str]) -> bool:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        errors.append(f"{label} must be an array of non-empty strings.")
        return False
    return True


def _task_id(value: object) -> bool:
    try:
        checked_id(value)
        return True
    except ValueError:
        return False


def validate_plan_metadata(project: Path, run_dir: Path, plan: dict) -> list[str]:
    """Check v2 identity and checkpoint shape, leaving unfinished runs valid."""
    errors: list[str] = []
    if not isinstance(plan, dict) or type(plan.get("schema_version")) is not int or plan["schema_version"] != 2:
        return ["Run plan requires schema_version=2; migrate legacy plans before checking completion."]
    project = project.resolve()
    identifier = plan.get("run_id")
    try:
        expected = run_path(project, identifier)
        if expected != run_dir.absolute() or run_dir.name != identifier:
            errors.append("Run ID must match its .harness/runs/<run-id> directory.")
    except (OSError, TypeError, ValueError) as exc:
        errors.append(f"Invalid run_id: {exc}")
    root = plan.get("project_root")
    if not isinstance(root, str) or not Path(root).is_absolute() or Path(root).resolve() != project:
        errors.append("Run project_root must identify the current absolute project directory.")
    if "previous_run_id" not in plan:
        errors.append("Run plan needs previous_run_id (null for an initial run).")
    previous = plan.get("previous_run_id")
    if previous is not None:
        try:
            previous_dir = run_path(project, previous)
            if previous == identifier:
                errors.append("previous_run_id cannot refer to the same run.")
            else:
                previous_plan = load_json(previous_dir / "plan.json")
                if not isinstance(previous_plan, dict) or previous_plan.get("run_id") != previous:
                    errors.append("Previous run identity does not match previous_run_id.")
                elif "project_root" in previous_plan and previous_plan["project_root"] != str(project):
                    errors.append("Previous run belongs to a different project_root.")
        except (OSError, TypeError, ValueError) as exc:
            errors.append(f"Cannot resolve previous_run_id: {exc}")
    tasks = plan.get("tasks")
    if not isinstance(tasks, list):
        return errors + ["Run plan needs a tasks array."]
    for task in tasks:
        if not isinstance(task, dict):
            errors.append("Every run task must be an object.")
            continue
        label = f"Task {task.get('id', '?')}"
        if not _task_id(task.get("id")):
            errors.append(f"{label}: id must use letters, digits, underscores or hyphens.")
        if not isinstance(task.get("role"), str) or not task["role"].strip():
            errors.append(f"{label}: role must be a non-empty string.")
        if _strings(task.get("inputs"), f"{label} inputs", errors):
            for relative in task["inputs"]:
                try:
                    project_path(project, relative, allow_missing=True)
                except (OSError, ValueError) as exc:
                    errors.append(f"{label}: invalid input path: {exc}")
        fingerprints = task.get("input_fingerprints")
        if not isinstance(fingerprints, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) or not value
            for key, value in fingerprints.items()
        ):
            errors.append(f"{label}: input_fingerprints must map paths to non-empty fingerprint strings.")
        if not isinstance(task.get("contract_fingerprint"), str) or not task["contract_fingerprint"].strip():
            errors.append(f"{label}: managed v2 task needs contract_fingerprint.")
        if task.get("status") == "completed" and not isinstance(task.get("artifact_fingerprints"), dict):
            errors.append(f"{label}: completed v2 task needs artifact_fingerprints.")
        context = task.get("context")
        if not isinstance(context, dict):
            errors.append(f"{label}: context must contain decisions and skill_paths.")
        else:
            _strings(context.get("decisions"), f"{label} context.decisions", errors)
            if _strings(context.get("skill_paths"), f"{label} context.skill_paths", errors):
                for relative in context["skill_paths"]:
                    try:
                        project_path(project, relative, allow_missing=True)
                    except (OSError, ValueError) as exc:
                        errors.append(f"{label}: invalid skill path: {exc}")
        agent_id = task.get("agent_id")
        if "agent_id" not in task or (agent_id is not None and (not isinstance(agent_id, str) or not agent_id.strip())):
            errors.append(f"{label}: agent_id must be null or a non-empty string.")
        if "reused_from" in task:
            reused = task["reused_from"]
            if not isinstance(reused, dict) or not _task_id(reused.get("task_id")):
                errors.append(f"{label}: reused_from needs a valid run_id and task_id.")
            else:
                try:
                    source = run_path(project, reused.get("run_id"))
                    if source == run_dir.absolute():
                        errors.append(f"{label}: reused_from cannot refer to the current run.")
                    elif not (source / "plan.json").is_file():
                        errors.append(f"{label}: reused_from run does not exist.")
                except (OSError, TypeError, ValueError) as exc:
                    errors.append(f"{label}: invalid reused_from: {exc}")
    return errors


def validate_context(project: Path, task: dict) -> list[str]:
    """Require the recorded input snapshot to describe the current inputs."""
    errors: list[str] = []
    if not isinstance(task, dict):
        return ["Task must be an object."]
    if not _strings(task.get("inputs"), "Task inputs", errors):
        return errors
    recorded = task.get("input_fingerprints")
    if not isinstance(recorded, dict) or any(not isinstance(value, str) for value in recorded.values()):
        return ["Task needs recorded input_fingerprints before its result can be accepted."]
    paths = list(task["inputs"])
    context = task.get("context", {})
    if not isinstance(context, dict):
        return ["Task context must be an object."]
    if not _strings(context.get("skill_paths", []), "Task context.skill_paths", errors):
        return errors
    paths.extend(context.get("skill_paths", []))
    try:
        current = snapshot_inputs(project, list(dict.fromkeys(paths)))
        if current != recorded:
            changed = sorted(key for key in set(current) | set(recorded) if current.get(key) != recorded.get(key))
            errors.append(f"Task input snapshot is stale: {', '.join(changed)}. Refresh the task and recheck its result.")
    except (OSError, TypeError, ValueError) as exc:
        errors.append(f"Cannot verify task inputs: {exc}")
    if "dependency_fingerprints" in task:
        dependencies = task["dependency_fingerprints"]
        if not isinstance(dependencies, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in dependencies.items()
        ):
            errors.append("Task dependency_fingerprints must map paths to fingerprint strings.")
        else:
            try:
                current = snapshot_inputs(project, list(dependencies))
                if current != dependencies:
                    errors.append("Task dependency snapshot is stale; rerun it against the current accepted dependency results.")
            except (OSError, TypeError, ValueError) as exc:
                errors.append(f"Cannot verify task dependencies: {exc}")
    return errors


def validate_result(project: Path, run_dir: Path, task: dict, result: dict) -> list[str]:
    """Check result identity, artifacts and evidence; never run its commands."""
    if not isinstance(task, dict) or not isinstance(result, dict):
        return ["Task and result must be objects."]
    errors: list[str] = []
    identifier = task.get("id")
    if not _task_id(identifier):
        errors.append("Task ID is invalid.")
    if result.get("task_id") != identifier:
        errors.append("Result task_id does not match its task.")
    if result.get("run_id") != run_dir.name:
        errors.append("Result run_id does not match its run.")
    status = result.get("status")
    if not isinstance(status, str) or status not in RESULT_STATUSES:
        errors.append("Result status must be completed, failed, or blocked.")
    if status != task.get("status"):
        errors.append("Result status does not agree with the plan task status.")
    if not isinstance(result.get("summary"), str) or not result["summary"].strip():
        errors.append("Result summary must be a non-empty string.")
    if _strings(result.get("artifacts"), "Result artifacts", errors):
        for relative in result["artifacts"]:
            try:
                artifact = project_path(project, relative)
                if not artifact.is_file() and not artifact.is_dir():
                    errors.append(f"Result artifact is not an existing file or directory: {relative}")
                elif artifact.is_dir():
                    # A declared output directory must not hide escaping links.
                    snapshot_inputs(project, [relative])
            except (OSError, ValueError) as exc:
                errors.append(f"Invalid result artifact {relative}: {exc}")
    _strings(result.get("issues"), "Result issues", errors)
    checks = result.get("checks")
    required_passes = 0
    if not isinstance(checks, list):
        errors.append("Result checks must be an array.")
    else:
        for index, check in enumerate(checks):
            label = f"Check {index + 1}"
            if not isinstance(check, dict):
                errors.append(f"{label} must be an object.")
                continue
            if not isinstance(check.get("name"), str) or not check["name"].strip():
                errors.append(f"{label} needs a non-empty name.")
            check_status = check.get("status")
            if not isinstance(check_status, str) or check_status not in CHECK_STATUSES:
                errors.append(f"{label} status must be passed, failed, or not_run.")
            required = check.get("required", True)
            if type(required) is not bool:
                errors.append(f"{label} required must be boolean when present.")
            evidence = check.get("evidence")
            if not isinstance(evidence, str):
                errors.append(f"{label} evidence must be a string.")
            if status == "completed" and required is True:
                if check_status != "passed":
                    errors.append(f"{label} is required and has not passed.")
                elif not isinstance(evidence, str) or not evidence.strip():
                    errors.append(f"{label} needs non-empty evidence for its required pass.")
                else:
                    required_passes += 1
    if status == "completed":
        if not required_passes:
            errors.append("Completed result needs at least one required passed check with evidence.")
        errors.extend(validate_context(project, task))
    return errors


def validate_completion(project: Path, run_dir: Path) -> list[str]:
    """Require v2 metadata and accepted evidence for every completed task."""
    project = project.resolve()
    try:
        relative = run_dir.absolute().relative_to(project).as_posix()
        run_dir = project_path(project, relative)
        plan = load_json(run_dir / "plan.json")
    except (OSError, TypeError, ValueError) as exc:
        return [f"Cannot read run completion record: {exc}"]
    errors = validate_plan_metadata(project, run_dir, plan)
    if errors:
        return errors
    # Import lazily so the structural validator can also call metadata checks.
    from validate import validate_plan

    try:
        errors.extend(validate_plan(run_dir / "plan.json"))
    except (OSError, TypeError, ValueError) as exc:
        errors.append(f"Invalid run plan: {exc}")
    if errors:
        return errors
    try:
        registry_path = project_path(project, (run_dir / "agents.json").relative_to(project).as_posix())
        registry = load_json(registry_path)
        if not isinstance(registry, dict) or registry.get("run_id") != plan["run_id"] or not isinstance(registry.get("agents"), dict):
            errors.append("Run agents.json needs matching run_id and an agents object.")
        else:
            for agent_id, agent in registry["agents"].items():
                if not isinstance(agent, dict) or agent.get("state") not in {"running", "stop_requested", "idle", "stopped", "closed"}:
                    errors.append(f"Agent {agent_id}: invalid registry state.")
                elif agent["state"] in {"running", "stop_requested"}:
                    errors.append(f"Agent {agent_id} is still {agent['state']}; record its observed native lifecycle before completion.")
                elif not isinstance(agent.get("evidence"), str) or not agent["evidence"].strip():
                    errors.append(f"Agent {agent_id}: lifecycle confirmation needs non-empty evidence.")
    except (OSError, TypeError, ValueError) as exc:
        errors.append(f"Cannot verify native agent lifecycle registry: {exc}")
    from run_state import task_contract_fingerprint

    for task in plan["tasks"]:
        identifier = task["id"]
        if task.get("contract_fingerprint") != task_contract_fingerprint(plan["objective"], task):
            errors.append(f"Task {identifier}: objective or task contract changed after its snapshot.")
        if task["required"] and task["status"] != "completed":
            errors.append(f"Required task {identifier} is {task['status']}, not completed.")
        if task["status"] == "running":
            errors.append(f"Task {identifier} is still running.")
        if task["status"] != "completed":
            continue
        try:
            relative = (run_dir / f"task-{identifier}" / "result.json").relative_to(project).as_posix()
            result = load_json(project_path(project, relative))
            result_errors = validate_result(project, run_dir, task, result)
            errors.extend(f"Task {identifier}: {message}" for message in result_errors)
            if not result_errors:
                if task["artifact_fingerprints"] != snapshot_inputs(project, result["artifacts"]):
                    errors.append(f"Task {identifier}: accepted artifact snapshot is stale.")
        except (OSError, TypeError, ValueError) as exc:
            errors.append(f"Task {identifier}: cannot read result.json: {exc}")
    return errors
