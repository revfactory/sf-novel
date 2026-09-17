"""Small filesystem primitives shared by the installed harness helpers."""

from __future__ import annotations

import os
from pathlib import Path
import tomllib


def safe_path(path: Path) -> Path:
    """Reject symlink traversal before writing project configuration."""
    path = Path(os.path.abspath(path.expanduser()))
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f"Refusing symlink destination: {part}")
        if part != path and part.exists() and not part.is_dir():
            raise ValueError(f"Destination parent is not a directory: {part}")
    return path


def existing_bytes(path: Path) -> bytes | None:
    safe_path(path)
    if path.exists():
        if not path.is_file():
            raise ValueError(f"Destination is not a regular file: {path}")
        return path.read_bytes()
    return None


def agent_names(project: Path) -> dict[str, Path]:
    """Codex identifies roles by TOML name, independently of the filename."""
    names: dict[str, Path] = {}
    for path in sorted((project / ".codex" / "agents").glob("*.toml")):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Existing agent has no valid name: {path}")
        if name in names:
            raise ValueError(f"Duplicate existing agent name {name}: {names[name]} and {path}")
        names[name] = path
    return names


def apply_files(files: dict[Path, bytes], *, dry_run: bool = False) -> list[Path]:
    """Preflight every path; restore writes if a later filesystem action fails.

    Callers decide which replacements are authorized. This does not provide
    a multi-process filesystem transaction; run one installer per project.
    """
    before = {path: existing_bytes(path) for path in files}
    changed = [path for path, data in files.items() if before[path] != data]
    if dry_run:
        return changed
    written: list[Path] = []
    created_dirs: list[Path] = []
    try:
        for path in changed:
            if existing_bytes(path) != before[path]:
                raise ValueError(f"Destination changed during installation: {path}")
            missing = []
            parent = path.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for directory in reversed(missing):
                directory.mkdir()
                created_dirs.append(directory)
            # Exclusive creation protects existing files from accidental overwrite.
            with path.open("xb" if before[path] is None else "wb") as stream:
                written.append(path)
                stream.write(files[path])
    except Exception as exc:
        rollback_errors = []
        for path in reversed(written):
            try:
                if before[path] is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(before[path])
            except OSError as rollback_error:
                rollback_errors.append(f"{path}: {rollback_error}")
        for directory in reversed(created_dirs):
            try:
                directory.rmdir()
            except OSError:
                # A concurrent creator's file must remain untouched.
                pass
        if rollback_errors:
            raise OSError(f"Write failed ({exc}); could not restore: {'; '.join(rollback_errors)}") from exc
        raise
    return changed
