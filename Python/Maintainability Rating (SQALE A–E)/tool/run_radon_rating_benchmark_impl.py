"""Radon maintainability rating benchmark execution helpers."""
from __future__ import annotations

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
    ".git", "venv", ".venv", "env", "__pycache__", "build", "dist", ".tox",
    "node_modules", "site-packages",
}
PY = sys.executable


def discover_python_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo.rglob("*.py"):
        if any(part in EXCLUDED for part in path.parts):
            continue
        files.append(path.resolve())
    return sorted(files)


def build_inventory(repo: Path, python_files: list[Path]) -> pd.DataFrame:
    rows = []
    for path in python_files:
        rows.append(
            {
                "file_path": str(path),
                "file_name": path.name,
                "directory": str(path.parent),
            }
        )
    return pd.DataFrame(rows, columns=["file_path", "file_name", "directory"])


def run_radon(command: list[str]) -> tuple[str, str, int]:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=os.environ.copy(),
    )
    return completed.stdout, completed.stderr, completed.returncode


def combine_raw(stdout: str, stderr: str) -> str:
    raw = stdout
    if stderr:
        if raw and not raw.endswith("\n"):
            raw += "\n"
        raw += stderr
    return raw


def run_radon_suite(repo: Path) -> tuple[dict[str, str], list[str], list[dict[str, str]]]:
    console_chunks: list[str] = []
    errors: list[dict[str, str]] = []
    outputs: dict[str, str] = {}

    commands = {
        "cc": [PY, "-m", "radon", "cc", str(repo), "-s", "-a", "-j"],
        "mi": [PY, "-m", "radon", "mi", str(repo), "-s", "-j"],
        "raw": [PY, "-m", "radon", "raw", str(repo), "-j"],
        "hal": [PY, "-m", "radon", "hal", str(repo), "-j"],
    }

    for label, command in commands.items():
        stdout, stderr, code = run_radon(command)
        chunk = combine_raw(stdout, stderr)
        console_chunks.append(f"=== radon {label} ===\n{chunk}\n")
        outputs[label] = stdout if stdout.strip() else stderr
        if code != 0 and not stdout.strip():
            errors.append(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "file": str(repo),
                    "error_message": f"radon {label} exited with code {code}: {stderr.strip()}",
                }
            )

    return outputs, console_chunks, errors


def run_radon_per_file(file_path: Path, metric: str) -> tuple[str, str, int]:
    command = [PY, "-m", "radon", metric, str(file_path), "-s", "-j"]
    if metric == "cc":
        command = [PY, "-m", "radon", "cc", str(file_path), "-s", "-j"]
    elif metric == "raw":
        command = [PY, "-m", "radon", "raw", str(file_path), "-j"]
    elif metric == "hal":
        command = [PY, "-m", "radon", "hal", str(file_path), "-j"]
    return run_radon(command)


def parse_json_payload(text: str) -> dict[str, Any]:
    if not text.strip():
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_cc_results(payload: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for file_path, items in payload.items():
        if not isinstance(items, list):
            continue
        for item in items:
            rows.append(
                {
                    "file": file_path,
                    "function": item.get("name", ""),
                    "complexity": item.get("complexity", ""),
                    "rank": item.get("rank", ""),
                    "line": item.get("lineno", ""),
                }
            )
    return pd.DataFrame(rows, columns=["file", "function", "complexity", "rank", "line"])


def parse_mi_results(payload: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for file_path, item in payload.items():
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "file": file_path,
                "maintainability_index": item.get("mi", ""),
                "rank": item.get("rank", ""),
            }
        )
    return pd.DataFrame(rows, columns=["file", "maintainability_index", "rank"])


def parse_raw_results(payload: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for file_path, item in payload.items():
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "file": file_path,
                "loc": item.get("loc", ""),
                "lloc": item.get("lloc", ""),
                "sloc": item.get("sloc", ""),
                "comments": item.get("comments", ""),
                "multi": item.get("multi", ""),
                "blank": item.get("blank", ""),
            }
        )
    return pd.DataFrame(rows, columns=["file", "loc", "lloc", "sloc", "comments", "multi", "blank"])


