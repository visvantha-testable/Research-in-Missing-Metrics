"""Run Java PathFinder benchmark pipeline."""
from __future__ import annotations

import json
from pathlib import Path

from run_jpf_benchmark_impl import run_pipeline

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO = ROOT / "workspace" / "java-tool-testing-jacoco"
FALLBACK_REPO = ROOT.parent / "JaCoCo Coverage" / "workspace" / "java-tool-testing-jacoco"
OUTPUT_DIR = ROOT / "outputs"
WORKSPACE_DIR = ROOT / "workspace"


def main() -> None:
    repo_path = DEFAULT_REPO if DEFAULT_REPO.exists() else FALLBACK_REPO
    if not repo_path.exists():
        raise FileNotFoundError(
            f"No benchmark repository found. Expected {DEFAULT_REPO} or {FALLBACK_REPO}."
        )
    result = run_pipeline(repo_path, OUTPUT_DIR, WORKSPACE_DIR)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
