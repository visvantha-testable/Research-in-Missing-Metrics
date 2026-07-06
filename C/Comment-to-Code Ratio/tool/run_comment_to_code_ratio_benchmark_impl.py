"""cloc Comment-to-Code Ratio benchmark execution helpers."""
from __future__ import annotations

import csv
import io
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

os.environ.pop("PYTHONPATH", None)

C_FILE_EXTENSIONS = {".c", ".h"}
EXCLUDED_DIR_NAMES = {".git", "build", "dist", "bin", "vendor", "docs", "tests", "third_party"}
CLOC_EXCLUDE_DIRS = "build,dist,bin,vendor,docs,tests,third_party,.git"
CLOC_VERSION = "2.08"
CLOC_RELEASE_TAG = "v2.08"
CLOC_WINDOWS_URL = f"https://github.com/AlDanial/cloc/releases/download/{CLOC_RELEASE_TAG}/cloc-{CLOC_VERSION}.exe"
CLOC_PERL_URL = f"https://github.com/AlDanial/cloc/releases/download/{CLOC_RELEASE_TAG}/cloc-{CLOC_VERSION}.pl"
METRICS_COLUMNS = ["language", "files", "blank_lines", "comment_lines", "code_lines"]


def resolve_project_root(metric_root: Path) -> Path:
    current = metric_root.resolve()
    for _ in range(8):
        if (current / "runtimes").is_dir():
            return current
        if (current / "README.md").is_file():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return metric_root.resolve().parent.parent


