"""Lizard maintainability rating benchmark execution helpers."""
from __future__ import annotations

import csv
import io
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

C_FILE_EXTENSIONS = {".c", ".h"}
EXCLUDED_DIR_NAMES = {
    ".git", "build", "dist", "out", "bin", "vendor", "third_party", "docs", "tests",
}
LIZARD_EXCLUDE_PATTERNS = [
    "*/.git/*", "*/build/*", "*/dist/*", "*/out/*", "*/bin/*",
    "*/vendor/*", "*/third_party/*", "*/docs/*", "*/tests/*",
]
LIZARD_RAW_COLUMNS = [
    "nloc", "ccn", "token_count", "parameter_count", "length", "location",
    "file", "function", "long_name", "start_line", "end_line",
]
LIZARD_OUTPUT_COLUMNS = [
    "NLOC", "CCN", "token", "PARAM", "length", "location", "file", "function", "start_line", "end_line",
]
DETAILED_COLUMNS = [
    "file", "function", "nloc", "cyclomatic_complexity", "token_count",
    "parameter_count", "function_length", "start_line", "end_line",
]
NESTING_COLUMNS = ["file", "function", "start_line", "end_line", "max_nesting_depth", "status"]
PY = sys.executable


def discover_c_files(repo_path: Path) -> list[Path]:
    files: list[Path] = []
    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in C_FILE_EXTENSIONS:
            continue
        if any(part in EXCLUDED_DIR_NAMES for part in file_path.parts):
            continue
        files.append(file_path.resolve())
    return sorted(files)


def save_c_inventory(c_files: list[Path], output: Path) -> None:
    rows = [
        {"file_path": str(path), "file_name": path.name, "directory": str(path.parent)}
        for path in c_files
    ]
    pd.DataFrame(rows, columns=["file_path", "file_name", "directory"]).to_csv(output, index=False)


def build_lizard_command(
    repo_path: Path,
    *,
    csv_output: bool = False,
    ens: bool = False,
) -> list[str]:
    command = [PY, "-m", "lizard", "-l", "cpp"]
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
            "start_line": lizard_df["start_line"],
            "end_line": lizard_df["end_line"],
        }
    )


def to_detailed_metrics(lizard_df: pd.DataFrame) -> pd.DataFrame:
    if lizard_df.empty:
        return pd.DataFrame(columns=DETAILED_COLUMNS)
    return pd.DataFrame(
        {
            "file": lizard_df["file"].astype(str).str.strip('"'),
            "function": lizard_df["function"].astype(str).str.strip('"'),
            "nloc": lizard_df["nloc"],
            "cyclomatic_complexity": lizard_df["ccn"],
            "token_count": lizard_df["token_count"],
            "parameter_count": lizard_df["parameter_count"],
            "function_length": lizard_df["length"],
            "start_line": lizard_df["start_line"],
            "end_line": lizard_df["end_line"],
        }
    )


def build_nesting_depth_results(base_df: pd.DataFrame, ens_df: pd.DataFrame) -> pd.DataFrame:
    source_df = ens_df if not ens_df.empty else base_df
    rows: list[dict[str, Any]] = []
    for _, record in source_df.iterrows():
        file_path = str(record.get("file", "")).strip('"')
        function_name = str(record.get("function", "")).strip('"')
        start_line = int(record.get("start_line", 0) or 0)
        end_line = int(record.get("end_line", 0) or 0)
        reported = None
        if not ens_df.empty and "max_nested_structures" in ens_df.columns:
            match = ens_df[
                (ens_df["function"].astype(str).str.strip('"') == function_name)
                & (ens_df["start_line"] == start_line)
            ]
            if not match.empty:
                reported = int(match.iloc[0]["max_nested_structures"])
        if reported is not None:
            rows.append(
                {
                    "file": file_path,
                    "function": function_name,
                    "start_line": start_line,
                    "end_line": end_line,
                    "max_nesting_depth": reported,
                    "status": "reported",
                }
            )
        else:
            rows.append(
                {
                    "file": file_path,
                    "function": function_name,
                    "start_line": start_line,
                    "end_line": end_line,
                    "max_nesting_depth": 0,
                    "status": "missing",
                }
            )
    return pd.DataFrame(rows, columns=NESTING_COLUMNS)


