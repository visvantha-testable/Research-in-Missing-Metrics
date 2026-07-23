"""JaCoCo + Static DU combined validation benchmark."""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

TOOL_ROOT = Path(__file__).resolve().parent
for path in (
    str(TOOL_ROOT),
    str(TOOL_ROOT.parent.parent / "JaCoCo Coverage" / "tool"),
):
    if path not in sys.path:
        sys.path.insert(0, path)

from _jacoco_notebook_utils import (  # noqa: E402
    NotebookLogger,
    configure_java_runtime,
    detect_build_tool,
    discover_java_files,
    ensure_output_dir,
    java_version_text,
    save_java_inventory,
)
from _jacoco_static_du_validation_utils import (  # noqa: E402
    collect_all_outputs,
    execute_platform_triggers,
)


def run_pipeline(repo_path: Path, output_dir: Path, baseline_xml: Path | None = None) -> dict:
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

    save_java_inventory(java_files, output / "java_files_inventory.csv")

    started = time.perf_counter()
    status, jacoco_build_console, jacoco_trigger_console, static_du_console = execute_platform_triggers(
        repo, java_env, logger, skip_verify=True
    )
    parsed = collect_all_outputs(
        status,
        repo,
        java_files,
        build_tool,
        output,
        baseline_xml,
        jacoco_build_console,
        jacoco_trigger_console,
        static_du_console,
    )
    total_time = round(time.perf_counter() - started, 5)

    return {
        "benchmark_ready": (
            status.build_status.report_generated
            and status.jacoco_trigger_success
            and status.static_du_trigger_success
            and parsed["copied"].get("jacoco.xml", False)
        ),
        "build_tool": build_tool,
        "java_files": len(java_files),
        "control_flow_supported": int((parsed["control_flow_df"]["Supported"].isin(["Supported", "Partially Supported"])).sum()),
        "coverage_regression_supported": int((parsed["coverage_delta_df"]["Supported"].isin(["Supported", "Partially Supported"])).sum()),
        "data_flow_supported": int((parsed["data_flow_df"]["Supported"].isin(["Supported", "Partially Supported"])).sum()),
        "taxonomy_native_tier": int((parsed["taxonomy_truth_df"]["Coverage_Tier"] == "Native").sum()),
        "taxonomy_platform_derived_tier": int((parsed["taxonomy_truth_df"]["Coverage_Tier"] == "Platform_Derived").sum()),
        "taxonomy_not_supported_tier": int((parsed["taxonomy_truth_df"]["Coverage_Tier"] == "Not_Supported").sum()),
        "branch_percent_discrepancy": parsed["dashboard_df"].loc[
            parsed["dashboard_df"]["Metric"] == "Branch Percent Discrepancy", "Value"
        ].iloc[0]
        if "Branch Percent Discrepancy" in parsed["dashboard_df"]["Metric"].values
        else "Unknown",
        "execution_time_seconds": total_time,
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
