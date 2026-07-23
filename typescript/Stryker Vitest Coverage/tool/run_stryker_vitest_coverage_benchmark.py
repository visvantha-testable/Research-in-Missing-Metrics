"""Execute Stryker vitest coverage extraction pipeline outside Jupyter."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _stryker_vitest_coverage_utils import (  # noqa: E402
    NotebookLogger,
    REPO_URL,
    clone_repository,
    ensure_output_dirs,
    resolve_metric_root,
    run_pipeline,
)


def main() -> int:
    metric_root = resolve_metric_root()
    dirs = ensure_output_dirs(metric_root)
    logger = NotebookLogger(dirs["reports"] / "error_log.txt")
    repo_path, clone_status = clone_repository(REPO_URL, dirs["workspace"], reuse=True)
    result = run_pipeline(repo_path, metric_root, logger)
    printable = {
        "clone_status": clone_status,
        "pipeline_success": result.get("pipeline_success"),
        "mutation_score": result.get("mutation_score"),
        "total_mutants": len(result["mutants_df"]),
        "summary": result["summary"],
        "exported_paths": result["exported_paths"],
        "elapsed_ms": result["elapsed_ms"],
    }
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(printable, indent=2, default=str))
    return 0 if result.get("pipeline_success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
