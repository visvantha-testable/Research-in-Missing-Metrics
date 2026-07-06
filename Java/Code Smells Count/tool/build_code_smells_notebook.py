"""Generate pmd_code_smells_extraction.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "pmd_code_smells_extraction.ipynb"

PMD_DOWNLOAD = r'''
import io
import os
import shutil
import zipfile
from pathlib import Path
from urllib.request import urlopen

os.environ.pop("PYTHONPATH", None)


def download_pmd_distribution(pmd_version: str = "7.0.0", install_root: Path = Path(".")) -> Path:
    pmd_home = install_root / f"pmd-bin-{pmd_version}"
    if (pmd_home / "bin").exists():
        print(f"PMD already installed at: {pmd_home}")
        return pmd_home.resolve()

    url = (
        f"https://github.com/pmd/pmd/releases/download/"
        f"pmd_releases%2F{pmd_version}/pmd-dist-{pmd_version}-bin.zip"
    )
    zip_path = install_root / f"pmd-dist-{pmd_version}-bin.zip"
    install_root.mkdir(parents=True, exist_ok=True)

    print(f"Downloading PMD {pmd_version} from GitHub releases...")
    with urlopen(url, timeout=120) as response, open(zip_path, "wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)

    print(f"Extracting {zip_path.name}...")
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(install_root)

    if not (pmd_home / "bin").exists():
        raise RuntimeError(f"PMD extraction failed; expected directory: {pmd_home}")

    print(f"PMD installed at: {pmd_home.resolve()}")
    return pmd_home.resolve()


PMD_HOME = download_pmd_distribution(pmd_version="7.0.0", install_root=Path("../../runtimes"))
'''

UTILS = r'''
from __future__ import annotations

import io
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

EXCLUDED_DIR_NAMES = {
    ".git", "target", "build", "out", "bin", "generated", "node_modules", ".gradle", ".idea",
}
CODE_SMELL_RULES = {
    "GodClass", "DataClass", "LongMethod", "ExcessiveMethodLength", "ExcessiveClassLength",
    "ExcessiveParameterList", "ExcessivePublicCount", "CyclomaticComplexity", "NPathComplexity",
    "TooManyFields", "TooManyMethods", "AvoidDeeplyNestedIfStmts", "CouplingBetweenObjects",
}
FINDINGS_COLUMNS = ["file", "begin_line", "end_line", "rule", "priority", "message", "ruleset"]
PMD_TEXT_VIOLATION_PATTERN = re.compile(r"^(?P<file>.+):(?P<line>\d+):\s*(?P<rule>[^:]+):\s*(?P<message>.*)$")
PARSE_ERROR_PATTERN = re.compile(r"Error (?:while )?processing(?: file)?:?\s*(?P<file>.+)", re.IGNORECASE)
PMD_SUCCESS_CODES = {0, 4}


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


def configure_java_runtime(jdk_home: Path | None = None) -> Path | None:
    if jdk_home is None:
        return None
    jdk_home = jdk_home.resolve()
    java_bin = jdk_home / "bin"
    java_exe = java_bin / ("java.exe" if sys.platform.startswith("win") else "java")
    if java_exe.exists():
        os.environ["JAVA_HOME"] = str(jdk_home)
        os.environ["PATH"] = str(java_bin) + os.pathsep + os.environ.get("PATH", "")
        return jdk_home
    return None


def resolve_pmd_executable(pmd_home: Path) -> Path:
    pmd_home = pmd_home.resolve()
    candidate = pmd_home / "bin" / ("pmd.bat" if sys.platform.startswith("win") else "pmd")
    if not candidate.exists():
        raise FileNotFoundError(f"PMD executable not found: {candidate}")
    return candidate


def verify_java_runtime(logger: NotebookLogger) -> None:
    try:
        completed = subprocess.run(["java", "-version"], capture_output=True, text=True, check=False)
        if completed.returncode != 0 and not completed.stderr.strip():
            raise RuntimeError("java -version failed")
    except FileNotFoundError as exc:
        logger.error("Java runtime is required for PMD execution.")
        raise RuntimeError("Java runtime is required for PMD execution.") from exc


def discover_java_files(repo_path: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo_path.rglob("*.java"):
        if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            continue
        files.append(path.resolve())
    return sorted(files)


def compute_repository_stats(repo_path: Path, java_files: list[Path]) -> dict[str, int]:
    total_size = sum(path.stat().st_size for path in java_files)
    directories = {path.parent for path in java_files if path.is_file()}
    return {"repository_size_bytes": total_size, "directory_count": len(directories)}


def save_java_file_list(java_files: list[Path], repo_path: Path, output_csv: Path) -> None:
    pd.DataFrame(
        [{"absolute_path": str(path), "relative_path": str(path.relative_to(repo_path))} for path in java_files]
    ).to_csv(output_csv, index=False)


def join_rulesets(rulesets: list[str]) -> str:
    return ",".join(rulesets)


def build_pmd_command(pmd_executable: Path, repo_path: Path, rulesets: list[str], output_format: str) -> list[str]:
    return [
        str(pmd_executable), "check", "-d", str(repo_path), "-R", join_rulesets(rulesets),
        "-f", output_format, "--no-cache", "--no-progress",
    ]


def run_pmd_command(command: list[str], logger: NotebookLogger, stream_raw: bool = False) -> tuple[str, str, int, bool]:
    try:
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
            return_code = process.returncode or 0
            return "".join(stdout_lines), "".join(stderr_lines), return_code, return_code in PMD_SUCCESS_CODES

        completed = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        return completed.stdout, completed.stderr, completed.returncode, completed.returncode in PMD_SUCCESS_CODES
    except Exception as exc:
        logger.error(f"PMD execution exception: {exc}")
        return "", str(exc), 1, False


def combine_raw_streams(stdout: str, stderr: str) -> str:
    raw = stdout
    if stderr:
        if raw and not raw.endswith("\n"):
            raw += "\n"
        raw += stderr
    return raw


def run_pmd_suite(
    pmd_home: Path, repo_path: Path, rulesets: list[str], logger: NotebookLogger, stream_raw: bool = False,
) -> dict[str, str]:
    pmd_executable = resolve_pmd_executable(pmd_home)
    logger.info(f"Running PMD on repository: {repo_path}")

    text_command = build_pmd_command(pmd_executable, repo_path, rulesets, "text")
    text_stdout, text_stderr, text_code, text_ok = run_pmd_command(text_command, logger, stream_raw=stream_raw)
    if text_code not in PMD_SUCCESS_CODES:
        logger.error(f"PMD text run exited with code {text_code}")

    csv_command = build_pmd_command(pmd_executable, repo_path, rulesets, "csv")
    csv_stdout, csv_stderr, csv_code, csv_ok = run_pmd_command(csv_command, logger, stream_raw=False)
    if csv_code not in PMD_SUCCESS_CODES:
        logger.error(f"PMD CSV run exited with code {csv_code}")
    if csv_stderr.strip():
        logger.error(f"PMD CSV stderr: {csv_stderr.strip()}")

    xml_command = build_pmd_command(pmd_executable, repo_path, rulesets, "xml")
    xml_stdout, xml_stderr, xml_code, xml_ok = run_pmd_command(xml_command, logger, stream_raw=False)
    if xml_code not in PMD_SUCCESS_CODES:
        logger.error(f"PMD XML run exited with code {xml_code}")
    if xml_stderr.strip():
        logger.error(f"PMD XML stderr: {xml_stderr.strip()}")

    return {
        "raw_text": combine_raw_streams(text_stdout, text_stderr),
        "csv_text": csv_stdout,
        "xml_text": xml_stdout,
        "execution_ok": str(text_ok or csv_ok or xml_ok),
    }


def parse_pmd_csv(csv_text: str) -> pd.DataFrame:
    if not csv_text.strip():
        return pd.DataFrame()
    return pd.read_csv(io.StringIO(csv_text.strip()))


def normalize_pmd_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    renamed = frame.copy()
    renamed.columns = [str(col).strip().lower().replace(" ", "_") for col in renamed.columns]
    return renamed


def violations_from_csv(csv_df: pd.DataFrame) -> pd.DataFrame:
    if csv_df.empty:
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    frame = normalize_pmd_columns(csv_df)
    rows = []
    for _, record in frame.iterrows():
        line_value = record.get("line", record.get("beginline", record.get("begin_line", "")))
        rows.append({
            "file": str(record.get("file", record.get("filename", ""))),
            "begin_line": line_value,
            "end_line": line_value,
            "rule": str(record.get("rule", "")),
            "priority": record.get("priority", ""),
            "message": str(record.get("description", record.get("message", ""))),
            "ruleset": str(record.get("rule_set", record.get("ruleset", ""))),
        })
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def parse_pmd_text_violations(raw_text: str) -> pd.DataFrame:
    rows = []
    for line in raw_text.splitlines():
        match = PMD_TEXT_VIOLATION_PATTERN.match(line.strip())
        if not match:
            continue
        rows.append({
            "file": match.group("file").strip(),
            "begin_line": int(match.group("line")),
            "end_line": int(match.group("line")),
            "rule": match.group("rule").strip(),
            "priority": "",
            "message": match.group("message").strip(),
            "ruleset": "",
        })
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def parse_pmd_xml_violations(xml_text: str) -> pd.DataFrame:
    if not xml_text.strip():
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    rows = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    for file_node in root.iter():
        if not str(file_node.tag).endswith("file"):
            continue
        file_name = file_node.attrib.get("name", "")
        for violation in file_node:
            if not str(violation.tag).endswith("violation"):
                continue
            begin_line = int(violation.attrib.get("beginline", violation.attrib.get("beginLine", 0)) or 0)
            end_line = int(violation.attrib.get("endline", violation.attrib.get("endLine", begin_line)) or begin_line)
            rows.append({
                "file": file_name,
                "begin_line": begin_line,
                "end_line": end_line,
                "rule": violation.attrib.get("rule", ""),
                "priority": violation.attrib.get("priority", ""),
                "message": (violation.text or "").strip(),
                "ruleset": violation.attrib.get("ruleset", ""),
            })
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def merge_violations(*frames: pd.DataFrame) -> pd.DataFrame:
    valid = [frame for frame in frames if frame is not None and not frame.empty]
    if not valid:
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    combined = pd.concat(valid, ignore_index=True)
    return combined.drop_duplicates(subset=["file", "begin_line", "rule", "message"], keep="first")


def is_code_smell(rule: str) -> bool:
    return rule in CODE_SMELL_RULES


def extract_code_smells_findings(violations: pd.DataFrame) -> pd.DataFrame:
    if violations.empty:
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    return violations[violations["rule"].map(is_code_smell)].reset_index(drop=True)


def compute_code_smells_summary(findings_df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame([{"metric_name": "Code_Smells_Count", "metric_value": len(findings_df)}])


def count_failed_files(raw_text: str, java_files: list[Path]) -> int:
    failed: set[str] = set()
    for match in PARSE_ERROR_PATTERN.finditer(raw_text):
        failed.add(str(Path(match.group("file").strip()).resolve()))
    for path in java_files:
        if f"Error processing {path}" in raw_text or f"Error while processing {path}" in raw_text:
            failed.add(str(path))
    return len(failed)


def preview_raw_output(raw_text: str, preview_lines: int, output_path: Path) -> None:
    lines = raw_text.splitlines()
    print(f"\n{'=' * 80}")
    print(f"RAW PMD OUTPUT PREVIEW (first {preview_lines} lines)")
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
        "# PMD Maintainability — Code Smells Count Raw Output Extraction (Java)\n\n"
        "This notebook analyzes **Java repositories** with **PMD** and captures the complete raw tool output "
        "for maintainability code-smells metric derivation and validation.\n\n"
        "**Default benchmark repository:** [spring-projects/spring-framework](https://github.com/spring-projects/spring-framework)\n\n"
        "The notebook supports:\n"
        "- **Mode 1:** Clone from a Git repository URL\n"
        "- **Mode 2:** Analyze an already-cloned local repository path\n\n"
        "All deliverables are written to the configured `OUTPUT_DIR`."
    ),
    md("## Section 1 — Install Dependencies\n\nInstall open-source Python packages and download the open-source PMD distribution automatically."),
    code("!pip install -q pandas gitpython jupyter requests tqdm"),
    code(PMD_DOWNLOAD.strip() + "\n\nimport subprocess\nimport sys\n\npmd_bin = PMD_HOME / 'bin' / ('pmd.bat' if sys.platform.startswith('win') else 'pmd')\nsubprocess.run([str(pmd_bin), '--version'], check=False)"),
    md(
        "## Section 2 — Configuration\n\n"
        "Set execution mode, repository source, output location, and PMD rulesets.\n\n"
        "- Set `USE_GIT_URL = True` to clone from `REPO_URL`.\n"
        "- Set `USE_GIT_URL = False` to analyze `LOCAL_REPO_PATH` directly."
    ),
    code(
        "USE_GIT_URL = True\n\n"
        "REPO_URL = 'https://github.com/spring-projects/spring-framework.git'\n\n"
        "LOCAL_REPO_PATH = '/content/spring-framework'\n\n"
        "OUTPUT_DIR = './outputs'\n\n"
        "PMD_HOME = '../../runtimes/pmd-bin-7.0.0'\n\n"
        "JDK_HOME = '../../runtimes/jdk-21'\n\n"
        "RULESETS = [\n"
        "    'category/java/bestpractices.xml',\n"
        "    'category/java/codestyle.xml',\n"
        "    'category/java/design.xml',\n"
        "    'category/java/errorprone.xml',\n"
        "]\n\n"
        "IF_CLONE_EXISTS = 'reuse'\n\n"
        "CLONE_DEPTH = 1\n\n"
        "WORKSPACE_DIR = './workspace'\n\n"
        "STREAM_RAW_OUTPUT = True\n\n"
        "RAW_OUTPUT_PREVIEW_LINES = 150\n\n"
        "# Fast validation benchmark:\n"
        "# USE_GIT_URL = False\n"
        "# LOCAL_REPO_PATH = './workspace/java_code_smells_benchmark'"
    ),
    md("## Section 3 — Imports and Utility Functions\n\nModular helpers for logging, repository setup, Java file discovery, PMD execution, and code-smell extraction."),
    code("from pathlib import Path\n\n" + UTILS.strip()),
    md("## Section 4 — Repository Setup\n\nResolve the repository path based on configuration and initialize output directories."),
    code(
        "OUTPUT_PATH = Path(OUTPUT_DIR).resolve()\n"
        "WORKSPACE_PATH = Path(WORKSPACE_DIR).resolve()\n"
        "ERROR_LOG_PATH = OUTPUT_PATH / 'error_log.txt'\n"
        "PMD_HOME_PATH = Path(PMD_HOME).resolve()\n"
        "JDK_HOME_PATH = Path(JDK_HOME).resolve() if JDK_HOME else None\n\n"
        "ensure_output_dir(OUTPUT_PATH)\n"
        "logger = NotebookLogger(ERROR_LOG_PATH)\n"
        "configure_java_runtime(JDK_HOME_PATH)\n"
        "verify_java_runtime(logger)\n"
        "resolve_pmd_executable(PMD_HOME_PATH)\n\n"
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
        "logger.info(f'Repository ready at: {REPO_PATH}')\n"
        "logger.info(f'PMD home: {PMD_HOME_PATH}')"
    ),
    md("## Section 5 — Discover Java Files\n\nRecursively discover `.java` files while excluding build and generated directories."),
    code(
        "JAVA_FILES = discover_java_files(REPO_PATH)\n"
        "REPO_STATS = compute_repository_stats(REPO_PATH, JAVA_FILES)\n\n"
        "JAVA_FILES_CSV = OUTPUT_PATH / 'java_files.csv'\n"
        "save_java_file_list(JAVA_FILES, REPO_PATH, JAVA_FILES_CSV)\n\n"
        "print(f'Total Java Files Found: {len(JAVA_FILES)}')\n"
        "print(f'Repository Size (Java files only): {REPO_STATS[\"repository_size_bytes\"]:,} bytes')\n"
        "print(f'Total Directories (excluding filtered paths): {REPO_STATS[\"directory_count\"]:,}')\n"
        "print(f'Saved file list to: {JAVA_FILES_CSV}')"
    ),
    md(
        "## Section 6 — Execute PMD\n\n"
        "Run PMD against the repository using configured rulesets. Execution continues even if individual files fail.\n\n"
        "```bash\n"
        "../../runtimes/pmd-bin-7.0.0/bin/pmd check -d <repo_path> -R category/java/bestpractices.xml,... -f text\n"
        "```"
    ),
    code(
        "if not JAVA_FILES:\n"
        "    logger.error('No Java files discovered; skipping PMD execution.')\n"
        "    PMD_OUTPUTS = {'raw_text': '', 'csv_text': '', 'xml_text': '', 'execution_ok': 'False'}\n"
        "    FILES_SUCCESS = 0\n"
        "    FILES_FAILED = 0\n"
        "else:\n"
        "    PMD_OUTPUTS = run_pmd_suite(\n"
        "        pmd_home=PMD_HOME_PATH,\n"
        "        repo_path=REPO_PATH,\n"
        "        rulesets=RULESETS,\n"
        "        logger=logger,\n"
        "        stream_raw=STREAM_RAW_OUTPUT,\n"
        "    )\n"
        "    FILES_FAILED = count_failed_files(PMD_OUTPUTS['raw_text'], JAVA_FILES)\n"
        "    FILES_SUCCESS = max(len(JAVA_FILES) - FILES_FAILED, 0)\n\n"
        "logger.info(f'PMD execution complete. Files success={FILES_SUCCESS}, failed={FILES_FAILED}')"
    ),
    md("## Section 7 — Raw Output Extraction\n\nPersist complete raw PMD text output, XML output, and CSV output exactly as emitted by the tool."),
    code(
        "RAW_OUTPUT_PATH = OUTPUT_PATH / 'pmd_raw_output.txt'\n"
        "CSV_OUTPUT_PATH = OUTPUT_PATH / 'pmd_output.csv'\n"
        "XML_OUTPUT_PATH = OUTPUT_PATH / 'pmd_output.xml'\n\n"
        "raw_text_output = PMD_OUTPUTS['raw_text']\n"
        "RAW_OUTPUT_PATH.write_text(raw_text_output, encoding='utf-8')\n"
        "CSV_OUTPUT_PATH.write_text(PMD_OUTPUTS['csv_text'], encoding='utf-8')\n"
        "XML_OUTPUT_PATH.write_text(PMD_OUTPUTS['xml_text'], encoding='utf-8')\n\n"
        "PMD_CSV_DF = parse_pmd_csv(PMD_OUTPUTS['csv_text'])\n"
        "ALL_VIOLATIONS_DF = merge_violations(\n"
        "    violations_from_csv(PMD_CSV_DF),\n"
        "    parse_pmd_text_violations(raw_text_output),\n"
        "    parse_pmd_xml_violations(PMD_OUTPUTS['xml_text']),\n"
        ")\n\n"
        "logger.info(f'Saved raw output: {RAW_OUTPUT_PATH}')\n"
        "logger.info(f'Saved CSV output: {CSV_OUTPUT_PATH}')\n"
        "logger.info(f'Saved XML output: {XML_OUTPUT_PATH}')\n"
        "logger.info(f'Total PMD findings: {len(ALL_VIOLATIONS_DF)}')\n\n"
        "preview_raw_output(raw_text_output, RAW_OUTPUT_PREVIEW_LINES, RAW_OUTPUT_PATH)"
    ),
    md(
        "## Section 8 — Code Smell Extraction\n\n"
        "Extract maintainability-related findings including GodClass, DataClass, ExcessiveMethodLength, "
        "CyclomaticComplexity, TooManyFields, TooManyMethods, AvoidDeeplyNestedIfStmts, and CouplingBetweenObjects."
    ),
    code(
        "CODE_SMELLS_DF = extract_code_smells_findings(ALL_VIOLATIONS_DF)\n"
        "CODE_SMELLS_CSV = OUTPUT_PATH / 'code_smells_findings.csv'\n"
        "CODE_SMELLS_DF.to_csv(CODE_SMELLS_CSV, index=False)\n\n"
        "logger.info(f'Saved code smells findings: {CODE_SMELLS_CSV}')\n"
        "logger.info(f'Code smells count: {len(CODE_SMELLS_DF)}')\n\n"
        "if not CODE_SMELLS_DF.empty:\n"
        "    display(CODE_SMELLS_DF.head(15))\n"
        "else:\n"
        "    print('No code smell findings detected.')"
    ),
    md("## Section 9 — Metric Computation\n\n**Code_Smells_Count** = count(all maintainability-related PMD findings)"),
    code(
        "SUMMARY_DF = compute_code_smells_summary(CODE_SMELLS_DF)\n"
        "SUMMARY_CSV = OUTPUT_PATH / 'code_smells_summary.csv'\n"
        "SUMMARY_DF.to_csv(SUMMARY_CSV, index=False)\n\n"
        "logger.info(f'Saved code smells summary: {SUMMARY_CSV}')\n"
        "display(SUMMARY_DF)"
    ),
    md("## Section 10 — Summary Dashboard\n\nOverview of analysis coverage, PMD findings, and code-smell metrics."),
    code(
        "code_smells_count = int(SUMMARY_DF.loc[SUMMARY_DF['metric_name'] == 'Code_Smells_Count', 'metric_value'].iloc[0])\n\n"
        "summary_df = pd.DataFrame([\n"
        "    {'Metric': 'Total Java Files', 'Value': len(JAVA_FILES)},\n"
        "    {'Metric': 'Files Successfully Analyzed', 'Value': FILES_SUCCESS},\n"
        "    {'Metric': 'Files Failed', 'Value': FILES_FAILED},\n"
        "    {'Metric': 'Total PMD Findings', 'Value': len(ALL_VIOLATIONS_DF)},\n"
        "    {'Metric': 'Total Code Smells', 'Value': code_smells_count},\n"
        "])\n\n"
        "display(summary_df)\n\n"
        "deliverables = [\n"
        "    RAW_OUTPUT_PATH, XML_OUTPUT_PATH, CSV_OUTPUT_PATH, JAVA_FILES_CSV,\n"
        "    CODE_SMELLS_CSV, SUMMARY_CSV, ERROR_LOG_PATH,\n"
        "]\n\n"
        "print('\\nDeliverables:')\n"
        "for deliverable in deliverables:\n"
        "    status = 'OK' if deliverable.exists() else 'MISSING'\n"
        "    print(f'  [{status}] {deliverable}')"
    ),
    md("## Section 11 — Error Handling\n\nFailures encountered during cloning, validation, or PMD execution are appended to `outputs/error_log.txt`."),
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
        "├── pmd_raw_output.txt\n"
        "├── pmd_output.xml\n"
        "├── pmd_output.csv\n"
        "├── java_files.csv\n"
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
