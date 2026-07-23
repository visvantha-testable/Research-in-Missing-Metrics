"""Static DU benchmark helpers."""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

TOOL_ROOT = Path(__file__).resolve().parent
JACOCO_TOOL_ROOT = TOOL_ROOT.parent.parent / "JaCoCo Coverage" / "tool"
for path in (str(TOOL_ROOT), str(JACOCO_TOOL_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from _jacoco_notebook_utils import (  # noqa: E402
    NotebookLogger,
    compute_repository_stats,
    configure_java_runtime,
    detect_build_tool,
    discover_java_files,
    ensure_output_dir,
    java_version_text,
    save_java_inventory,
)
from _static_du_notebook_utils import (  # noqa: E402
    collect_outputs,
    execute_static_du,
    preserve_static_du_artifacts,
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
    status, raw_console = execute_static_du(repo, java_env, logger, skip_verify=True)
    total_execution_time = round(time.perf_counter() - started, 5)
    (output / "static_du_console_output.txt").write_text(raw_console, encoding="utf-8")
    copied = preserve_static_du_artifacts(status, output, repo)

    parsed = collect_outputs(status, repo, java_files, output, total_execution_time)
    if parsed["definitions_df"].empty:
        logger.error(
            "Static DU did not emit per-definition records; only aggregate definition counts are present in JSON.",
            step="parse_definitions",
        )

    supported_count = int((parsed["metrics_df"]["Supported"] == "Supported").sum())
    directly_emitted_count = int((parsed["metrics_df"]["Directly Emitted"] == "Yes").sum())

    return {
        "benchmark_ready": status.build_success and status.run_success and copied.get("static_du_output.json", False),
        "build_tool": build_tool,
        "java_files": len(java_files),
        "du_pairs_extracted": len(parsed["du_pairs_df"]),
        "definitions_extracted": len(parsed["definitions_df"]),
        "data_flow_metrics_supported": supported_count,
        "data_flow_metrics_directly_emitted": directly_emitted_count,
        "execution_time_seconds": total_execution_time,
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
