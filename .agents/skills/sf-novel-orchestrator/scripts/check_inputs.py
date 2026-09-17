#!/usr/bin/env python3
"""Check required SF task input paths before dispatch; does not start agents."""
import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=Path.cwd())
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--task', help='Check one task; otherwise check all plan inputs.')
    args = parser.parse_args()
    errors = []
    try:
        root = args.project.expanduser().resolve(strict=True)
        plan_path = args.plan if args.plan.is_absolute() else root / args.plan
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
        tasks = plan.get('tasks')
        if not isinstance(tasks, list) or not tasks:
            raise ValueError('plan must contain a nonempty tasks array')
        selected = [t for t in tasks if not args.task or t.get('id') == args.task]
        if not selected:
            raise ValueError(f'unknown task: {args.task}')
        for task in selected:
            paths = task.get('inputs', [])
            skills = task.get('context', {}).get('skill_paths', [])
            if not isinstance(paths, list) or not isinstance(skills, list):
                raise ValueError('inputs and skill_paths must be arrays')
            for value in paths + skills:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError('input paths must be nonempty strings')
                relative = Path(value)
                resolved = (root / relative).resolve()
                label = f'{task.get("id", "?")}: {value}'
                if relative.is_absolute() or '..' in relative.parts or not resolved.is_relative_to(root):
                    errors.append(f'{label}: outside project or not project-relative')
                elif not resolved.exists():
                    errors.append(f'{label}: missing required input')
                elif not (resolved.is_file() or resolved.is_dir()):
                    errors.append(f'{label}: unsupported input type')
                elif resolved.is_file() and resolved.stat().st_size == 0:
                    errors.append(f'{label}: empty required input')
                elif value in skills and not resolved.is_file():
                    errors.append(f'{label}: skill must identify a file')
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        errors.append(str(exc))
    for error in errors:
        print(f'ERROR: {error}', file=sys.stderr)
    print(f'{"FAIL" if errors else "PASS"}: required input paths; {len(errors)} error(s). Content adequacy requires review.')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
