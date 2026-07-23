"""Run JaCoCo Path Analysis Validation benchmark."""
from __future__ import annotations

import json
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent
METRIC_ROOT = TOOL_ROOT.parent
BENCHMARK = METRIC_ROOT / "workspace" / "java-tool-testing-jacoco"
OUTPUT = METRIC_ROOT / "outputs"

sys.path.insert(0, str(TOOL_ROOT))
from run_jacoco_path_analysis_benchmark_impl import run_pipeline

if __name__ == "__main__":
    if not BENCHMARK.exists():
        BENCHMARK = METRIC_ROOT.parent / "JaCoCo Coverage" / "workspace" / "java-tool-testing-jacoco"
    result = run_pipeline(BENCHMARK, OUTPUT)
    print(json.dumps(result, indent=2))
    if not result.get("benchmark_ready"):
        sys.exit(1)
