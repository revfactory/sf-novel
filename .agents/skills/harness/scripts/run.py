#!/usr/bin/env python3
"""Record persistent task/context state after actual Codex agent operations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from run_state import init_run, ready_tasks, record_result, resume_run, run_status, start_task, update_agent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="Target project root.")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create a new run and capture immutable input context.")
    init.add_argument("--plan-file", type=Path, required=True)
    init.add_argument("--run-id", required=True)
    for name, help_text in (("ready", "List tasks whose dependencies and ownership allow dispatch."),
                            ("status", "Show the run plan and native agent registry.")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--run", required=True)
    start = commands.add_parser("start", help="Register an existing native ID and prepare its packet before task dispatch.")
    start.add_argument("--run", required=True)
    start.add_argument("--task", required=True)
    start.add_argument("--agent-id", required=True)
    result = commands.add_parser("result", help="Validate and record a task result; does not stop its native agent.")
    result.add_argument("--run", required=True)
    result.add_argument("--task", required=True)
    result.add_argument("--result-file", type=Path, required=True)
    agent = commands.add_parser("agent", help="Record a confirmed native lifecycle transition with evidence.")
    agent.add_argument("--run", required=True)
    agent.add_argument("--agent-id", required=True)
    agent.add_argument("--state", choices=("idle", "stop_requested", "stopped", "closed"), required=True)
    agent.add_argument("--evidence", required=True)
    resume = commands.add_parser("resume", help="Create a new run, reusing only unchanged accepted results.")
    resume.add_argument("--run", required=True)
    resume.add_argument("--new-run", required=True)
    resume.add_argument("--plan-file", type=Path, help="Optional replacement task template; preserves the previous run.")
    args = parser.parse_args()
    try:
        if args.command == "init":
            output = init_run(args.project, args.plan_file, args.run_id)
        elif args.command == "ready":
            output = ready_tasks(args.project, args.run)
        elif args.command == "status":
            output = run_status(args.project, args.run)
        elif args.command == "start":
            output = start_task(args.project, args.run, args.task, args.agent_id)
        elif args.command == "result":
            output = record_result(args.project, args.run, args.task, args.result_file)
        elif args.command == "agent":
            output = update_agent(args.project, args.run, args.agent_id, args.state, args.evidence)
        else:
            output = resume_run(args.project, args.run, args.new_run, plan_file=args.plan_file)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
