#!/usr/bin/env python3
"""Create one project-scoped Codex custom agent without overwriting files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import tomllib

from common import agent_names, apply_files, existing_bytes, safe_path

NAME = re.compile(r"[a-z][a-z0-9_]{1,62}\Z")


def render_agent(name: str, description: str, instructions: str,
                 sandbox_mode: str | None = None, model: str | None = None,
                 reasoning_effort: str | None = None) -> str:
    if not NAME.fullmatch(name):
        raise ValueError("Agent name must be 2-63 lowercase snake_case characters, starting with a letter.")
    fields = {"name": name, "description": description,
              "developer_instructions": instructions}
    if not all(value.strip() for value in fields.values()):
        raise ValueError("Description and developer instructions must be non-empty.")
    if sandbox_mode:
        if sandbox_mode not in {"read-only", "workspace-write"}:
            raise ValueError("Use read-only or workspace-write sandbox mode.")
        fields["sandbox_mode"] = sandbox_mode
    if model:
        fields["model"] = model
    if reasoning_effort:
        fields["model_reasoning_effort"] = reasoning_effort
    # JSON basic strings are compatible with TOML for these string values.
    content = "\n".join(f"{key} = {json.dumps(value, ensure_ascii=False)}"
                        for key, value in fields.items()) + "\n"
    if tomllib.loads(content) != fields:
        raise ValueError("Agent TOML did not round-trip.")
    return content


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--instructions-file", type=Path, required=True)
    parser.add_argument("--sandbox-mode", choices=("read-only", "workspace-write"))
    parser.add_argument("--model", help="Explicit optional override; omitted by default.")
    parser.add_argument("--reasoning-effort", help="Optional override; verify support in the selected model.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        content = render_agent(args.name, args.description,
                               args.instructions_file.read_text(encoding="utf-8"),
                               args.sandbox_mode, args.model, args.reasoning_effort)
        if args.target.expanduser().is_symlink():
            raise ValueError(f"Refusing symlink target: {args.target}")
        target = args.target.expanduser().resolve()
        path = safe_path(target / ".codex" / "agents" / f"{args.name}.toml")
        existing_names = agent_names(target)
        if args.name in existing_names:
            raise ValueError(f"Agent name already exists: {existing_names[args.name]}")
        if existing_bytes(path) is not None:
            raise ValueError(f"Refusing to overwrite existing agent: {path}")
        apply_files({path: content.encode("utf-8")}, dry_run=args.dry_run)
        if args.dry_run:
            print(content, end="")
        print(f"{'Would create' if args.dry_run else 'Created'} {path}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
