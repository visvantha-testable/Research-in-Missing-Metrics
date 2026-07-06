"""Lizard Parameter Count benchmark execution helpers (Java)."""
from __future__ import annotations

import csv
import io
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

EXCLUDED_DIR_NAMES = {
    ".git", "target", "build", "out", ".gradle", ".mvn", "generated-sources", "docs",
}
LIZARD_EXCLUDE_PATTERNS = [
    "*/.git/*", "*/target/*", "*/build/*", "*/out/*", "*/.gradle/*",
    "*/.mvn/*", "*/generated-sources/*", "*/docs/*",
]
LIZARD_RAW_COLUMNS = [
    "nloc", "ccn", "token_count", "parameter_count", "length", "location",
    "file", "function", "long_name", "start_line", "end_line",
]
LIZARD_OUTPUT_COLUMNS = [
    "NLOC", "CCN", "token", "PARAM", "length", "location", "file", "function",
]
LIZARD_METRICS_COLUMNS = [
    "file", "class", "method", "nloc", "cyclomatic_complexity", "token_count",
    "parameter_count", "function_length", "start_line", "end_line",
]
LONG_PARAMETER_LIST_COLUMNS = ["file", "class", "method", "parameter_count", "status"]
LONG_PARAMETER_THRESHOLD = 5
PY = sys.executable


def split_java_symbol(function_name: str) -> tuple[str, str]:
    name = str(function_name).strip('"')
    if "::" in name:
        class_name, method_name = name.split("::", 1)
        return class_name, method_name
    return "", name


def discover_java_files(repo_path: Path) -> list[Path]:
    files: list[Path] = []
    for file_path in repo_path.rglob("*.java"):
        if any(part in EXCLUDED_DIR_NAMES for part in file_path.parts):
            continue
        files.append(file_path.resolve())
    return sorted(files)


def save_java_inventory(java_files: list[Path], output: Path) -> None:
    rows = [
        {"file_path": str(path), "file_name": path.name, "directory": str(path.parent)}
        for path in java_files
    ]
    pd.DataFrame(rows, columns=["file_path", "file_name", "directory"]).to_csv(output, index=False)


def build_lizard_command(
    repo_path: Path,
    *,
    csv_output: bool = False,
    ens: bool = False,
) -> list[str]:
    command = [PY, "-m", "lizard", "-l", "java"]
    for pattern in LIZARD_EXCLUDE_PATTERNS:
        command.extend(["-x", pattern])
    if csv_output:
        command.append("--csv")
    if ens:
        command.append("-ENS")
    command.append(str(repo_path))
    return command


def run_command(command: list[str]) -> tuple[str, str, int]:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.stdout, completed.stderr, completed.returncode


def combine_raw(stdout: str, stderr: str) -> str:
    raw = stdout
    if stderr:
        if raw and not raw.endswith("\n"):
            raw += "\n"
        raw += stderr
    return raw


def parse_lizard_csv(csv_text: str, *, with_ens: bool = False) -> pd.DataFrame:
    if not csv_text.strip():
        columns = LIZARD_RAW_COLUMNS + (["max_nested_structures"] if with_ens else [])
        return pd.DataFrame(columns=columns)

    columns = LIZARD_RAW_COLUMNS + (["max_nested_structures"] if with_ens else [])
    rows = list(csv.reader(io.StringIO(csv_text.strip())))
    if rows and rows[0] and rows[0][0].lower() in {"nloc", "ncss"}:
        rows = rows[1:]

    parsed = [dict(zip(columns, row + [""] * (len(columns) - len(row)))) for row in rows]
    frame = pd.DataFrame(parsed)
    numeric_cols = [
        "nloc", "ccn", "token_count", "parameter_count", "length", "start_line", "end_line",
    ]
    if with_ens:
        numeric_cols.append("max_nested_structures")
    for col in numeric_cols:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


def to_lizard_output_csv(lizard_df: pd.DataFrame) -> pd.DataFrame:
    if lizard_df.empty:
        return pd.DataFrame(columns=LIZARD_OUTPUT_COLUMNS)
    return pd.DataFrame(
        {
            "NLOC": lizard_df["nloc"],
            "CCN": lizard_df["ccn"],
            "token": lizard_df["token_count"],
            "PARAM": lizard_df["parameter_count"],
            "length": lizard_df["length"],
            "location": lizard_df["location"].astype(str).str.strip('"'),
            "file": lizard_df["file"].astype(str).str.strip('"'),
            "function": lizard_df["function"].astype(str).str.strip('"'),
        }
    )


def to_lizard_metrics(lizard_df: pd.DataFrame) -> pd.DataFrame:
    if lizard_df.empty:
        return pd.DataFrame(columns=LIZARD_METRICS_COLUMNS)

    classes: list[str] = []
    methods: list[str] = []
    for function_name in lizard_df["function"].astype(str):
        class_name, method_name = split_java_symbol(function_name)
        classes.append(class_name)
        methods.append(method_name)

    return pd.DataFrame(
        {
            "file": lizard_df["file"].astype(str).str.strip('"'),
            "class": classes,
            "method": methods,
            "nloc": lizard_df["nloc"],
            "cyclomatic_complexity": lizard_df["ccn"],
            "token_count": lizard_df["token_count"],
            "parameter_count": lizard_df["parameter_count"],
            "function_length": lizard_df["length"],
            "start_line": lizard_df["start_line"],
            "end_line": lizard_df["end_line"],
        }
    )


