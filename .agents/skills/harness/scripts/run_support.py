"""Portable filesystem, fingerprints and locking for local harness runs."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import time

from common import safe_path

IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}\Z")
CACHE_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".DS_Store"}


def checked_id(value: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError("Run/task ID must be 1-96 letters, digits, underscores or hyphens, starting with a letter or digit.")
    return value


def project_path(project: Path, relative: str, allow_missing: bool = False) -> Path:
    project = project.expanduser().resolve()
    if (not isinstance(relative, str) or not relative or "\\" in relative
            or PurePosixPath(relative).is_absolute() or ".." in relative.split("/")
            or re.match(r"^[A-Za-z]:", relative)):
        raise ValueError(f"Expected a project-relative path without traversal: {relative!r}")
    path = (project / relative).resolve()
    if not path.is_relative_to(project):
        raise ValueError(f"Path escapes project: {relative}")
    if not allow_missing and not path.exists():
        raise ValueError(f"Missing project path: {relative}")
    return path


def run_path(project: Path, run_id: str) -> Path:
    return safe_path(project.expanduser().resolve() / ".harness" / "runs" / checked_id(run_id))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, data) -> None:
    """Replace one state file atomically; caller holds the run lock."""
    path = safe_path(path)
    content = (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".harness-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


@contextmanager
def locked(path: Path, timeout: float = 10.0):
    """OS lock released on process exit; the small lock file may remain."""
    path = safe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()

            def acquire():
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)

            def release():
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            def acquire():
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            def release():
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        deadline = time.monotonic() + timeout
        while True:
            try:
                acquire()
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting for harness lock: {path}") from exc
                time.sleep(0.02)
        try:
            yield
        finally:
            release()


def snapshot_inputs(project: Path, paths: list[str]) -> dict[str, str]:
    """Hash explicit files/directories, including directory membership.

    Directory walks exclude standard Python/tool caches; explicitly named cache
    files are still hashed. Inputs must be stable external context. Do not include run/log directories
    or a task's mutable output. In-project symlinks are read, escapes/cycles
    are rejected. Missing paths have an explicit marker for drift detection.
    """
    if not isinstance(paths, list) or any(not isinstance(p, str) for p in paths):
        raise ValueError("Input paths must be a string array.")
    project = project.expanduser().resolve()

    def digest(path: Path, visiting: set[Path]) -> str:
        resolved = path.resolve()
        if not resolved.is_relative_to(project):
            raise ValueError(f"Input symlink escapes project: {path}")
        if not resolved.exists():
            return "missing"
        if resolved in visiting:
            raise ValueError(f"Input directory symlink cycle: {path}")
        hasher = hashlib.sha256()
        if resolved.is_file():
            hasher.update(b"file\0")
            with resolved.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    hasher.update(chunk)
        elif resolved.is_dir():
            hasher.update(b"directory\0")
            visiting.add(resolved)
            try:
                for child in sorted(resolved.iterdir(), key=lambda p: p.name):
                    if child.name in CACHE_NAMES or child.suffix in {".pyc", ".pyo"}:
                        continue
                    hasher.update(child.name.encode("utf-8") + b"\0")
                    hasher.update(digest(child, visiting).encode("ascii") + b"\0")
            finally:
                visiting.remove(resolved)
        else:
            raise ValueError(f"Input is not a regular file or directory: {path}")
        return "sha256:" + hasher.hexdigest()

    return {str(PurePosixPath(value)): digest(project_path(project, value, allow_missing=True), set())
            for value in sorted(set(paths))}
