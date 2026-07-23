"""Static DU raw output extraction helpers."""
from __future__ import annotations

import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

TOOL_ROOT = Path(__file__).resolve().parent
JACOCO_TOOL_ROOT = TOOL_ROOT.parent.parent / "JaCoCo Coverage" / "tool"
if str(JACOCO_TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(JACOCO_TOOL_ROOT))

from _jacoco_notebook_utils import (  # noqa: E402
    CommandResult,
    NotebookLogger,
    combine_streams,
    compute_repository_stats,
    detect_build_tool,
    discover_java_files,
    ensure_output_dir,
    extract_package_name,
    resolve_gradle_command,
    resolve_maven_command,
    run_shell_command,
    save_java_inventory,
)

DATA_FLOW_METRICS = [
    "Variable Definition Detection",
    "Definition-Use Mapping",
    "Coverage Measurement",
    "Uncovered Definition Detection",
    "Variable Use Detection",
]

METRIC_EVIDENCE_KEYS: dict[str, list[str]] = {
    "Variable Definition Detection": [
        "definitions_total",
        "definitions_covered",
        "all_defs_percent",
        "all_defs_coverage_score",
    ],
    "Definition-Use Mapping": [
        "du_paths",
        "du_pairs_total",
        "du_pairs_covered",
        "data_path_correlation_percent",
        "data_path_correlation_score",
    ],
    "Coverage Measurement": [
        "du_path_percent",
        "all_uses_percent",
        "all_defs_percent",
        "du_path_validation_score",
    ],
    "Uncovered Definition Detection": [
        "uncovered_definitions",
        "dead_data_identification_score",
    ],
    "Variable Use Detection": [
        "uses_total",
        "uses_covered",
        "c_use_total",
        "p_use_total",
        "all_uses_percent",
        "all_uses_coverage_score",
    ],
}

DERIVED_SCORE_KEYS = {
    "dead_data_identification_score",
    "all_defs_coverage_score",
    "data_path_correlation_score",
    "du_path_validation_score",
    "all_uses_coverage_score",
}

STATIC_DU_MAIN_CLASS = "com.testable.training.platform.StaticDuTrigger"
STATIC_DU_PLATFORM_DIR = "static-du-platform"

USE_TYPE_MAP = {
    "computational": "C-Use",
    "return": "C-Use",
    "predicate": "P-Use",
    "c-use": "C-Use",
    "p-use": "P-Use",
}

CLASS_NAME_RE = re.compile(r"(?:public\s+)?(?:final\s+)?class\s+(\w+)")
METHOD_RE = re.compile(r"(?:public|private|protected)\s+[\w<>,\s\[\]]+\s+(\w+)\s*\(")


@dataclass
class StaticDuRunStatus:
    command: list[str]
    build_command: list[str]
    build_result: CommandResult | None
    run_result: CommandResult | None
    build_success: bool = False
    run_success: bool = False
    static_du_json: Path | None = None
    static_du_summary_json: Path | None = None
    du_path_correlation_json: Path | None = None
    static_du_meta_json: Path | None = None


def detect_static_du_platform(repo_path: Path) -> Path | None:
    platform = repo_path / STATIC_DU_PLATFORM_DIR
    if (platform / "pom.xml").exists():
        return platform.resolve()
    for pom in repo_path.rglob("pom.xml"):
        if pom.parent.name == STATIC_DU_PLATFORM_DIR:
            return pom.parent.resolve()
    return None


def resolve_static_du_command(repo_path: Path, logger: NotebookLogger, skip_verify: bool = False) -> list[str]:
    platform = detect_static_du_platform(repo_path)
    if platform is None:
        raise FileNotFoundError(
            f"No {STATIC_DU_PLATFORM_DIR} module found in repository. Cannot execute Static DU trigger."
        )
    maven = resolve_maven_command(repo_path, logger)
    command = [
        *maven,
        "-pl",
        STATIC_DU_PLATFORM_DIR,
        "exec:java",
        f"-Dexec.mainClass={STATIC_DU_MAIN_CLASS}",
    ]
    if skip_verify:
        command.append("-Dexec.args=--skip-verify")
    return command


