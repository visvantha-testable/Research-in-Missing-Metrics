"""CLI entry point for ESLint Path Coverage benchmark."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _eslint_path_coverage_utils import (
    DEFAULT_REPO_URL,
    NotebookLogger,
    clone_or_reuse_repository,
    ensure_output_dir,
    resolve_metric_root,
    run_pipeline,
    validate_local_repo_path,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ESLint + SonarJS Path Coverage benchmark.")
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    parser.add_argument("--local-repo", default="")
    parser.add_argument("--workspace", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--if-clone-exists", choices=("reuse", "reclone"), default="reuse")
    parser.add_argument("--clone-depth", type=int, default=1)
    args = parser.parse_args()

    metric_root = resolve_metric_root()
    workspace_dir = Path(args.workspace or metric_root / "workspace")
    output_dir = Path(args.output or metric_root / "outputs")
    ensure_output_dir(output_dir)
    logger = NotebookLogger(output_dir / "error_log.txt")

    if args.local_repo:
        repo_path = validate_local_repo_path(Path(args.local_repo), logger)
    else:
        repo_path = clone_or_reuse_repository(
            args.repo_url,
            workspace_dir,
            args.if_clone_exists,
            logger,
            args.clone_depth,
        )

    result = run_pipeline(repo_path, output_dir, logger)
    print(json.dumps(result, indent=2))
    return 0 if result["pipeline_success"] else 1


if __name__ == "__main__":
    sys.exit(main())
