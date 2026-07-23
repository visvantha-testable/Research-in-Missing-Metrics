"""Run Static DU benchmark pipeline."""
from __future__ import annotations

import json
from pathlib import Path

from run_static_du_benchmark_impl import run_pipeline

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO = ROOT / "workspace" / "java-tool-testing-static-du"
OUTPUT_DIR = ROOT / "outputs"


def main() -> None:
    if not DEFAULT_REPO.exists():
        raise FileNotFoundError(f"Benchmark repository not found: {DEFAULT_REPO}")
    result = run_pipeline(DEFAULT_REPO, OUTPUT_DIR)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
