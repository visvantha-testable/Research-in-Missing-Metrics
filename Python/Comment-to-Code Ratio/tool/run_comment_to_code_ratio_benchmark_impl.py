"""Radon Comment-to-Code Ratio benchmark execution helpers."""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

os.environ.pop("PYTHONPATH", None)

EXCLUDED = {
    ".git", "venv", ".venv", "env", "__pycache__", "build", "dist", ".tox", "node_modules", "site-packages",
}
PY = sys.executable
RAW_METRICS_COLUMNS = ["file", "loc", "lloc", "sloc", "comments", "multi", "blank", "single_comments"]
CC_COLUMNS = ["file", "function", "complexity", "rank"]


def discover_python_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo.rglob("*.py"):
        if any(part in EXCLUDED for part in path.parts):
            continue
        files.append(path.resolve())
    return sorted(files)


def build_radon_command(repo: Path, subcommand: str, *, json_output: bool = False, extra_args: list[str] | None = None) -> list[str]:
    command = [PY, "-m", "radon", subcommand, str(repo)]
    if subcommand in {"cc", "mi"}:
        command.append("-s")
    if extra_args:
        command.extend(extra_args)
    if json_output:
        command.append("-j")
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


def parse_json_payload(text: str) -> dict[str, Any]:
    if not text.strip():
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def save_inventory(python_files: list[Path], output: Path) -> None:
    rows = [
        {"file_path": str(path), "file_name": path.name, "directory": str(path.parent)}
        for path in python_files
    ]
    pd.DataFrame(rows, columns=["file_path", "file_name", "directory"]).to_csv(output, index=False)


