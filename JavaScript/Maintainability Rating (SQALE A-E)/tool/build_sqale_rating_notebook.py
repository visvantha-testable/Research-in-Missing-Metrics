"""Generate eslint_maintainability_rating_extraction.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "eslint_maintainability_rating_extraction.ipynb"

UTILS = r'''
from __future__ import annotations

import csv
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

JS_EXTENSIONS = {".js", ".mjs", ".cjs"}
EXCLUDED_DIR_NAMES = {".git", "node_modules", "dist", "build", "coverage", "vendor", "docs", "test", "tests"}
MAINTAINABILITY_RULES = {
    "complexity", "max-depth", "max-lines", "max-lines-per-function",
    "max-params", "max-statements", "max-nested-callbacks",
}
ESLINT_CONFIG = {
    "env": {"es2022": True, "node": True},
    "extends": ["eslint:recommended"],
    "parserOptions": {"ecmaVersion": "latest"},
    "rules": {
        "complexity": ["warn", 10],
        "max-depth": ["warn", 4],
        "max-lines": ["warn", 300],
        "max-lines-per-function": ["warn", 50],
        "max-params": ["warn", 5],
        "max-statements": ["warn", 20],
        "max-nested-callbacks": ["warn", 3],
    },
}
FINDINGS_COLUMNS = ["file", "line", "column", "severity", "rule_id", "message"]
ESLINT_SUCCESS_CODES = {0, 1}
MAX_DEPTH_PATTERN = re.compile(
    r"Blocks are nested too deeply \((?P<actual>\d+)\)\. Maximum allowed is (?P<threshold>\d+)\."
)


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
    files: list[Path] = []
    for path in repo_path.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in JS_EXTENSIONS:
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


def ensure_eslint_config(repo_path: Path) -> Path:
    eslintrc = repo_path / ".eslintrc.json"
    eslintrc.write_text(json.dumps(ESLINT_CONFIG, indent=2), encoding="utf-8")
    rules_json = json.dumps(ESLINT_CONFIG["rules"], indent=6).replace("\n", "\n      ")
    (repo_path / "eslint.config.js").write_text(
        "export default [\n"
        "  {\n"
        "    files: ['**/*.{js,mjs,cjs}'],\n"
        "    languageOptions: { ecmaVersion: 'latest', sourceType: 'module' },\n"
        f"    rules: {rules_json},\n"
        "  },\n"
        "];\n",
        encoding="utf-8",
    )
    return eslintrc


def build_eslint_command(eslint_executable: list[str], repo_path: Path, output_format: str | None = None) -> list[str]:
    command = [*eslint_executable, str(repo_path), "--ext", ".js,.mjs,.cjs"]
    if output_format:
        command.extend(["-f", output_format])
    return command


def run_eslint_command(command: list[str], logger: NotebookLogger) -> tuple[str, str, int]:
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


def records_to_findings(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for record in records:
        for message in record.get("messages", []):
            rows.append({
                "file": record.get("filePath", ""),
                "line": message.get("line", ""),
                "column": message.get("column", ""),
                "severity": message.get("severity", ""),
                "rule_id": message.get("ruleId", ""),
                "message": message.get("message", ""),
            })
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def is_maintainability_violation(rule_id: str) -> bool:
    return str(rule_id) in MAINTAINABILITY_RULES


def extract_maintainability_findings(findings_df: pd.DataFrame) -> pd.DataFrame:
    if findings_df.empty:
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    return findings_df[findings_df["rule_id"].map(is_maintainability_violation)].reset_index(drop=True)


def extract_max_nesting_depth(findings_df: pd.DataFrame) -> int:
    depth_rows = findings_df[findings_df["rule_id"] == "max-depth"]
    depths = []
    for message in depth_rows["message"].astype(str):
        match = MAX_DEPTH_PATTERN.search(message)
        if match:
            depths.append(int(match.group("actual")))
    return max(depths) if depths else 0


def compute_maintainability_score(violation_count: int, file_count: int) -> float:
    if file_count <= 0:
        return 0.0
    return round(max(100 - ((violation_count / file_count) * 5), 0.0), 4)


def score_to_sqale_rating(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "E"


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
        "# ESLint Maintainability Rating (SQALE A–E) — Raw Output Extraction (JavaScript)\n\n"
        "This notebook analyzes **JavaScript repositories** with **ESLint** and captures complete raw tool output "
        "for Code Smells Count, Cyclomatic Complexity, Maximum Nesting Depth, Maintainability Score, "
        "and Maintainability Rating (A–E).\n\n"
        "**Default benchmark repository:** [expressjs/express](https://github.com/expressjs/express)"
    ),
    md("## Section 1 — Install Dependencies\n\nInstall Python packages and verify Node.js / ESLint."),
    code(
        "!pip install -q pandas gitpython jupyter\n\n"
        "import shutil, subprocess\n\n"
        "for cmd in [['node', '--version'], ['npm', '--version']]:\n"
        "    subprocess.run(cmd, check=False)\n\n"
        "if not shutil.which('eslint'):\n"
        "    !npm install -g eslint\n\n"
        "subprocess.run(['eslint', '--version'], check=False)"
    ),
    md("## Section 2 — Configuration\n\nSet repository source, workspace, and output directory."),
    code(
        "USE_GIT_URL = True\n\n"
        "REPO_URL = 'https://github.com/expressjs/express.git'\n\n"
        "LOCAL_REPO_PATH = '/content/express'\n\n"
        "WORKSPACE_DIR = './workspace'\n\n"
        "OUTPUT_DIR = './outputs'\n\n"
        "IF_CLONE_EXISTS = 'reuse'\n\n"
        "CLONE_DEPTH = 1\n\n"
        "RAW_OUTPUT_PREVIEW_LINES = 150\n\n"
        "RUNTIMES_ROOT = Path('../../runtimes').resolve()\n\n"
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
        "logger.info(f'Repository ready at: {REPO_PATH}')\n"
        "print(f\"Repository: {REPO_STATS['repository_name']}\")\n"
        "print(f\"Size (JS files): {REPO_STATS['repository_size_bytes']:,} bytes\")\n"
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
    md("## Section 6 — Create ESLint Configuration\n\nGenerate `.eslintrc.json` and flat `eslint.config.js` with maintainability rules."),
    code(
        "ESLINTRC_PATH = ensure_eslint_config(REPO_PATH)\n"
        "logger.info(f'Generated ESLint config: {ESLINTRC_PATH}')\n"
        "print(ESLINTRC_PATH.read_text(encoding='utf-8'))"
    ),
    md("## Section 7 — Execute ESLint\n\nRun ESLint in text and JSON formats. Preserve stdout/stderr exactly as emitted."),
    code(
        "ESLINT_EXECUTABLE = resolve_eslint_executable(RUNTIMES_ROOT)\n"
        "ESLINT_CONSOLE_CHUNKS: list[str] = []\n"
        "ESLINT_RAW: dict[str, str] = {}\n\n"
        "for label, fmt in [('text', None), ('json', 'json')]:\n"
        "    cmd = build_eslint_command(ESLINT_EXECUTABLE, REPO_PATH, fmt)\n"
        "    stdout, stderr, code = run_eslint_command(cmd, logger)\n"
        "    ESLINT_CONSOLE_CHUNKS.append(f'===== eslint ({label}) =====\\n' + combine_raw_streams(stdout, stderr))\n"
        "    ESLINT_RAW[label] = stdout\n"
        "    if code not in ESLINT_SUCCESS_CODES and not stdout.strip():\n"
        "        logger.error(f'ESLint {label} run exited with code {code}', file=label)\n\n"
        "logger.info('ESLint execution complete.')"
    ),
    md("## Section 8 — Raw Output Extraction"),
    code(
        "CONSOLE_PATH = OUTPUT_PATH / 'eslint_raw_console_output.txt'\n"
        "JSON_PATH = OUTPUT_PATH / 'eslint_output.json'\n\n"
        "CONSOLE_PATH.write_text('\\n'.join(ESLINT_CONSOLE_CHUNKS), encoding='utf-8')\n"
        "JSON_PATH.write_text(ESLINT_RAW.get('json', ''), encoding='utf-8')\n\n"
        "logger.info('Saved ESLint raw console and JSON outputs.')\n"
        "preview_raw_output(CONSOLE_PATH.read_text(encoding='utf-8'), RAW_OUTPUT_PREVIEW_LINES, CONSOLE_PATH)"
    ),
    md("## Section 9 — Parse Findings"),
    code(
        "RECORDS = parse_eslint_json(ESLINT_RAW.get('json', ''))\n"
        "FINDINGS_DF = records_to_findings(RECORDS)\n"
        "FINDINGS_CSV = OUTPUT_PATH / 'eslint_findings.csv'\n"
        "FINDINGS_DF.to_csv(FINDINGS_CSV, index=False)\n\n"
        "logger.info(f'Parsed {len(FINDINGS_DF)} total ESLint findings')"
    ),
    md("## Section 10 — Metric Computation"),
    code(
        "MAINTAINABILITY_DF = extract_maintainability_findings(FINDINGS_DF)\n"
        "violation_count = len(MAINTAINABILITY_DF)\n"
        "code_smells_count = violation_count\n\n"
        "CODE_SMELLS_CSV = OUTPUT_PATH / 'code_smells_summary.csv'\n"
        "pd.DataFrame([{'metric_name': 'Code_Smells_Count', 'metric_value': code_smells_count}]).to_csv(CODE_SMELLS_CSV, index=False)\n\n"
        "max_nesting = extract_max_nesting_depth(FINDINGS_DF)\n"
        "NESTING_CSV = OUTPUT_PATH / 'nesting_depth_summary.csv'\n"
        "pd.DataFrame([{'metric_name': 'Maximum_Nesting_Depth', 'metric_value': max_nesting}]).to_csv(NESTING_CSV, index=False)\n\n"
        "maintainability_score = compute_maintainability_score(violation_count, len(JS_FILES))\n"
        "SCORE_CSV = OUTPUT_PATH / 'maintainability_score_summary.csv'\n"
        "pd.DataFrame([{'metric_name': 'Maintainability_Score', 'metric_value': maintainability_score}]).to_csv(SCORE_CSV, index=False)\n\n"
        "rating = score_to_sqale_rating(maintainability_score)\n"
        "RATING_CSV = OUTPUT_PATH / 'maintainability_rating_summary.csv'\n"
        "pd.DataFrame([{'metric_name': 'Maintainability_Rating', 'metric_value': rating}]).to_csv(RATING_CSV, index=False)\n\n"
        "logger.info(f'Code Smells={code_smells_count}, Score={maintainability_score}, Rating={rating}')\n"
        "display(pd.DataFrame([\n"
        "    {'metric_name': 'Code_Smells_Count', 'metric_value': code_smells_count},\n"
        "    {'metric_name': 'Maximum_Nesting_Depth', 'metric_value': max_nesting},\n"
        "    {'metric_name': 'Maintainability_Score', 'metric_value': maintainability_score},\n"
        "    {'metric_name': 'Maintainability_Rating', 'metric_value': rating},\n"
        "]))"
    ),
    md("## Section 11 — Summary Dashboard"),
    code(
        "summary_df = pd.DataFrame([\n"
        "    {'Metric': 'Total JavaScript Files', 'Value': len(JS_FILES)},\n"
        "    {'Metric': 'Total ESLint Findings', 'Value': len(FINDINGS_DF)},\n"
        "    {'Metric': 'Code Smells Count', 'Value': code_smells_count},\n"
        "    {'Metric': 'Maximum Nesting Depth', 'Value': max_nesting},\n"
        "    {'Metric': 'Maintainability Score', 'Value': maintainability_score},\n"
        "    {'Metric': 'Maintainability Rating', 'Value': rating},\n"
        "])\n"
        "display(summary_df)\n\n"
        "deliverables = [\n"
        "    CONSOLE_PATH, JSON_PATH, FINDINGS_CSV, CODE_SMELLS_CSV, NESTING_CSV,\n"
        "    SCORE_CSV, RATING_CSV, INVENTORY_CSV, ERROR_LOG_PATH,\n"
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
        "├── eslint_raw_console_output.txt\n"
        "├── eslint_output.json\n"
        "├── eslint_findings.csv\n"
        "├── code_smells_summary.csv\n"
        "├── nesting_depth_summary.csv\n"
        "├── maintainability_score_summary.csv\n"
        "├── maintainability_rating_summary.csv\n"
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
