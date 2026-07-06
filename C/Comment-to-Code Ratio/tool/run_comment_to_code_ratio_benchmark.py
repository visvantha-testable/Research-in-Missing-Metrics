"""Run cloc Comment-to-Code Ratio benchmark pipeline."""
from __future__ import annotations

import json
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent
METRIC_ROOT = TOOL_ROOT.parent
PROJECT_ROOT = METRIC_ROOT.parent.parent
BENCHMARK = METRIC_ROOT / "workspace" / "comment_to_code_ratio_benchmark"
OUTPUT = METRIC_ROOT / "outputs"

sys.path.insert(0, str(TOOL_ROOT))
from run_comment_to_code_ratio_benchmark_impl import resolve_project_root, run_pipeline

if __name__ == "__main__":
    project_root = resolve_project_root(METRIC_ROOT)
    result = run_pipeline(BENCHMARK, OUTPUT, project_root)
    print(json.dumps(result, indent=2))
    if not result.get("benchmark_ready"):
        sys.exit(1)
