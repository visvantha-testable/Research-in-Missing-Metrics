"""CLI entry point for Vitest Exception Path Handling benchmark."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from _vitest_exception_path_utils import (
    DEFAULT_REPO_URL,
    NotebookLogger,
    clone_or_reuse_repository,
    ensure_artifact_dirs,
    resolve_metric_root,
    run_pipeline,
    validate_local_repo_path,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Vitest Exception Path Handling validation benchmark.")
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    parser.add_argument("--local-repo", default="")
    parser.add_argument("--metric-root", default="")
    parser.add_argument("--if-clone-exists", choices=("reuse", "reclone"), default="reuse")
    parser.add_argument("--clone-depth", type=int, default=1)
    args = parser.parse_args()

    metric_root = Path(args.metric_root) if args.metric_root else resolve_metric_root()
    artifact_dirs = ensure_artifact_dirs(metric_root)
    logger = NotebookLogger(artifact_dirs["reports"] / "error_log.txt")

    if args.local_repo:
        repo_path = validate_local_repo_path(Path(args.local_repo), logger)
    else:
        workspace_dir = metric_root / "workspace"
        repo_path = clone_or_reuse_repository(
            args.repo_url,
            workspace_dir,
            args.if_clone_exists,
            logger,
            args.clone_depth,
        )

    result = run_pipeline(repo_path, metric_root, logger)
    printable = {
        key: value
        for key, value in result.items()
        if key
        not in {
            "coverage_summary_raw",
            "coverage_final_raw",
            "evidence_df",
            "taxonomy_df",
            "taxonomy_markdown",
            "final_assessment_markdown",
        }
    }
    print(json.dumps(printable, indent=2))
    return 0 if result.get("pipeline_success") else 1


if __name__ == "__main__":
    sys.exit(main())
