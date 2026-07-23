"""Execute Stryker raw output extraction pipeline outside Jupyter."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _stryker_mutation_utils import (  # noqa: E402
    NotebookLogger,
    REPO_URL,
    clone_repository,
    ensure_artifact_dirs,
    resolve_metric_root,
    run_pipeline,
)


def main() -> int:
    metric_root = resolve_metric_root()
    dirs = ensure_artifact_dirs(metric_root)
    logger = NotebookLogger(dirs["reports"] / "error_log.txt")
    repo_path, clone_status = clone_repository(REPO_URL, dirs["workspace"], reuse=True)
    result = run_pipeline(repo_path, metric_root, logger)

    printable = {
        "clone_status": clone_status,
        "pipeline_success": result.get("pipeline_success"),
        "baseline_returncode": result["baseline_result"]["returncode"],
        "stryker_returncode": result["stryker_result"]["returncode"],
        "exported_paths": result["exported_paths"],
        "mutants_count": len(result["mutants_df"]),
        "mutator_types_count": len(result["mutator_types_df"]),
        "elapsed_ms": result["elapsed_ms"],
    }
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(printable, indent=2))
    print(result["summary_df"].to_string(index=False))
    return 0 if result.get("pipeline_success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
