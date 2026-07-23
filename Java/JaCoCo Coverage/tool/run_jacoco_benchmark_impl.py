"""JaCoCo Coverage benchmark execution helpers."""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from _jacoco_notebook_utils import (  # noqa: E402
    NotebookLogger,
    collect_outputs,
    compute_repository_stats,
    configure_java_runtime,
    detect_build_tool,
    discover_java_files,
    ensure_output_dir,
    execute_build_and_jacoco,
    java_version_text,
    save_java_inventory,
)


def run_pipeline(repo_path: Path, output_dir: Path) -> dict:
    repo = repo_path.resolve()
    output = output_dir.resolve()
    ensure_output_dir(output)
    logger = NotebookLogger(output / "error_log.txt")
    java_env = configure_java_runtime(logger)
    java_version = java_version_text(java_env)

    build_tool = detect_build_tool(repo)
    java_files = discover_java_files(repo)
    if not java_files:
        raise FileNotFoundError(f"No Java files found in {repo}")

    repo_stats = compute_repository_stats(repo, java_files, build_tool, java_version)
    pd.DataFrame([repo_stats]).to_csv(output / "repository_summary.csv", index=False)
    save_java_inventory(java_files, output / "java_files_inventory.csv")

    started = time.perf_counter()
    build_status, raw_console = execute_build_and_jacoco(repo, build_tool, java_env, logger)
    total_execution_time = round(time.perf_counter() - started, 5)
    (output / "jacoco_console_output.txt").write_text(raw_console, encoding="utf-8")

    if not build_status.report_generated:
        return {
            "benchmark_ready": False,
            "reason": "JaCoCo report not generated",
            "repo_path": str(repo),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    parsed = collect_outputs(build_status, repo_stats, output, total_execution_time, logger)
    repository_metrics = parsed["repository_metrics"]

    return {
        "benchmark_ready": repository_metrics["Total Classes"] == 3 and repository_metrics["Line Coverage %"] == 100.0,
        "build_tool": build_tool,
        "java_files": len(java_files),
        "total_packages": repository_metrics["Total Packages"],
        "total_classes": repository_metrics["Total Classes"],
        "instruction_coverage_percent": repository_metrics["Instruction Coverage %"],
        "branch_coverage_percent": repository_metrics["Branch Coverage %"],
        "line_coverage_percent": repository_metrics["Line Coverage %"],
        "method_coverage_percent": repository_metrics["Method Coverage %"],
        "class_coverage_percent": repository_metrics["Class Coverage %"],
        "complexity_coverage_percent": repository_metrics["Complexity Coverage %"],
        "execution_time_seconds": total_execution_time,
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
