"""Generate pylint_code_smells_extraction.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "pylint_code_smells_extraction.ipynb"

UTILS = r'''
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from IPython.display import display
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

EXCLUDED_DIR_NAMES = {
    ".git", "venv", ".venv", "env", "__pycache__", "build", "dist", "node_modules", ".tox",
}

CODE_SMELL_SYMBOLS = {
    "duplicate-code",
    "too-many-branches",
    "too-many-arguments",
    "too-many-instance-attributes",
    "too-many-locals",
    "too-many-public-methods",
    "too-many-return-statements",
    "too-many-statements",
    "too-many-nested-blocks",
    "too-many-boolean-expressions",
    "too-many-ancestors",
}

CODE_SMELL_MESSAGE_IDS = {
    "R0801", "R0912", "R0913", "R0902", "R0914", "R0904", "R0911", "R0915", "R1702", "R0916", "R0901",
}

SEVERITY_MAP = {
    "convention": "convention",
    "refactor": "refactor",
    "warning": "warning",
    "error": "error",
    "fatal": "fatal",
}


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
    repo_url: str,
    workspace_dir: Path,
    if_clone_exists: str,
    logger: NotebookLogger,
    clone_depth: int | None = None,
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
            raise ValueError('IF_CLONE_EXISTS must be either "reuse" or "reclone"')
    logger.info(f"Cloning {repo_url} into {clone_path} (depth={clone_depth})")
    try:
        clone_kwargs = {"depth": clone_depth} if clone_depth else {}
        Repo.clone_from(repo_url, clone_path, **clone_kwargs)
    except GitCommandError as exc:
        logger.error(f"Clone failed for {repo_url}: {exc}")
        raise
    logger.info(f"Clone completed: {clone_path}")
    return clone_path.resolve()


def validate_local_repository(local_repo_path: Path, logger: NotebookLogger) -> Path:
    if not local_repo_path.exists():
        message = f"Local repository path does not exist: {local_repo_path}"
        logger.error(message)
        raise FileNotFoundError(message)
    if not local_repo_path.is_dir():
        message = f"Local repository path is not a directory: {local_repo_path}"
        logger.error(message)
        raise NotADirectoryError(message)
    has_git = (local_repo_path / ".git").exists()
    has_python = any(local_repo_path.rglob("*.py"))
    if not has_git and not has_python:
        message = f"Path is neither a Git repository nor a Python source directory: {local_repo_path}"
        logger.error(message)
        raise ValueError(message)
    if has_git:
        try:
            Repo(local_repo_path)
        except InvalidGitRepositoryError as exc:
            logger.error(f"Invalid Git repository at {local_repo_path}: {exc}")
            raise
    logger.info(f"Validated local repository path: {local_repo_path}")
    return local_repo_path.resolve()


def resolve_repository_path(
    use_git_url: bool,
    repo_url: str,
    local_repo_path: str,
    workspace_dir: Path,
    if_clone_exists: str,
    logger: NotebookLogger,
    clone_depth: int | None = None,
) -> Path:
    if use_git_url:
        logger.info("Execution mode: Git repository URL")
        return clone_or_reuse_repository(repo_url, workspace_dir, if_clone_exists, logger, clone_depth=clone_depth)
    logger.info("Execution mode: Local repository path")
    return validate_local_repository(Path(local_repo_path), logger)


def should_exclude_path(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def discover_python_files(repo_path: Path) -> list[Path]:
    python_files: list[Path] = []
    for file_path in repo_path.rglob("*.py"):
        if should_exclude_path(file_path.relative_to(repo_path)):
            continue
        python_files.append(file_path.resolve())
    python_files.sort()
    return python_files


def compute_repository_stats(repo_path: Path, python_files: list[Path]) -> dict[str, Any]:
    total_size_bytes = sum(file_path.stat().st_size for file_path in python_files)
    directory_count = sum(
        1
        for current_path, _, _ in os.walk(repo_path)
        if not should_exclude_path(Path(current_path).relative_to(repo_path))
    )
    return {
        "python_file_count": len(python_files),
        "repository_size_bytes": total_size_bytes,
        "directory_count": directory_count,
    }


def save_python_file_list(python_files: list[Path], repo_path: Path, output_csv: Path) -> None:
    rows = [
        {"absolute_path": str(file_path), "relative_path": str(file_path.relative_to(repo_path))}
        for file_path in python_files
    ]
    pd.DataFrame(rows).to_csv(output_csv, index=False)


def build_pylint_command(
    targets: Path | list[Path],
    output_format: str | None = None,
    rcfile: str | None = None,
) -> list[str]:
    target_list = [targets] if isinstance(targets, Path) else list(targets)
    command = [sys.executable, "-m", "pylint", *[str(target) for target in target_list]]
    command.extend(["--ignore=venv,.venv,env,build,dist,.tox,node_modules"])
    if output_format:
        command.extend(["--output-format", output_format])
    if rcfile:
        command.extend(["--rcfile", rcfile])
    return command


def run_pylint_command(
    command: list[str],
    logger: NotebookLogger,
    stream_raw: bool = False,
) -> tuple[str, str, int, bool]:
    try:
        if stream_raw:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=os.environ.copy(),
            )
            stdout_lines: list[str] = []
            stderr_lines: list[str] = []

            def _read_stream(pipe, sink, label):
                for line in iter(pipe.readline, ""):
                    print(line, end="", file=sys.stderr if label == "stderr" else sys.stdout)
                    sink.append(line)
                pipe.close()

            assert process.stdout is not None
            assert process.stderr is not None
            stdout_thread = threading.Thread(
                target=_read_stream, args=(process.stdout, stdout_lines, "stdout"), daemon=True
            )
            stderr_thread = threading.Thread(
                target=_read_stream, args=(process.stderr, stderr_lines, "stderr"), daemon=True
            )
            stdout_thread.start()
            stderr_thread.start()
            return_code = process.wait()
            stdout_thread.join()
            stderr_thread.join()
            stdout = "".join(stdout_lines)
            stderr = "".join(stderr_lines)
        else:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                env=os.environ.copy(),
            )
            stdout = completed.stdout
            stderr = completed.stderr
            return_code = completed.returncode
        success = return_code in (0, 1, 2, 4, 8, 16, 32)
        if not success:
            logger.error(f"Pylint command failed with exit code {return_code}: {' '.join(command[:6])}...")
        return stdout, stderr, return_code, success
    except Exception as exc:
        logger.error(f"Pylint execution exception: {exc}")
        return "", str(exc), -1, False


def combine_raw_streams(stdout: str, stderr: str) -> str:
    raw_output = stdout
    if stderr:
        if raw_output and not raw_output.endswith("\n"):
            raw_output += "\n"
        raw_output += stderr
    return raw_output


def run_pylint_on_file(
    python_file: Path,
    output_format: str | None,
    rcfile: str | None,
    logger: NotebookLogger,
    stream_raw: bool = False,
) -> tuple[str, str, int, bool]:
    command = build_pylint_command(python_file, output_format=output_format, rcfile=rcfile)
    stdout, stderr, return_code, success = run_pylint_command(command, logger, stream_raw=stream_raw)
    return stdout, stderr, return_code, success


def run_pylint_on_repo(
    repo_path: Path,
    rcfile: str | None,
    logger: NotebookLogger,
    stream_raw: bool = False,
) -> tuple[str, str, bool]:
    command = build_pylint_command(repo_path, rcfile=rcfile)
    stdout, stderr, _, success = run_pylint_command(command, logger, stream_raw=stream_raw)
    return stdout, stderr, success


def run_pylint_per_file(
    python_files: list[Path],
    rcfile: str | None,
    logger: NotebookLogger,
    stream_raw: bool = False,
) -> tuple[str, str, int, int]:
    raw_chunks: list[str] = []
    json_chunks: list[str] = []
    success_count = 0
    failure_count = 0
    total_files = len(python_files)

    for index, python_file in enumerate(python_files, start=1):
        if index == 1 or index % 25 == 0 or index == total_files:
            logger.info(f"Running Pylint ({index}/{total_files}): {python_file.name}")

        raw_stdout, raw_stderr, _, raw_success = run_pylint_on_file(
            python_file, output_format=None, rcfile=rcfile, logger=logger, stream_raw=stream_raw
        )
        json_stdout, json_stderr, _, json_success = run_pylint_on_file(
            python_file, output_format="json", rcfile=rcfile, logger=logger, stream_raw=False
        )
        if json_stderr.strip():
            logger.error(f"Pylint JSON stderr for {python_file}: {json_stderr.strip()}")

        raw_chunks.append(combine_raw_streams(raw_stdout, raw_stderr))
        if json_stdout.strip():
            json_chunks.append(json_stdout.strip())

        if raw_success or json_success:
            success_count += 1
        else:
            failure_count += 1

    return "".join(raw_chunks), "\n".join(json_chunks), success_count, failure_count


def parse_pylint_json(json_text: str, logger: NotebookLogger) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not json_text.strip():
        return records
    for chunk in json_text.split("\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            parsed = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            records.extend(parsed)
    if not records:
        try:
            parsed = json.loads(json_text)
            if isinstance(parsed, list):
                records = parsed
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to parse Pylint JSON output: {exc}")
    return records


def pylint_json_to_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for record in records:
        rows.append(
            {
                "file": record.get("path") or record.get("module", ""),
                "line": record.get("line", ""),
                "column": record.get("column", ""),
                "type": record.get("type", ""),
                "symbol": record.get("symbol", ""),
                "message": record.get("message", ""),
                "message-id": record.get("message-id", ""),
                "confidence": record.get("confidence", ""),
            }
        )
    columns = ["file", "line", "column", "type", "symbol", "message", "message-id", "confidence"]
    return pd.DataFrame(rows, columns=columns)


def is_code_smell(record: dict[str, Any]) -> bool:
    symbol = str(record.get("symbol", "")).lower()
    message_id = str(record.get("message-id", "")).upper()
    return symbol in CODE_SMELL_SYMBOLS or message_id in CODE_SMELL_MESSAGE_IDS


def extract_code_smells_findings(records: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for record in records:
        if not is_code_smell(record):
            continue
        record_type = str(record.get("type", "")).lower()
        rows.append(
            {
                "file": record.get("path") or record.get("module", ""),
                "line": record.get("line", ""),
                "message_id": record.get("message-id", ""),
                "symbol": record.get("symbol", ""),
                "message": record.get("message", ""),
                "severity": SEVERITY_MAP.get(record_type, record_type or "unknown"),
            }
        )
    columns = ["file", "line", "message_id", "symbol", "message", "severity"]
    return pd.DataFrame(rows, columns=columns)


def merge_records(existing: list[dict[str, Any]], new_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = {
        (str(r.get("message-id", "")), str(r.get("path") or r.get("module", "")), str(r.get("line", "")))
        for r in existing
    }
    merged = list(existing)
    for record in new_records:
        key = (str(record.get("message-id", "")), str(record.get("path") or record.get("module", "")), str(record.get("line", "")))
        if key not in seen:
            merged.append(record)
            seen.add(key)
    return merged


def compute_code_smells_summary(findings_df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame([{"metric_name": "Code_Smells_Count", "metric_value": len(findings_df)}])


def preview_raw_output(raw_text: str, preview_lines: int, output_path: Path) -> None:
    lines = raw_text.splitlines()
    print(f"\n{'=' * 80}")
    print(f"RAW PYLINT OUTPUT PREVIEW (first {preview_lines} lines)")
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
        "# Pylint Maintainability — Code Smells Count Raw Output Extraction\n\n"
        "This notebook analyzes **Python repositories** with **Pylint** and captures the complete raw tool output "
        "for maintainability code-smells metric derivation and validation.\n\n"
        "**Default benchmark repository:** [pallets/flask](https://github.com/pallets/flask)\n\n"
        "The notebook supports:\n"
        "- **Mode 1:** Clone from a Git repository URL\n"
        "- **Mode 2:** Analyze an already-cloned local repository path\n\n"
        "All deliverables are written to the configured `OUTPUT_DIR`."
    ),
    md("## Section 1 — Install Dependencies\n\nInstall open-source packages required for repository acquisition, static analysis, and result processing."),
    code("!pip install -q pylint pandas gitpython jupyter"),
    md(
        "## Section 2 — Configuration\n\n"
        "Set execution mode, repository source, and output location.\n\n"
        "- Set `USE_GIT_URL = True` to clone from `REPO_URL`.\n"
        "- Set `USE_GIT_URL = False` to analyze `LOCAL_REPO_PATH` directly.\n"
        "- When cloning, use `IF_CLONE_EXISTS` to choose between reusing or re-cloning an existing local copy."
    ),
    code(
        "USE_GIT_URL = True\n\n"
        "REPO_URL = 'https://github.com/pallets/flask.git'\n\n"
        "LOCAL_REPO_PATH = '/content/flask'\n\n"
        "OUTPUT_DIR = './outputs'\n\n"
        "IF_CLONE_EXISTS = 'reuse'\n\n"
        "CLONE_DEPTH = 1\n\n"
        "WORKSPACE_DIR = './workspace'\n\n"
        "PYLINT_RCFILE = None\n\n"
        "STREAM_RAW_OUTPUT = True\n\n"
        "RAW_OUTPUT_PREVIEW_LINES = 150\n\n"
        "# Fast validation benchmark (predictable code-smell outcomes):\n"
        "# USE_GIT_URL = False\n"
        "# LOCAL_REPO_PATH = './workspace/code_smells_benchmark'"
    ),
    md("## Section 3 — Imports and Utility Functions\n\nModular helpers for logging, repository setup, Pylint execution, and code-smell extraction."),
    code(UTILS.strip()),
    md("## Section 4 — Repository Setup\n\nResolve the repository path based on configuration and initialize output directories."),
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
        "logger.info(f'Repository ready at: {REPO_PATH}')"
    ),
    md("## Section 5 — Discover Python Files\n\nRecursively discover `.py` files while excluding virtual environments and build directories."),
    code(
        "PYTHON_FILES = discover_python_files(REPO_PATH)\n"
        "REPO_STATS = compute_repository_stats(REPO_PATH, PYTHON_FILES)\n\n"
        "PYTHON_FILES_CSV = OUTPUT_PATH / 'python_files.csv'\n"
        "save_python_file_list(PYTHON_FILES, REPO_PATH, PYTHON_FILES_CSV)\n\n"
        "print(f'Total Python Files Found: {len(PYTHON_FILES)}')\n"
        "print(f'Repository Size (Python files only): {REPO_STATS[\"repository_size_bytes\"]:,} bytes')\n"
        "print(f'Total Directories (excluding filtered paths): {REPO_STATS[\"directory_count\"]:,}')\n"
        "print(f'Saved file list to: {PYTHON_FILES_CSV}')"
    ),
    md(
        "## Section 6 — Execute Pylint\n\n"
        "Run Pylint against each discovered Python file. Execution continues even if individual files fail.\n\n"
        "A supplementary repository-level scan captures `duplicate-code` findings that require multi-file analysis.\n\n"
        "Example equivalent command:\n\n"
        "```bash\n"
        "pylint <repo_path>\n"
        "```"
    ),
    code(
        "if not PYTHON_FILES:\n"
        "    logger.error('No Python files discovered; skipping Pylint execution.')\n"
        "    PYLINT_RAW_TEXT = ''\n"
        "    PYLINT_JSON_TEXT = ''\n"
        "    FILES_SUCCESS = 0\n"
        "    FILES_FAILED = 0\n"
        "    PYLINT_RECORDS: list[dict] = []\n"
        "else:\n"
        "    PYLINT_RAW_TEXT, PYLINT_JSON_TEXT, FILES_SUCCESS, FILES_FAILED = run_pylint_per_file(\n"
        "        python_files=PYTHON_FILES,\n"
        "        rcfile=PYLINT_RCFILE,\n"
        "        logger=logger,\n"
        "        stream_raw=STREAM_RAW_OUTPUT,\n"
        "    )\n"
        "    PYLINT_RECORDS = parse_pylint_json(PYLINT_JSON_TEXT, logger)\n\n"
        "    repo_raw, repo_stderr, repo_ok = run_pylint_on_repo(\n"
        "        REPO_PATH, rcfile=PYLINT_RCFILE, logger=logger, stream_raw=False\n"
        "    )\n"
        "    if repo_stderr.strip():\n"
        "        logger.error(f'Repository-level Pylint stderr: {repo_stderr.strip()}')\n"
        "    if repo_ok:\n"
        "        repo_json_cmd = build_pylint_command(REPO_PATH, output_format='json', rcfile=PYLINT_RCFILE)\n"
        "        repo_json_stdout, _, _, _ = run_pylint_command(repo_json_cmd, logger, stream_raw=False)\n"
        "        repo_records = parse_pylint_json(repo_json_stdout, logger)\n"
        "        PYLINT_RECORDS = merge_records(PYLINT_RECORDS, repo_records)\n"
        "        PYLINT_RAW_TEXT += combine_raw_streams(repo_raw, repo_stderr)\n\n"
        "logger.info(f'Pylint execution complete. Files success={FILES_SUCCESS}, failed={FILES_FAILED}')"
    ),
    md("## Section 7 — Raw Output Extraction\n\nPersist complete raw Pylint text output, JSON output, and a CSV representation of all findings."),
    code(
        "RAW_OUTPUT_PATH = OUTPUT_PATH / 'pylint_raw_output.txt'\n"
        "JSON_OUTPUT_PATH = OUTPUT_PATH / 'pylint_output.json'\n"
        "RESULTS_CSV_PATH = OUTPUT_PATH / 'pylint_results.csv'\n\n"
        "RAW_OUTPUT_PATH.write_text(PYLINT_RAW_TEXT, encoding='utf-8')\n"
        "JSON_OUTPUT_PATH.write_text(json.dumps(PYLINT_RECORDS, indent=2, ensure_ascii=False), encoding='utf-8')\n\n"
        "PYLINT_RESULTS_DF = pylint_json_to_dataframe(PYLINT_RECORDS)\n"
        "PYLINT_RESULTS_DF.to_csv(RESULTS_CSV_PATH, index=False)\n\n"
        "logger.info(f'Saved raw output: {RAW_OUTPUT_PATH}')\n"
        "logger.info(f'Saved JSON output: {JSON_OUTPUT_PATH}')\n"
        "logger.info(f'Saved CSV results: {RESULTS_CSV_PATH}')\n"
        "logger.info(f'Total Pylint findings: {len(PYLINT_RESULTS_DF)}')\n\n"
        "preview_raw_output(PYLINT_RAW_TEXT, RAW_OUTPUT_PREVIEW_LINES, RAW_OUTPUT_PATH)"
    ),
    md(
        "## Section 8 — Code Smell Extraction\n\n"
        "Extract maintainability-related findings including duplicate-code, too-many-branches, too-many-arguments, "
        "too-many-locals, too-many-statements, and related refactor rules."
    ),
    code(
        "CODE_SMELLS_DF = extract_code_smells_findings(PYLINT_RECORDS)\n"
        "CODE_SMELLS_CSV = OUTPUT_PATH / 'code_smells_findings.csv'\n"
        "CODE_SMELLS_DF.to_csv(CODE_SMELLS_CSV, index=False)\n\n"
        "logger.info(f'Saved code smells findings: {CODE_SMELLS_CSV}')\n"
        "logger.info(f'Code smells count: {len(CODE_SMELLS_DF)}')\n\n"
        "if not CODE_SMELLS_DF.empty:\n"
        "    display(CODE_SMELLS_DF.head(15))\n"
        "else:\n"
        "    print('No code smell findings detected.')"
    ),
    md("## Section 9 — Metric Computation\n\nCompute repository-level code smells count:\n\n**Code_Smells_Count** = count(all maintainability-related findings)"),
    code(
        "SUMMARY_DF = compute_code_smells_summary(CODE_SMELLS_DF)\n"
        "SUMMARY_CSV = OUTPUT_PATH / 'code_smells_summary.csv'\n"
        "SUMMARY_DF.to_csv(SUMMARY_CSV, index=False)\n\n"
        "logger.info(f'Saved code smells summary: {SUMMARY_CSV}')\n"
        "display(SUMMARY_DF)"
    ),
    md("## Section 10 — Summary Dashboard\n\nOverview of analysis coverage, Pylint findings, and code-smell metrics."),
    code(
        "code_smells_count = int(SUMMARY_DF.loc[SUMMARY_DF['metric_name'] == 'Code_Smells_Count', 'metric_value'].iloc[0])\n\n"
        "summary_df = pd.DataFrame(\n"
        "    [\n"
        "        {'Metric': 'Total Python Files', 'Value': len(PYTHON_FILES)},\n"
        "        {'Metric': 'Files Successfully Analyzed', 'Value': FILES_SUCCESS},\n"
        "        {'Metric': 'Files Failed', 'Value': FILES_FAILED},\n"
        "        {'Metric': 'Total Pylint Findings', 'Value': len(PYLINT_RESULTS_DF)},\n"
        "        {'Metric': 'Total Code Smells', 'Value': code_smells_count},\n"
        "    ]\n"
        ")\n\n"
        "display(summary_df)\n\n"
        "deliverables = [\n"
        "    RAW_OUTPUT_PATH,\n"
        "    JSON_OUTPUT_PATH,\n"
        "    RESULTS_CSV_PATH,\n"
        "    PYTHON_FILES_CSV,\n"
        "    CODE_SMELLS_CSV,\n"
        "    SUMMARY_CSV,\n"
        "    ERROR_LOG_PATH,\n"
        "]\n\n"
        "print('\\nDeliverables:')\n"
        "for deliverable in deliverables:\n"
        "    status = 'OK' if deliverable.exists() else 'MISSING'\n"
        "    print(f'  [{status}] {deliverable}')"
    ),
    md("## Section 11 — Error Handling\n\nFailures encountered during cloning, validation, or Pylint execution are appended to `outputs/error_log.txt`."),
    code(
        "if ERROR_LOG_PATH.exists() and ERROR_LOG_PATH.stat().st_size > 0:\n"
        "    print(ERROR_LOG_PATH.read_text(encoding='utf-8'))\n"
        "else:\n"
        "    print('No errors logged.')"
    ),
    md(
        "## Section 12 — Deliverables\n\n"
        "Upon successful completion, the following artifacts are available under `outputs/`:\n\n"
        "```text\n"
        "outputs/\n"
        "├── pylint_raw_output.txt\n"
        "├── pylint_output.json\n"
        "├── pylint_results.csv\n"
        "├── python_files.csv\n"
        "├── code_smells_findings.csv\n"
        "├── code_smells_summary.csv\n"
        "└── error_log.txt\n"
        "```\n\n"
        "The notebook is designed to run end-to-end in Jupyter Notebook and Google Colab without manual intervention."
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
