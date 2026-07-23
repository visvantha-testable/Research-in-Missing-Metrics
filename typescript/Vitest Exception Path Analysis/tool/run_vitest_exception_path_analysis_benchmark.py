"""Execute Vitest Exception Path Analysis pipeline outside Jupyter."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _vitest_exception_path_analysis_utils import (  # noqa: E402
    REPO_URL,
    build_exception_evidence_dataframe,
    build_execution_summary,
    build_metric_mapping,
    clone_repository,
    collect_coverage_artifacts,
    collect_environment,
    detect_test_configuration,
    ensure_dirs,
    ensure_vitest_packages,
    extract_coverage_metrics,
    load_taxonomy_metrics,
    locate_coverage_dir,
    npm_install,
    read_text,
    resolve_metric_root,
    run_command,
)


def main() -> int:
    metric_root = resolve_metric_root()
    dirs = ensure_dirs(metric_root)
    artifacts = dirs["artifacts"]
    repo_path, clone_status = clone_repository(REPO_URL, dirs["workspace"], reuse=True)
    os.chdir(repo_path)

    env = collect_environment(repo_path)
    install = npm_install(repo_path)
    packages = ensure_vitest_packages(repo_path)
    config = detect_test_configuration(repo_path)

    test_result = run_command(config["test_command"].split(), repo_path, "vitest test run")
    (artifacts / "raw_vitest_output.txt").write_text(test_result["terminal_output"], encoding="utf-8")

    coverage_result = run_command(config["coverage_command"].split(), repo_path, "vitest coverage run")
    (artifacts / "raw_coverage_output.txt").write_text(coverage_result["terminal_output"], encoding="utf-8")

    coverage_dir = locate_coverage_dir(repo_path, config.get("vitest_config_files", []))
    artifact_info = collect_coverage_artifacts(coverage_dir, artifacts)

    summary_raw = read_text(artifacts / "coverage-summary.json")
    final_raw = read_text(artifacts / "coverage-final.json")
    lcov_raw = read_text(artifacts / "lcov.info")

    taxonomy_raw = read_text(artifacts / "taxonomy_metrics.json")
    taxonomy_metrics = load_taxonomy_metrics(artifacts / "taxonomy_metrics.json")

    evidence_df = build_exception_evidence_dataframe(
        {
            "raw_vitest_output.txt": test_result["terminal_output"],
            "raw_coverage_output.txt": coverage_result["terminal_output"],
            "coverage-summary.json": summary_raw,
            "coverage-final.json": final_raw,
            "lcov.info": lcov_raw,
            "taxonomy_metrics.json": taxonomy_raw,
        }
    )
    evidence_df.to_csv(artifacts / "exception_path_analysis.csv", index=False)

    metrics_df = extract_coverage_metrics(artifacts / "coverage-summary.json")
    mapping_df = build_metric_mapping(
        evidence_df,
        metrics_df,
        test_result,
        coverage_result,
        artifact_info,
        taxonomy_metrics,
    )
    summary_df = build_execution_summary(
        REPO_URL,
        test_result,
        coverage_result,
        artifact_info,
        evidence_df,
        [
            "raw_vitest_output.txt",
            "raw_coverage_output.txt",
            "coverage-final.json",
            "coverage-summary.json",
            "lcov.info",
            "taxonomy_metrics.json",
            "exception_path_analysis.csv",
        ],
        "COMPLETED" if test_result["success"] and coverage_result["success"] else "COMPLETED WITH WARNINGS",
        taxonomy_metrics,
    )

    print(json.dumps({"clone_status": clone_status, "environment": env, "packages": packages.to_dict(orient="records")}, indent=2))
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(mapping_df.to_string(index=False))
    print(summary_df.to_string(index=False))
    return 0 if test_result["success"] and coverage_result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
