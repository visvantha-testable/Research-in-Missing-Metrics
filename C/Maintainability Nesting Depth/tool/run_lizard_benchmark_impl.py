"""Implementation helpers for Lizard benchmark execution."""
from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

C_FILE_EXTENSIONS = {".c", ".h"}
EXCLUDED_DIR_NAMES = {
    ".git", "build", "dist", "out", "bin", "obj", "vendor", "third_party", "tests", "docs",
}
LIZARD_EXCLUDE_PATTERNS = [
    "*/.git/*", "*/build/*", "*/dist/*", "*/out/*", "*/bin/*", "*/obj/*",
    "*/vendor/*", "*/third_party/*", "*/tests/*", "*/docs/*",
]
LIZARD_CSV_COLUMNS = [
    "nloc", "ccn", "token_count", "parameter_count", "length", "location",
    "file", "function", "long_name", "start_line", "end_line",
]
LIZARD_CSV_COLUMNS_ENS = LIZARD_CSV_COLUMNS + ["max_nested_structures"]


def should_exclude_path(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def discover_c_files(repo_path: Path) -> list[Path]:
    files = []
    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in C_FILE_EXTENSIONS:
            continue
        if should_exclude_path(file_path.relative_to(repo_path)):
            continue
        files.append(file_path.resolve())
    return sorted(files)


def build_lizard_command(repo_path: Path, output_csv=False, output_xml=False, ens=False) -> list[str]:
    cmd = [sys.executable, "-m", "lizard", "-l", "cpp"]
    for pattern in LIZARD_EXCLUDE_PATTERNS:
        cmd.extend(["-x", pattern])
    if output_csv:
        cmd.append("--csv")
    if output_xml:
        cmd.append("-X")
    if ens:
        cmd.append("-ENS")
    cmd.append(str(repo_path))
    return cmd


def run_cmd(command: list[str]) -> tuple[str, str, int]:
    completed = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )
    return completed.stdout, completed.stderr, completed.returncode


def combine_raw(stdout: str, stderr: str) -> str:
    raw = stdout
    if stderr:
        if raw and not raw.endswith("\n"):
            raw += "\n"
        raw += stderr
    return raw


def parse_lizard_csv(csv_text: str, with_ens: bool = False) -> pd.DataFrame:
    if not csv_text.strip():
        return pd.DataFrame(columns=LIZARD_CSV_COLUMNS_ENS if with_ens else LIZARD_CSV_COLUMNS)
    columns = LIZARD_CSV_COLUMNS_ENS if with_ens else LIZARD_CSV_COLUMNS
    rows = list(csv.reader(io.StringIO(csv_text.strip())))
    if rows and rows[0] and rows[0][0].lower() in {"nloc", "ncss"}:
        rows = rows[1:]
    parsed = [dict(zip(columns, row + [""] * (len(columns) - len(row)))) for row in rows]
    frame = pd.DataFrame(parsed)
    for col in ["nloc", "ccn", "token_count", "parameter_count", "length", "start_line", "end_line"]:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    if with_ens and "max_nested_structures" in frame.columns:
        frame["max_nested_structures"] = pd.to_numeric(frame["max_nested_structures"], errors="coerce")
    return frame


def strip_c_comments_and_strings(line: str) -> str:
    line = re.sub(r"//.*$", "", line)
    line = re.sub(r"/\*.*?\*/", "", line)
    line = re.sub(r'"(\\.|[^"\\])*"', '""', line)
    line = re.sub(r"'(\\.|[^'\\])*'", "''", line)
    return line


def derive_max_nesting_depth_from_source(source_text: str, start_line: int, end_line: int) -> int:
    lines = source_text.splitlines()
    body_lines = lines[start_line - 1 : end_line]
    max_depth = 0
    brace_depth = 0
    control_pattern = re.compile(r"\b(if|for|while|switch|do)\b")
    for line in body_lines:
        code = strip_c_comments_and_strings(line)
        if control_pattern.search(code):
            max_depth = max(max_depth, brace_depth + 1)
        for char in code:
            if char == "{":
                brace_depth += 1
                max_depth = max(max_depth, brace_depth)
            elif char == "}":
                brace_depth = max(brace_depth - 1, 0)
    return int(max_depth)


