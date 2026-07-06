"""Generate lizard_maintainability_rating_extraction.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "lizard_maintainability_rating_extraction.ipynb"

UTILS = r'''
from __future__ import annotations

import csv
import io
import math
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from IPython.display import display
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

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


class NotebookLogger:
    def __init__(self, error_log_path: Path) -> None:
        self.error_log_path = error_log_path
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._errors: list[dict[str, str]] = []
        if not self.error_log_path.exists():
            self.write_errors()

    def info(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"[{timestamp}] INFO: {message}")

    def error(self, message: str, file: str = "notebook") -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        line = f"[{timestamp}] ERROR: {message}\n"
        print(line, end="")
        self._errors.append({"timestamp": timestamp, "file": file, "error_message": message})
        self.write_errors()

    def write_errors(self) -> None:
        with self.error_log_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["timestamp", "file", "error_message"])
            writer.writeheader()
            writer.writerows(self._errors)


def ensure_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)


def derive_clone_path(repo_url: str, workspace_dir: Path) -> Path:
    repo_name = repo_url.rstrip("/").removesuffix(".git").split("/")[-1]
    if not repo_name:
        raise ValueError(f"Unable to derive repository name from URL: {repo_url}")
    return workspace_dir / repo_name


def validate_repo_url(repo_url: str) -> None:
    if not repo_url or not isinstance(repo_url, str):
        raise ValueError("REPO_URL must be a non-empty string.")
    if not (repo_url.startswith("https://") or repo_url.startswith("git@") or repo_url.startswith("http://")):
        raise ValueError(f"Invalid repository URL format: {repo_url}")


def clone_or_reuse_repository(
    repo_url: str, workspace_dir: Path, if_clone_exists: str, logger: NotebookLogger, clone_depth: int | None = None,
) -> Path:
    validate_repo_url(repo_url)
    workspace_dir.mkdir(parents=True, exist_ok=True)
    clone_path = derive_clone_path(repo_url, workspace_dir)
    if clone_path.exists():
        if if_clone_exists == "reclone":
            logger.info(f"Removing existing clone at {clone_path}")
            shutil.rmtree(clone_path)
        elif if_clone_exists == "reuse":
            logger.info(f"Reusing existing clone at {clone_path}")
            return clone_path.resolve()
        else:
            raise ValueError("IF_CLONE_EXISTS must be 'reuse' or 'reclone'.")
    logger.info(f"Cloning {repo_url} into {clone_path}")
    clone_kwargs: dict[str, Any] = {"depth": clone_depth} if clone_depth else {}
    try:
        Repo.clone_from(repo_url, clone_path, **clone_kwargs)
    except GitCommandError as exc:
        logger.error(f"Git clone failed: {exc}", file=repo_url)
        raise
    return clone_path.resolve()


def validate_local_repo_path(local_repo_path: Path, logger: NotebookLogger) -> Path:
    if not local_repo_path.exists():
        msg = f"Local repository path does not exist: {local_repo_path}"
        logger.error(msg, file=str(local_repo_path))
        raise FileNotFoundError(msg)
    if not local_repo_path.is_dir():
        msg = f"Local repository path is not a directory: {local_repo_path}"
        logger.error(msg, file=str(local_repo_path))
        raise NotADirectoryError(msg)
    try:
        Repo(local_repo_path)
        logger.info("Validated Git repository.")
    except InvalidGitRepositoryError:
        logger.info("Path is not a Git repository; proceeding as source directory.")
    return local_repo_path.resolve()


def resolve_repository_path(
    use_git_url: bool, repo_url: str, local_repo_path: str | Path, workspace_dir: Path,
    if_clone_exists: str, logger: NotebookLogger, clone_depth: int | None = None,
) -> Path:
    if use_git_url:
        return clone_or_reuse_repository(repo_url, workspace_dir, if_clone_exists, logger, clone_depth)
    return validate_local_repo_path(Path(local_repo_path), logger)


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


def compute_repository_stats(repo_path: Path, c_files: list[Path]) -> dict[str, Any]:
    total_size = sum(path.stat().st_size for path in c_files)
    directories = {path.parent for path in c_files}
    return {
        "repository_name": repo_path.name,
        "repository_size_bytes": total_size,
        "directory_count": len(directories),
        "c_file_count": len(c_files),
    }


def save_c_inventory(c_files: list[Path], output_csv: Path) -> None:
    pd.DataFrame(
        [{"file_path": str(p), "file_name": p.name, "directory": str(p.parent)} for p in c_files]
    ).to_csv(output_csv, index=False)


def build_lizard_command(repo_path: Path, *, csv_output: bool = False, ens: bool = False) -> list[str]:
    command = [PY, "-m", "lizard", "-l", "cpp"]
    for pattern in LIZARD_EXCLUDE_PATTERNS:
        command.extend(["-x", pattern])
    if csv_output:
        command.append("--csv")
    if ens:
        command.append("-ENS")
    command.append(str(repo_path))
    return command


def run_lizard_command(command: list[str], logger: NotebookLogger, stream_raw: bool = False) -> tuple[str, str, int]:
    if stream_raw:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace",
        )
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        assert process.stdout is not None
        assert process.stderr is not None
        while True:
            stdout_line = process.stdout.readline()
            stderr_line = process.stderr.readline()
            if stdout_line:
                stdout_lines.append(stdout_line)
                print(stdout_line, end="")
            if stderr_line:
                stderr_lines.append(stderr_line)
                print(stderr_line, end="")
            if not stdout_line and not stderr_line and process.poll() is not None:
                break
        return "".join(stdout_lines), "".join(stderr_lines), process.returncode or 0

    completed = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    return completed.stdout, completed.stderr, completed.returncode


def combine_raw_streams(stdout: str, stderr: str) -> str:
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
    numeric_cols = ["nloc", "ccn", "token_count", "parameter_count", "length", "start_line", "end_line"]
    if with_ens:
        numeric_cols.append("max_nested_structures")
    for col in numeric_cols:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


def to_lizard_output_csv(lizard_df: pd.DataFrame) -> pd.DataFrame:
    if lizard_df.empty:
        return pd.DataFrame(columns=LIZARD_OUTPUT_COLUMNS)
    return pd.DataFrame({
        "NLOC": lizard_df["nloc"], "CCN": lizard_df["ccn"], "token": lizard_df["token_count"],
        "PARAM": lizard_df["parameter_count"], "length": lizard_df["length"],
        "location": lizard_df["location"].astype(str).str.strip('"'),
        "file": lizard_df["file"].astype(str).str.strip('"'),
        "function": lizard_df["function"].astype(str).str.strip('"'),
        "start_line": lizard_df["start_line"], "end_line": lizard_df["end_line"],
    })


def to_detailed_metrics(lizard_df: pd.DataFrame) -> pd.DataFrame:
    if lizard_df.empty:
        return pd.DataFrame(columns=DETAILED_COLUMNS)
    return pd.DataFrame({
        "file": lizard_df["file"].astype(str).str.strip('"'),
        "function": lizard_df["function"].astype(str).str.strip('"'),
        "nloc": lizard_df["nloc"], "cyclomatic_complexity": lizard_df["ccn"],
        "token_count": lizard_df["token_count"], "parameter_count": lizard_df["parameter_count"],
        "function_length": lizard_df["length"], "start_line": lizard_df["start_line"],
        "end_line": lizard_df["end_line"],
    })


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
        rows.append({
            "file": file_path, "function": function_name,
            "start_line": start_line, "end_line": end_line,
            "max_nesting_depth": reported if reported is not None else 0,
            "status": "reported" if reported is not None else "missing",
        })
    return pd.DataFrame(rows, columns=NESTING_COLUMNS)


def resolve_halstead_volume(total_tokens: float, configured: float | None) -> float:
    if configured is not None and configured > 0:
        return float(configured)
    return max(float(total_tokens), 1.0)


def compute_maintainability_index(avg_ccn: float, total_nloc: float, halstead_volume: float) -> float:
    loc = max(float(total_nloc), 1.0)
    volume = max(float(halstead_volume), 1.0)
    return round(171 - 5.2 * math.log(volume) - 0.23 * avg_ccn - 16.2 * math.log(loc), 4)


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


def preview_raw_output(raw_text: str, preview_lines: int, output_path: Path) -> None:
    lines = raw_text.splitlines()
    print(f"\n{'=' * 80}")
    print(f"RAW LIZARD OUTPUT PREVIEW (first {preview_lines} lines)")
    print(f"{'=' * 80}\n")
    if not lines:
        print("(empty raw output)")
        return
    print("\n".join(lines[:preview_lines]))
    remaining = len(lines) - preview_lines
    if remaining > 0:
        print(f"\n... ({remaining} more lines saved to {output_path})")
'''


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": [line + "\n" for line in source.split("\n")]}


def code(source: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [line + "\n" for line in source.split("\n")]}


cells = [
    md(
        "# Lizard Maintainability Rating (SQALE A–E) — Raw Output Extraction (C)\n\n"
        "This notebook analyzes **C repositories** with **Lizard** and captures complete raw tool output "
        "for Cyclomatic Complexity, Maximum Nesting Depth, Function Length, NLOC, Token Count, "
        "Parameter Count, Maintainability Index, and Maintainability Rating (A–E).\n\n"
        "**Default benchmark repository:** [redis/redis](https://github.com/redis/redis)"
    ),
    md("## Section 1 — Install Dependencies\n\nInstall open-source Python packages and verify Lizard."),
    code("!pip install -q lizard pandas gitpython jupyter\n\nimport subprocess, sys\nsubprocess.run([sys.executable, '-m', 'lizard', '--version'], check=False)"),
    md("## Section 2 — Configuration\n\nSet repository source, workspace, output directory, and optional Halstead Volume."),
    code(
        "USE_GIT_URL = True\n\n"
        "REPO_URL = 'https://github.com/redis/redis.git'\n\n"
        "LOCAL_REPO_PATH = '/content/redis'\n\n"
        "WORKSPACE_DIR = './workspace'\n\n"
        "OUTPUT_DIR = './outputs'\n\n"
        "IF_CLONE_EXISTS = 'reuse'\n\n"
        "CLONE_DEPTH = 1\n\n"
        "STREAM_RAW_OUTPUT = False\n\n"
        "RAW_OUTPUT_PREVIEW_LINES = 150\n\n"
        "# User-supplied or externally computed Halstead Volume for MI formula.\n"
        "# When None, aggregate token count from Lizard is used as a fallback proxy.\n"
        "HALSTEAD_VOLUME = None\n\n"
        "# Fast validation benchmark:\n"
        "# USE_GIT_URL = False\n"
        "# LOCAL_REPO_PATH = './workspace/sqale_rating_benchmark'"
    ),
    md("## Section 3 — Imports and Utility Functions"),
    code("from pathlib import Path\n\n" + UTILS.strip()),
    md("## Section 4 — Repository Setup"),
    code(
        "OUTPUT_PATH = Path(OUTPUT_DIR).resolve()\n"
        "WORKSPACE_PATH = Path(WORKSPACE_DIR).resolve()\n"
        "ERROR_LOG_PATH = OUTPUT_PATH / 'error_log.txt'\n\n"
        "ensure_output_dir(OUTPUT_PATH)\n"
        "logger = NotebookLogger(ERROR_LOG_PATH)\n\n"
        "try:\n"
        "    REPO_PATH = resolve_repository_path(\n"
        "        use_git_url=USE_GIT_URL,\n"
        "        repo_url=REPO_URL,\n"
        "        local_repo_path=LOCAL_REPO_PATH,\n"
        "        workspace_dir=WORKSPACE_PATH,\n"
        "        if_clone_exists=IF_CLONE_EXISTS,\n"
        "        logger=logger,\n"
        "        clone_depth=CLONE_DEPTH,\n"
        "    )\n"
        "except Exception as exc:\n"
        "    logger.error(f'Repository setup failed: {exc}')\n"
        "    raise\n\n"
        "C_FILES = discover_c_files(REPO_PATH)\n"
        "if not C_FILES:\n"
        "    logger.error('No C source files found in repository.', file=str(REPO_PATH))\n"
        "    raise FileNotFoundError('No C source files found.')\n\n"
        "REPO_STATS = compute_repository_stats(REPO_PATH, C_FILES)\n"
        "logger.info(f'Repository ready at: {REPO_PATH}')\n"
        "print(f\"Repository: {REPO_STATS['repository_name']}\")\n"
        "print(f\"Size (C files): {REPO_STATS['repository_size_bytes']:,} bytes\")\n"
        "print(f\"Directories: {REPO_STATS['directory_count']:,}\")\n"
        "print(f\"C files: {REPO_STATS['c_file_count']:,}\")"
    ),
    md("## Section 5 — Discover C Files"),
    code(
        "INVENTORY_CSV = OUTPUT_PATH / 'c_files_inventory.csv'\n"
        "save_c_inventory(C_FILES, INVENTORY_CSV)\n\n"
        "print(f'Total C Files Found: {len(C_FILES)}')\n"
        "print(f'Saved inventory to: {INVENTORY_CSV}')"
    ),
    md(
        "## Section 6 — Execute Lizard\n\n"
        "Run `lizard`, `lizard --csv`, and `lizard --csv -ENS`. Preserve stdout/stderr exactly as emitted."
    ),
    code(
        "LIZARD_CONSOLE_CHUNKS: list[str] = []\n"
        "LIZARD_RAW: dict[str, str] = {}\n\n"
        "suites = [\n"
        "    ('text', build_lizard_command(REPO_PATH)),\n"
        "    ('csv', build_lizard_command(REPO_PATH, csv_output=True)),\n"
        "    ('csv_ens', build_lizard_command(REPO_PATH, csv_output=True, ens=True)),\n"
        "]\n\n"
        "for label, command in suites:\n"
        "    stdout, stderr, code = run_lizard_command(command, logger, stream_raw=STREAM_RAW_OUTPUT)\n"
        "    LIZARD_CONSOLE_CHUNKS.append(f'===== lizard {label} =====\\n' + combine_raw_streams(stdout, stderr))\n"
        "    LIZARD_RAW[label] = stdout\n"
        "    if code not in (0, 1):\n"
        "        logger.error(f'Lizard {label} run exited with code {code}', file=label)\n\n"
        "logger.info('Lizard execution complete.')"
    ),
    md("## Section 7 — Raw Output Extraction"),
    code(
        "CONSOLE_PATH = OUTPUT_PATH / 'lizard_raw_console_output.txt'\n"
        "CONSOLE_PATH.write_text('\\n'.join(LIZARD_CONSOLE_CHUNKS), encoding='utf-8')\n\n"
        "BASE_DF = parse_lizard_csv(LIZARD_RAW.get('csv', ''), with_ens=False)\n"
        "ENS_DF = parse_lizard_csv(LIZARD_RAW.get('csv_ens', ''), with_ens=True)\n\n"
        "OUTPUT_DF = to_lizard_output_csv(BASE_DF)\n"
        "OUTPUT_DF.to_csv(OUTPUT_PATH / 'lizard_output.csv', index=False)\n\n"
        "DETAILED_DF = to_detailed_metrics(BASE_DF)\n"
        "DETAILED_DF.to_csv(OUTPUT_PATH / 'lizard_detailed_metrics.csv', index=False)\n\n"
        "logger.info('Saved Lizard CSV outputs.')\n"
        "preview_raw_output(CONSOLE_PATH.read_text(encoding='utf-8'), RAW_OUTPUT_PREVIEW_LINES, CONSOLE_PATH)"
    ),
    md("## Section 8 — Maximum Nesting Depth Extraction\n\nExtract nesting depth using Lizard `-E NS` extension."),
    code(
        "NESTING_DF = build_nesting_depth_results(BASE_DF, ENS_DF)\n"
        "NESTING_CSV = OUTPUT_PATH / 'nesting_depth_results.csv'\n"
        "NESTING_DF.to_csv(NESTING_CSV, index=False)\n\n"
        "logger.info(f'Saved nesting depth results: {len(NESTING_DF)} functions')"
    ),
    md(
        "## Section 9 — Maintainability Metric Computation\n\n"
        "```text\n"
        "Maintainability_Index = 171 - 5.2 * ln(Halstead_Volume) - 0.23 * Cyclomatic_Complexity - 16.2 * ln(LOC)\n"
        "```\n\n"
        "Where `Cyclomatic_Complexity` is average CCN and `LOC` is total NLOC from Lizard."
    ),
    code(
        "ccn_values = pd.to_numeric(BASE_DF['ccn'], errors='coerce').dropna()\n"
        "nloc_values = pd.to_numeric(BASE_DF['nloc'], errors='coerce').dropna()\n"
        "token_values = pd.to_numeric(BASE_DF['token_count'], errors='coerce').dropna()\n\n"
        "avg_ccn = round(float(ccn_values.mean()), 4) if not ccn_values.empty else 0.0\n"
        "total_nloc = float(nloc_values.sum()) if not nloc_values.empty else 0.0\n"
        "total_tokens = float(token_values.sum()) if not token_values.empty else 0.0\n"
        "halstead_used = resolve_halstead_volume(total_tokens, HALSTEAD_VOLUME)\n"
        "mi_value = compute_maintainability_index(avg_ccn, total_nloc, halstead_used)\n\n"
        "MI_SUMMARY_DF = pd.DataFrame([{'metric_name': 'Maintainability_Index', 'metric_value': mi_value}])\n"
        "MI_SUMMARY_CSV = OUTPUT_PATH / 'maintainability_index_summary.csv'\n"
        "MI_SUMMARY_DF.to_csv(MI_SUMMARY_CSV, index=False)\n\n"
        "logger.info(f'Maintainability Index={mi_value} (Halstead Volume used={halstead_used})')\n"
        "display(MI_SUMMARY_DF)"
    ),
    md("## Section 10 — Maintainability Rating Computation\n\nSQALE A–E mapping from computed Maintainability Index."),
    code(
        "rating = mi_to_sqale_rating(mi_value)\n"
        "RATING_SUMMARY_DF = pd.DataFrame([{'metric_name': 'Maintainability_Rating', 'metric_value': rating}])\n"
        "RATING_SUMMARY_CSV = OUTPUT_PATH / 'maintainability_rating_summary.csv'\n"
        "RATING_SUMMARY_DF.to_csv(RATING_SUMMARY_CSV, index=False)\n\n"
        "logger.info(f'Maintainability Rating={rating}')\n"
        "display(RATING_SUMMARY_DF)"
    ),
    md("## Section 11 — Summary Dashboard"),
    code(
        "avg_nloc = round(float(nloc_values.mean()), 4) if not nloc_values.empty else 0.0\n"
        "avg_nesting = round(float(NESTING_DF['max_nesting_depth'].mean()), 4) if not NESTING_DF.empty else 0.0\n\n"
        "summary_df = pd.DataFrame([\n"
        "    {'Metric': 'Total C Files', 'Value': len(C_FILES)},\n"
        "    {'Metric': 'Average Cyclomatic Complexity', 'Value': avg_ccn},\n"
        "    {'Metric': 'Average Maximum Nesting Depth', 'Value': avg_nesting},\n"
        "    {'Metric': 'Average NLOC', 'Value': avg_nloc},\n"
        "    {'Metric': 'Maintainability Index', 'Value': mi_value},\n"
        "    {'Metric': 'Maintainability Rating', 'Value': rating},\n"
        "])\n"
        "display(summary_df)\n\n"
        "deliverables = [\n"
        "    CONSOLE_PATH, OUTPUT_PATH / 'lizard_output.csv', OUTPUT_PATH / 'lizard_detailed_metrics.csv',\n"
        "    NESTING_CSV, MI_SUMMARY_CSV, RATING_SUMMARY_CSV, INVENTORY_CSV, ERROR_LOG_PATH,\n"
        "]\n"
        "print('\\nDeliverables:')\n"
        "for path in deliverables:\n"
        "    print(f\"  [{'OK' if path.exists() else 'MISSING'}] {path}\")"
    ),
    md("## Section 12 — Error Handling"),
    code(
        "if ERROR_LOG_PATH.exists() and ERROR_LOG_PATH.stat().st_size > 0:\n"
        "    print(ERROR_LOG_PATH.read_text(encoding='utf-8'))\n"
        "else:\n"
        "    print('No errors logged.')"
    ),
    md(
        "## Section 13 — Deliverables\n\n"
        "```text\n"
        "outputs/\n"
        "├── lizard_raw_console_output.txt\n"
        "├── lizard_output.csv\n"
        "├── lizard_detailed_metrics.csv\n"
        "├── nesting_depth_results.csv\n"
        "├── maintainability_index_summary.csv\n"
        "├── maintainability_rating_summary.csv\n"
        "├── c_files_inventory.csv\n"
        "└── error_log.txt\n"
        "```"
    ),
]

NOTEBOOK.write_text(
    json.dumps(
        {
            "cells": cells,
            "metadata": {
                "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                "language_info": {"name": "python", "version": "3.11.0"},
            },
            "nbformat": 4,
            "nbformat_minor": 5,
        },
        indent=1,
    ),
    encoding="utf-8",
)
print(f"Wrote {NOTEBOOK}")
