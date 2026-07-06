"""Run Roslynator Parameter Count benchmark pipeline."""
from __future__ import annotations

import json
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent
METRIC_ROOT = TOOL_ROOT.parent

sys.path.insert(0, str(TOOL_ROOT))
from run_parameter_count_benchmark_impl import resolve_project_root, run_pipeline

PROJECT_ROOT = resolve_project_root(METRIC_ROOT)
BENCHMARK = METRIC_ROOT / "workspace" / "parameter_count_benchmark"
OUTPUT = METRIC_ROOT / "outputs"
DOTNET_ROOT = PROJECT_ROOT / "runtimes" / "dotnet-sdk"
TOOLS_DIR = PROJECT_ROOT / "runtimes" / "dotnet-tools"

if __name__ == "__main__":
    result = run_pipeline(BENCHMARK, OUTPUT, DOTNET_ROOT, TOOLS_DIR)
    print(json.dumps(result, indent=2))
    if not result.get("benchmark_ready"):
        sys.exit(1)
