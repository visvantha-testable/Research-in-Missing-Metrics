"""Run ESLint Parameter Count benchmark pipeline (JavaScript)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent
METRIC_ROOT = TOOL_ROOT.parent
BENCHMARK = METRIC_ROOT / "workspace" / "parameter_count_benchmark"
OUTPUT = METRIC_ROOT / "outputs"

sys.path.insert(0, str(TOOL_ROOT))
from run_parameter_count_benchmark_impl import resolve_project_root, run_pipeline

if __name__ == "__main__":
    result = run_pipeline(BENCHMARK, OUTPUT, resolve_project_root(METRIC_ROOT))
    print(json.dumps(result, indent=2))
    if not result.get("benchmark_ready"):
        sys.exit(1)
