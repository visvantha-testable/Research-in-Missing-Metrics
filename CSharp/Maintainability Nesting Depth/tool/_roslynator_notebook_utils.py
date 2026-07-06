from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.pop("PYTHONPATH", None)
METRIC_ROOT = Path.cwd().resolve()
TOOL_ROOT = METRIC_ROOT / "tool"
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

import pandas as pd
from IPython.display import display
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

from run_roslynator_benchmark_impl import (
    analyze_targets,
    build_nesting_analyzer,
    compute_summary,
    discover_csharp_files,
    discover_solution_and_project_files,
    dotnet_env,
    install_roslynator,
    merge_roslynator_results,
    parse_roslynator_text,
    parse_roslynator_xml,
    run_nesting_analyzer,
    run_roslynator_suite,
)

CS_EXTENSIONS = {".cs"}
EXCLUDED_DIR_NAMES = {
    ".git",
    "bin",
    "obj",
    "packages",
    "artifacts",
    "TestResults",
    "node_modules",
}


class NotebookLogger:
    def __init__(self, error_log_path: Path) -> None:
        self.error_log_path = error_log_path
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.error_log_path.exists():
            self.error_log_path.write_text("", encoding="utf-8")

    def info(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"[{timestamp}] INFO: {message}")

    def error(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        line = f"[{timestamp}] ERROR: {message}\n"
        print(line, end="")
        with self.error_log_path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def ensure_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)


def derive_clone_path(repo_url: str, workspace_dir: Path) -> Path:
    repo_name = repo_url.rstrip("/").removesuffix(".git").split("/")[-1]
    if not repo_name:
        raise ValueError(f"Unable to derive repository name from URL: {repo_url}")
    return workspace_dir / repo_name


def validate_repo_url(repo_url: str) -> None:
    if not repo_url or not isinstance(repo_url, str):
        raise ValueError("REPO_URL must be a non-empty string.")
    if not (repo_url.startswith("https://") or repo_url.startswith("git@") or repo_url.startswith("http://")):
        raise ValueError(f"Invalid repository URL format: {repo_url}")


def clone_or_reuse_repository(
    repo_url: str,
    workspace_dir: Path,
    if_clone_exists: str,
    logger: NotebookLogger,
    clone_depth: int | None = None,
) -> Path:
    validate_repo_url(repo_url)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    clone_path = derive_clone_path(repo_url, workspace_dir)

    if clone_path.exists():
        if if_clone_exists == "reclone":
            logger.info(f"Removing existing clone at {clone_path}")
            shutil.rmtree(clone_path)
        elif if_clone_exists == "reuse":
            logger.info(f"Reusing existing clone at {clone_path}")
            return clone_path.resolve()
        else:
            raise ValueError('IF_CLONE_EXISTS must be either "reuse" or "reclone"')

    logger.info(f"Cloning {repo_url} into {clone_path} (depth={clone_depth})")
    try:
        clone_kwargs = {"depth": clone_depth} if clone_depth else {}
        Repo.clone_from(repo_url, clone_path, **clone_kwargs)
    except GitCommandError as exc:
        logger.error(f"Clone failed for {repo_url}: {exc}")
        raise

    logger.info(f"Clone completed: {clone_path}")
    return clone_path.resolve()


def validate_local_repository(local_repo_path: Path, logger: NotebookLogger) -> Path:
    if not local_repo_path.exists():
        message = f"Local repository path does not exist: {local_repo_path}"
        logger.error(message)
        raise FileNotFoundError(message)

    if not local_repo_path.is_dir():
        message = f"Local repository path is not a directory: {local_repo_path}"
        logger.error(message)
        raise NotADirectoryError(message)

    has_git = (local_repo_path / ".git").exists()
    has_cs = any(
        file_path.suffix.lower() in CS_EXTENSIONS
        for file_path in local_repo_path.rglob("*")
        if file_path.is_file()
    )

    if not has_git and not has_cs:
        message = (
            f"Path is neither a Git repository nor a C# source directory: {local_repo_path}"
        )
        logger.error(message)
        raise ValueError(message)

    if has_git:
        try:
            Repo(local_repo_path)
        except InvalidGitRepositoryError as exc:
            logger.error(f"Invalid Git repository at {local_repo_path}: {exc}")
            raise

    logger.info(f"Validated local repository path: {local_repo_path}")
    return local_repo_path.resolve()


def resolve_repository_path(
    use_git_url: bool,
    repo_url: str,
    local_repo_path: str,
    workspace_dir: Path,
    if_clone_exists: str,
    logger: NotebookLogger,
    clone_depth: int | None = None,
) -> Path:
    if use_git_url:
        logger.info("Execution mode: Git repository URL")
        return clone_or_reuse_repository(
            repo_url, workspace_dir, if_clone_exists, logger, clone_depth=clone_depth
        )
    logger.info("Execution mode: Local repository path")
    return validate_local_repository(Path(local_repo_path), logger)


def should_exclude_path(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def compute_repository_stats(repo_path: Path, cs_files: list[Path]) -> dict[str, Any]:
    total_size_bytes = sum(file_path.stat().st_size for file_path in cs_files)
    directory_count = sum(
        1
        for current_path, _, _ in os.walk(repo_path)
        if not should_exclude_path(Path(current_path).relative_to(repo_path))
    )
    return {
        "csharp_file_count": len(cs_files),
        "repository_size_bytes": total_size_bytes,
        "directory_count": directory_count,
    }


def save_csharp_file_list(cs_files: list[Path], repo_path: Path, output_csv: Path) -> None:
    rows = [
        {
            "absolute_path": str(file_path),
            "relative_path": str(file_path.relative_to(repo_path)),
        }
        for file_path in cs_files
    ]
    pd.DataFrame(rows).to_csv(output_csv, index=False)


def preview_raw_output(raw_text: str, preview_lines: int, output_path: Path) -> None:
    lines = raw_text.splitlines()
    print(f"\n{'=' * 80}")
    print(f"RAW ROSLYNATOR OUTPUT PREVIEW (first {preview_lines} lines)")
    print(f"{'=' * 80}\n")
    if not lines:
        print("(empty raw output)")
        return
    print("\n".join(lines[:preview_lines]))
    remaining = len(lines) - preview_lines
    if remaining > 0:
        print(f"\n... ({remaining} more lines saved to {output_path})")


def count_failed_methods(nesting_df: pd.DataFrame) -> int:
    if nesting_df.empty or "status" not in nesting_df.columns:
        return 0
    return int((nesting_df["status"] != "analyzed").sum())
