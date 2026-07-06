"""Generate cloc_comment_to_code_ratio_extraction.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "cloc_comment_to_code_ratio_extraction.ipynb"

UTILS = r'''
from __future__ import annotations

import csv
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
from IPython.display import display
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

C_FILE_EXTENSIONS = {".c", ".h"}
EXCLUDED_DIR_NAMES = {".git", "build", "dist", "bin", "vendor", "docs", "tests", "third_party"}
CLOC_EXCLUDE_DIRS = "build,dist,bin,vendor,docs,tests,third_party,.git"
CLOC_VERSION = "2.08"
CLOC_RELEASE_TAG = "v2.08"
CLOC_WINDOWS_URL = f"https://github.com/AlDanial/cloc/releases/download/{CLOC_RELEASE_TAG}/cloc-{CLOC_VERSION}.exe"
CLOC_PERL_URL = f"https://github.com/AlDanial/cloc/releases/download/{CLOC_RELEASE_TAG}/cloc-{CLOC_VERSION}.pl"
METRICS_COLUMNS = ["language", "files", "blank_lines", "comment_lines", "code_lines"]


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


def resolve_cloc_executable(runtimes_root: Path) -> Path:
    env_path = os.environ.get("CLOC")
    if env_path:
        candidate = Path(env_path)
        if candidate.exists():
            return candidate.resolve()
    which = shutil.which("cloc")
    if which:
        return Path(which).resolve()
    runtime_dir = runtimes_root / "cloc"
    for candidate in [runtime_dir / "cloc.exe", runtime_dir / "cloc.pl", runtime_dir / "cloc"]:
        if candidate.exists():
            return candidate.resolve()
    downloaded = download_cloc(runtime_dir)
    return downloaded.resolve()


def build_cloc_command(cloc_exe: Path, repo_path: Path, *, json_output: bool = False, csv_output: bool = False) -> list[str]:
    if cloc_exe.suffix.lower() == ".pl":
        command = ["perl", str(cloc_exe)]
    else:
        command = [str(cloc_exe)]
    command.extend([
        str(repo_path), "--include-lang=C", f"--exclude-dir={CLOC_EXCLUDE_DIRS}", "--quiet",
    ])
    if json_output:
        command.append("--json")
    if csv_output:
        command.append("--csv")
    return command


def run_cloc_command(command: list[str], logger: NotebookLogger) -> tuple[str, str, int]:
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
    rows = []
    for key, value in payload.items():
        if key == "header" or not isinstance(value, dict):
            continue
        if "code" not in value:
            continue
        rows.append({
            "language": key,
            "files": value.get("nFiles", value.get("files", "")),
            "blank_lines": value.get("blank", ""),
            "comment_lines": value.get("comment", ""),
            "code_lines": value.get("code", ""),
        })
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


def preview_raw_output(raw_text: str, preview_lines: int, output_path: Path) -> None:
    lines = raw_text.splitlines()
    print(f"\n{'=' * 80}")
    print(f"RAW CLOC OUTPUT PREVIEW (first {preview_lines} lines)")
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
        "# cloc Comment-to-Code Ratio — Raw Output Extraction (C)\n\n"
        "This notebook analyzes **C repositories** with **cloc (Count Lines of Code)** and captures complete raw "
        "tool output for Comment-to-Code Ratio, blank lines, comment lines, and code lines.\n\n"
        "**Default benchmark repository:** [redis/redis](https://github.com/redis/redis)\n\n"
        "> **Note:** Comment-to-Code Ratio is a **Derived** metric computed from cloc output "
        "(comment / code). cloc does not emit this ratio directly."
    ),
    md(
        "## Section 1 — Install Dependencies\n\n"
        "Install Python packages and verify cloc. If cloc is unavailable via pip, use the OS package manager "
        "(e.g. `sudo apt-get install -y cloc` on Ubuntu)."
    ),
    code(
        "!pip install -q pandas gitpython jupyter\n\n"
        "import shutil, subprocess, sys\n\n"
        "try:\n"
        "    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'cloc'], check=False)\n"
        "except Exception:\n"
        "    pass\n\n"
        "if not shutil.which('cloc'):\n"
        "    print('cloc not on PATH; notebook will bootstrap to ../../runtimes/cloc/ if needed.')\n"
        "else:\n"
        "    subprocess.run(['cloc', '--version'], check=False)"
    ),
    md("## Section 2 — Configuration"),
    code(
        "USE_GIT_URL = True\n\n"
        "REPO_URL = 'https://github.com/redis/redis.git'\n\n"
        "LOCAL_REPO_PATH = '/content/redis'\n\n"
        "WORKSPACE_DIR = './workspace'\n\n"
        "OUTPUT_DIR = './outputs'\n\n"
        "IF_CLONE_EXISTS = 'reuse'\n\n"
        "CLONE_DEPTH = 1\n\n"
        "RAW_OUTPUT_PREVIEW_LINES = 150\n\n"
        "from pathlib import Path\n\n"
        "METRIC_ROOT = Path('.').resolve()\n"
        "PROJECT_ROOT = METRIC_ROOT\n"
        "for _ in range(8):\n"
        "    if (PROJECT_ROOT / 'runtimes').is_dir() or (PROJECT_ROOT / 'README.md').is_file():\n"
        "        break\n"
        "    if PROJECT_ROOT.parent == PROJECT_ROOT:\n"
        "        break\n"
        "    PROJECT_ROOT = PROJECT_ROOT.parent\n"
        "RUNTIMES_ROOT = PROJECT_ROOT / 'runtimes'\n\n"
        "# Fast validation benchmark:\n"
        "# USE_GIT_URL = False\n"
        "# LOCAL_REPO_PATH = './workspace/comment_to_code_ratio_benchmark'"
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
        "        use_git_url=USE_GIT_URL, repo_url=REPO_URL, local_repo_path=LOCAL_REPO_PATH,\n"
        "        workspace_dir=WORKSPACE_PATH, if_clone_exists=IF_CLONE_EXISTS, logger=logger, clone_depth=CLONE_DEPTH,\n"
        "    )\n"
        "except Exception as exc:\n"
        "    logger.error(f'Repository setup failed: {exc}')\n"
        "    raise\n\n"
        "C_FILES = discover_c_files(REPO_PATH)\n"
        "if not C_FILES:\n"
        "    logger.error('No C source files found in repository.', file=str(REPO_PATH))\n"
        "    raise FileNotFoundError('No C source files found.')\n\n"
        "REPO_STATS = compute_repository_stats(REPO_PATH, C_FILES)\n"
        "CLOC_EXE = resolve_cloc_executable(RUNTIMES_ROOT)\n"
        "logger.info(f'Repository ready at: {REPO_PATH}')\n"
        "logger.info(f'Using cloc executable: {CLOC_EXE}')\n"
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
    md("## Section 6 — Execute cloc\n\nRun cloc in text, JSON, and CSV modes. Preserve stdout/stderr exactly as emitted."),
    code(
        "CLOC_CONSOLE_CHUNKS: list[str] = []\n"
        "CLOC_JSON = ''\n"
        "CLOC_CSV = ''\n\n"
        "for label, json_output, csv_output in [('text', False, False), ('json', True, False), ('csv', False, True)]:\n"
        "    cmd = build_cloc_command(CLOC_EXE, REPO_PATH, json_output=json_output, csv_output=csv_output)\n"
        "    stdout, stderr, code = run_cloc_command(cmd, logger)\n"
        "    CLOC_CONSOLE_CHUNKS.append(f'===== cloc ({label}) =====\\n' + combine_raw_streams(stdout, stderr))\n"
        "    if code != 0:\n"
        "        logger.error(f'cloc {label} run exited with code {code}', file=f'cloc_{label}')\n"
        "    if json_output:\n"
        "        CLOC_JSON = stdout\n"
        "    elif csv_output:\n"
        "        CLOC_CSV = stdout\n\n"
        "logger.info('cloc execution complete.')"
    ),
    md("## Section 7 — Raw Output Extraction"),
    code(
        "CONSOLE_PATH = OUTPUT_PATH / 'cloc_raw_console_output.txt'\n"
        "JSON_PATH = OUTPUT_PATH / 'cloc_output.json'\n"
        "CSV_PATH = OUTPUT_PATH / 'cloc_output.csv'\n\n"
        "CONSOLE_PATH.write_text('\\n'.join(CLOC_CONSOLE_CHUNKS), encoding='utf-8')\n"
        "JSON_PATH.write_text(CLOC_JSON, encoding='utf-8')\n"
        "CSV_PATH.write_text(CLOC_CSV, encoding='utf-8')\n\n"
        "logger.info('Saved cloc raw console, JSON, and CSV outputs.')\n"
        "preview_raw_output(CONSOLE_PATH.read_text(encoding='utf-8'), RAW_OUTPUT_PREVIEW_LINES, CONSOLE_PATH)"
    ),
    md("## Section 8 — Parse cloc Output"),
    code(
        "JSON_PAYLOAD = parse_json_payload(CLOC_JSON)\n"
        "METRICS_DF = parse_cloc_metrics(JSON_PAYLOAD)\n"
        "METRICS_CSV = OUTPUT_PATH / 'cloc_metrics.csv'\n"
        "METRICS_DF.to_csv(METRICS_CSV, index=False)\n\n"
        "logger.info(f'Parsed cloc metrics rows={len(METRICS_DF)}')\n"
        "display(METRICS_DF)"
    ),
    md(
        "## Section 9 — Comment-to-Code Ratio (Derived)\n\n"
        "**Derived metric** (not emitted directly by cloc):\n\n"
        "```text\n"
        "Total_Comment_Lines = comment\n"
        "Comment_to_Code_Ratio = comment / code\n"
        "```"
    ),
    code(
        "C_METRICS = extract_language_metrics(JSON_PAYLOAD, 'C')\n"
        "COMMENT_METRICS = compute_comment_metrics(C_METRICS)\n"
        "RATIO_CSV = OUTPUT_PATH / 'comment_to_code_ratio_summary.csv'\n"
        "pd.DataFrame([\n"
        "    {'metric_name': 'Comment_to_Code_Ratio', 'metric_value': COMMENT_METRICS['comment_to_code_ratio']},\n"
        "]).to_csv(RATIO_CSV, index=False)\n\n"
        "logger.info(\n"
        "    f\"Comment-to-Code Ratio={COMMENT_METRICS['comment_to_code_ratio']} \"\n"
        "    f\"(Derived from cloc metrics)\"\n"
        ")\n"
        "display(pd.read_csv(RATIO_CSV))"
    ),
    md("## Section 10 — Comment Percentage (Derived)"),
    code(
        "PERCENTAGE_CSV = OUTPUT_PATH / 'comment_percentage_summary.csv'\n"
        "pd.DataFrame([\n"
        "    {'metric_name': 'Comment_to_Code_Percentage', 'metric_value': COMMENT_METRICS['comment_to_code_percentage']},\n"
        "]).to_csv(PERCENTAGE_CSV, index=False)\n\n"
        "logger.info(f\"Comment Percentage={COMMENT_METRICS['comment_to_code_percentage']}%\")\n"
        "display(pd.read_csv(PERCENTAGE_CSV))"
    ),
    md("## Section 11 — Summary Dashboard"),
    code(
        "summary_df = pd.DataFrame([\n"
        "    {'Metric': 'Total C Files', 'Value': len(C_FILES)},\n"
        "    {'Metric': 'Total Blank Lines', 'Value': int(COMMENT_METRICS['blank_lines'])},\n"
        "    {'Metric': 'Total Comment Lines', 'Value': int(COMMENT_METRICS['comment_lines'])},\n"
        "    {'Metric': 'Total Code Lines', 'Value': int(COMMENT_METRICS['code_lines'])},\n"
        "    {'Metric': 'Comment-to-Code Ratio (Derived)', 'Value': COMMENT_METRICS['comment_to_code_ratio']},\n"
        "    {'Metric': 'Comment Percentage (Derived)', 'Value': COMMENT_METRICS['comment_to_code_percentage']},\n"
        "])\n"
        "display(summary_df)\n\n"
        "deliverables = [\n"
        "    CONSOLE_PATH, JSON_PATH, CSV_PATH, METRICS_CSV, RATIO_CSV, PERCENTAGE_CSV,\n"
        "    INVENTORY_CSV, ERROR_LOG_PATH,\n"
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
        "├── cloc_raw_console_output.txt\n"
        "├── cloc_output.json\n"
        "├── cloc_output.csv\n"
        "├── cloc_metrics.csv\n"
        "├── comment_to_code_ratio_summary.csv\n"
        "├── comment_percentage_summary.csv\n"
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
