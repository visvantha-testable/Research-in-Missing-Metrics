"""Run Roslynator benchmark pipeline on cs_nesting_benchmark."""
from __future__ import annotations

import json
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent
METRIC_ROOT = TOOL_ROOT.parent
PROJECT_ROOT = METRIC_ROOT.parent.parent
sys.path.insert(0, str(TOOL_ROOT))

from run_roslynator_benchmark_impl import run_pipeline

BENCHMARK = METRIC_ROOT / "workspace" / "cs_nesting_benchmark"
OUTPUT = METRIC_ROOT / "outputs"
DOTNET_ROOT = PROJECT_ROOT / "runtimes" / "dotnet-sdk"
TOOLS_DIR = PROJECT_ROOT / "runtimes" / "dotnet-tools"

if __name__ == "__main__":
    result = run_pipeline(BENCHMARK, OUTPUT, DOTNET_ROOT, TOOLS_DIR)
    print(json.dumps(result, indent=2))
    if not result.get("benchmark_ready"):
        sys.exit(1)