def build_long_parameter_list(metrics_df: pd.DataFrame) -> pd.DataFrame:
    if metrics_df.empty:
        return pd.DataFrame(columns=LONG_PARAMETER_LIST_COLUMNS)
    rows: list[dict[str, Any]] = []
    for _, record in metrics_df.iterrows():
        param_count = int(record.get("parameter_count", 0) or 0)
        status = "Long Parameter List" if param_count > LONG_PARAMETER_THRESHOLD else "OK"
        rows.append(
            {
                "file": record.get("file", ""),
                "class": record.get("class", ""),
                "method": record.get("method", ""),
                "parameter_count": param_count,
                "status": status,
            }
        )
    return pd.DataFrame(rows, columns=LONG_PARAMETER_LIST_COLUMNS)


def compute_max_nesting_depth(ens_df: pd.DataFrame) -> int:
    if ens_df.empty or "max_nested_structures" not in ens_df.columns:
        return 0
    values = pd.to_numeric(ens_df["max_nested_structures"], errors="coerce").dropna()
    return int(values.max()) if not values.empty else 0


def compute_complexity_summary(metrics_df: pd.DataFrame, max_nesting_depth: int) -> pd.DataFrame:
    ccn_values = pd.to_numeric(metrics_df["cyclomatic_complexity"], errors="coerce").dropna()
    param_values = pd.to_numeric(metrics_df["parameter_count"], errors="coerce").dropna()
    length_values = pd.to_numeric(metrics_df["function_length"], errors="coerce").dropna()

    return pd.DataFrame(
        [
            {
                "metric_name": "Cyclomatic_Complexity",
                "metric_value": int(ccn_values.max()) if not ccn_values.empty else 0,
            },
            {
                "metric_name": "Parameter_Count",
                "metric_value": int(param_values.max()) if not param_values.empty else 0,
            },
            {
                "metric_name": "Function_Length",
                "metric_value": int(length_values.max()) if not length_values.empty else 0,
            },
            {
                "metric_name": "Maximum_Nesting_Depth",
                "metric_value": max_nesting_depth,
            },
        ]
    )


def append_error(errors: list[dict[str, str]], file: str, message: str) -> None:
    errors.append(
        {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "file": file,
            "error_message": message,
        }
    )


def write_error_log(errors: list[dict[str, str]], output: Path) -> None:
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp", "file", "error_message"])
        writer.writeheader()
        writer.writerows(errors)


def run_lizard_suite(repo: Path, errors: list[dict[str, str]]) -> dict[str, str]:
    console_chunks: list[str] = []
    outputs: dict[str, str] = {}

    suites = [
        ("text", build_lizard_command(repo), "text"),
        ("csv", build_lizard_command(repo, csv_output=True), "csv"),
        ("csv_ens", build_lizard_command(repo, csv_output=True, ens=True), "csv_ens"),
    ]

    for label, command, key in suites:
        stdout, stderr, code = run_command(command)
        header = f"===== lizard {label} =====\n"
        console_chunks.append(header + combine_raw(stdout, stderr))
        if code not in (0, 1):
            append_error(errors, label, f"Lizard {label} run exited with code {code}")
        outputs[key] = stdout

    outputs["console"] = "\n".join(
        chunk if chunk.endswith("\n") else chunk + "\n" for chunk in console_chunks
    )
    return outputs


def run_pipeline(repo: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    errors: list[dict[str, str]] = []

    java_files = discover_java_files(repo)
    save_java_inventory(java_files, output / "java_files_inventory.csv")

    lizard_outputs = run_lizard_suite(repo, errors)
    (output / "lizard_raw_console_output.txt").write_text(
        lizard_outputs.get("console", ""), encoding="utf-8"
    )

    base_df = parse_lizard_csv(lizard_outputs.get("csv", ""), with_ens=False)
    ens_df = parse_lizard_csv(lizard_outputs.get("csv_ens", ""), with_ens=True)

    output_df = to_lizard_output_csv(base_df)
    output_df.to_csv(output / "lizard_output.csv", index=False)

    metrics_df = to_lizard_metrics(base_df)
    metrics_df.to_csv(output / "lizard_metrics.csv", index=False)

    param_values = pd.to_numeric(metrics_df["parameter_count"], errors="coerce").dropna()
    max_param = int(param_values.max()) if not param_values.empty else 0
    avg_param = round(float(param_values.mean()), 4) if not param_values.empty else 0.0

    pd.DataFrame([{"metric_name": "Parameter_Count", "metric_value": max_param}]).to_csv(
        output / "parameter_count_summary.csv", index=False
    )

    long_param_df = build_long_parameter_list(metrics_df)
    long_param_df.to_csv(output / "long_parameter_list.csv", index=False)
    long_param_count = int((long_param_df["status"] == "Long Parameter List").sum())

    max_nesting = compute_max_nesting_depth(ens_df)
    complexity_df = compute_complexity_summary(metrics_df, max_nesting)
    complexity_df.to_csv(output / "complexity_summary.csv", index=False)

    ccn_values = pd.to_numeric(metrics_df["cyclomatic_complexity"], errors="coerce").dropna()
    avg_ccn = round(float(ccn_values.mean()), 4) if not ccn_values.empty else 0.0

    write_error_log(errors, output / "error_log.txt")

    return {
        "benchmark_ready": len(java_files) > 0 and not metrics_df.empty and max_param >= 8,
        "java_files": len(java_files),
        "methods": len(metrics_df),
        "average_parameter_count": avg_param,
        "maximum_parameter_count": max_param,
        "long_parameter_list_count": long_param_count,
        "average_cyclomatic_complexity": avg_ccn,
        "maximum_nesting_depth": max_nesting,
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
