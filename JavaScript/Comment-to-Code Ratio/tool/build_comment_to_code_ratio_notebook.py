"""Generate eslint_comment_to_code_ratio_extraction.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "eslint_comment_to_code_ratio_extraction.ipynb"

NOTEBOOK_UTILS = r'''
from __future__ import annotations

import csv
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from IPython.display import display
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

EXCLUDED_DIR_NAMES = {
    ".git", "node_modules", "dist", "build", "coverage", "vendor", "docs", "test", "tests",
}


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


def discover_javascript_files(repo_path: Path) -> list[Path]:
    extensions = {".js", ".mjs", ".cjs"}
    files: list[Path] = []
    for path in repo_path.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            continue
        files.append(path.resolve())
    return sorted(files)


def compute_repository_stats(repo_path: Path, js_files: list[Path]) -> dict[str, Any]:
    total_size = sum(path.stat().st_size for path in js_files)
    directories = {path.parent for path in js_files}
    return {
        "repository_name": repo_path.name,
        "repository_size_bytes": total_size,
        "directory_count": len(directories),
        "javascript_file_count": len(js_files),
    }


def save_javascript_inventory(js_files: list[Path], output_csv: Path) -> None:
    pd.DataFrame(
        [{"file_path": str(p), "file_name": p.name, "directory": str(p.parent)} for p in js_files]
    ).to_csv(output_csv, index=False)


def preview_raw_output(raw_text: str, preview_lines: int, output_path: Path) -> None:
    lines = raw_text.splitlines()
    print(f"\n{'=' * 80}")
    print(f"RAW ESLINT OUTPUT PREVIEW (first {preview_lines} lines)")
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
        "# ESLint Comment-to-Code Ratio — Raw Output Extraction (JavaScript)\n\n"
        "This notebook analyzes **JavaScript repositories** with **ESLint** and derives **Comment-to-Code Ratio** "
        "from extracted comment and code line metrics alongside ESLint findings.\n\n"
        "**Default benchmark repository:** [expressjs/express](https://github.com/expressjs/express)\n\n"
        "> **Note:** Comment-to-Code Ratio is a **Derived** metric. ESLint does not emit it directly; "
        "the notebook parses JavaScript sources for comment/code lines and runs ESLint for documentation and maintainability rules."
    ),
    md(
        "## Section 1 — Install Dependencies\n\n"
        "Install Python packages and verify Node.js / ESLint."
    ),
    code(
        "!pip install -q pandas gitpython jupyter\n\n"
        "import shutil, subprocess, sys\n\n"
        "for cmd in [['node', '--version'], ['npm', '--version']]:\n"
        "    subprocess.run(cmd, check=False)\n\n"
        "if not shutil.which('eslint'):\n"
        "    !npm install -g eslint\n\n"
        "subprocess.run(['eslint', '--version'], check=False)"
    ),
    md("## Section 2 — Configuration"),
    code(
        "USE_GIT_URL = True\n\n"
        "REPO_URL = 'https://github.com/expressjs/express.git'\n\n"
        "LOCAL_REPO_PATH = '/content/express'\n\n"
        "WORKSPACE_DIR = './workspace'\n\n"
        "OUTPUT_DIR = './outputs'\n\n"
        "IF_CLONE_EXISTS = 'reuse'\n\n"
        "CLONE_DEPTH = 1\n\n"
        "RAW_OUTPUT_PREVIEW_LINES = 150\n\n"
        "from pathlib import Path\n\n"
        "METRIC_ROOT = Path('.').resolve()\n"
        "PROJECT_ROOT = METRIC_ROOT\n"
        "for _ in range(8):\n"
        "    runtimes = PROJECT_ROOT / 'runtimes'\n"
        "    if runtimes.is_dir() and (runtimes / 'node_modules').is_dir():\n"
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
    code(
        "from pathlib import Path\n"
        "import sys\n\n"
        "TOOL_ROOT = Path('tool').resolve()\n"
        "if str(TOOL_ROOT) not in sys.path:\n"
        "    sys.path.insert(0, str(TOOL_ROOT))\n\n"
        + NOTEBOOK_UTILS.strip()
        + "\n\nfrom run_comment_to_code_ratio_benchmark_impl import (\n"
        "    build_comment_code_metrics,\n"
        "    build_eslint_command,\n"
        "    build_maintainability_summary,\n"
        "    combine_raw,\n"
        "    compute_comment_ratio,\n"
        "    ensure_eslint_config,\n"
        "    parse_eslint_json,\n"
        "    records_to_findings,\n"
        "    resolve_eslint_executable,\n"
        "    run_command,\n"
        ")\n"
    ),
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
        "JS_FILES = discover_javascript_files(REPO_PATH)\n"
        "if not JS_FILES:\n"
        "    logger.error('No JavaScript source files found in repository.', file=str(REPO_PATH))\n"
        "    raise FileNotFoundError('No JavaScript source files found.')\n\n"
        "REPO_STATS = compute_repository_stats(REPO_PATH, JS_FILES)\n"
        "ESLINT_EXE = resolve_eslint_executable(RUNTIMES_ROOT)\n"
        "logger.info(f'Repository ready at: {REPO_PATH}')\n"
        "logger.info(f'Using ESLint: {ESLINT_EXE}')\n"
        "print(f\"Repository: {REPO_STATS['repository_name']}\")\n"
        "print(f\"Size (JavaScript files): {REPO_STATS['repository_size_bytes']:,} bytes\")\n"
        "print(f\"Directories: {REPO_STATS['directory_count']:,}\")\n"
        "print(f\"JavaScript files: {REPO_STATS['javascript_file_count']:,}\")"
    ),
    md("## Section 5 — Discover JavaScript Files"),
    code(
        "INVENTORY_CSV = OUTPUT_PATH / 'javascript_files_inventory.csv'\n"
        "save_javascript_inventory(JS_FILES, INVENTORY_CSV)\n\n"
        "print(f'Total JavaScript Files Found: {len(JS_FILES)}')\n"
        "print(f'Saved inventory to: {INVENTORY_CSV}')"
    ),
    md("## Section 6 — Generate ESLint Configuration"),
    code(
        "ESLINTRC_PATH = ensure_eslint_config(REPO_PATH)\n\n"
        "print(f'Generated ESLint config: {ESLINTRC_PATH}')\n"
        "print(ESLINTRC_PATH.read_text(encoding='utf-8'))"
    ),
    md("## Section 7 — Execute ESLint\n\nRun ESLint in text and JSON formats. Preserve stdout/stderr exactly as emitted."),
    code(
        "text_cmd = build_eslint_command(ESLINT_EXE, REPO_PATH)\n"
        "json_cmd = build_eslint_command(ESLINT_EXE, REPO_PATH, 'json')\n\n"
        "raw_out, raw_err, raw_code = run_command(text_cmd)\n"
        "json_out, json_err, json_code = run_command(json_cmd)\n\n"
        "ESLINT_CONSOLE_CHUNKS = [\n"
        "    '===== eslint (text) =====\\n' + combine_raw(raw_out, raw_err),\n"
        "    '===== eslint (json) =====\\n' + combine_raw(json_out, json_err),\n"
        "]\n\n"
        "if raw_code not in {0, 1} and not json_out.strip():\n"
        "    logger.error(f'ESLint text run exited with code {raw_code}', file='eslint_text')\n"
        "if json_code not in {0, 1} and not json_out.strip():\n"
        "    logger.error(f'ESLint JSON run exited with code {json_code}', file='eslint_json')\n\n"
        "logger.info('ESLint execution complete.')"
    ),
    md("## Section 8 — Raw Output Extraction"),
    code(
        "CONSOLE_PATH = OUTPUT_PATH / 'eslint_raw_console_output.txt'\n"
        "JSON_PATH = OUTPUT_PATH / 'eslint_output.json'\n\n"
        "CONSOLE_PATH.write_text('\\n'.join(ESLINT_CONSOLE_CHUNKS), encoding='utf-8')\n"
        "JSON_PATH.write_text(json_out, encoding='utf-8')\n\n"
        "FINDINGS_DF = records_to_findings(parse_eslint_json(json_out))\n"
        "FINDINGS_DF.to_csv(OUTPUT_PATH / 'eslint_findings.csv', index=False)\n\n"
        "logger.info(f'Saved ESLint outputs and {len(FINDINGS_DF)} findings.')\n"
        "preview_raw_output(CONSOLE_PATH.read_text(encoding='utf-8'), RAW_OUTPUT_PREVIEW_LINES, CONSOLE_PATH)"
    ),
    md("## Section 9 — Extract Comment and Code Metrics\n\nParse JavaScript source files for comment and executable code line counts."),
    code(
        "COMMENT_METRICS_DF = build_comment_code_metrics(JS_FILES)\n"
        "COMMENT_METRICS_CSV = OUTPUT_PATH / 'comment_code_metrics.csv'\n"
        "COMMENT_METRICS_DF.to_csv(COMMENT_METRICS_CSV, index=False)\n\n"
        "logger.info(f'Extracted comment/code metrics for {len(COMMENT_METRICS_DF)} files.')\n"
        "display(COMMENT_METRICS_DF)"
    ),
    md(
        "## Section 10 — Comment-to-Code Ratio (Derived)\n\n"
        "**Derived metric** (not emitted directly by ESLint):\n\n"
        "```text\n"
        "Total_Comment_Lines = comment_lines + block_comment_lines + single_comment_lines\n"
        "Comment_to_Code_Ratio = Total_Comment_Lines / code_lines\n"
        "```"
    ),
    code(
        "COMMENT_RATIO = compute_comment_ratio(COMMENT_METRICS_DF)\n"
        "RATIO_CSV = OUTPUT_PATH / 'comment_to_code_ratio_summary.csv'\n"
        "pd.DataFrame([\n"
        "    {'metric_name': 'Comment_to_Code_Ratio', 'metric_value': COMMENT_RATIO['comment_to_code_ratio']},\n"
        "]).to_csv(RATIO_CSV, index=False)\n\n"
        "logger.info(f\"Comment-to-Code Ratio={COMMENT_RATIO['comment_to_code_ratio']} (Derived)\")\n"
        "display(pd.read_csv(RATIO_CSV))"
    ),
    md("## Section 11 — Comment Percentage (Derived)"),
    code(
        "PERCENTAGE_CSV = OUTPUT_PATH / 'comment_percentage_summary.csv'\n"
        "pd.DataFrame([\n"
        "    {'metric_name': 'Comment_to_Code_Percentage', 'metric_value': COMMENT_RATIO['comment_to_code_percentage']},\n"
        "]).to_csv(PERCENTAGE_CSV, index=False)\n\n"
        "logger.info(f\"Comment Percentage={COMMENT_RATIO['comment_to_code_percentage']}%\")\n"
        "display(pd.read_csv(PERCENTAGE_CSV))"
    ),
    md("## Section 12 — Maintainability Summary"),
    code(
        "MAINTAINABILITY_DF = build_maintainability_summary(FINDINGS_DF)\n"
        "MAINTAINABILITY_CSV = OUTPUT_PATH / 'maintainability_summary.csv'\n"
        "MAINTAINABILITY_DF.to_csv(MAINTAINABILITY_CSV, index=False)\n\n"
        "display(MAINTAINABILITY_DF)"
    ),
    md("## Section 13 — Summary Dashboard"),
    code(
        "doc_violations = int(MAINTAINABILITY_DF.loc[MAINTAINABILITY_DF['metric_name'] == 'Total_Documentation_Violations', 'metric_value'].iloc[0])\n"
        "maint_violations = int(MAINTAINABILITY_DF.loc[MAINTAINABILITY_DF['metric_name'] == 'Total_Maintainability_Violations', 'metric_value'].iloc[0])\n\n"
        "summary_df = pd.DataFrame([\n"
        "    {'Metric': 'Total JavaScript Files', 'Value': len(JS_FILES)},\n"
        "    {'Metric': 'Total Comment Lines', 'Value': int(COMMENT_RATIO['total_comment_lines'])},\n"
        "    {'Metric': 'Total Code Lines', 'Value': int(COMMENT_RATIO['total_code_lines'])},\n"
        "    {'Metric': 'Comment-to-Code Ratio (Derived)', 'Value': COMMENT_RATIO['comment_to_code_ratio']},\n"
        "    {'Metric': 'Comment Percentage (Derived)', 'Value': COMMENT_RATIO['comment_to_code_percentage']},\n"
        "    {'Metric': 'Documentation Violations', 'Value': doc_violations},\n"
        "    {'Metric': 'Maintainability Violations', 'Value': maint_violations},\n"
        "])\n"
        "display(summary_df)\n\n"
        "deliverables = [\n"
        "    CONSOLE_PATH, JSON_PATH, OUTPUT_PATH / 'eslint_findings.csv', COMMENT_METRICS_CSV,\n"
        "    RATIO_CSV, PERCENTAGE_CSV, MAINTAINABILITY_CSV, INVENTORY_CSV, ERROR_LOG_PATH,\n"
        "    REPO_PATH / '.eslintrc.json',\n"
        "]\n"
        "print('\\nDeliverables:')\n"
        "for path in deliverables:\n"
        "    print(f\"  [{'OK' if path.exists() else 'MISSING'}] {path}\")"
    ),
    md("## Section 14 — Error Handling"),
    code(
        "if ERROR_LOG_PATH.exists() and ERROR_LOG_PATH.stat().st_size > 0:\n"
        "    print(ERROR_LOG_PATH.read_text(encoding='utf-8'))\n"
        "else:\n"
        "    print('No errors logged.')"
    ),
    md(
        "## Section 15 — Deliverables\n\n"
        "```text\n"
        "outputs/\n"
        "├── eslint_raw_console_output.txt\n"
        "├── eslint_output.json\n"
        "├── eslint_findings.csv\n"
        "├── comment_code_metrics.csv\n"
        "├── comment_to_code_ratio_summary.csv\n"
        "├── comment_percentage_summary.csv\n"
        "├── maintainability_summary.csv\n"
        "├── javascript_files_inventory.csv\n"
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
