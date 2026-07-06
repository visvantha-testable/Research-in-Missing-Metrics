"""Generate eslint_parameter_count_extraction.ipynb for JavaScript repositories."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "eslint_parameter_count_extraction.ipynb"

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

os.environ.pop("PYTHONPATH", None)

JS_EXTENSIONS = {".js", ".mjs", ".cjs"}
EXCLUDED = {".git", "node_modules", "dist", "build", "coverage", "vendor", "docs", "test", "tests"}
FINDINGS_COLUMNS = ["file", "line", "column", "severity", "rule", "message"]
PARAM_SUMMARY_COLUMNS = ["file", "function", "parameter_count", "allowed_limit"]
LONG_PARAMETER_LIST_COLUMNS = ["file", "function", "parameter_count", "status"]
MAX_PARAMS_RULE = "max-params"
LONG_PARAMETER_THRESHOLD = 5
ESLINT_CONFIG = {
    "env": {"node": True, "es2022": True},
    "extends": ["eslint:recommended"],
    "rules": {"max-params": ["error", LONG_PARAMETER_THRESHOLD]},
}
ESLINT_SUCCESS_CODES = {0, 1}
MAX_PARAMS_MESSAGE = re.compile(
    r"Function\s+'(?P<function>[^']+)'\s+has too many parameters\s+\((?P<count>\d+)\)\.\s+Maximum allowed is\s+(?P<limit>\d+)\.",
    re.IGNORECASE,
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


def resolve_project_root(metric_root: Path) -> Path:
    current = metric_root.resolve()
    for _ in range(8):
        runtimes = current / "runtimes"
        if runtimes.is_dir() and (runtimes / "node_modules").is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return metric_root.resolve().parent.parent


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
    skip_names = {".eslintrc.json", "eslint.config.js", "eslint.config.mjs", "eslint.config.cjs"}
    files: list[Path] = []
    for path in repo_path.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in JS_EXTENSIONS:
            continue
        if path.name in skip_names:
            continue
        if any(part in EXCLUDED for part in path.parts):
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


def resolve_eslint_executable(project_root: Path) -> list[str]:
    runtimes = project_root / "runtimes"
    search_roots = [runtimes, project_root]
    for base in search_roots:
        local = base / "node_modules" / ".bin" / "eslint"
        for candidate in (local.with_suffix(".cmd"), local):
            if candidate.exists():
                return [str(candidate.resolve())]
    for name in ("eslint", "npx"):
        resolved = shutil.which(name)
        if resolved:
            return [resolved, "eslint"] if name == "npx" else [resolved]
    raise FileNotFoundError("ESLint not found. Install with: npm install -g eslint")


def ensure_eslint_config(repo: Path) -> Path:
    for config_name in ("eslint.config.js", "eslint.config.mjs", "eslint.config.cjs"):
        config_path = repo / config_name
        if config_path.exists():
            config_path.unlink()
    eslintrc = repo / ".eslintrc.json"
    eslintrc.write_text(json.dumps(ESLINT_CONFIG, indent=2), encoding="utf-8")
    rules_json = json.dumps(ESLINT_CONFIG["rules"], indent=6).replace("\n", "\n      ")
    flat_config = repo / "eslint.config.cjs"
    flat_config.write_text(
        "module.exports = [\n"
        "  {\n"
        "    files: ['**/*.{js,mjs,cjs}'],\n"
        "    ignores: ['**/eslint.config.cjs', '**/.eslintrc.json'],\n"
        "    languageOptions: { ecmaVersion: 'latest', sourceType: 'commonjs' },\n"
        f"    rules: {rules_json},\n"
        "  },\n"
        "];\n",
        encoding="utf-8",
    )
    return eslintrc


def build_eslint_command(eslint_executable: list[str], repo: Path, output_format: str | None = None) -> list[str]:
    command = [*eslint_executable, str(repo)]
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
                "rule": message.get("ruleId", ""),
                "message": message.get("message", ""),
            })
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def parse_max_params_violation(message: str) -> dict[str, Any] | None:
    match = MAX_PARAMS_MESSAGE.search(message)
    if not match:
        return None
    return {
        "function": match.group("function"),
        "parameter_count": int(match.group("count")),
        "allowed_limit": int(match.group("limit")),
    }


def build_parameter_count_summary(findings_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if not findings_df.empty:
        for _, record in findings_df[findings_df["rule"] == MAX_PARAMS_RULE].iterrows():
            parsed = parse_max_params_violation(str(record.get("message", "")))
            if parsed:
                rows.append({
                    "file": record.get("file", ""),
                    "function": parsed["function"],
                    "parameter_count": parsed["parameter_count"],
                    "allowed_limit": parsed["allowed_limit"],
                })
    return pd.DataFrame(rows, columns=PARAM_SUMMARY_COLUMNS)


def build_long_parameter_list(param_summary_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, record in param_summary_df.iterrows():
        param_count = int(record.get("parameter_count", 0) or 0)
        status = "Long Parameter List" if param_count > LONG_PARAMETER_THRESHOLD else "OK"
        rows.append({
            "file": record.get("file", ""),
            "function": record.get("function", ""),
            "parameter_count": param_count,
            "status": status,
        })
    return pd.DataFrame(rows, columns=LONG_PARAMETER_LIST_COLUMNS)


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
        "# ESLint Parameter Count — Raw Output Extraction (JavaScript)\n\n"
        "This notebook analyzes **JavaScript repositories** with **ESLint** and captures complete raw tool output "
        "for Parameter Count derived from **`max-params`** rule violations.\n\n"
        "**Default benchmark repository:** [expressjs/express](https://github.com/expressjs/express)\n\n"
        "> **Note:** **Parameter Count is a derived metric.** ESLint does **not** emit parameter counts for every "
        "function — it reports counts only for functions that violate the **`max-params`** rule."
    ),
    md("## Section 1 — Install Dependencies\n\nInstall Python packages and verify Node.js / ESLint."),
    code(
        "!pip install -q pandas gitpython jupyter\n\n"
        "import shutil, subprocess\n"
        "for cmd in ([\"node\", \"--version\"], [\"npm\", \"--version\"], [\"eslint\", \"--version\"]):\n"
        "    resolved = shutil.which(cmd[0])\n"
        "    if resolved:\n"
        "        subprocess.run(cmd, check=False)\n"
        "    else:\n"
        "        print(f'{cmd[0]} not found on PATH')"
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
        "# Fast validation benchmark:\n"
        "# USE_GIT_URL = False\n"
        "# LOCAL_REPO_PATH = './workspace/parameter_count_benchmark'"
    ),
    md("## Section 3 — Imports and Utility Functions"),
    code("from pathlib import Path\n\nPROJECT_ROOT = Path('.').resolve()\n\n" + UTILS.strip()),
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
        "JS_FILES = discover_javascript_files(REPO_PATH)\n"
        "if not JS_FILES:\n"
        "    logger.error('No JavaScript source files found in repository.', file=str(REPO_PATH))\n"
        "    raise FileNotFoundError('No JavaScript source files found.')\n\n"
        "REPO_STATS = compute_repository_stats(REPO_PATH, JS_FILES)\n"
        "logger.info(f'Repository ready at: {REPO_PATH}')\n"
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
    md("## Section 6 — Generate ESLint Configuration\n\nWrite `.eslintrc.json` and `eslint.config.cjs` with `max-params` rule."),
    code(
        "ESLINTRC_PATH = ensure_eslint_config(REPO_PATH)\n"
        "logger.info(f'Generated ESLint configuration at: {ESLINTRC_PATH}')\n"
        "print(ESLINTRC_PATH.read_text(encoding='utf-8'))"
    ),
    md("## Section 7 — Execute ESLint\n\nRun ESLint in stylish and JSON formats. Preserve stdout and stderr exactly as emitted."),
    code(
        "PROJECT_ROOT = resolve_project_root(Path('.').resolve())\n"
        "ESLINT_EXECUTABLE = resolve_eslint_executable(PROJECT_ROOT)\n"
        "logger.info(f'Using ESLint executable: {\" \".join(ESLINT_EXECUTABLE)}')\n\n"
        "text_cmd = build_eslint_command(ESLINT_EXECUTABLE, REPO_PATH)\n"
        "json_cmd = build_eslint_command(ESLINT_EXECUTABLE, REPO_PATH, 'json')\n\n"
        "raw_out, raw_err, raw_code = run_eslint_command(text_cmd, logger)\n"
        "json_out, json_err, json_code = run_eslint_command(json_cmd, logger)\n\n"
        "if raw_code not in ESLINT_SUCCESS_CODES and not json_out.strip():\n"
        "    logger.error(f'ESLint text run exited with code {raw_code}', file='eslint_text')\n"
        "if json_code not in ESLINT_SUCCESS_CODES and not json_out.strip():\n"
        "    logger.error(f'ESLint JSON run exited with code {json_code}', file='eslint_json')\n\n"
        "logger.info('ESLint execution complete.')"
    ),
    md("## Section 8 — Raw Output Extraction"),
    code(
        "CONSOLE_PATH = OUTPUT_PATH / 'eslint_raw_console_output.txt'\n"
        "JSON_PATH = OUTPUT_PATH / 'eslint_output.json'\n\n"
        "CONSOLE_PATH.write_text(\n"
        "    '===== eslint (text) =====\\n' + combine_raw_streams(raw_out, raw_err) + '\\n'\n"
        "    '===== eslint (json) =====\\n' + combine_raw_streams(json_out, json_err),\n"
        "    encoding='utf-8',\n"
        ")\n"
        "JSON_PATH.write_text(json_out, encoding='utf-8')\n\n"
        "RECORDS = parse_eslint_json(json_out)\n"
        "FINDINGS_DF = records_to_findings(RECORDS)\n"
        "FINDINGS_CSV = OUTPUT_PATH / 'eslint_findings.csv'\n"
        "FINDINGS_DF.to_csv(FINDINGS_CSV, index=False)\n\n"
        "logger.info(f'Saved ESLint raw output and {len(FINDINGS_DF)} findings.')\n"
        "preview_raw_output(CONSOLE_PATH.read_text(encoding='utf-8'), RAW_OUTPUT_PREVIEW_LINES, CONSOLE_PATH)"
    ),
    md(
        "## Section 9 — Parameter Count (Derived)\n\n"
        "**Derived metric** from ESLint `max-params` violations:\n\n"
        "```text\n"
        "Current Parameter Count = parsed from violation message\n"
        "```\n\n"
        "Example message: `Function 'foo' has too many parameters (8). Maximum allowed is 5.`"
    ),
    code(
        "PARAM_SUMMARY_DF = build_parameter_count_summary(FINDINGS_DF)\n"
        "PARAM_SUMMARY_CSV = OUTPUT_PATH / 'parameter_count_summary.csv'\n"
        "PARAM_SUMMARY_DF.to_csv(PARAM_SUMMARY_CSV, index=False)\n\n"
        "PARAM_VALUES = pd.to_numeric(PARAM_SUMMARY_DF['parameter_count'], errors='coerce').dropna()\n"
        "MAX_PARAM = int(PARAM_VALUES.max()) if not PARAM_VALUES.empty else 0\n"
        "AVG_PARAM = round(float(PARAM_VALUES.mean()), 4) if not PARAM_VALUES.empty else 0.0\n"
        "VIOLATION_COUNT = len(PARAM_SUMMARY_DF)\n\n"
        "logger.info(f'Maximum Parameter Count (derived)={MAX_PARAM} from {VIOLATION_COUNT} violation(s)')\n"
        "display(PARAM_SUMMARY_DF)"
    ),
    md("## Section 10 — Long Parameter List Summary"),
    code(
        "LONG_PARAM_DF = build_long_parameter_list(PARAM_SUMMARY_DF)\n"
        "LONG_PARAM_CSV = OUTPUT_PATH / 'long_parameter_list.csv'\n"
        "LONG_PARAM_DF.to_csv(LONG_PARAM_CSV, index=False)\n\n"
        "LONG_PARAM_COUNT = int((LONG_PARAM_DF['status'] == 'Long Parameter List').sum())\n"
        "logger.info(f'Long parameter list violations={LONG_PARAM_COUNT}')\n"
        "display(LONG_PARAM_DF)"
    ),
    md("## Section 11 — Summary Dashboard"),
    code(
        "summary_df = pd.DataFrame([\n"
        "    {'Metric': 'Total JavaScript Files', 'Value': len(JS_FILES)},\n"
        "    {'Metric': 'Total Functions with Parameter Violations', 'Value': VIOLATION_COUNT},\n"
        "    {'Metric': 'Maximum Parameter Count', 'Value': MAX_PARAM},\n"
        "    {'Metric': 'Average Parameter Count (violating functions)', 'Value': AVG_PARAM},\n"
        "    {'Metric': 'Long Parameter List Violations', 'Value': LONG_PARAM_COUNT},\n"
        "])\n"
        "display(summary_df)\n\n"
        "deliverables = [\n"
        "    CONSOLE_PATH, JSON_PATH, FINDINGS_CSV, PARAM_SUMMARY_CSV,\n"
        "    LONG_PARAM_CSV, INVENTORY_CSV, ERROR_LOG_PATH,\n"
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
        "├── parameter_count_summary.csv\n"
        "├── long_parameter_list.csv\n"
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
