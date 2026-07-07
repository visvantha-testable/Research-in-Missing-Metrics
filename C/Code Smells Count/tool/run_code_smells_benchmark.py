"""Run Cppcheck code smells benchmark pipeline."""
from __future__ import annotations

import json
import sys
from pathlib import Path
"""hii"""
TOOL_ROOT = Path(__file__).resolve().parent
METRIC_ROOT = TOOL_ROOT.parent
PROJECT_ROOT = METRIC_ROOT.parent.parent
BENCHMARK = METRIC_ROOT / "workspace" / "c_code_smells_benchmark"
OUTPUT = METRIC_ROOT / "outputs"

if __name__ == "__main__":
    sys.path.insert(0, str(TOOL_ROOT))
    from run_code_smells_benchmark_impl import run_pipeline

    result = run_pipeline(BENCHMARK, OUTPUT, PROJECT_ROOT)
    print(json.dumps(result, indent=2))
    if not result.get("benchmark_ready"):
        sys.exit(1)
