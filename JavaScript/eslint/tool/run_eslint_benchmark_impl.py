"""Execute ESLint extraction pipeline outside Jupyter."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _eslint_utils import NotebookLogger, resolve_metric_root, run_pipeline  # noqa: E402


def main() -> int:
    metric_root = resolve_metric_root()
    output_dir = metric_root / "outputs"
    logger = NotebookLogger(output_dir / "error_log.txt")
    try:
        result = run_pipeline(
            metric_root,
            use_git_url=True,
            repo_url="https://github.com/visvantha-testable/javascript-testing-eslint.git",
            local_repo_path=str(metric_root / "workspace" / "javascript-testing-eslint"),
            workspace_dir=metric_root / "workspace",
            output_dir=output_dir,
            if_clone_exists="reuse",
            logger=logger,
        )
    except Exception as exc:
        logger.error(str(exc))
        logger.write_errors()
        print(json.dumps({"pipeline_success": False, "error": str(exc)}, indent=2))
        return 1

    printable = {
        "pipeline_success": result["pipeline_success"],
        "execution_status": result["execution_status"],
        "clone_status": result["clone_status"],
        "summary": result["summary"],
        "eslint_config": str(result["eslint_config"]) if result["eslint_config"] else "",
        "exported_paths": {key: str(path) for key, path in result["exported_paths"].items()},
    }
    logger.write_errors()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(json.dumps(printable, indent=2, default=str))
    return 0 if result["pipeline_success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