def parse_cc_results(payload: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for file_path, blocks in payload.items():
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            rows.append(
                {
                    "file": file_path,
                    "function": block.get("name", ""),
                    "complexity": block.get("complexity", ""),
                    "rank": block.get("rank", ""),
                }
            )
    return pd.DataFrame(rows, columns=CC_COLUMNS)


def parse_mi_results(payload: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for file_path, metrics in payload.items():
        if not isinstance(metrics, dict):
            continue
        rows.append(
            {
                "file": file_path,
                "maintainability_index": metrics.get("mi", ""),
                "rank": metrics.get("rank", ""),
            }
        )
    return pd.DataFrame(rows, columns=["file", "maintainability_index", "rank"])


def parse_raw_results(payload: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for file_path, metrics in payload.items():
        if not isinstance(metrics, dict):
            continue
        single_comments = metrics.get("single_comments", metrics.get("comments", ""))
        rows.append(
            {
                "file": file_path,
                "loc": metrics.get("loc", ""),
                "lloc": metrics.get("lloc", ""),
                "sloc": metrics.get("sloc", ""),
                "comments": metrics.get("comments", ""),
                "multi": metrics.get("multi", ""),
                "blank": metrics.get("blank", ""),
                "single_comments": single_comments,
            }
        )
    return pd.DataFrame(rows, columns=RAW_METRICS_COLUMNS)


def mi_to_maintainability_rating(mi: float) -> str:
    if mi >= 85:
        return "A"
    if mi >= 70:
        return "B"
    if mi >= 55:
        return "C"
    if mi >= 40:
        return "D"
    return "E"


def compute_comment_metrics(raw_df: pd.DataFrame) -> dict[str, float]:
    comments = pd.to_numeric(raw_df["comments"], errors="coerce").fillna(0)
    multi = pd.to_numeric(raw_df["multi"], errors="coerce").fillna(0)
    sloc = pd.to_numeric(raw_df["sloc"], errors="coerce").fillna(0)

    total_comment_lines = float(comments.sum() + multi.sum())
    total_sloc = float(sloc.sum())
    ratio = round(total_comment_lines / total_sloc, 4) if total_sloc > 0 else 0.0
    percentage = round(ratio * 100, 2)
    return {
        "total_sloc": total_sloc,
        "total_comment_lines": total_comment_lines,
        "comment_to_code_ratio": ratio,
        "comment_to_code_percentage": percentage,
    }


def compute_maintainability_summary(mi_df: pd.DataFrame) -> pd.DataFrame:
    mi_values = pd.to_numeric(mi_df["maintainability_index"], errors="coerce").dropna()
    avg_mi = round(float(mi_values.mean()), 4) if not mi_values.empty else 0.0
    rating = mi_to_maintainability_rating(avg_mi) if not mi_values.empty else "E"
    return pd.DataFrame(
        [
            {"metric_name": "Maintainability_Index", "metric_value": avg_mi},
            {"metric_name": "Maintainability_Rating", "metric_value": rating},
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


def run_radon_suite(repo: Path, errors: list[dict[str, str]]) -> dict[str, str]:
    console_chunks: list[str] = []
    outputs: dict[str, str] = {}

    suites = [
        ("raw", [], "radon_raw_metrics.json"),
        ("mi", [], "radon_mi.json"),
        ("cc", ["-a"], "radon_cc.json"),
    ]

    for subcommand, extra_args, _ in suites:
        json_cmd = build_radon_command(repo, subcommand, json_output=True, extra_args=extra_args)
        text_cmd = build_radon_command(repo, subcommand, json_output=False, extra_args=extra_args)

        text_stdout, text_stderr, text_code = run_command(text_cmd)
        json_stdout, json_stderr, json_code = run_command(json_cmd)

        console_chunks.append(f"===== radon {subcommand} (text) =====\n" + combine_raw(text_stdout, text_stderr))
        console_chunks.append(f"===== radon {subcommand} (json) =====\n" + combine_raw(json_stdout, json_stderr))

        if text_code not in (0, 1):
            append_error(errors, subcommand, f"Radon {subcommand} text run exited with code {text_code}")
        if json_code not in (0, 1):
            append_error(errors, subcommand, f"Radon {subcommand} json run exited with code {json_code}")

        outputs[subcommand] = json_stdout

    outputs["console"] = "\n".join(chunk if chunk.endswith("\n") else chunk + "\n" for chunk in console_chunks)
    return outputs


def run_pipeline(repo: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    errors: list[dict[str, str]] = []
    repo = repo.resolve()

    python_files = discover_python_files(repo)
    save_inventory(python_files, output / "python_files_inventory.csv")

    radon_outputs = run_radon_suite(repo, errors)

    (output / "radon_raw_console_output.txt").write_text(radon_outputs.get("console", ""), encoding="utf-8")
    (output / "radon_raw_metrics.json").write_text(radon_outputs.get("raw", ""), encoding="utf-8")
    (output / "radon_mi.json").write_text(radon_outputs.get("mi", ""), encoding="utf-8")
    (output / "radon_cc.json").write_text(radon_outputs.get("cc", ""), encoding="utf-8")

    raw_payload = parse_json_payload(radon_outputs.get("raw", ""))
    mi_payload = parse_json_payload(radon_outputs.get("mi", ""))
    cc_payload = parse_json_payload(radon_outputs.get("cc", ""))

    if not raw_payload:
        append_error(errors, "radon_raw_metrics.json", "Failed to parse Radon raw metrics JSON output")
    if not mi_payload:
        append_error(errors, "radon_mi.json", "Failed to parse Radon maintainability index JSON output")
    if not cc_payload:
        append_error(errors, "radon_cc.json", "Failed to parse Radon cyclomatic complexity JSON output")

    raw_df = parse_raw_results(raw_payload)
    mi_df = parse_mi_results(mi_payload)
    cc_df = parse_cc_results(cc_payload)

    raw_df.to_csv(output / "radon_raw_metrics.csv", index=False)
    cc_df.to_csv(output / "cyclomatic_complexity_summary.csv", index=False)

    comment_metrics = compute_comment_metrics(raw_df)
    maintainability_df = compute_maintainability_summary(mi_df)

    pd.DataFrame(
        [{"metric_name": "Comment_to_Code_Ratio", "metric_value": comment_metrics["comment_to_code_ratio"]}]
    ).to_csv(output / "comment_to_code_ratio_summary.csv", index=False)
    pd.DataFrame(
        [{"metric_name": "Comment_to_Code_Percentage", "metric_value": comment_metrics["comment_to_code_percentage"]}]
    ).to_csv(output / "comment_to_code_percentage_summary.csv", index=False)
    maintainability_df.to_csv(output / "maintainability_summary.csv", index=False)
    write_error_log(errors, output / "error_log.txt")

    avg_mi = float(maintainability_df.loc[maintainability_df["metric_name"] == "Maintainability_Index", "metric_value"].iloc[0])
    rating = str(maintainability_df.loc[maintainability_df["metric_name"] == "Maintainability_Rating", "metric_value"].iloc[0])

    return {
        "benchmark_ready": len(python_files) > 0 and not raw_df.empty and comment_metrics["total_sloc"] > 0,
        "python_files": len(python_files),
        "total_sloc": int(comment_metrics["total_sloc"]),
        "total_comment_lines": int(comment_metrics["total_comment_lines"]),
        "comment_to_code_ratio": comment_metrics["comment_to_code_ratio"],
        "comment_to_code_percentage": comment_metrics["comment_to_code_percentage"],
        "maintainability_index": avg_mi,
        "maintainability_rating": rating,
        "cyclomatic_complexity_rows": len(cc_df),
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