def execute_build_only(
    repo_path: Path,
    build_tool: str,
    env: dict[str, str],
    logger: NotebookLogger,
) -> CommandResult:
    if build_tool == "Maven":
        command = [*resolve_maven_command(repo_path, logger), "clean", "compile"]
        platform = detect_static_du_platform(repo_path)
        if platform is not None:
            command = [*resolve_maven_command(repo_path, logger), "clean", "compile", "-pl", STATIC_DU_PLATFORM_DIR, "-am"]
    else:
        command = [*resolve_gradle_command(repo_path, logger), "clean", "build", "-x", "test"]
    return run_shell_command(command, repo_path, env, logger, "build")


def execute_static_du(
    repo_path: Path,
    env: dict[str, str],
    logger: NotebookLogger,
    skip_verify: bool = True,
) -> tuple[StaticDuRunStatus, str]:
    chunks: list[str] = []
    status = StaticDuRunStatus(command=[], build_command=[], build_result=None, run_result=None)
    build_tool = detect_build_tool(repo_path)

    if build_tool == "Maven":
        build_command = [*resolve_maven_command(repo_path, logger), "clean", "compile"]
        if detect_static_du_platform(repo_path) is not None:
            build_command = [
                *resolve_maven_command(repo_path, logger),
                "clean",
                "compile",
                "-pl",
                STATIC_DU_PLATFORM_DIR,
                "-am",
            ]
    else:
        build_command = [*resolve_gradle_command(repo_path, logger), "clean", "build", "-x", "test"]
    status.build_command = build_command
    build_result = run_shell_command(build_command, repo_path, env, logger, "build")
    status.build_result = build_result
    status.build_success = build_result.exit_code == 0
    chunks.append(f"===== {' '.join(build_result.command)} =====")
    chunks.append(combine_streams(build_result.stdout, build_result.stderr))

    try:
        status.command = resolve_static_du_command(repo_path, logger, skip_verify=skip_verify)
    except FileNotFoundError as exc:
        logger.error(str(exc), step="static_du_detect")
        return status, "\n".join(chunks)

    run_result = run_shell_command(status.command, repo_path, env, logger, "static_du_run")
    status.run_result = run_result
    status.run_success = run_result.exit_code == 0
    chunks.append(f"===== {' '.join(status.command)} =====")
    chunks.append(combine_streams(run_result.stdout, run_result.stderr))

    status.static_du_json = repo_path / "static_du.json"
    status.static_du_summary_json = repo_path / "artifacts" / "training" / "static_du_summary.json"
    status.du_path_correlation_json = repo_path / "artifacts" / "training" / "du_path_correlation.json"
    status.static_du_meta_json = repo_path / "artifacts" / "training" / "static_du_meta.json"
    return status, "\n".join(chunks)


def copy_artifact(source: Path | None, destination: Path) -> bool:
    if source is None or not source.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return True


def preserve_static_du_artifacts(status: StaticDuRunStatus, output_dir: Path, repo_path: Path | None = None) -> dict[str, bool]:
    ensure_output_dir(output_dir)
    copied = {
        "static_du_output.json": copy_artifact(status.static_du_json, output_dir / "static_du_output.json"),
        "static_du_summary": copy_artifact(
            status.static_du_summary_json,
            output_dir / "static_du_summary_copy.json",
        ),
    }
    if repo_path is not None:
        for pattern in ("static_du*.xml", "static_du*.csv", "*static_du*.xml", "*static_du*.csv"):
            for source in repo_path.rglob(pattern.split("/")[-1]):
                if not source.is_file():
                    continue
                suffix = source.suffix.lower()
                if suffix == ".xml":
                    copied["static_du_output.xml"] = copy_artifact(source, output_dir / "static_du_output.xml")
                elif suffix == ".csv":
                    copied["static_du_output.csv"] = copy_artifact(source, output_dir / "static_du_output.csv")
    return copied


