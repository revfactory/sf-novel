#!/usr/bin/env python3
"""Record harness messages separately from native transport delivery."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import uuid

from common import safe_path
from run_support import checked_id, locked

KINDS = {"discovery", "question", "answer", "contract", "decision", "blocker",
         "handoff", "progress", "completion", "ack", "lifecycle"}
DELIVERIES = {"recorded", "sent", "received", "failed"}


def log_path(project: Path, run_id: str) -> Path:
    return safe_path(project.expanduser().resolve() / "_workspace" / "communications" / f"{checked_id(run_id)}.jsonl")


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    events = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise ValueError(f"Blank communication record at {path}:{number}")
        try:
            event = json.loads(line)
        except ValueError as exc:
            raise ValueError(f"Incomplete or invalid communication record at {path}:{number}; preserve and repair it before appending.") from exc
        if not isinstance(event, dict) or event.get("sequence") != number or not isinstance(event.get("message_id"), str):
            raise ValueError(f"Invalid communication event at {path}:{number}")
        events.append(event)
    return events


def append_event(project: Path, run_id: str, sender: str, recipient: str, kind: str,
                 body: str, task_id: str | None = None, reply_to: str | None = None,
                 delivery: str = "recorded") -> dict:
    """Append under an interprocess lock. This function never sends a message."""
    for label, value in (("sender", sender), ("recipient", recipient), ("body", body)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} must be a non-empty string.")
    if kind not in KINDS or delivery not in DELIVERIES:
        raise ValueError("Unknown communication kind or delivery state.")
    if task_id is not None:
        checked_id(task_id)
    path = log_path(project, run_id)
    with locked(path.with_suffix(".lock")):
        events = _read(path)
        if reply_to is not None and reply_to not in {e["message_id"] for e in events}:
            raise ValueError(f"Unknown reply_to message ID in this run: {reply_to}")
        if kind in {"answer", "ack"} and reply_to is None:
            raise ValueError(f"{kind} must reference the original message with reply_to.")
        event = {"schema_version": 1, "sequence": len(events) + 1,
                 "message_id": uuid.uuid4().hex,
                 "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                 "run_id": run_id, "task_id": task_id,
                 "sender": sender, "recipient": recipient, "kind": kind,
                 "delivery": delivery, "reply_to": reply_to, "body": body}
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return event


def read_events(project: Path, run_id: str) -> list[dict]:
    path = log_path(project, run_id)
    if not path.exists():
        return []
    with locked(path.with_suffix(".lock")):
        return _read(path)


def markdown(events: list[dict], run_id: str) -> str:
    lines = [f"# Agent communication: {run_id}", "",
             "Explicit harness records. A recorded event is not proof of native delivery.", ""]
    for event in events:
        lines += [f"## {event['sequence']}. {event['kind']} — {event['sender']} → {event['recipient']}", "",
                  f"- Time: {event['timestamp']}", f"- Message: `{event['message_id']}`",
                  f"- Delivery: `{event['delivery']}`", f"- Task: `{event['task_id'] or '-'}`",
                  f"- Reply to: `{event['reply_to'] or '-'}`", ""]
        lines += ["> " + line for line in event["body"].splitlines()]
        lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--run", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    log = sub.add_parser("log", help="Record an explicit message or delivery observation.")
    log.add_argument("--sender", required=True)
    log.add_argument("--recipient", required=True)
    log.add_argument("--kind", choices=sorted(KINDS), required=True)
    body = log.add_mutually_exclusive_group(required=True)
    body.add_argument("--body")
    body.add_argument("--body-file", type=Path)
    log.add_argument("--task")
    log.add_argument("--reply-to")
    log.add_argument("--delivery", choices=sorted(DELIVERIES), default="recorded")
    view = sub.add_parser("view", help="View records without changing delivery state.")
    view.add_argument("--format", choices=("markdown", "jsonl"), default="markdown")
    view.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "log":
            content = args.body_file.read_text(encoding="utf-8") if args.body_file else args.body
            event = append_event(args.project, args.run, args.sender, args.recipient, args.kind,
                                 content, args.task, args.reply_to, args.delivery)
            print(json.dumps(event, ensure_ascii=False))
        else:
            events = read_events(args.project, args.run)
            content = (markdown(events, args.run) if args.format == "markdown" else
                       "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events))
            if args.output:
                output = args.output.expanduser()
                if output.resolve() in {log_path(args.project, args.run).resolve(), log_path(args.project, args.run).with_suffix(".lock").resolve()}:
                    raise ValueError("Export cannot overwrite the source log or lock.")
                output = safe_path(output.parent.resolve() / output.name)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(content, encoding="utf-8")
                print(f"Wrote {output}")
            else:
                print(content, end="")
        return 0
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
