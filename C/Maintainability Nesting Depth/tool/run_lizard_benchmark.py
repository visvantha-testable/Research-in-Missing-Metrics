"""Run Lizard benchmark pipeline on c_nesting_benchmark for validation."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent
METRIC_ROOT = TOOL_ROOT.parent
BENCHMARK = METRIC_ROOT / "workspace" / "c_nesting_benchmark"
OUTPUT = METRIC_ROOT / "outputs"


def load_notebook_utils():
    spec_path = TOOL_ROOT / "run_lizard_benchmark_impl.py"
    if not spec_path.exists():
        raise FileNotFoundError("Helper module missing")
    spec = importlib.util.spec_from_file_location("lizard_impl", spec_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    sys.path.insert(0, str(TOOL_ROOT))
    from run_lizard_benchmark_impl import run_pipeline

    result = run_pipeline(BENCHMARK, OUTPUT)
    print(json.dumps(result, indent=2))
    if not result.get("benchmark_ready"):
        sys.exit(1)
