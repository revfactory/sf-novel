#!/usr/bin/env python3
"""Validate local harness structure; this is not a Codex runtime smoke test."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tomllib
from urllib.parse import unquote, urlsplit

AGENT_NAME = re.compile(r"[a-z][a-z0-9_]{1,62}\Z")
SKILL_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
STALE = re.compile(r"\b(?:TeamCreate|TeamDelete|TaskCreate|TaskUpdate|SendMessage|CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS)\b|\.claude/(?:agents|skills)/|\bclaude -p\b|run_in_background\s*[:=]|model:\s*[\"']?opus\b")
MARKDOWN_LINK = re.compile(r"\[[^\]\n]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+\"[^\"]*\")?\s*\)")


def read_frontmatter(text: str) -> dict[str, str]:
    """Read required scalar fields, including common folded YAML descriptions.

    This intentionally validates the portable name/description contract, not
    arbitrary YAML extensions. Extra metadata is left to Codex's own parser.
    """
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md must start with YAML frontmatter.")
    head, separator, _ = text[4:].partition("\n---")
    if not separator:
        raise ValueError("SKILL.md frontmatter has no closing delimiter.")
    fields: dict[str, str] = {}
    lines = head.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^(name|description):\s*(.*)$", line)
        if not match:
            continue
        key, value = match.groups()
        if key in fields:
            raise ValueError(f"Duplicate frontmatter key: {key}")
        if value in {">", ">-", "|", "|-"}:
            folded = []
            for following in lines[index + 1:]:
                if following and not following[0].isspace():
                    break
                folded.append(following.strip())
            value = " ".join(folded)
        elif value.startswith('"'):
            # Skill helper output uses JSON-compatible double-quoted YAML.
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid quoted {key}; use a plain or JSON-quoted scalar.") from exc
        elif value.startswith("'"):
            if len(value) < 2 or not value.endswith("'") or "'" in value[1:-1].replace("''", ""):
                raise ValueError(f"Invalid single-quoted {key}.")
            value = value[1:-1].replace("''", "'")
        else:
            value = value.split(" #", 1)[0].rstrip()
            if (value.lower() in {"true", "false", "null", "~", ".nan", ".inf", "-.inf", "+.inf"}
                    or re.fullmatch(r"[-+]?(?:\d[\d_.]*(?:[eE][-+]?\d+)?|0[xob][0-9a-fA-F_]+)", value)
                    or value.startswith(("[", "{", "&", "*", "!"))):
                raise ValueError(f"Frontmatter {key} must be a string; quote non-string YAML scalars.")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Missing non-empty frontmatter string: {key}")
        fields[key] = value
    for key in ("name", "description"):
        if key not in fields:
            raise ValueError(f"Missing frontmatter field: {key}")
    return fields


def markdown_issues(path: Path, *, check_runtime: bool) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors = []
    # Examples in code fences contain placeholders, not document navigation.
    prose = re.sub(r"(?ms)^```[^\n]*\n.*?^```[^\n]*(?:\n|$)", "", text)
    for match in MARKDOWN_LINK.finditer(prose):
        link = match.group(1).strip("<>")
        parsed = urlsplit(link)
        if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith("/"):
            continue
        destination = path.parent / unquote(parsed.path)
        if not destination.exists():
            errors.append(f"{path}: broken relative link: {link}")
    if check_runtime:
        for match in STALE.finditer(text):
            errors.append(f"{path}: obsolete Claude runtime token: {match.group()}")
    return errors


def ownership_prefix(value: str) -> str:
    if not isinstance(value, str) or not value or value.startswith(("/", "\\")) or "\\" in value:
        raise ValueError("Ownership must use non-empty project-relative POSIX paths.")
    if ".." in value.split("/") or re.match(r"^[A-Za-z]:", value):
        raise ValueError(f"Ownership escapes the project: {value}")
    if value in {".", "./", "**", "**/*"}:
        return ""
    first_glob = re.search(r"[?*[]", value)
    if first_glob:
        # Conservative directory prefix: sibling globs may be serialized.
        value = value[:first_glob.start()].rsplit("/", 1)[0] if "/" in value[:first_glob.start()] else ""
    normalized = str(PurePosixPath(value))
    return "" if normalized == "." else normalized


def validate_plan(path: Path) -> list[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
        raise ValueError("Run plan must be an object with a tasks array.")
    for key in ("run_id", "objective"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f"Run plan needs {key}.")
    tasks = {}
    prefixes = {}
    for task in data["tasks"]:
        if not isinstance(task, dict) or not isinstance(task.get("id"), str) or not task["id"]:
            raise ValueError("Each task needs a non-empty string id.")
        identifier = task["id"]
        if identifier in tasks:
            raise ValueError(f"Duplicate task id: {identifier}")
        for field in ("dependencies", "ownership", "acceptance"):
            if not isinstance(task.get(field), list) or any(not isinstance(x, str) for x in task[field]):
                raise ValueError(f"Task {identifier}: {field} must be a string array.")
        if not task["acceptance"]:
            raise ValueError(f"Task {identifier} needs acceptance criteria.")
        if task.get("status") not in {"pending", "running", "completed", "blocked", "failed", "skipped"}:
            raise ValueError(f"Task {identifier}: invalid status.")
        if type(task.get("attempts")) is not int or task["attempts"] < 0:
            raise ValueError(f"Task {identifier}: attempts must be a non-negative integer.")
        if type(task.get("required")) is not bool:
            raise ValueError(f"Task {identifier}: required must be boolean.")
        if task["required"] and task["status"] == "skipped":
            raise ValueError(f"Required task {identifier} cannot be skipped.")
        tasks[identifier] = task
        prefixes[identifier] = [ownership_prefix(item) for item in task["ownership"]]
    visiting, visited = set(), set()

    def visit(identifier: str) -> None:
        if identifier not in tasks:
            raise ValueError(f"Unknown task dependency: {identifier}")
        if identifier in visiting:
            raise ValueError(f"Dependency cycle at task: {identifier}")
        if identifier in visited:
            return
        visiting.add(identifier)
        task = tasks[identifier]
        for dependency in task["dependencies"]:
            visit(dependency)
            if task["status"] in {"running", "completed"} and tasks[dependency]["status"] != "completed":
                raise ValueError(f"Task {identifier} started before dependency {dependency} completed.")
        visiting.remove(identifier)
        visited.add(identifier)

    for identifier in tasks:
        visit(identifier)
    running = [key for key, task in tasks.items() if task["status"] == "running"]
    for index, left in enumerate(running):
        for right in running[index + 1:]:
            for a in prefixes[left]:
                for b in prefixes[right]:
                    if not a or not b or a == b or a.startswith(b + "/") or b.startswith(a + "/"):
                        raise ValueError(f"Running tasks {left} and {right} have overlapping write ownership.")
    if "schema_version" in data:
        from run_checks import validate_plan_metadata

        return validate_plan_metadata(path.parents[3].resolve(), path.parent.absolute(), data)
    return []


def validate_project(project: Path) -> tuple[list[str], list[str], int, int]:
    errors: list[str] = []
    warnings: list[str] = []
    agents_seen: dict[str, Path] = {}
    agent_files = sorted((project / ".codex" / "agents").glob("*.toml"))
    skill_files = sorted((project / ".agents" / "skills").glob("*/SKILL.md"))
    for path in agent_files:
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            for key in ("name", "description", "developer_instructions"):
                if not isinstance(data.get(key), str) or not data[key].strip():
                    raise ValueError(f"Missing required non-empty agent string: {key}")
            if not AGENT_NAME.fullmatch(data["name"]):
                raise ValueError("Agent name must be lowercase snake_case (2-63 characters).")
            if data["name"] in agents_seen:
                raise ValueError(f"Duplicate agent name {data['name']} in {agents_seen[data['name']]}")
            agents_seen[data["name"]] = path
            if "sandbox_mode" in data and data["sandbox_mode"] not in {"read-only", "workspace-write", "danger-full-access"}:
                raise ValueError("Invalid agent sandbox_mode.")
        except (OSError, ValueError) as exc:
            errors.append(f"{path}: {exc}")
    skills_seen = set()
    for path in skill_files:
        try:
            fields = read_frontmatter(path.read_text(encoding="utf-8"))
            name = fields["name"]
            if len(name) > 64 or not SKILL_NAME.fullmatch(name) or name != path.parent.name:
                raise ValueError("Skill name must be lowercase hyphenated, <=64 characters, and match its directory.")
            if name in skills_seen:
                raise ValueError(f"Duplicate skill name: {name}")
            skills_seen.add(name)
            for document in sorted(path.parent.rglob("*.md")):
                errors.extend(markdown_issues(document, check_runtime=document == path or "references" in document.relative_to(path.parent).parts))
        except (OSError, ValueError) as exc:
            errors.append(f"{path}: {exc}")
    for directory in (project / ".agents" / "skills").glob("*"):
        if directory.is_dir() and not (directory / "SKILL.md").is_file() and directory.name != "__pycache__":
            errors.append(f"{directory}: missing SKILL.md")
    config = project / ".codex" / "config.toml"
    if config.is_file():
        try:
            data = tomllib.loads(config.read_text(encoding="utf-8"))
            agents = data.get("agents", {})
            if not isinstance(agents, dict):
                raise ValueError("agents must be a table.")
            if "enabled" in agents and type(agents["enabled"]) is not bool:
                raise ValueError("agents.enabled must be boolean.")
            if agents.get("enabled") is False:
                warnings.append("Multi-agent tools are disabled by the existing project configuration.")
            for key in ("max_concurrent_threads_per_session", "max_threads"):
                if key in agents and (type(agents[key]) is not int or agents[key] <= 0):
                    raise ValueError(f"agents.{key} must be a positive integer.")
            if "max_concurrent_threads_per_session" in agents and "max_threads" in agents:
                raise ValueError("Use only one concurrency key; max_threads is a legacy alias.")
        except (OSError, ValueError) as exc:
            errors.append(f"{config}: {exc}")
    instructions = project / "AGENTS.md"
    if instructions.is_file():
        text = instructions.read_text(encoding="utf-8")
        for namespace in ("codex-harness", "codex-harness:domain"):
            start, end = f"<!-- {namespace}:start -->", f"<!-- {namespace}:end -->"
            if (start in text or end in text) and (text.count(start) != 1 or text.count(end) != 1 or text.index(start) > text.index(end)):
                errors.append(f"{instructions}: malformed {namespace} marker block")
    if not agent_files and not skill_files:
        errors.append(f"{project}: no native agents or skills found")
    for path in sorted((project / ".harness" / "runs").glob("*/plan.json")):
        try:
            errors.extend(validate_plan(path))
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"{path}: {exc}")
    return errors, warnings, len(agent_files), len(skill_files)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--run", help="Run ID to check with --complete.")
    parser.add_argument("--complete", action="store_true", help="Require completed tasks and recorded verification evidence.")
    args = parser.parse_args()
    if bool(args.run) != args.complete:
        parser.error("Use --run RUN_ID and --complete together.")
    try:
        project = args.project.expanduser().resolve()
        if args.complete:
            from run_checks import validate_completion
            from run_support import run_path

            errors = validate_completion(project, run_path(project, args.run))
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            print(f"{'FAIL' if errors else 'PASS'}: run {args.run}, {len(errors)} completion error(s). Recorded evidence only.")
            return 1 if errors else 0
        errors, warnings, agents, skills = validate_project(project)
    except (OSError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for warning in warnings:
        print(f"WARNING: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    print(f"{'FAIL' if errors else 'PASS'}: {agents} agent(s), {skills} skill(s), {len(errors)} error(s). Static validation only.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
