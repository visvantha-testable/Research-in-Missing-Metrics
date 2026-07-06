"""Run PMD benchmark pipeline on java_nesting_benchmark."""
from __future__ import annotations

import json
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parent
METRIC_ROOT = TOOL_ROOT.parent
PROJECT_ROOT = METRIC_ROOT.parent.parent
sys.path.insert(0, str(TOOL_ROOT))

from run_pmd_benchmark_impl import configure_java_runtime, download_pmd, run_pipeline

BENCHMARK = METRIC_ROOT / "workspace" / "java_nesting_benchmark"
OUTPUT = METRIC_ROOT / "outputs"
PMD_HOME = PROJECT_ROOT / "runtimes" / "pmd-bin-7.0.0"
JDK_HOME = PROJECT_ROOT / "runtimes" / "jdk-21"
RULESET = "category/java/design.xml/AvoidDeeplyNestedIfStmts"

if __name__ == "__main__":
    configure_java_runtime(JDK_HOME)
    download_pmd(PMD_HOME, cache_dir=PROJECT_ROOT / "runtimes" / "cache")
    result = run_pipeline(BENCHMARK, OUTPUT, PMD_HOME, RULESET)
    print(json.dumps(result, indent=2))
    if not result.get("benchmark_ready"):
        sys.exit(1)
