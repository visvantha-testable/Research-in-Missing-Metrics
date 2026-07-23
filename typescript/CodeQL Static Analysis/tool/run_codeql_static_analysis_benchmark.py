"""Execute CodeQL static analysis pipeline outside Jupyter."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _codeql_static_analysis_utils import (  # noqa: E402
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
        "exported_paths": result["exported_paths"],
        "total_findings": len(result["findings_df"]),
        "summary": result["summary"],
        "elapsed_ms": result["elapsed_ms"],
    }
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(printable, indent=2, default=str))
    return 0 if result.get("pipeline_success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