def load_json_map(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def merged_summary_payload(repo_path: Path, output_dir: Path) -> dict[str, Any]:
    candidates = [
        output_dir / "static_du_output.json",
        repo_path / "static_du.json",
        repo_path / "artifacts" / "training" / "static_du_summary.json",
        repo_path / "artifacts" / "training" / "du_path_correlation.json",
    ]
    merged: dict[str, Any] = {}
    for path in candidates:
        if not path.exists():
            continue
        payload = load_json_map(path)
        if "supplemental_raw_data" in payload:
            supplemental = payload.get("supplemental_raw_data", {})
            if isinstance(supplemental, dict):
                summary = supplemental.get("static_du_summary", {})
                if isinstance(summary, dict):
                    merged.update(summary)
                correlation = supplemental.get("du_path_correlation", {})
                if isinstance(correlation, dict):
                    for key, value in correlation.items():
                        merged.setdefault(key, value)
        if "summary" in payload and isinstance(payload["summary"], dict):
            merged.update(payload["summary"])
        if "definitions_total" in payload:
            merged.update(payload)
        if "du_paths" in payload and "du_paths" not in merged:
            merged["du_paths"] = payload["du_paths"]
    return merged


def map_use_type(raw_value: str) -> str:
    normalized = raw_value.strip().lower()
    return USE_TYPE_MAP.get(normalized, raw_value)


def extract_class_name(java_path: Path) -> str:
    try:
        text = java_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return java_path.stem
    match = CLASS_NAME_RE.search(text)
    return match.group(1) if match else java_path.stem


def find_java_file_by_name(repo_path: Path, file_name: str) -> Path | None:
    for path in repo_path.rglob(file_name):
        if any(part in {".git", "target", "build"} for part in path.parts):
            continue
        return path.resolve()
    return None


def extract_variable_definitions(summary: dict[str, Any], repo_path: Path) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    definitions = summary.get("definitions")
    if isinstance(definitions, list):
        for item in definitions:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "file": str(item.get("file", "")),
                    "class": str(item.get("class", "")),
                    "method": str(item.get("method", "")),
                    "variable": str(item.get("variable", "")),
                    "definition_line": str(item.get("definition_line", item.get("line", ""))),
                    "definition_type": str(item.get("definition_type", item.get("type", ""))),
                }
            )
    return pd.DataFrame(
        rows,
        columns=["file", "class", "method", "variable", "definition_line", "definition_type"],
    )


def extract_definition_use_pairs(summary: dict[str, Any], repo_path: Path) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    du_paths = summary.get("du_paths", [])
    if not isinstance(du_paths, list):
        return pd.DataFrame(
            columns=[
                "file",
                "class",
                "method",
                "variable",
                "definition_line",
                "use_line",
                "use_type",
                "du_pair",
            ]
        )

    for item in du_paths:
        if not isinstance(item, dict):
            continue
        file_name = str(item.get("file", ""))
        variable = str(item.get("variable", ""))
        use_line = str(item.get("line", ""))
        emitted_use_type = str(item.get("use_type", ""))
        mapped_use_type = map_use_type(emitted_use_type)
        java_path = find_java_file_by_name(repo_path, file_name) if file_name else None
        class_name = extract_class_name(java_path) if java_path else ""
        du_pair = f"{variable}@{use_line}" if variable and use_line else variable
        rows.append(
            {
                "file": file_name,
                "class": class_name,
                "method": "",
                "variable": variable,
                "definition_line": "",
                "use_line": use_line,
                "use_type": mapped_use_type,
                "du_pair": du_pair,
            }
        )
    return pd.DataFrame(rows)


def collect_metric_evidence(summary: dict[str, Any], unified_json: dict[str, Any]) -> dict[str, list[str]]:
    evidence: dict[str, list[str]] = {metric: [] for metric in DATA_FLOW_METRICS}
    for key, value in summary.items():
        for metric, keys in METRIC_EVIDENCE_KEYS.items():
            if key in keys:
                evidence[metric].append(f"{key}={value}")
    metrics_rows = unified_json.get("metrics", [])
    if isinstance(metrics_rows, list):
        for row in metrics_rows:
            if not isinstance(row, dict):
                continue
            l5 = str(row.get("l5_metric", ""))
            if l5 in evidence:
                for field in ("covered", "score", "value", "formula"):
                    if field in row:
                        evidence[l5].append(f"{field}={row[field]}")
    return evidence


def validate_data_flow_metrics(summary: dict[str, Any], unified_json: dict[str, Any]) -> pd.DataFrame:
    evidence_map = collect_metric_evidence(summary, unified_json)
    rows: list[dict[str, str]] = []
    for metric in DATA_FLOW_METRICS:
        evidence_parts = evidence_map.get(metric, [])
        directly_emitted = any(
            part.split("=", 1)[0] not in DERIVED_SCORE_KEYS
            for part in evidence_parts
            if "=" in part
        )
        derived = any(
            part.split("=", 1)[0] in DERIVED_SCORE_KEYS
            for part in evidence_parts
            if "=" in part
        )
        if evidence_parts:
            supported = "Supported"
            evidence = " | ".join(evidence_parts[:6])
        else:
            supported = "Not Supported"
            evidence = ""
        rows.append(
            {
                "Metric": metric,
                "Supported": supported,
                "Directly Emitted": "Yes" if directly_emitted else "No",
                "Derived": "Yes" if derived and not directly_emitted else ("Yes" if derived else "No"),
                "Evidence": evidence,
            }
        )
    return pd.DataFrame(rows)


