"""Generate cppcheck_code_smells_extraction.ipynb."""
from __future__ import annotations
"""HELLO TEAM"""
import json
from pathlib import Path
"""TEAM"""
"""BYE"""
ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "cppcheck_code_smells_extraction.ipynb"

UTILS = r'''
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
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
CPPCHECK_EXCLUDE_ARGS = [
    "-i.git", "-ibuild", "-idist", "-iout", "-ibin", "-ivendor", "-ithird_party", "-idocs", "-itests",
]
CODE_SMELL_RULE_IDS = {
    "duplicateExpression", "variableScope", "functionStatic", "staticFunction", "constVariable",
    "unreadVariable", "unusedFunction", "unusedStructMember", "shadowVariable", "passedByValue",
    "knownConditionTrueFalse",
}
RESULTS_COLUMNS = ["file", "line", "severity", "id", "message", "verbose", "cwe"]
SMELLS_COLUMNS = ["file", "line", "severity", "rule_id", "message", "cwe"]
PROGRESS_RE = re.compile(r"(\d+)/(\d+) files checked")


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
    use_git_url: bool,
    repo_url: str,
    local_repo_path: str | Path,
    workspace_dir: Path,
    if_clone_exists: str,
    logger: NotebookLogger,
    clone_depth: int | None = None,
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


def compute_repository_stats(repo_path: Path, c_files: list[Path]) -> dict[str, int]:
    total_size = sum(path.stat().st_size for path in c_files)
    directories = {
        path.parent for path in c_files if not should_exclude_path(path.relative_to(repo_path))
    }
    return {
        "repository_size_bytes": total_size,
        "directory_count": len(directories),
    }


def save_c_file_list(c_files: list[Path], repo_path: Path, output_csv: Path) -> None:
    pd.DataFrame(
        [{"absolute_path": str(path), "relative_path": str(path.relative_to(repo_path))} for path in c_files]
    ).to_csv(output_csv, index=False)


def resolve_cppcheck_executable(project_root: Path | None = None) -> Path:
    env_path = os.environ.get("CPPCHECK")
    if env_path:
        candidate = Path(env_path)
        if candidate.exists():
            return candidate.resolve()

    which = shutil.which("cppcheck")
    if which:
        return Path(which).resolve()

    roots = []
    if project_root is not None:
        roots.append(project_root)
    roots.append(Path.cwd().resolve())
    for root in roots:
        for relative in (
            Path("runtimes/cppcheck/PFiles/Cppcheck/cppcheck.exe"),
            Path("runtimes/cppcheck/PFiles/Cppcheck/cppcheck"),
            Path("runtimes/cppcheck/cppcheck.exe"),
            Path("runtimes/cppcheck/cppcheck"),
            Path("../../runtimes/cppcheck/PFiles/Cppcheck/cppcheck.exe"),
            Path("../../runtimes/cppcheck/PFiles/Cppcheck/cppcheck"),
        ):
            candidate = (root / relative).resolve()
            if candidate.exists():
                return candidate

    raise FileNotFoundError(
        "Cppcheck executable not found. Install Cppcheck (apt-get install cppcheck) or set CPPCHECK."
    )


def build_cppcheck_command(cppcheck_exe: Path, repo_path: Path, xml_output: bool = False) -> list[str]:
    command = [str(cppcheck_exe), "--enable=all", "--inconclusive", "--force", *CPPCHECK_EXCLUDE_ARGS]
    if xml_output:
        command.extend(["--xml", "--xml-version=2"])
    command.append(str(repo_path))
    return command


def run_cppcheck_command(command: list[str], logger: NotebookLogger, stream_raw: bool = False) -> tuple[str, str, int]:
    if stream_raw:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
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
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.stdout, completed.stderr, completed.returncode


def combine_raw_streams(stdout: str, stderr: str) -> str:
    raw = stdout
    if stderr:
        if raw and not raw.endswith("\n"):
            raw += "\n"
        raw += stderr
    return raw


def parse_cppcheck_xml(xml_text: str, logger: NotebookLogger) -> list[dict[str, Any]]:
    if not xml_text.strip():
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.error(f"Failed to parse Cppcheck XML: {exc}")
        return []

    rows: list[dict[str, Any]] = []
    for error in root.findall(".//error"):
        rule_id = error.get("id", "")
        if rule_id == "checkersReport":
            continue
        locations = error.findall("location")
        if not locations:
            rows.append({
                "file": error.get("file0", ""),
                "line": "",
                "severity": error.get("severity", ""),
                "id": rule_id,
                "message": error.get("msg", ""),
                "verbose": error.get("verbose", ""),
                "cwe": error.get("cwe", ""),
            })
            continue
        for location in locations:
            rows.append({
                "file": location.get("file", error.get("file0", "")),
                "line": location.get("line", ""),
                "severity": error.get("severity", ""),
                "id": rule_id,
                "message": error.get("msg", ""),
                "verbose": error.get("verbose", ""),
                "cwe": error.get("cwe", ""),
            })
    return rows


def findings_to_dataframe(findings: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(findings, columns=RESULTS_COLUMNS)


def is_code_smell(rule_id: str) -> bool:
    return rule_id in CODE_SMELL_RULE_IDS


def extract_code_smells_findings(findings: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for finding in findings:
        rule_id = str(finding.get("id", ""))
        if not is_code_smell(rule_id):
            continue
        key = (
            str(finding.get("file", "")),
            str(finding.get("line", "")),
            rule_id,
            str(finding.get("message", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "file": finding.get("file", ""),
            "line": finding.get("line", ""),
            "severity": finding.get("severity", ""),
            "rule_id": rule_id,
            "message": finding.get("message", ""),
            "cwe": finding.get("cwe", ""),
        })
    return pd.DataFrame(rows, columns=SMELLS_COLUMNS)


def parse_progress_stats(stdout: str, total_files: int) -> tuple[int, int]:
    checked = 0
    total = total_files
    for match in PROGRESS_RE.finditer(stdout):
        checked = int(match.group(1))
        total = int(match.group(2))
    if checked == 0 and total_files > 0:
        checked = total_files
        total = total_files
    return checked, max(total - checked, 0)


def count_failed_files(findings: list[dict[str, Any]]) -> int:
    failure_ids = {"syntaxError", "internalError", "unknownMacro", "preprocessorErrorDirective"}
    failed_files = {
        str(item.get("file", ""))
        for item in findings
        if str(item.get("id", "")) in failure_ids and str(item.get("file", ""))
    }
    return len(failed_files)


def compute_code_smells_summary(findings_df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame([{"metric_name": "Code_Smells_Count", "metric_value": len(findings_df)}])


def preview_raw_output(raw_text: str, preview_lines: int, output_path: Path) -> None:
    lines = raw_text.splitlines()
    print(f"\n{'=' * 80}")
    print(f"RAW CPPCHECK OUTPUT PREVIEW (first {preview_lines} lines)")
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
        "# Cppcheck Maintainability — Code Smells Count Raw Output Extraction\n\n"
        "This notebook analyzes **C repositories** with **Cppcheck** and captures the complete raw tool output "
        "for maintainability code-smells metric derivation and validation.\n\n"
        "**Default benchmark repository:** [redis/redis](https://github.com/redis/redis)\n\n"
        "The notebook supports:\n"
        "- **Mode 1:** Clone from a Git repository URL\n"
        "- **Mode 2:** Analyze an already-cloned local repository path\n\n"
        "All deliverables are written to the configured `OUTPUT_DIR`."
    ),
    md(
        "## Section 1 — Install Dependencies\n\n"
        "Install open-source packages required for repository acquisition, static analysis, and result processing.\n\n"
        "On Linux/Colab, Cppcheck is installed via `apt-get`. On Windows/macOS, ensure `cppcheck` is on PATH "
        "or bootstrap it under `../../runtimes/cppcheck/`."
    ),
    code(
        "!pip install -q pandas gitpython jupyter\n\n"
        "import platform\n"
        "if platform.system() == 'Linux':\n"
        "    !apt-get update -qq\n"
        "    !apt-get install -y -qq cppcheck\n\n"
        "!cppcheck --version"
    ),
    md(
        "## Section 2 — Configuration\n\n"
        "Set execution mode, repository source, and output location.\n\n"
        "- Set `USE_GIT_URL = True` to clone from `REPO_URL`.\n"
        "- Set `USE_GIT_URL = False` to analyze `LOCAL_REPO_PATH` directly.\n"
        "- When cloning, use `IF_CLONE_EXISTS` to choose between reusing or re-cloning an existing local copy."
    ),
    code(
        "USE_GIT_URL = True\n\n"
        "REPO_URL = 'https://github.com/redis/redis.git'\n\n"
        "LOCAL_REPO_PATH = '/content/redis'\n\n"
        "OUTPUT_DIR = './outputs'\n\n"
        "IF_CLONE_EXISTS = 'reuse'\n\n"
        "CLONE_DEPTH = 1\n\n"
        "WORKSPACE_DIR = './workspace'\n\n"
        "PROJECT_ROOT = Path('../../').resolve()\n\n"
        "STREAM_RAW_OUTPUT = True\n\n"
        "RAW_OUTPUT_PREVIEW_LINES = 150\n\n"
        "# Fast validation benchmark (predictable code-smell outcomes):\n"
        "# USE_GIT_URL = False\n"
        "# LOCAL_REPO_PATH = './workspace/c_code_smells_benchmark'"
    ),
    md("## Section 3 — Imports and Utility Functions\n\nModular helpers for logging, repository setup, Cppcheck execution, and code-smell extraction."),
    code("from pathlib import Path\n\n" + UTILS.strip()),
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
    md("## Section 5 — Discover C Files\n\nRecursively discover `.c` and `.h` files while excluding build, vendor, and test directories."),
    code(
        "C_FILES = discover_c_files(REPO_PATH)\n"
        "REPO_STATS = compute_repository_stats(REPO_PATH, C_FILES)\n\n"
        "C_FILES_CSV = OUTPUT_PATH / 'c_files.csv'\n"
        "save_c_file_list(C_FILES, REPO_PATH, C_FILES_CSV)\n\n"
        "print(f'Total C Files Found: {len(C_FILES)}')\n"
        "print(f'Repository Size (C files only): {REPO_STATS[\"repository_size_bytes\"]:,} bytes')\n"
        "print(f'Total Directories (excluding filtered paths): {REPO_STATS[\"directory_count\"]:,}')\n"
        "print(f'Saved file list to: {C_FILES_CSV}')"
    ),
    md(
        "## Section 6 — Execute Cppcheck\n\n"
        "Run Cppcheck against the repository. Execution continues even if individual files fail.\n\n"
        "Example equivalent command:\n\n"
        "```bash\n"
        "cppcheck --enable=all --inconclusive --force --xml --xml-version=2 <repo_path>\n"
        "```"
    ),
    code(
        "try:\n"
        "    CPPCHECK_EXE = resolve_cppcheck_executable(PROJECT_ROOT)\n"
        "    logger.info(f'Using Cppcheck executable: {CPPCHECK_EXE}')\n"
        "except Exception as exc:\n"
        "    logger.error(str(exc))\n"
        "    raise\n\n"
        "if not C_FILES:\n"
        "    logger.error('No C files discovered; skipping Cppcheck execution.')\n"
        "    CPPCHECK_RAW_TEXT = ''\n"
        "    CPPCHECK_XML_TEXT = ''\n"
        "    FILES_SUCCESS = 0\n"
        "    FILES_FAILED = 0\n"
        "    CPPCHECK_FINDINGS: list[dict] = []\n"
        "else:\n"
        "    text_cmd = build_cppcheck_command(CPPCHECK_EXE, REPO_PATH, xml_output=False)\n"
        "    text_stdout, text_stderr, text_code = run_cppcheck_command(text_cmd, logger, stream_raw=STREAM_RAW_OUTPUT)\n"
        "    CPPCHECK_RAW_TEXT = combine_raw_streams(text_stdout, text_stderr)\n"
        "    if text_code not in (0, 1):\n"
        "        logger.error(f'Cppcheck text run exited with code {text_code}')\n\n"
        "    xml_cmd = build_cppcheck_command(CPPCHECK_EXE, REPO_PATH, xml_output=True)\n"
        "    xml_stdout, xml_stderr, xml_code = run_cppcheck_command(xml_cmd, logger, stream_raw=False)\n"
        "    CPPCHECK_XML_TEXT = xml_stderr if xml_stderr.strip().startswith('<?xml') else xml_stderr\n"
        "    if not CPPCHECK_XML_TEXT.strip().startswith('<?xml') and xml_stdout.strip().startswith('<?xml'):\n"
        "        CPPCHECK_XML_TEXT = xml_stdout\n"
        "    if xml_code not in (0, 1):\n"
        "        logger.error(f'Cppcheck XML run exited with code {xml_code}')\n\n"
        "    CPPCHECK_FINDINGS = parse_cppcheck_xml(CPPCHECK_XML_TEXT, logger)\n"
        "    FILES_SUCCESS, FILES_FAILED = parse_progress_stats(text_stdout, len(C_FILES))\n"
        "    FILES_FAILED = max(FILES_FAILED, count_failed_files(CPPCHECK_FINDINGS))\n"
        "    if FILES_SUCCESS == 0 and len(C_FILES) > 0:\n"
        "        FILES_SUCCESS = len(C_FILES) - FILES_FAILED\n\n"
        "logger.info(f'Cppcheck execution complete. Files success={FILES_SUCCESS}, failed={FILES_FAILED}')"
    ),
    md("## Section 7 — Raw Output Extraction\n\nPersist complete raw Cppcheck text output, XML output, and a CSV representation of all findings."),
    code(
        "RAW_OUTPUT_PATH = OUTPUT_PATH / 'cppcheck_raw_output.txt'\n"
        "XML_OUTPUT_PATH = OUTPUT_PATH / 'cppcheck_output.xml'\n"
        "RESULTS_CSV_PATH = OUTPUT_PATH / 'cppcheck_results.csv'\n\n"
        "RAW_OUTPUT_PATH.write_text(CPPCHECK_RAW_TEXT, encoding='utf-8')\n"
        "XML_OUTPUT_PATH.write_text(CPPCHECK_XML_TEXT, encoding='utf-8')\n\n"
        "CPPCHECK_RESULTS_DF = findings_to_dataframe(CPPCHECK_FINDINGS)\n"
        "CPPCHECK_RESULTS_DF.to_csv(RESULTS_CSV_PATH, index=False)\n\n"
        "logger.info(f'Saved raw output: {RAW_OUTPUT_PATH}')\n"
        "logger.info(f'Saved XML output: {XML_OUTPUT_PATH}')\n"
        "logger.info(f'Saved CSV results: {RESULTS_CSV_PATH}')\n"
        "logger.info(f'Total Cppcheck findings: {len(CPPCHECK_RESULTS_DF)}')\n\n"
        "preview_raw_output(CPPCHECK_RAW_TEXT, RAW_OUTPUT_PREVIEW_LINES, RAW_OUTPUT_PATH)"
    ),
    md(
        "## Section 8 — Code Smell Extraction\n\n"
        "Extract maintainability-related findings including duplicateExpression, variableScope, functionStatic, "
        "constVariable, unreadVariable, unusedFunction, unusedStructMember, shadowVariable, passedByValue, "
        "and knownConditionTrueFalse."
    ),
    code(
        "CODE_SMELLS_DF = extract_code_smells_findings(CPPCHECK_FINDINGS)\n"
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
    md("## Section 10 — Summary Dashboard\n\nOverview of analysis coverage, Cppcheck findings, and code-smell metrics."),
    code(
        "code_smells_count = int(SUMMARY_DF.loc[SUMMARY_DF['metric_name'] == 'Code_Smells_Count', 'metric_value'].iloc[0])\n\n"
        "summary_df = pd.DataFrame(\n"
        "    [\n"
        "        {'Metric': 'Total C Files', 'Value': len(C_FILES)},\n"
        "        {'Metric': 'Files Successfully Analyzed', 'Value': FILES_SUCCESS},\n"
        "        {'Metric': 'Files Failed', 'Value': FILES_FAILED},\n"
        "        {'Metric': 'Total Cppcheck Findings', 'Value': len(CPPCHECK_RESULTS_DF)},\n"
        "        {'Metric': 'Total Code Smells', 'Value': code_smells_count},\n"
        "    ]\n"
        ")\n\n"
        "display(summary_df)\n\n"
        "deliverables = [\n"
        "    RAW_OUTPUT_PATH,\n"
        "    XML_OUTPUT_PATH,\n"
        "    RESULTS_CSV_PATH,\n"
        "    C_FILES_CSV,\n"
        "    CODE_SMELLS_CSV,\n"
        "    SUMMARY_CSV,\n"
        "    ERROR_LOG_PATH,\n"
        "]\n\n"
        "print('\\nDeliverables:')\n"
        "for deliverable in deliverables:\n"
        "    status = 'OK' if deliverable.exists() else 'MISSING'\n"
        "    print(f'  [{status}] {deliverable}')"
    ),
    md("## Section 11 — Error Handling\n\nFailures encountered during cloning, validation, or Cppcheck execution are appended to `outputs/error_log.txt`."),
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
        "├── cppcheck_raw_output.txt\n"
        "├── cppcheck_output.xml\n"
        "├── cppcheck_results.csv\n"
        "├── c_files.csv\n"
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
