"""JaCoCo Path Analysis Validation benchmark helpers."""
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
    execute_build_and_jacoco,
    java_version_text,
    save_java_inventory,
)
from _jacoco_path_analysis_utils import (  # noqa: E402
    copy_raw_jacoco_artifacts,
    dump_jacoco_xml_nodes,
    search_path_keywords,
    validate_path_metrics,
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

    copied = copy_raw_jacoco_artifacts(build_status, output)
    xml_dump = dump_jacoco_xml_nodes(output / "jacoco.xml", output / "jacoco_xml_dump.csv")
    artifacts = {
        "jacoco_console_output.txt": output / "jacoco_console_output.txt",
        "jacoco.xml": output / "jacoco.xml",
        "jacoco.csv": output / "jacoco.csv",
        "index.html": output / "index.html",
        "jacoco.exec": output / "jacoco.exec",
    }
    keyword_df = search_path_keywords(artifacts)
    keyword_df.to_csv(output / "path_keyword_search.csv", index=False)
    validation_df = validate_path_metrics(keyword_df, artifacts, output / "jacoco.xml")
    validation_df.to_csv(output / "path_metric_validation.csv", index=False)

    supported_count = int((validation_df["Supported"] == "Supported").sum())
    not_supported_count = int((validation_df["Supported"] == "Not Supported").sum())

    return {
        "benchmark_ready": copied["jacoco.xml"] and len(xml_dump) > 0 and not_supported_count == 10,
        "build_tool": build_tool,
        "java_files": len(java_files),
        "xml_nodes_dumped": len(xml_dump),
        "path_keywords_found": int((keyword_df["Found (Yes/No)"] == "Yes").sum()),
        "path_metrics_supported": supported_count,
        "path_metrics_not_supported": not_supported_count,
        "execution_time_seconds": total_execution_time,
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
