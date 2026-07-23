"""Implementation wrapper for ESLint Path Coverage benchmark."""
from __future__ import annotations

from pathlib import Path

from _eslint_path_coverage_utils import NotebookLogger, ensure_output_dir, run_pipeline


def run_benchmark(repo_path: Path, output_dir: Path) -> dict:
    ensure_output_dir(output_dir)
    logger = NotebookLogger(output_dir / "error_log.txt")
    return run_pipeline(repo_path, output_dir, logger)
