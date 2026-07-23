"""Dependabot benchmark execution helpers."""
from __future__ import annotations

import os
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from _dependabot_notebook_utils import (  # noqa: E402
    DEFAULT_OWNER,
    DEFAULT_REPOSITORY,
    NotebookLogger,
    run_pipeline,
)


def run_benchmark(repo_path: Path, output_dir: Path) -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    logger = NotebookLogger(output_dir / "error_log.txt")
    return run_pipeline(
        repo_path=repo_path.resolve(),
        output_dir=output_dir.resolve(),
        owner=DEFAULT_OWNER,
        repository=DEFAULT_REPOSITORY,
        github_token=token,
        logger=logger,
    )