def build_repository_metrics(
    java_files: list[Path],
    summary: dict[str, Any],
    du_pairs_df: pd.DataFrame,
    execution_time: float,
) -> pd.DataFrame:
    classes = {extract_class_name(path) for path in java_files}
    c_uses = int((du_pairs_df["use_type"] == "C-Use").sum()) if not du_pairs_df.empty else int(summary.get("c_use_total", 0) or 0)
    p_uses_reported = int(summary.get("p_use_total", 0) or 0)
    p_uses_pairs = int((du_pairs_df["use_type"] == "P-Use").sum()) if not du_pairs_df.empty else 0
    files_emitted = summary.get("files", [])
    total_classes = len(files_emitted) if isinstance(files_emitted, list) and files_emitted else len(classes)
    return pd.DataFrame(
        [
            {
                "Total Java Files": len(java_files),
                "Total Classes": total_classes,
                "Total Methods": "",
                "Total Variable Definitions": int(summary.get("definitions_total", 0) or 0),
                "Total Variable Uses": int(summary.get("uses_total", 0) or 0),
                "Total DU Pairs": int(summary.get("du_pairs_total", 0) or 0),
                "Total C-Uses": c_uses if c_uses else int(summary.get("c_use_total", 0) or 0),
                "Total P-Uses": p_uses_reported if p_uses_reported else p_uses_pairs,
                "Execution Time": execution_time,
            }
        ]
    )


def build_dashboard_table(repo_metrics: pd.DataFrame) -> pd.DataFrame:
    if repo_metrics.empty:
        return pd.DataFrame(columns=["Metric", "Value"])
    row = repo_metrics.iloc[0].to_dict()
    return pd.DataFrame(
        [
            {"Metric": "Java Files", "Value": row.get("Total Java Files", "")},
            {"Metric": "Classes", "Value": row.get("Total Classes", "")},
            {"Metric": "Methods", "Value": row.get("Total Methods", "")},
            {"Metric": "Variable Definitions", "Value": row.get("Total Variable Definitions", "")},
            {"Metric": "Variable Uses", "Value": row.get("Total Variable Uses", "")},
            {"Metric": "Definition-Use Pairs", "Value": row.get("Total DU Pairs", "")},
            {"Metric": "C-Uses", "Value": row.get("Total C-Uses", "")},
            {"Metric": "P-Uses", "Value": row.get("Total P-Uses", "")},
        ]
    )


def preview_raw_output(raw_text: str, max_lines: int, source_path: Path) -> None:
    lines = raw_text.splitlines()
    print(f"Saved raw output: {source_path} ({len(lines)} lines)")
    preview = "\n".join(lines[:max_lines])
    print(preview)
    if len(lines) > max_lines:
        print(f"... truncated preview ({len(lines) - max_lines} additional lines in file)")


def collect_outputs(
    status: StaticDuRunStatus,
    repo_path: Path,
    java_files: list[Path],
    output_dir: Path,
    execution_time: float,
) -> dict[str, Any]:
    ensure_output_dir(output_dir)
    unified_json = load_json_map(status.static_du_json) if status.static_du_json and status.static_du_json.exists() else {}
    summary = merged_summary_payload(repo_path, output_dir)

    definitions_df = extract_variable_definitions(summary, repo_path)
    du_pairs_df = extract_definition_use_pairs(summary, repo_path)
    metrics_df = validate_data_flow_metrics(summary, unified_json)
    repository_metrics_df = build_repository_metrics(java_files, summary, du_pairs_df, execution_time)
    dashboard_df = build_dashboard_table(repository_metrics_df)

    definitions_df.to_csv(output_dir / "variable_definitions.csv", index=False)
    du_pairs_df.to_csv(output_dir / "definition_use_pairs.csv", index=False)
    metrics_df.to_csv(output_dir / "data_flow_metrics.csv", index=False)
    repository_metrics_df.to_csv(output_dir / "repository_metrics.csv", index=False)
    dashboard_df.to_csv(output_dir / "dashboard.csv", index=False)

    return {
        "definitions_df": definitions_df,
        "du_pairs_df": du_pairs_df,
        "metrics_df": metrics_df,
        "repository_metrics_df": repository_metrics_df,
        "dashboard_df": dashboard_df,
        "summary": summary,
    }
