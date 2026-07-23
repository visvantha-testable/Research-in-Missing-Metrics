"""PyMCDC MC/DC Coverage benchmark execution helpers."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

TOOL_ROOT = Path(__file__).resolve().parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from _pymcdc_notebook_utils import (  # noqa: E402
    NotebookLogger,
    build_file_summary_rows,
    build_metrics_rows,
    build_repository_summary_row,
    compute_repository_stats,
    detect_pymcdc_cli,
    discover_python_files,
    ensure_output_dir,
    export_parsed_json,
    export_parsed_xml,
    install_repository_requirements,
    run_pymcdc_on_repository,
    save_python_inventory,
    save_repository_summary,
)


def run_pipeline(repo_path: Path, output_dir: Path) -> dict:
    repo = repo_path.resolve()
    output = output_dir.resolve()
    ensure_output_dir(output)
    logger = NotebookLogger(output / "error_log.txt")
    cli_prefix = detect_pymcdc_cli(logger)

    python_files = discover_python_files(repo)
    if not python_files:
        raise FileNotFoundError(f"No Python files found in {repo}")

    repo_stats = compute_repository_stats(repo, python_files)
    save_repository_summary(repo_stats, output / "repository_summary.csv")
    save_python_inventory(python_files, output / "python_files_inventory.csv")
    install_repository_requirements(repo, logger)

    file_results, raw_console, total_execution_time = run_pymcdc_on_repository(
        cli_prefix, python_files, logger
    )
    (output / "pymcdc_raw_console_output.txt").write_text(raw_console, encoding="utf-8")

    metrics_df = pd.DataFrame(
        build_metrics_rows(file_results),
        columns=["metric_name", "metric_value", "file", "function"],
    )
    metrics_df.to_csv(output / "pymcdc_metrics.csv", index=False)

    file_summary_df = pd.DataFrame(build_file_summary_rows(file_results))
    file_summary_df.to_csv(output / "pymcdc_file_summary.csv", index=False)

    repo_summary = build_repository_summary_row(repo_stats, file_results, total_execution_time)
    pd.DataFrame([repo_summary]).to_csv(output / "pymcdc_repository_summary.csv", index=False)
    export_parsed_json(file_results, repo_summary, output / "pymcdc_output.json")
    export_parsed_xml(file_results, repo_summary, output / "pymcdc_output.xml")

    logic_rows = file_summary_df[
        file_summary_df["file"].str.replace("\\", "/").str.endswith("sample_subject/logic.py")
    ]
    logic_decisions = int(logic_rows["decisions"].iloc[0]) if not logic_rows.empty else 0
    logic_requirements = 0
    for result in file_results:
        if result.file_path.replace("\\", "/").endswith("sample_subject/logic.py"):
            logic_requirements = result.total_requirements
            break

    total_requirements = sum(result.total_requirements for result in file_results)
    covered_requirements = sum(result.covered_requirements for result in file_results)

    return {
        "benchmark_ready": len(python_files) > 0 and repo_summary["Total Decisions"] > 0 and logic_decisions == 3,
        "python_files": len(python_files),
        "total_decisions": int(repo_summary["Total Decisions"]),
        "total_requirements": total_requirements,
        "covered_requirements": covered_requirements,
        "logic_file_decisions": logic_decisions,
        "logic_file_requirements": logic_requirements,
        "mcdc_coverage_percent": repo_summary["MC/DC Coverage %"],
        "execution_time_seconds": total_execution_time,
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