def parse_halstead_results(payload: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for file_path, item in payload.items():
        if not isinstance(item, dict):
            continue
        total = item.get("total", {})
        if not isinstance(total, dict):
            continue
        rows.append(
            {
                "file": file_path,
                "h1": total.get("h1", ""),
                "h2": total.get("h2", ""),
                "N1": total.get("N1", ""),
                "N2": total.get("N2", ""),
                "vocabulary": total.get("vocabulary", ""),
                "length": total.get("length", ""),
                "volume": total.get("volume", ""),
                "difficulty": total.get("difficulty", ""),
                "effort": total.get("effort", ""),
                "bugs": total.get("bugs", ""),
                "time": total.get("time", ""),
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "file", "h1", "h2", "N1", "N2", "vocabulary", "length",
            "volume", "difficulty", "effort", "bugs", "time",
        ],
    )


def mi_to_rating(mi: float) -> str:
    if mi >= 85:
        return "A"
    if mi >= 70:
        return "B"
    if mi >= 55:
        return "C"
    if mi >= 40:
        return "D"
    return "E"


def compute_rating_summary(mi_df: pd.DataFrame) -> pd.DataFrame:
    if mi_df.empty:
        return pd.DataFrame(
            [
                {"metric_name": "Maintainability_Index", "metric_value": 0},
                {"metric_name": "Maintainability_Rating", "metric_value": "E"},
            ]
        )
    values = pd.to_numeric(mi_df["maintainability_index"], errors="coerce").dropna()
    avg_mi = round(float(values.mean()), 1) if not values.empty else 0.0
    rating = mi_to_rating(avg_mi)
    return pd.DataFrame(
        [
            {"metric_name": "Maintainability_Index", "metric_value": avg_mi},
            {"metric_name": "Maintainability_Rating", "metric_value": rating},
        ]
    )


def run_pipeline(repo: Path, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    repo = repo.resolve()
    python_files = discover_python_files(repo)
    build_inventory(repo, python_files).to_csv(output / "python_files_inventory.csv", index=False)

    radon_outputs, console_chunks, errors = run_radon_suite(repo)

    (output / "radon_cc_output.json").write_text(radon_outputs.get("cc", ""), encoding="utf-8")
    (output / "radon_mi_output.json").write_text(radon_outputs.get("mi", ""), encoding="utf-8")
    (output / "radon_raw_output.json").write_text(radon_outputs.get("raw", ""), encoding="utf-8")
    (output / "radon_halstead_output.json").write_text(radon_outputs.get("hal", ""), encoding="utf-8")
    (output / "radon_raw_console_output.txt").write_text("".join(console_chunks), encoding="utf-8")

    cc_df = parse_cc_results(parse_json_payload(radon_outputs.get("cc", "")))
    mi_df = parse_mi_results(parse_json_payload(radon_outputs.get("mi", "")))
    raw_df = parse_raw_results(parse_json_payload(radon_outputs.get("raw", "")))
    hal_df = parse_halstead_results(parse_json_payload(radon_outputs.get("hal", "")))

    cc_df.to_csv(output / "cyclomatic_complexity_results.csv", index=False)
    mi_df.to_csv(output / "maintainability_index_results.csv", index=False)
    raw_df.to_csv(output / "raw_metrics_results.csv", index=False)
    hal_df.to_csv(output / "halstead_metrics_results.csv", index=False)

    summary_df = compute_rating_summary(mi_df)
    summary_df.to_csv(output / "maintainability_rating_summary.csv", index=False)

    error_df = pd.DataFrame(errors, columns=["timestamp", "file", "error_message"])
    if error_df.empty:
        error_df = pd.DataFrame(columns=["timestamp", "file", "error_message"])
    error_df.to_csv(output / "error_log.txt", index=False)

    avg_cc = round(float(pd.to_numeric(cc_df["complexity"], errors="coerce").mean()), 4) if not cc_df.empty else 0.0
    avg_mi = round(float(pd.to_numeric(mi_df["maintainability_index"], errors="coerce").mean()), 1) if not mi_df.empty else 0.0
    total_loc = int(pd.to_numeric(raw_df["loc"], errors="coerce").sum()) if not raw_df.empty else 0
    rating = str(summary_df.loc[summary_df["metric_name"] == "Maintainability_Rating", "metric_value"].iloc[0])

    return {
        "benchmark_ready": len(python_files) > 0 and not mi_df.empty,
        "python_files": len(python_files),
        "average_cyclomatic_complexity": avg_cc,
        "average_maintainability_index": avg_mi,
        "maintainability_rating": rating,
        "total_loc": total_loc,
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
