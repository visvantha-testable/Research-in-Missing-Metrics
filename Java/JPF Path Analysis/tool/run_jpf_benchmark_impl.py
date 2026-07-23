"""Java PathFinder benchmark helpers."""
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
    configure_java_runtime,
    detect_build_tool,
    discover_java_files,
    ensure_output_dir,
    java_version_text,
    resolve_repository_path,
)
from _jpf_notebook_utils import (  # noqa: E402
    JpfNotebookLogger,
    build_class_summary,
    build_dashboard_table,
    build_java_inventory,
    build_repository_metrics,
    compute_repository_summary,
    copy_generated_jpf_artifacts,
    ensure_jpf_installed,
    execute_compile_only,
    execute_jpf_for_classes,
    extract_verbatim_sections,
    save_java_inventory,
    validate_path_metrics,
    write_project_jpf_properties,
    discover_compiled_classpath_dirs,
    discover_sourcepath_dirs,
)


def run_pipeline(repo_path: Path, output_dir: Path, workspace_dir: Path) -> dict:
    repo = repo_path.resolve()
    output = output_dir.resolve()
    workspace = workspace_dir.resolve()
    ensure_output_dir(output)
    logger = JpfNotebookLogger(output / "error_log.txt")
    java_env = configure_java_runtime(logger)
    java_version = java_version_text(java_env)

    build_tool = detect_build_tool(repo)
    java_files = discover_java_files(repo)
    if not java_files:
        raise FileNotFoundError(f"No Java files found in {repo}")

    java_classes = build_java_inventory(java_files)
    repo_stats = compute_repository_summary(repo, java_classes, build_tool, java_version)
    pd.DataFrame([repo_stats]).to_csv(output / "repository_summary.csv", index=False)
    save_java_inventory(java_classes, output / "java_files_inventory.csv")

    started = time.perf_counter()
    build_result, build_console = execute_compile_only(repo, build_tool, java_env, logger)

    jpf_install = ensure_jpf_installed(java_env, logger, workspace)
    classpath_dirs = discover_compiled_classpath_dirs(repo)
    source_dirs = discover_sourcepath_dirs(repo)
    write_project_jpf_properties(repo, classpath_dirs, source_dirs)

    jpf_config_dir = output / "jpf_configs"
    if jpf_install.build_success:
        jpf_runs, jpf_console = execute_jpf_for_classes(
            jpf_install,
            java_classes,
            classpath_dirs,
            source_dirs,
            java_env,
            logger,
            jpf_config_dir,
        )
        raw_console = build_console + "\n" + jpf_console
    else:
        jpf_runs = []
        raw_console = build_console

    total_execution_time = round(time.perf_counter() - started, 5)
    (output / "jpf_console_output.txt").write_text(raw_console, encoding="utf-8")

    section_artifacts = extract_verbatim_sections(raw_console, output)
    copied_artifacts = copy_generated_jpf_artifacts([jpf_config_dir, repo], output)

    metric_rows = [metric for run in jpf_runs for metric in run.metrics]
    metrics_df = pd.DataFrame(metric_rows)
    if metrics_df.empty:
        metrics_df = pd.DataFrame(columns=["metric_name", "metric_value", "source_class", "method"])
    metrics_df.to_csv(output / "jpf_metrics.csv", index=False)

    path_validation_df = validate_path_metrics(raw_console, "jpf_console_output.txt")
    path_validation_df.to_csv(output / "path_validation.csv", index=False)

    class_summary_df = build_class_summary(jpf_runs)
    class_summary_df.to_csv(output / "class_summary.csv", index=False)

    repository_metrics_df = build_repository_metrics(java_classes, jpf_runs, total_execution_time)
    repository_metrics_df.to_csv(output / "repository_metrics.csv", index=False)

    dashboard_df = build_dashboard_table(repo_stats, class_summary_df, repository_metrics_df)
    dashboard_df.to_csv(output / "dashboard.csv", index=False)

    supported_count = int((path_validation_df["Supported"] == "Supported").sum())
    no_evidence_count = int((path_validation_df["Supported"] == "No Evidence Found").sum())

    return {
        "benchmark_ready": jpf_install.build_success and build_result.exit_code == 0 and len(jpf_runs) > 0,
        "build_tool": build_tool,
        "java_files": len(java_files),
        "classes_with_main": sum(1 for item in java_classes if item.has_main),
        "classes_executed": len(jpf_runs),
        "path_metrics_supported": supported_count,
        "path_metrics_no_evidence": no_evidence_count,
        "jpf_metrics_rows": len(metrics_df),
        "section_artifacts": section_artifacts,
        "copied_artifacts": copied_artifacts,
        "execution_time_seconds": total_execution_time,
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
