"""Run Dependabot extraction benchmark against the local training repository."""
from __future__ import annotations

import json
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent
METRIC_ROOT = TOOL_ROOT.parent
BENCHMARK = METRIC_ROOT / "workspace" / "typescript-tool-testing-dependabot"
OUTPUT = METRIC_ROOT / "outputs"

sys.path.insert(0, str(TOOL_ROOT))
from run_dependabot_benchmark_impl import run_benchmark  # noqa: E402

if __name__ == "__main__":
    result = run_benchmark(BENCHMARK, OUTPUT)
    print(json.dumps(result, indent=2))
    if not result.get("benchmark_ready"):
        sys.exit(1)
