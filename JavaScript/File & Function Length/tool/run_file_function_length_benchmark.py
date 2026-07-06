"""Run Lizard File & Function Length benchmark pipeline (JavaScript)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent
METRIC_ROOT = TOOL_ROOT.parent
BENCHMARK = METRIC_ROOT / "workspace" / "file_function_length_benchmark"
OUTPUT = METRIC_ROOT / "outputs"

sys.path.insert(0, str(TOOL_ROOT))
from run_file_function_length_benchmark_impl import run_pipeline

if __name__ == "__main__":
    result = run_pipeline(BENCHMARK, OUTPUT)
    print(json.dumps(result, indent=2))
    if not result.get("benchmark_ready"):
        sys.exit(1)