def build_nesting_depth_results(csv_df: pd.DataFrame, ens_csv_df: pd.DataFrame) -> pd.DataFrame:
    base_df = ens_csv_df if not ens_csv_df.empty else csv_df
    rows = []
    for _, record in base_df.iterrows():
        file_path = str(record.get("file", "")).strip('"')
        function_name = str(record.get("function", "")).strip('"')
        start_line = int(record.get("start_line", 0) or 0)
        end_line = int(record.get("end_line", 0) or 0)
        reported = None
        if not ens_csv_df.empty:
            match = ens_csv_df[
                (ens_csv_df["function"].astype(str).str.strip('"') == function_name)
                & (ens_csv_df["start_line"] == start_line)
            ]
            if not match.empty:
                reported = int(match.iloc[0]["max_nested_structures"])
        if reported is not None:
            rows.append({
                "file": file_path, "function": function_name,
                "start_line": start_line, "end_line": end_line,
                "max_nesting_depth": reported, "status": "reported",
            })
        else:
            source = Path(file_path).read_text(encoding="utf-8", errors="replace")
            derived = derive_max_nesting_depth_from_source(source, start_line, end_line)
            rows.append({
                "file": file_path, "function": function_name,
                "start_line": start_line, "end_line": end_line,
                "max_nesting_depth": derived, "status": "derived",
            })
    return pd.DataFrame(rows)


def compute_summary(nesting_df: pd.DataFrame) -> pd.DataFrame:
    valid = nesting_df[nesting_df["max_nesting_depth"].notna()]
    if valid.empty:
        return pd.DataFrame([
            {"metric_name": "Maintainability_Nesting_Depth", "metric_value": 0},
            {"metric_name": "Average_Nesting_Depth", "metric_value": 0},
        ])
    return pd.DataFrame([
        {"metric_name": "Maintainability_Nesting_Depth", "metric_value": int(valid["max_nesting_depth"].max())},
        {"metric_name": "Average_Nesting_Depth", "metric_value": round(float(valid["max_nesting_depth"].mean()), 4)},
    ])


def run_pipeline(repo_path: Path, output_path: Path) -> dict[str, Any]:
    output_path.mkdir(parents=True, exist_ok=True)
    c_files = discover_c_files(repo_path)
    pd.DataFrame([
        {"absolute_path": str(p), "relative_path": str(p.relative_to(repo_path)), "extension": p.suffix.lower()}
        for p in c_files
    ]).to_csv(output_path / "c_files.csv", index=False)

    raw_out, raw_err, _ = run_cmd(build_lizard_command(repo_path))
    csv_out, _, _ = run_cmd(build_lizard_command(repo_path, output_csv=True))
    xml_out, _, _ = run_cmd(build_lizard_command(repo_path, output_xml=True))
    ens_out, _, _ = run_cmd(build_lizard_command(repo_path, output_csv=True, ens=True))

    raw_text = combine_raw(raw_out, raw_err)
    (output_path / "lizard_raw_output.txt").write_text(raw_text, encoding="utf-8")
    (output_path / "lizard_output.csv").write_text(csv_out, encoding="utf-8")
    (output_path / "lizard_output.xml").write_text(xml_out, encoding="utf-8")
    (output_path / "error_log.txt").write_text("", encoding="utf-8")

    csv_df = parse_lizard_csv(csv_out, with_ens=False)
    ens_df = parse_lizard_csv(ens_out, with_ens=True)
    nesting_df = build_nesting_depth_results(csv_df, ens_df)
    nesting_df.to_csv(output_path / "nesting_depth_results.csv", index=False)
    summary_df = compute_summary(nesting_df)
    summary_df.to_csv(output_path / "maintainability_nesting_depth_summary.csv", index=False)

    return {
        "benchmark_ready": len(c_files) > 0 and len(nesting_df) > 0,
        "c_files": len(c_files),
        "functions": len(nesting_df),
        "max_nesting_depth": int(nesting_df["max_nesting_depth"].max()) if not nesting_df.empty else 0,
        "repo_path": str(repo_path),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
