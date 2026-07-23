"""NuGet Audit SCA benchmark runner implementation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from _nuget_audit_sca_utils import NotebookLogger, resolve_metric_root, run_pipeline


def main() -> int:
    metric_root = resolve_metric_root()
    output_dir = metric_root / "output"
    logger = NotebookLogger(output_dir / "error_log.txt")
    try:
        result = run_pipeline(metric_root, logger)
    except Exception as exc:
        logger.error(str(exc))
        logger.write_errors()
        print(json.dumps({"pipeline_success": False, "error": str(exc)}, indent=2))
        return 1

    printable = {
        "clone_status": result["clone_status"],
        "pipeline_success": result["pipeline_success"],
        "exported_paths": {key: str(path) for key, path in result["exported_paths"].items()},
        "summary": result["summary"],
        "metrics_with_supporting_evidence": result["summary"]["metrics_with_supporting_evidence"],
        "metrics_without_supporting_evidence": result["summary"]["metrics_without_supporting_evidence"],
    }
    logger.write_errors()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(printable, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