def should_exclude_path(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def discover_c_files(repo_path: Path) -> list[Path]:
    files: list[Path] = []
    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in C_FILE_EXTENSIONS:
            continue
        if should_exclude_path(file_path.relative_to(repo_path)):
            continue
        files.append(file_path.resolve())
    return sorted(files)


def save_c_inventory(c_files: list[Path], output: Path) -> None:
    rows = [
        {"file_path": str(path), "file_name": path.name, "directory": str(path.parent)}
        for path in c_files
    ]
    pd.DataFrame(rows, columns=["file_path", "file_name", "directory"]).to_csv(output, index=False)


def download_cloc(cloc_dir: Path) -> Path:
    cloc_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        target = cloc_dir / "cloc.exe"
        if not target.exists():
            urllib.request.urlretrieve(CLOC_WINDOWS_URL, target)
        return target

    target = cloc_dir / "cloc.pl"
    if not target.exists():
        urllib.request.urlretrieve(CLOC_PERL_URL, target)
    target.chmod(0o755)
    return target


def resolve_cloc_executable(project_root: Path) -> Path:
    env_path = os.environ.get("CLOC")
    if env_path:
        candidate = Path(env_path)
        if candidate.exists():
            return candidate.resolve()

    which = shutil.which("cloc")
    if which:
        return Path(which).resolve()

    runtime_dir = project_root / "runtimes" / "cloc"
    runtime_candidates = [
        runtime_dir / "cloc.exe",
        runtime_dir / "cloc.pl",
        runtime_dir / "cloc",
    ]
    for candidate in runtime_candidates:
        if candidate.exists():
            return candidate.resolve()

    downloaded = download_cloc(runtime_dir)
    if downloaded.exists():
        return downloaded.resolve()

    raise FileNotFoundError(
        "cloc executable not found. Install cloc (apt-get install cloc / winget install Cloc), "
        "set CLOC, or allow bootstrap to runtimes/cloc/."
    )


def build_cloc_command(cloc_exe: Path, repo_path: Path, *, json_output: bool = False, csv_output: bool = False) -> list[str]:
    if cloc_exe.suffix.lower() == ".pl":
        command = ["perl", str(cloc_exe)]
    elif cloc_exe.suffix.lower() == ".exe" or cloc_exe.name == "cloc":
        command = [str(cloc_exe)]
    else:
        command = [str(cloc_exe)]

    command.extend(
        [
            str(repo_path),
            "--include-lang=C",
            f"--exclude-dir={CLOC_EXCLUDE_DIRS}",
            "--quiet",
        ]
    )
    if json_output:
        command.append("--json")
    if csv_output:
        command.append("--csv")
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


def extract_language_metrics(payload: dict[str, Any], language: str = "C") -> dict[str, Any]:
    if language in payload and isinstance(payload[language], dict):
        return payload[language]
    if "SUM" in payload and isinstance(payload["SUM"], dict):
        return payload["SUM"]
    for key, value in payload.items():
        if key == "header" or not isinstance(value, dict):
            continue
        if {"comment", "code"}.issubset(value.keys()):
            return value
    return {}


def parse_cloc_metrics(payload: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, value in payload.items():
        if key == "header" or not isinstance(value, dict):
            continue
        if "code" not in value:
            continue
        rows.append(
            {
                "language": key,
                "files": value.get("nFiles", value.get("files", "")),
                "blank_lines": value.get("blank", ""),
                "comment_lines": value.get("comment", ""),
                "code_lines": value.get("code", ""),
            }
        )
    if not rows:
        return pd.DataFrame(columns=METRICS_COLUMNS)
    frame = pd.DataFrame(rows, columns=METRICS_COLUMNS)
    if "SUM" in frame["language"].values:
        frame = frame[frame["language"] != "SUM"].reset_index(drop=True)
    return frame


def compute_comment_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    comment_lines = float(metrics.get("comment", 0) or 0)
    code_lines = float(metrics.get("code", 0) or 0)
    blank_lines = float(metrics.get("blank", 0) or 0)
    files = float(metrics.get("nFiles", metrics.get("files", 0)) or 0)
    ratio = round(comment_lines / code_lines, 4) if code_lines > 0 else 0.0
    percentage = round(ratio * 100, 2)
    return {
        "files": files,
        "blank_lines": blank_lines,
        "comment_lines": comment_lines,
        "code_lines": code_lines,
        "comment_to_code_ratio": ratio,
        "comment_to_code_percentage": percentage,
    }


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


def run_cloc_suite(cloc_exe: Path, repo: Path, errors: list[dict[str, str]]) -> dict[str, str]:
    console_chunks: list[str] = []
    outputs: dict[str, str] = {}

    runs = [
        ("text", False, False),
        ("json", True, False),
        ("csv", False, True),
    ]

    for label, json_output, csv_output in runs:
        command = build_cloc_command(cloc_exe, repo, json_output=json_output, csv_output=csv_output)
        stdout, stderr, code = run_command(command)
        console_chunks.append(f"===== cloc ({label}) =====\n" + combine_raw(stdout, stderr))
        if code != 0:
            append_error(errors, f"cloc_{label}", f"cloc {label} run exited with code {code}")
        if json_output:
            outputs["json"] = stdout
        elif csv_output:
            outputs["csv"] = stdout
        else:
            outputs["text"] = stdout

    outputs["console"] = "\n".join(chunk if chunk.endswith("\n") else chunk + "\n" for chunk in console_chunks)
    return outputs


def run_pipeline(repo: Path, output: Path, project_root: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    errors: list[dict[str, str]] = []
    repo = repo.resolve()

    cloc_exe = resolve_cloc_executable(project_root)
    c_files = discover_c_files(repo)
    save_c_inventory(c_files, output / "c_files_inventory.csv")

    cloc_outputs = run_cloc_suite(cloc_exe, repo, errors)

    (output / "cloc_raw_console_output.txt").write_text(cloc_outputs.get("console", ""), encoding="utf-8")
    (output / "cloc_output.json").write_text(cloc_outputs.get("json", ""), encoding="utf-8")
    (output / "cloc_output.csv").write_text(cloc_outputs.get("csv", ""), encoding="utf-8")

    json_payload = parse_json_payload(cloc_outputs.get("json", ""))
    if not json_payload:
        append_error(errors, "cloc_output.json", "Failed to parse cloc JSON output")

    metrics_df = parse_cloc_metrics(json_payload)
    metrics_df.to_csv(output / "cloc_metrics.csv", index=False)

    c_metrics = extract_language_metrics(json_payload, "C")
    comment_metrics = compute_comment_metrics(c_metrics)

    pd.DataFrame(
        [{"metric_name": "Comment_to_Code_Ratio", "metric_value": comment_metrics["comment_to_code_ratio"]}]
    ).to_csv(output / "comment_to_code_ratio_summary.csv", index=False)
    pd.DataFrame(
        [{"metric_name": "Comment_to_Code_Percentage", "metric_value": comment_metrics["comment_to_code_percentage"]}]
    ).to_csv(output / "comment_percentage_summary.csv", index=False)
    write_error_log(errors, output / "error_log.txt")

    return {
        "benchmark_ready": len(c_files) > 0 and comment_metrics["code_lines"] > 0,
        "c_files": len(c_files),
        "total_files": int(comment_metrics["files"]),
        "total_blank_lines": int(comment_metrics["blank_lines"]),
        "total_comment_lines": int(comment_metrics["comment_lines"]),
        "total_code_lines": int(comment_metrics["code_lines"]),
        "comment_to_code_ratio": comment_metrics["comment_to_code_ratio"],
        "comment_to_code_percentage": comment_metrics["comment_to_code_percentage"],
        "cloc_executable": str(cloc_exe),
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
