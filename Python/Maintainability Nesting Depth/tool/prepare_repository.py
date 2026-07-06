"""Prepare a Python repository for Pylint execution."""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

TOOL_ROOT = Path(__file__).resolve().parent
METRIC_ROOT = TOOL_ROOT.parent
DEFAULT_REPO_URL = "https://github.com/django/django.git"
DEFAULT_WORKSPACE = METRIC_ROOT / "workspace"
DEFAULT_OUTPUT = METRIC_ROOT / "outputs"

EXCLUDED_DIR_NAMES = {
    ".git",
    "venv",
    ".venv",
    "env",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    ".tox",
    "migrations",
}


def derive_clone_path(repo_url: str, workspace_dir: Path) -> Path:
    repo_name = repo_url.rstrip("/").removesuffix(".git").split("/")[-1]
    return workspace_dir / repo_name


def should_exclude_path(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def discover_python_files(repo_path: Path) -> list[Path]:
    files = []
    for file_path in repo_path.rglob("*.py"):
        if should_exclude_path(file_path.relative_to(repo_path)):
            continue
        files.append(file_path.resolve())
    return sorted(files)


def clone_repository(
    repo_url: str,
    workspace_dir: Path,
    if_exists: str = "reuse",
    clone_depth: int | None = 1,
) -> Path:
    workspace_dir.mkdir(parents=True, exist_ok=True)
    clone_path = derive_clone_path(repo_url, workspace_dir)

    if clone_path.exists():
        if if_exists == "reclone":
            shutil.rmtree(clone_path)
        elif if_exists == "reuse":
            print(f"Reusing existing clone: {clone_path}")
            return clone_path.resolve()
        else:
            raise ValueError('if_exists must be "reuse" or "reclone"')

    print(f"Cloning {repo_url} -> {clone_path} (depth={clone_depth})")
    try:
        kwargs = {"depth": clone_depth} if clone_depth else {}
        Repo.clone_from(repo_url, clone_path, **kwargs)
    except GitCommandError as exc:
        raise RuntimeError(f"Clone failed: {exc}") from exc

    return clone_path.resolve()


def validate_repository(repo_path: Path) -> Path:
    repo_path = repo_path.resolve()
    if not repo_path.exists():
        raise FileNotFoundError(f"Repository path does not exist: {repo_path}")
    if not repo_path.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: {repo_path}")

    has_git = (repo_path / ".git").exists()
    has_python = any(repo_path.rglob("*.py"))
    if not has_git and not has_python:
        raise ValueError(f"Not a Git repository or Python source tree: {repo_path}")

    if has_git:
        Repo(repo_path)
    return repo_path


def configure_pythonpath(repo_path: Path) -> str:
    entries = [str(repo_path)]
    django_pkg = repo_path / "django"
    if django_pkg.is_dir() and (django_pkg / "__init__.py").exists():
        entries.append(str(django_pkg))
    pythonpath = os.pathsep.join(dict.fromkeys(entries))
    os.environ["PYTHONPATH"] = pythonpath
    return pythonpath


def detect_pylint_rcfile(repo_path: Path) -> str | None:
    candidates = [
        repo_path / "pylintrc",
        repo_path / ".pylintrc",
        repo_path / "setup.cfg",
        repo_path / "pyproject.toml",
        repo_path / "tox.ini",
    ]
    for candidate in candidates:
        if candidate.exists():
            if candidate.suffix == ".toml":
                text = candidate.read_text(encoding="utf-8", errors="replace")
                if "[tool.pylint" in text:
                    return str(candidate)
            elif candidate.name in {"pylintrc", ".pylintrc"}:
                return str(candidate)
            else:
                text = candidate.read_text(encoding="utf-8", errors="replace")
                if "[pylint" in text.lower() or "[MASTER]" in text:
                    return str(candidate)
    return None


def prepare_repository(
    repo_path: Path | None = None,
    repo_url: str = DEFAULT_REPO_URL,
    workspace_dir: Path = DEFAULT_WORKSPACE,
    output_dir: Path = DEFAULT_OUTPUT,
    if_exists: str = "reuse",
    clone_depth: int | None = 1,
    clone_if_missing: bool = True,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    if repo_path is None:
        clone_path = derive_clone_path(repo_url, workspace_dir)
        if clone_if_missing and not clone_path.exists():
            repo_path = clone_repository(repo_url, workspace_dir, if_exists, clone_depth)
        else:
            repo_path = clone_path

    repo_path = validate_repository(Path(repo_path))
    pythonpath = configure_pythonpath(repo_path)
    python_files = discover_python_files(repo_path)
    rcfile = detect_pylint_rcfile(repo_path)

    git_head = None
    git_remote = None
    if (repo_path / ".git").exists():
        git_repo = Repo(repo_path)
        git_head = git_repo.head.commit.hexsha[:12]
        try:
            git_remote = git_repo.remotes.origin.url
        except Exception:
            git_remote = None

    manifest = {
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "repo_path": str(repo_path),
        "repo_url": repo_url,
        "git_head": git_head,
        "git_remote": git_remote,
        "python_file_count": len(python_files),
        "repository_size_bytes": sum(p.stat().st_size for p in python_files),
        "directory_count": sum(
            1
            for current_path, _, _ in os.walk(repo_path)
            if not should_exclude_path(Path(current_path).relative_to(repo_path))
        ),
        "pythonpath": pythonpath,
        "pylint_rcfile": rcfile,
        "recommended_local_repo_path": str(repo_path),
        "recommended_notebook_config": {
            "USE_GIT_URL": False,
            "LOCAL_REPO_PATH": str(repo_path),
            "PYLINT_RCFILE": rcfile,
        },
    }

    manifest_path = output_dir / "repo_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    print(f"\nRepository prepared for Pylint execution.")
    print(f"Manifest: {manifest_path}")
    return manifest


if __name__ == "__main__":
    target = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
    prepare_repository(repo_path=target)
