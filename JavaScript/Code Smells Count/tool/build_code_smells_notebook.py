"""Generate eslint_code_smells_extraction.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "eslint_code_smells_extraction.ipynb"

UTILS = r'''
from __future__ import annotations

import json
import os
import re
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

JS_EXTENSIONS = {".js", ".jsx", ".mjs", ".cjs"}
EXCLUDED_DIR_NAMES = {".git", "node_modules", "dist", "build", "coverage", "out", "vendor", "docs"}
CODE_SMELL_RULES = {
    "complexity", "max-depth", "max-lines-per-function", "max-params", "max-statements",
    "no-duplicate-imports", "no-unused-vars", "no-unreachable", "no-shadow",
}
ESLINT_CONFIG = {
    "env": {"browser": True, "node": True, "es2022": True},
    "parserOptions": {"ecmaVersion": "latest", "sourceType": "module"},
    "extends": ["eslint:recommended"],
    "rules": {
        "complexity": ["warn", 10],
        "max-depth": ["warn", 4],
        "max-lines-per-function": ["warn", 50],
        "max-params": ["warn", 5],
        "max-statements": ["warn", 20],
        "no-duplicate-imports": "warn",
        "no-unused-vars": "warn",
        "no-unreachable": "warn",
        "no-shadow": "warn",
    },
}
RESULTS_COLUMNS = ["file", "line", "column", "severity", "ruleId", "message", "nodeType"]
SMELLS_COLUMNS = ["file", "line", "rule_id", "severity", "message"]
ESLINT_SUCCESS_CODES = {0, 1}


class NotebookLogger:
    def __init__(self, error_log_path: Path) -> None:
        self.error_log_path = error_log_path
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.error_log_path.exists():
            self.error_log_path.write_text("", encoding="utf-8")

    def info(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"[{timestamp}] INFO: {message}")

    def error(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        line = f"[{timestamp}] ERROR: {message}\n"
        print(line, end="")
        with self.error_log_path.open("a", encoding="utf-8") as handle:
            handle.write(line)


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
        logger.error(f"Git clone failed: {exc}")
        raise
    return clone_path.resolve()


def validate_local_repo_path(local_repo_path: Path, logger: NotebookLogger) -> Path:
    if not local_repo_path.exists():
        msg = f"Local repository path does not exist: {local_repo_path}"
        logger.error(msg)
        raise FileNotFoundError(msg)
    if not local_repo_path.is_dir():
        msg = f"Local repository path is not a directory: {local_repo_path}"
        logger.error(msg)
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
    files: list[Path] = []
    for path in repo_path.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in JS_EXTENSIONS:
            continue
        if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            continue
        files.append(path.resolve())
    return sorted(files)


def compute_repository_stats(repo_path: Path, javascript_files: list[Path]) -> dict[str, int]:
    total_size = sum(path.stat().st_size for path in javascript_files)
    directories = {path.parent for path in javascript_files}
    return {"repository_size_bytes": total_size, "directory_count": len(directories)}


def save_javascript_file_list(javascript_files: list[Path], repo_path: Path, output_csv: Path) -> None:
    pd.DataFrame(
        [
            {
                "absolute_path": str(path),
                "relative_path": str(path.relative_to(repo_path)),
                "extension": path.suffix.lower(),
            }
            for path in javascript_files
        ]
    ).to_csv(output_csv, index=False)


def resolve_eslint_executable(runtimes_root: Path) -> list[str]:
    search_roots = [runtimes_root, runtimes_root.parent]
    for base in search_roots:
        local = base / "node_modules" / ".bin" / "eslint"
        for candidate in (local.with_suffix(".cmd"), local):
            if candidate.exists():
                return [str(candidate.resolve())]
    for name in ("eslint", "npx"):
        resolved = shutil.which(name)
        if resolved:
            if name == "npx":
                return [resolved, "eslint"]
            return [resolved]
    raise FileNotFoundError("ESLint not found. Install with: npm install -g eslint")


def ensure_eslint_config(repo_path: Path, logger: NotebookLogger) -> tuple[Path, Path | None]:
    eslintrc = repo_path / ".eslintrc.json"
    created_eslintrc = False
    if not eslintrc.exists():
        eslintrc.write_text(json.dumps(ESLINT_CONFIG, indent=2), encoding="utf-8")
        created_eslintrc = True
        logger.info(f"Created ESLint config: {eslintrc}")

    flat_config = repo_path / "eslint.config.js"
    created_flat = None
    if not flat_config.exists():
        rules_json = json.dumps(ESLINT_CONFIG["rules"], indent=6).replace("\n", "\n      ")
        flat_config.write_text(
            "export default [\n"
            "  {\n"
            "    files: ['**/*.{js,jsx,mjs,cjs}'],\n"
            "    languageOptions: { ecmaVersion: 'latest', sourceType: 'module' },\n"
            f"    rules: {rules_json},\n"
            "  },\n"
            "];\n",
            encoding="utf-8",
        )
        created_flat = flat_config
        logger.info(f"Created flat ESLint config: {flat_config}")
    return eslintrc, created_flat


def build_eslint_command(eslint_executable: list[str], repo_path: Path, output_format: str | None = None) -> list[str]:
    command = [*eslint_executable, str(repo_path)]
    if output_format:
        command.extend(["-f", output_format])
    return command


def run_eslint_command(command: list[str], logger: NotebookLogger, stream_raw: bool = False) -> tuple[str, str, int]:
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


def parse_eslint_json(json_text: str) -> list[dict[str, Any]]:
    if not json_text.strip():
        return []
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def records_to_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for record in records:
        for message in record.get("messages", []):
            rows.append({
                "file": record.get("filePath", ""),
                "line": message.get("line", ""),
                "column": message.get("column", ""),
                "severity": message.get("severity", ""),
                "ruleId": message.get("ruleId", ""),
                "message": message.get("message", ""),
                "nodeType": message.get("nodeType", ""),
            })
    return pd.DataFrame(rows, columns=RESULTS_COLUMNS)


def is_code_smell(rule_id: str) -> bool:
    return rule_id in CODE_SMELL_RULES


def extract_code_smells_findings(results_df: pd.DataFrame) -> pd.DataFrame:
    if results_df.empty:
        return pd.DataFrame(columns=SMELLS_COLUMNS)
    smells = results_df[results_df["ruleId"].map(lambda value: is_code_smell(str(value)))].copy()
    smells = smells.rename(columns={"ruleId": "rule_id"})
    return smells[SMELLS_COLUMNS].reset_index(drop=True)


def count_failed_files(records: list[dict[str, Any]], javascript_files: list[Path]) -> int:
    analyzed = {
        str(record.get("filePath", ""))
        for record in records
        if not any(message.get("fatal") for message in record.get("messages", []))
    }
    return max(len(javascript_files) - len(analyzed), 0)


def compute_code_smells_summary(findings_df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame([{"metric_name": "Code_Smells_Count", "metric_value": len(findings_df)}])


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
        "# ESLint Maintainability — Code Smells Count Raw Output Extraction (JavaScript)\n\n"
        "This notebook analyzes **JavaScript repositories** with **ESLint** and captures the complete raw tool output "
        "for maintainability code-smells metric derivation and validation.\n\n"
        "**Default benchmark repository:** [facebook/react](https://github.com/facebook/react)\n\n"
        "Supports Git URL cloning and local repository analysis. All deliverables are written to `OUTPUT_DIR`."
    ),
    md("## Section 1 — Install Dependencies\n\nInstall Python packages and verify ESLint from shared runtimes or global install."),
    code("!pip install -q pandas gitpython jupyter"),
    code(
        "import shutil\n"
        "import subprocess\n"
        "from pathlib import Path\n\n"
        "RUNTIMES_ROOT = Path('../../runtimes').resolve()\n"
        "eslint_cmd = RUNTIMES_ROOT / 'node_modules' / '.bin' / ('eslint.cmd' if __import__('sys').platform.startswith('win') else 'eslint')\n"
        "if eslint_cmd.exists():\n"
        "    subprocess.run([str(eslint_cmd), '--version'], check=False)\n"
        "elif shutil.which('eslint'):\n"
        "    subprocess.run(['eslint', '--version'], check=False)\n"
        "else:\n"
        "    print('ESLint not found. Run: npm install -g eslint or install under ../../runtimes/node_modules')"
    ),
    md(
        "## Section 2 — Configuration\n\n"
        "Set execution mode, repository source, and output location.\n\n"
        "- `USE_GIT_URL = True` clones from `REPO_URL`.\n"
        "- `USE_GIT_URL = False` analyzes `LOCAL_REPO_PATH` directly."
    ),
    code(
        "USE_GIT_URL = True\n\n"
        "REPO_URL = 'https://github.com/facebook/react.git'\n\n"
        "LOCAL_REPO_PATH = '/content/react'\n\n"
        "OUTPUT_DIR = './outputs'\n\n"
        "RUNTIMES_ROOT = Path('../../runtimes').resolve()\n\n"
        "IF_CLONE_EXISTS = 'reuse'\n\n"
        "CLONE_DEPTH = 1\n\n"
        "WORKSPACE_DIR = './workspace'\n\n"
        "STREAM_RAW_OUTPUT = True\n\n"
        "RAW_OUTPUT_PREVIEW_LINES = 150\n\n"
        "# Fast validation benchmark:\n"
        "# USE_GIT_URL = False\n"
        "# LOCAL_REPO_PATH = './workspace/js_code_smells_benchmark'"
    ),
    md("## Section 3 — Imports and Utility Functions\n\nModular helpers for repository setup, ESLint configuration, execution, and code-smell extraction."),
    code("from pathlib import Path\n\n" + UTILS.strip()),
    md("## Section 4 — Repository Setup\n\nResolve the repository path and initialize output directories."),
    code(
        "OUTPUT_PATH = Path(OUTPUT_DIR).resolve()\n"
        "WORKSPACE_PATH = Path(WORKSPACE_DIR).resolve()\n"
        "ERROR_LOG_PATH = OUTPUT_PATH / 'error_log.txt'\n\n"
        "ensure_output_dir(OUTPUT_PATH)\n"
        "logger = NotebookLogger(ERROR_LOG_PATH)\n"
        "ESLINT_EXECUTABLE = resolve_eslint_executable(RUNTIMES_ROOT)\n"
        "logger.info(f'Using ESLint executable: {\" \".join(ESLINT_EXECUTABLE)}')\n\n"
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
        "logger.info(f'Repository ready at: {REPO_PATH}')"
    ),
    md("## Section 5 — Discover JavaScript Files\n\nRecursively discover `.js`, `.jsx`, `.mjs`, and `.cjs` files."),
    code(
        "JAVASCRIPT_FILES = discover_javascript_files(REPO_PATH)\n"
        "REPO_STATS = compute_repository_stats(REPO_PATH, JAVASCRIPT_FILES)\n\n"
        "JAVASCRIPT_FILES_CSV = OUTPUT_PATH / 'javascript_files.csv'\n"
        "save_javascript_file_list(JAVASCRIPT_FILES, REPO_PATH, JAVASCRIPT_FILES_CSV)\n\n"
        "print(f'Total JavaScript Files Found: {len(JAVASCRIPT_FILES)}')\n"
        "print(f'Repository Size (JavaScript files only): {REPO_STATS[\"repository_size_bytes\"]:,} bytes')\n"
        "print(f'Total Directories: {REPO_STATS[\"directory_count\"]:,}')\n"
        "print(f'Saved file list to: {JAVASCRIPT_FILES_CSV}')"
    ),
    md("## Section 6 — Create ESLint Configuration\n\nCreate `.eslintrc.json` and `eslint.config.js` when missing, using maintainability-focused rules."),
    code(
        "ESLINTRC_PATH, FLAT_CONFIG_PATH = ensure_eslint_config(REPO_PATH, logger)\n"
        "print(f'ESLint legacy config: {ESLINTRC_PATH}')\n"
        "if FLAT_CONFIG_PATH:\n"
        "    print(f'ESLint flat config: {FLAT_CONFIG_PATH}')"
    ),
    md(
        "## Section 7 — Execute ESLint\n\n"
        "Run ESLint against the repository. Execution continues even if individual files fail.\n\n"
        "```bash\n"
        "eslint <repo_path> -f json\n"
        "```"
    ),
    code(
        "if not JAVASCRIPT_FILES:\n"
        "    logger.error('No JavaScript files discovered; skipping ESLint execution.')\n"
        "    ESLINT_RAW_TEXT = ''\n"
        "    ESLINT_JSON_TEXT = '[]'\n"
        "    ESLINT_RECORDS: list[dict] = []\n"
        "    FILES_SUCCESS = 0\n"
        "    FILES_FAILED = 0\n"
        "else:\n"
        "    text_cmd = build_eslint_command(ESLINT_EXECUTABLE, REPO_PATH)\n"
        "    json_cmd = build_eslint_command(ESLINT_EXECUTABLE, REPO_PATH, 'json')\n"
        "    text_stdout, text_stderr, text_code = run_eslint_command(text_cmd, logger, stream_raw=STREAM_RAW_OUTPUT)\n"
        "    json_stdout, json_stderr, json_code = run_eslint_command(json_cmd, logger, stream_raw=False)\n"
        "    ESLINT_RAW_TEXT = combine_raw_streams(text_stdout, text_stderr)\n"
        "    ESLINT_JSON_TEXT = json_stdout\n"
        "    ESLINT_RECORDS = parse_eslint_json(json_stdout)\n"
        "    if text_code not in ESLINT_SUCCESS_CODES and not ESLINT_RECORDS:\n"
        "        logger.error(f'ESLint text run exited with code {text_code}')\n"
        "    if json_code not in ESLINT_SUCCESS_CODES and not ESLINT_RECORDS:\n"
        "        logger.error(f'ESLint JSON run exited with code {json_code}')\n"
        "    if json_stderr.strip():\n"
        "        logger.error(f'ESLint JSON stderr: {json_stderr.strip()}')\n"
        "    FILES_FAILED = count_failed_files(ESLINT_RECORDS, JAVASCRIPT_FILES)\n"
        "    FILES_SUCCESS = max(len(JAVASCRIPT_FILES) - FILES_FAILED, 0)\n\n"
        "logger.info(f'ESLint execution complete. Files success={FILES_SUCCESS}, failed={FILES_FAILED}')"
    ),
    md("## Section 8 — Raw Output Extraction\n\nPersist raw ESLint text output, JSON output, and CSV findings."),
    code(
        "RAW_OUTPUT_PATH = OUTPUT_PATH / 'eslint_raw_output.txt'\n"
        "JSON_OUTPUT_PATH = OUTPUT_PATH / 'eslint_output.json'\n"
        "RESULTS_CSV_PATH = OUTPUT_PATH / 'eslint_results.csv'\n\n"
        "RAW_OUTPUT_PATH.write_text(ESLINT_RAW_TEXT, encoding='utf-8')\n"
        "JSON_OUTPUT_PATH.write_text(json.dumps(ESLINT_RECORDS, indent=2, ensure_ascii=False), encoding='utf-8')\n\n"
        "ESLINT_RESULTS_DF = records_to_dataframe(ESLINT_RECORDS)\n"
        "ESLINT_RESULTS_DF.to_csv(RESULTS_CSV_PATH, index=False)\n\n"
        "logger.info(f'Saved raw output: {RAW_OUTPUT_PATH}')\n"
        "logger.info(f'Saved JSON output: {JSON_OUTPUT_PATH}')\n"
        "logger.info(f'Saved CSV results: {RESULTS_CSV_PATH}')\n"
        "logger.info(f'Total ESLint findings: {len(ESLINT_RESULTS_DF)}')\n\n"
        "preview_raw_output(ESLINT_RAW_TEXT, RAW_OUTPUT_PREVIEW_LINES, RAW_OUTPUT_PATH)"
    ),
    md("## Section 9 — Code Smell Extraction\n\nExtract maintainability-related ESLint findings for configured code-smell rules."),
    code(
        "CODE_SMELLS_DF = extract_code_smells_findings(ESLINT_RESULTS_DF)\n"
        "CODE_SMELLS_CSV = OUTPUT_PATH / 'code_smells_findings.csv'\n"
        "CODE_SMELLS_DF.to_csv(CODE_SMELLS_CSV, index=False)\n\n"
        "logger.info(f'Saved code smells findings: {CODE_SMELLS_CSV}')\n"
        "logger.info(f'Code smells count: {len(CODE_SMELLS_DF)}')\n\n"
        "if not CODE_SMELLS_DF.empty:\n"
        "    display(CODE_SMELLS_DF.head(15))\n"
        "else:\n"
        "    print('No code smell findings detected.')"
    ),
    md("## Section 10 — Metric Computation\n\n**Code_Smells_Count** = count(all maintainability-related ESLint findings)"),
    code(
        "SUMMARY_DF = compute_code_smells_summary(CODE_SMELLS_DF)\n"
        "SUMMARY_CSV = OUTPUT_PATH / 'code_smells_summary.csv'\n"
        "SUMMARY_DF.to_csv(SUMMARY_CSV, index=False)\n\n"
        "logger.info(f'Saved code smells summary: {SUMMARY_CSV}')\n"
        "display(SUMMARY_DF)"
    ),
    md("## Section 11 — Summary Dashboard\n\nOverview of analysis coverage and code-smell metrics."),
    code(
        "code_smells_count = int(SUMMARY_DF.loc[SUMMARY_DF['metric_name'] == 'Code_Smells_Count', 'metric_value'].iloc[0])\n\n"
        "summary_df = pd.DataFrame([\n"
        "    {'Metric': 'Total JavaScript Files', 'Value': len(JAVASCRIPT_FILES)},\n"
        "    {'Metric': 'Files Successfully Analyzed', 'Value': FILES_SUCCESS},\n"
        "    {'Metric': 'Files Failed', 'Value': FILES_FAILED},\n"
        "    {'Metric': 'Total ESLint Findings', 'Value': len(ESLINT_RESULTS_DF)},\n"
        "    {'Metric': 'Total Code Smells', 'Value': code_smells_count},\n"
        "])\n\n"
        "display(summary_df)\n\n"
        "deliverables = [\n"
        "    RAW_OUTPUT_PATH, JSON_OUTPUT_PATH, RESULTS_CSV_PATH, JAVASCRIPT_FILES_CSV,\n"
        "    CODE_SMELLS_CSV, SUMMARY_CSV, ERROR_LOG_PATH,\n"
        "]\n\n"
        "print('\\nDeliverables:')\n"
        "for deliverable in deliverables:\n"
        "    status = 'OK' if deliverable.exists() else 'MISSING'\n"
        "    print(f'  [{status}] {deliverable}')"
    ),
    md("## Section 12 — Error Handling\n\nFailures are appended to `outputs/error_log.txt`."),
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
        "├── eslint_raw_output.txt\n"
        "├── eslint_output.json\n"
        "├── eslint_results.csv\n"
        "├── javascript_files.csv\n"
        "├── code_smells_findings.csv\n"
        "├── code_smells_summary.csv\n"
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
