"""Run StyleCop code smells benchmark pipeline."""
from __future__ import annotations

import json
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent
METRIC_ROOT = TOOL_ROOT.parent
PROJECT_ROOT = METRIC_ROOT.parent.parent
sys.path.insert(0, str(TOOL_ROOT))

from run_code_smells_benchmark_impl import download_dotnet_sdk, run_pipeline

BENCHMARK = METRIC_ROOT / "workspace" / "cs_code_smells_benchmark"
OUTPUT = METRIC_ROOT / "outputs"
DOTNET_ROOT = PROJECT_ROOT / "runtimes" / "dotnet-sdk"

if __name__ == "__main__":
    download_dotnet_sdk(DOTNET_ROOT)
    result = run_pipeline(BENCHMARK, OUTPUT, DOTNET_ROOT)
    print(json.dumps(result, indent=2))
    if not result.get("benchmark_ready"):
        sys.exit(1)
