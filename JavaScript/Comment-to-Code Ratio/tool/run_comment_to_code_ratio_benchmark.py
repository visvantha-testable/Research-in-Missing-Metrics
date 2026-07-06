"""Run ESLint Comment-to-Code Ratio benchmark pipeline."""
from __future__ import annotations

import json
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent
METRIC_ROOT = TOOL_ROOT.parent

sys.path.insert(0, str(TOOL_ROOT))
from run_comment_to_code_ratio_benchmark_impl import resolve_project_root, run_pipeline

PROJECT_ROOT = resolve_project_root(METRIC_ROOT)
BENCHMARK = METRIC_ROOT / "workspace" / "comment_to_code_ratio_benchmark"
OUTPUT = METRIC_ROOT / "outputs"
RUNTIMES_ROOT = PROJECT_ROOT / "runtimes"

if __name__ == "__main__":
    result = run_pipeline(BENCHMARK, OUTPUT, RUNTIMES_ROOT)
    print(json.dumps(result, indent=2))
    if not result.get("benchmark_ready"):
        sys.exit(1)
