"""Generate radon_maintainability_rating_extraction.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "radon_maintainability_rating_extraction.ipynb"

UTILS = r'''
from __future__ import annotations

import csv
import json
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

EXCLUDED_DIR_NAMES = {
    ".git", "venv", ".venv", "env", "__pycache__", "build", "dist", ".tox", "node_modules", "site-packages",
}
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


def discover_python_files(repo_path: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo_path.rglob("*.py"):
        if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            continue
        files.append(path.resolve())
    return sorted(files)


def compute_repository_stats(repo_path: Path, python_files: list[Path]) -> dict[str, Any]:
    total_size = sum(path.stat().st_size for path in python_files)
    directories = {path.parent for path in python_files}
    return {
        "repository_name": repo_path.name,
        "repository_size_bytes": total_size,
        "directory_count": len(directories),
        "python_file_count": len(python_files),
    }


def save_python_inventory(python_files: list[Path], output_csv: Path) -> None:
    pd.DataFrame(
        [{"file_path": str(p), "file_name": p.name, "directory": str(p.parent)} for p in python_files]
    ).to_csv(output_csv, index=False)


def build_radon_command(repo_path: Path, subcommand: str, *, json_output: bool = False, extra_args: list[str] | None = None) -> list[str]:
    command = [PY, "-m", "radon", subcommand, str(repo_path)]
    if subcommand in {"cc", "mi"}:
        command.append("-s")
    if extra_args:
        command.extend(extra_args)
    if json_output:
        command.append("-j")
    return command


def run_radon_command(command: list[str], logger: NotebookLogger, stream_raw: bool = False) -> tuple[str, str, int]:
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


def parse_json_payload(text: str) -> dict[str, Any]:
    if not text.strip():
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_cc_results(payload: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for file_path, blocks in payload.items():
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            rows.append({
                "file": file_path,
                "function": block.get("name", ""),
                "complexity": block.get("complexity", ""),
                "rank": block.get("rank", ""),
                "line": block.get("lineno", ""),
            })
    return pd.DataFrame(rows, columns=["file", "function", "complexity", "rank", "line"])


def parse_mi_results(payload: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for file_path, metrics in payload.items():
        if not isinstance(metrics, dict):
            continue
        rows.append({
            "file": file_path,
            "maintainability_index": metrics.get("mi", ""),
            "rank": metrics.get("rank", ""),
        })
    return pd.DataFrame(rows, columns=["file", "maintainability_index", "rank"])


def parse_raw_results(payload: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for file_path, metrics in payload.items():
        if not isinstance(metrics, dict):
            continue
        rows.append({
            "file": file_path,
            "loc": metrics.get("loc", ""),
            "lloc": metrics.get("lloc", ""),
            "sloc": metrics.get("sloc", ""),
            "comments": metrics.get("comments", ""),
            "multi": metrics.get("multi", ""),
            "blank": metrics.get("blank", ""),
        })
    return pd.DataFrame(rows, columns=["file", "loc", "lloc", "sloc", "comments", "multi", "blank"])


def parse_halstead_results(payload: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for file_path, metrics in payload.items():
        if not isinstance(metrics, dict):
            continue
        total = metrics.get("total", {})
        if not isinstance(total, dict):
            continue
        rows.append({
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
        })
    return pd.DataFrame(
        rows,
        columns=["file", "h1", "h2", "N1", "N2", "vocabulary", "length", "volume", "difficulty", "effort", "bugs", "time"],
    )


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


def compute_maintainability_summary(mi_df: pd.DataFrame) -> pd.DataFrame:
    mi_values = pd.to_numeric(mi_df["maintainability_index"], errors="coerce").dropna()
    avg_mi = round(float(mi_values.mean()), 4) if not mi_values.empty else 0.0
    rating = mi_to_sqale_rating(avg_mi) if not mi_values.empty else "E"
    return pd.DataFrame([
        {"metric_name": "Maintainability_Index", "metric_value": avg_mi},
        {"metric_name": "Maintainability_Rating", "metric_value": rating},
    ])


def preview_raw_output(raw_text: str, preview_lines: int, output_path: Path) -> None:
    lines = raw_text.splitlines()
    print(f"\n{'=' * 80}")
    print(f"RAW RADON OUTPUT PREVIEW (first {preview_lines} lines)")
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
        "# Radon Maintainability Rating (SQALE A–E) — Raw Output Extraction (Python)\n\n"
        "This notebook analyzes **Python repositories** with **Radon** and captures complete raw tool output "
        "for Maintainability Index, Maintainability Rating (A–E), Cyclomatic Complexity, Raw Metrics, and Halstead Metrics.\n\n"
        "**Default benchmark repository:** [pallets/flask](https://github.com/pallets/flask)"
    ),
    md("## Section 1 — Install Dependencies\n\nInstall open-source Python packages and verify Radon."),
    code("!pip install -q radon pandas gitpython jupyter\n\nimport subprocess, sys\nsubprocess.run([sys.executable, '-m', 'radon', '--version'], check=False)"),
    md("## Section 2 — Configuration\n\nSet repository source, workspace, and output directory."),
    code(
        "USE_GIT_URL = True\n\n"
        "REPO_URL = 'https://github.com/pallets/flask.git'\n\n"
        "LOCAL_REPO_PATH = '/content/flask'\n\n"
        "WORKSPACE_DIR = './workspace'\n\n"
        "OUTPUT_DIR = './outputs'\n\n"
        "IF_CLONE_EXISTS = 'reuse'\n\n"
        "CLONE_DEPTH = 1\n\n"
        "STREAM_RAW_OUTPUT = False\n\n"
        "RAW_OUTPUT_PREVIEW_LINES = 150\n\n"
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
        "REPO_STATS = compute_repository_stats(REPO_PATH, discover_python_files(REPO_PATH))\n"
        "logger.info(f'Repository ready at: {REPO_PATH}')\n"
        "print(f\"Repository: {REPO_STATS['repository_name']}\")\n"
        "print(f\"Size (Python files): {REPO_STATS['repository_size_bytes']:,} bytes\")\n"
        "print(f\"Directories: {REPO_STATS['directory_count']:,}\")\n"
        "print(f\"Python files: {REPO_STATS['python_file_count']:,}\")"
    ),
    md("## Section 5 — Discover Python Files"),
    code(
        "PYTHON_FILES = discover_python_files(REPO_PATH)\n"
        "INVENTORY_CSV = OUTPUT_PATH / 'python_files_inventory.csv'\n"
        "save_python_inventory(PYTHON_FILES, INVENTORY_CSV)\n\n"
        "print(f'Total Python Files Found: {len(PYTHON_FILES)}')\n"
        "print(f'Saved inventory to: {INVENTORY_CSV}')"
    ),
    md(
        "## Section 6 — Execute Radon\n\n"
        "Run Radon CC, MI, Raw, and Halstead commands. Preserve stdout/stderr exactly as emitted."
    ),
    code(
        "RADON_CONSOLE_CHUNKS: list[str] = []\n"
        "RADON_JSON: dict[str, str] = {}\n\n"
        "if not PYTHON_FILES:\n"
        "    logger.error('No Python files discovered; skipping Radon execution.')\n"
        "else:\n"
        "    for subcommand, extra in [('cc', ['-a']), ('mi', []), ('raw', []), ('hal', [])]:\n"
        "        text_cmd = build_radon_command(REPO_PATH, subcommand, json_output=False, extra_args=extra)\n"
        "        json_cmd = build_radon_command(REPO_PATH, subcommand, json_output=True, extra_args=extra)\n"
        "        text_stdout, text_stderr, text_code = run_radon_command(text_cmd, logger, stream_raw=STREAM_RAW_OUTPUT)\n"
        "        json_stdout, json_stderr, json_code = run_radon_command(json_cmd, logger, stream_raw=False)\n"
        "        RADON_CONSOLE_CHUNKS.append(f'===== radon {subcommand} (text) =====\\n' + combine_raw_streams(text_stdout, text_stderr))\n"
        "        RADON_CONSOLE_CHUNKS.append(f'===== radon {subcommand} (json) =====\\n' + combine_raw_streams(json_stdout, json_stderr))\n"
        "        RADON_JSON[subcommand] = json_stdout\n"
        "        if text_code not in (0, 1):\n"
        "            logger.error(f'Radon {subcommand} text run exited with code {text_code}', file=subcommand)\n"
        "        if json_code not in (0, 1):\n"
        "            logger.error(f'Radon {subcommand} json run exited with code {json_code}', file=subcommand)\n\n"
        "logger.info('Radon execution complete.')"
    ),
    md("## Section 7 — Raw Output Extraction"),
    code(
        "CONSOLE_PATH = OUTPUT_PATH / 'radon_raw_console_output.txt'\n"
        "CC_JSON_PATH = OUTPUT_PATH / 'radon_cc_output.json'\n"
        "MI_JSON_PATH = OUTPUT_PATH / 'radon_mi_output.json'\n"
        "RAW_JSON_PATH = OUTPUT_PATH / 'radon_raw_output.json'\n"
        "HAL_JSON_PATH = OUTPUT_PATH / 'radon_halstead_output.json'\n\n"
        "CONSOLE_PATH.write_text('\\n'.join(RADON_CONSOLE_CHUNKS), encoding='utf-8')\n"
        "CC_JSON_PATH.write_text(RADON_JSON.get('cc', ''), encoding='utf-8')\n"
        "MI_JSON_PATH.write_text(RADON_JSON.get('mi', ''), encoding='utf-8')\n"
        "RAW_JSON_PATH.write_text(RADON_JSON.get('raw', ''), encoding='utf-8')\n"
        "HAL_JSON_PATH.write_text(RADON_JSON.get('hal', ''), encoding='utf-8')\n\n"
        "logger.info('Saved Radon raw JSON and console outputs.')\n"
        "preview_raw_output(CONSOLE_PATH.read_text(encoding='utf-8'), RAW_OUTPUT_PREVIEW_LINES, CONSOLE_PATH)"
    ),
    md("## Section 8 — Parse Results"),
    code(
        "CC_DF = parse_cc_results(parse_json_payload(RADON_JSON.get('cc', '')))\n"
        "MI_DF = parse_mi_results(parse_json_payload(RADON_JSON.get('mi', '')))\n"
        "RAW_DF = parse_raw_results(parse_json_payload(RADON_JSON.get('raw', '')))\n"
        "HAL_DF = parse_halstead_results(parse_json_payload(RADON_JSON.get('hal', '')))\n\n"
        "CC_DF.to_csv(OUTPUT_PATH / 'cyclomatic_complexity_results.csv', index=False)\n"
        "MI_DF.to_csv(OUTPUT_PATH / 'maintainability_index_results.csv', index=False)\n"
        "RAW_DF.to_csv(OUTPUT_PATH / 'raw_metrics_results.csv', index=False)\n"
        "HAL_DF.to_csv(OUTPUT_PATH / 'halstead_metrics_results.csv', index=False)\n\n"
        "logger.info(f'Parsed CC rows={len(CC_DF)}, MI rows={len(MI_DF)}, Raw rows={len(RAW_DF)}, Halstead rows={len(HAL_DF)}')"
    ),
    md("## Section 9 — Maintainability Rating Computation\n\nSQALE A–E mapping from average Maintainability Index."),
    code(
        "SUMMARY_DF = compute_maintainability_summary(MI_DF)\n"
        "SUMMARY_CSV = OUTPUT_PATH / 'maintainability_rating_summary.csv'\n"
        "SUMMARY_DF.to_csv(SUMMARY_CSV, index=False)\n\n"
        "logger.info(f'Saved maintainability rating summary: {SUMMARY_CSV}')\n"
        "display(SUMMARY_DF)"
    ),
    md("## Section 10 — Summary Dashboard"),
    code(
        "avg_mi = float(SUMMARY_DF.loc[SUMMARY_DF['metric_name'] == 'Maintainability_Index', 'metric_value'].iloc[0])\n"
        "rating = str(SUMMARY_DF.loc[SUMMARY_DF['metric_name'] == 'Maintainability_Rating', 'metric_value'].iloc[0])\n"
        "avg_cc = round(float(pd.to_numeric(CC_DF['complexity'], errors='coerce').dropna().mean()), 4) if not CC_DF.empty else 0.0\n"
        "total_loc = int(pd.to_numeric(RAW_DF['loc'], errors='coerce').fillna(0).sum()) if not RAW_DF.empty else 0\n\n"
        "summary_df = pd.DataFrame([\n"
        "    {'Metric': 'Total Python Files', 'Value': len(PYTHON_FILES)},\n"
        "    {'Metric': 'Average Cyclomatic Complexity', 'Value': avg_cc},\n"
        "    {'Metric': 'Average Maintainability Index', 'Value': avg_mi},\n"
        "    {'Metric': 'Maintainability Rating', 'Value': rating},\n"
        "    {'Metric': 'Total LOC', 'Value': total_loc},\n"
        "])\n"
        "display(summary_df)\n\n"
        "deliverables = [\n"
        "    CONSOLE_PATH, CC_JSON_PATH, MI_JSON_PATH, RAW_JSON_PATH, HAL_JSON_PATH,\n"
        "    OUTPUT_PATH / 'cyclomatic_complexity_results.csv',\n"
        "    OUTPUT_PATH / 'maintainability_index_results.csv',\n"
        "    OUTPUT_PATH / 'raw_metrics_results.csv',\n"
        "    OUTPUT_PATH / 'halstead_metrics_results.csv',\n"
        "    SUMMARY_CSV, INVENTORY_CSV, ERROR_LOG_PATH,\n"
        "]\n"
        "print('\\nDeliverables:')\n"
        "for path in deliverables:\n"
        "    print(f\"  [{'OK' if path.exists() else 'MISSING'}] {path}\")"
    ),
    md("## Section 11 — Error Handling"),
    code(
        "if ERROR_LOG_PATH.exists() and ERROR_LOG_PATH.stat().st_size > 0:\n"
        "    print(ERROR_LOG_PATH.read_text(encoding='utf-8'))\n"
        "else:\n"
        "    print('No errors logged.')"
    ),
    md(
        "## Section 12 — Deliverables\n\n"
        "```text\n"
        "outputs/\n"
        "├── radon_cc_output.json\n"
        "├── radon_mi_output.json\n"
        "├── radon_raw_output.json\n"
        "├── radon_halstead_output.json\n"
        "├── radon_raw_console_output.txt\n"
        "├── cyclomatic_complexity_results.csv\n"
        "├── maintainability_index_results.csv\n"
        "├── raw_metrics_results.csv\n"
        "├── halstead_metrics_results.csv\n"
        "├── maintainability_rating_summary.csv\n"
        "├── python_files_inventory.csv\n"
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