def resolve_halstead_volume(total_tokens: float, configured: float | None) -> float:
    if configured is not None and configured > 0:
        return float(configured)
    return max(float(total_tokens), 1.0)


def compute_maintainability_index(
    avg_ccn: float,
    total_nloc: float,
    halstead_volume: float,
) -> float:
    loc = max(float(total_nloc), 1.0)
    volume = max(float(halstead_volume), 1.0)
    mi = 171 - 5.2 * math.log(volume) - 0.23 * avg_ccn - 16.2 * math.log(loc)
    return round(mi, 4)


def mi_to_sqale_rating(mi: float) -> str:
    if mi >= 85:
        return "A"
    if mi >= 70:
        return "B"
    if mi >= 55:
        return "C"
    if mi >= 40:
        return "D"
    return "E"


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


def run_pipeline(
    repo: Path,
    output: Path,
    halstead_volume: float | None = None,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    errors: list[dict[str, str]] = []

    c_files = discover_c_files(repo)
    save_c_inventory(c_files, output / "c_files_inventory.csv")

    lizard_outputs = run_lizard_suite(repo, errors)

    (output / "lizard_raw_console_output.txt").write_text(
        lizard_outputs.get("console", ""), encoding="utf-8"
    )

    base_df = parse_lizard_csv(lizard_outputs.get("csv", ""), with_ens=False)
    ens_df = parse_lizard_csv(lizard_outputs.get("csv_ens", ""), with_ens=True)

    output_df = to_lizard_output_csv(base_df)
    output_df.to_csv(output / "lizard_output.csv", index=False)

    detailed_df = to_detailed_metrics(base_df)
    detailed_df.to_csv(output / "lizard_detailed_metrics.csv", index=False)

    nesting_df = build_nesting_depth_results(base_df, ens_df)
    nesting_df.to_csv(output / "nesting_depth_results.csv", index=False)

    ccn_values = pd.to_numeric(base_df["ccn"], errors="coerce").dropna()
    nloc_values = pd.to_numeric(base_df["nloc"], errors="coerce").dropna()
    token_values = pd.to_numeric(base_df["token_count"], errors="coerce").dropna()

    avg_ccn = round(float(ccn_values.mean()), 4) if not ccn_values.empty else 0.0
    total_nloc = float(nloc_values.sum()) if not nloc_values.empty else 0.0
    total_tokens = float(token_values.sum()) if not token_values.empty else 0.0
    avg_nloc = round(float(nloc_values.mean()), 4) if not nloc_values.empty else 0.0
    avg_nesting = (
        round(float(nesting_df["max_nesting_depth"].mean()), 4) if not nesting_df.empty else 0.0
    )

    resolved_volume = resolve_halstead_volume(total_tokens, halstead_volume)
    mi = compute_maintainability_index(avg_ccn, total_nloc, resolved_volume)
    rating = mi_to_sqale_rating(mi)

    mi_summary = pd.DataFrame([{"metric_name": "Maintainability_Index", "metric_value": mi}])
    mi_summary.to_csv(output / "maintainability_index_summary.csv", index=False)

    rating_summary = pd.DataFrame([{"metric_name": "Maintainability_Rating", "metric_value": rating}])
    rating_summary.to_csv(output / "maintainability_rating_summary.csv", index=False)

    write_error_log(errors, output / "error_log.txt")

    return {
        "benchmark_ready": len(c_files) > 0 and not base_df.empty,
        "c_files": len(c_files),
        "functions": len(base_df),
        "average_cyclomatic_complexity": avg_ccn,
        "average_max_nesting_depth": avg_nesting,
        "average_nloc": avg_nloc,
        "total_nloc": int(total_nloc),
        "maintainability_index": mi,
        "maintainability_rating": rating,
        "halstead_volume_used": resolved_volume,
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
