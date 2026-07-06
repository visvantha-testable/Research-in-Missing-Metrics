"""Generate pmd_maintainability_rating_extraction.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "pmd_maintainability_rating_extraction.ipynb"

PMD_SETUP = r'''
import io
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.request import urlopen

os.environ.pop("PYTHONPATH", None)


def configure_java_runtime(jdk_home: Path | None = None) -> None:
    if jdk_home is None:
        return
    jdk_home = jdk_home.resolve()
    java_bin = jdk_home / "bin"
    java_exe = java_bin / ("java.exe" if sys.platform.startswith("win") else "java")
    if java_exe.exists():
        os.environ["JAVA_HOME"] = str(jdk_home)
        os.environ["PATH"] = str(java_bin) + os.pathsep + os.environ.get("PATH", "")


def download_pmd_distribution(pmd_version: str, install_root: Path) -> Path:
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
    cache_dir = install_root / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached_zip = cache_dir / zip_path.name

    source_zip = cached_zip if cached_zip.exists() else zip_path
    if not source_zip.exists():
        print(f"Downloading PMD {pmd_version}...")
        with urlopen(url, timeout=120) as response, open(source_zip, "wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
        if source_zip != zip_path:
            shutil.copy2(source_zip, zip_path)

    print(f"Extracting {source_zip.name}...")
    with zipfile.ZipFile(source_zip, "r") as archive:
        archive.extractall(install_root)

    if not (pmd_home / "bin").exists():
        raise RuntimeError(f"PMD extraction failed; expected directory: {pmd_home}")

    print(f"PMD installed at: {pmd_home.resolve()}")
    return pmd_home.resolve()


PROJECT_RUNTIMES = Path("../../runtimes").resolve()
configure_java_runtime(PROJECT_RUNTIMES / "jdk-21")
PMD_HOME = download_pmd_distribution(PMD_VERSION, PROJECT_RUNTIMES)
subprocess.run(["java", "-version"], check=False)
subprocess.run([str(PMD_HOME / "bin" / ("pmd.bat" if sys.platform.startswith("win") else "pmd")), "check", "--help"], check=False)
'''

UTILS = r'''
from __future__ import annotations

import csv
import io
import json
import math
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

EXCLUDED_DIR_NAMES = {
    ".git", "target", "build", "out", "bin", ".gradle", ".mvn", "node_modules", "docs", "generated-sources",
}
RULESET_CATEGORIES = [
    "category/java/design.xml", "category/java/codestyle.xml",
    "category/java/errorprone.xml", "category/java/bestpractices.xml",
]
EXPLICIT_RULES = [
    "CyclomaticComplexity", "NPathComplexity", "ExcessiveMethodLength",
    "ExcessiveClassLength", "ExcessiveParameterList", "GodClass",
]
MAINTAINABILITY_RULES = {
    "CyclomaticComplexity", "NPathComplexity", "ExcessiveMethodLength", "ExcessiveClassLength",
    "ExcessiveParameterList", "GodClass", "TooManyFields", "TooManyMethods", "AvoidDeeplyNestedIfStmts",
    "CouplingBetweenObjects", "DataClass", "LongMethod", "ExcessivePublicCount",
    "AvoidDuplicateLiterals", "DuplicateImports",
}
FINDINGS_COLUMNS = ["file", "rule", "priority", "description", "line", "ruleset"]
PMD_SUCCESS_CODES = {0, 4}
CCN_PATTERN = re.compile(r"cyclomatic complexity of (\d+)", re.IGNORECASE)
TEXT_PATTERN = re.compile(r"^(?P<file>.+):(?P<line>\d+):\s*(?P<rule>[^:]+):\s*(?P<message>.*)$")


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


def discover_java_files(repo_path: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo_path.rglob("*.java"):
        if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            continue
        files.append(path.resolve())
    return sorted(files)


def compute_repository_stats(repo_path: Path, java_files: list[Path]) -> dict[str, Any]:
    total_size = sum(path.stat().st_size for path in java_files)
    directories = {path.parent for path in java_files}
    return {
        "repository_name": repo_path.name,
        "repository_size_bytes": total_size,
        "directory_count": len(directories),
        "java_file_count": len(java_files),
    }


def save_java_inventory(java_files: list[Path], output_csv: Path) -> None:
    pd.DataFrame(
        [{"file_path": str(p), "file_name": p.name, "directory": str(p.parent)} for p in java_files]
    ).to_csv(output_csv, index=False)


def write_custom_ruleset(ruleset_path: Path) -> Path:
    explicit_note = ", ".join(EXPLICIT_RULES)
    lines = [
        '<?xml version="1.0"?>',
        '<ruleset name="custom_ruleset"',
        '    xmlns="http://pmd.sourceforge.net/ruleset/2.0.0"',
        '    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        '    xsi:schemaLocation="http://pmd.sourceforge.net/ruleset/2.0.0 https://pmd.sourceforge.io/ruleset_2_0_0.xsd">',
        "    <description>Custom SQALE maintainability ruleset for Java repositories</description>",
        f"    <!-- Explicit rules covered via design.xml: {explicit_note} -->",
    ]
    for category in RULESET_CATEGORIES:
        lines.append(f'    <rule ref="{category}"/>')
    lines.append("</ruleset>")
    ruleset_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ruleset_path


def pmd_executable(pmd_home: Path) -> Path:
    return pmd_home / "bin" / ("pmd.bat" if sys.platform.startswith("win") else "pmd")


def run_pmd_command(pmd_home: Path, repo_path: Path, ruleset_path: Path, fmt: str, logger: NotebookLogger) -> tuple[str, str, int]:
    cmd = [
        str(pmd_executable(pmd_home)), "check", "-d", str(repo_path), "-R", str(ruleset_path),
        "-f", fmt, "--no-cache", "--no-progress",
    ]
    completed = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    return completed.stdout, completed.stderr, completed.returncode


def combine_raw_streams(stdout: str, stderr: str) -> str:
    raw = stdout
    if stderr:
        if raw and not raw.endswith("\n"):
            raw += "\n"
        raw += stderr
    return raw


def normalize_pmd_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    renamed = frame.copy()
    renamed.columns = [str(col).strip().lower().replace(" ", "_") for col in renamed.columns]
    return renamed


def parse_pmd_csv(csv_text: str) -> pd.DataFrame:
    if not csv_text.strip():
        return pd.DataFrame()
    return pd.read_csv(io.StringIO(csv_text.strip()))


def violations_from_csv(csv_df: pd.DataFrame) -> pd.DataFrame:
    if csv_df.empty:
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    frame = normalize_pmd_columns(csv_df)
    rows = []
    for _, record in frame.iterrows():
        line_value = record.get("line", record.get("beginline", record.get("begin_line", "")))
        rows.append({
            "file": str(record.get("file", record.get("filename", ""))),
            "rule": str(record.get("rule", "")),
            "priority": record.get("priority", ""),
            "description": str(record.get("description", record.get("message", ""))),
            "line": line_value,
            "ruleset": str(record.get("rule_set", record.get("ruleset", ""))),
        })
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def parse_pmd_json(json_text: str) -> pd.DataFrame:
    if not json_text.strip():
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError:
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    rows = []
    for file_entry in payload.get("files", []):
        file_name = file_entry.get("filename", "")
        for violation in file_entry.get("violations", []):
            rows.append({
                "file": file_name, "rule": violation.get("rule", ""),
                "priority": violation.get("priority", ""), "description": violation.get("description", ""),
                "line": violation.get("beginline", violation.get("beginLine", "")),
                "ruleset": violation.get("ruleset", ""),
            })
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def parse_pmd_text_violations(raw_text: str) -> pd.DataFrame:
    rows = []
    for line in raw_text.splitlines():
        match = TEXT_PATTERN.match(line.strip())
        if not match:
            continue
        rows.append({
            "file": match.group("file").strip(), "rule": match.group("rule").strip(),
            "priority": "", "description": match.group("message").strip(),
            "line": int(match.group("line")), "ruleset": "",
        })
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def merge_violations(*frames: pd.DataFrame) -> pd.DataFrame:
    valid = [frame for frame in frames if frame is not None and not frame.empty]
    if not valid:
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    combined = pd.concat(valid, ignore_index=True)
    return combined.drop_duplicates(subset=["file", "line", "rule", "description"], keep="first")


def is_maintainability_finding(rule: str) -> bool:
    return rule in MAINTAINABILITY_RULES


def extract_maintainability_findings(violations: pd.DataFrame) -> pd.DataFrame:
    if violations.empty:
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    return violations[violations["rule"].map(is_maintainability_finding)].reset_index(drop=True)


def extract_cyclomatic_complexity_values(violations: pd.DataFrame) -> list[float]:
    values = []
    for description in violations[violations["rule"] == "CyclomaticComplexity"]["description"].astype(str):
        match = CCN_PATTERN.search(description)
        if match:
            values.append(float(match.group(1)))
    return values


def count_loc(java_files: list[Path]) -> int:
    total = 0
    for path in java_files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                continue
            total += 1
    return total


def compute_maintainability_index(avg_ccn: float, loc: int, halstead_volume: float | None) -> str | float:
    if halstead_volume is None or halstead_volume <= 0:
        return "Not Computed"
    volume = max(float(halstead_volume), 1.0)
    lines = max(int(loc), 1)
    return round(171 - 5.2 * math.log(volume) - 0.23 * avg_ccn - 16.2 * math.log(lines), 4)


def mi_to_sqale_rating(mi: str | float) -> str:
    if isinstance(mi, str):
        return "Not Computed"
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
        "# PMD Maintainability Rating (SQALE A–E) — Raw Output Extraction (Java)\n\n"
        "This notebook analyzes **Java repositories** with **PMD** and captures complete raw tool output "
        "for Code Smells Count, Cyclomatic Complexity, NPath Complexity, Excessive Method/Class Length, "
        "God Class indicators, Maintainability Index, and Maintainability Rating (A–E).\n\n"
        "**Default benchmark repository:** [spring-projects/spring-petclinic](https://github.com/spring-projects/spring-petclinic)"
    ),
    md(
        "## Section 1 — Install Dependencies\n\n"
        "Install Python packages, configure Java, and download PMD."
    ),
    code(
        "!pip install -q pandas gitpython jupyter\n\n"
        "PMD_VERSION = '7.0.0'\n\n"
        + PMD_SETUP.strip()
    ),
    md("## Section 2 — Configuration\n\nSet repository source, workspace, output directory, and optional Halstead Volume."),
    code(
        "USE_GIT_URL = True\n\n"
        "REPO_URL = 'https://github.com/spring-projects/spring-petclinic.git'\n\n"
        "LOCAL_REPO_PATH = '/content/spring-petclinic'\n\n"
        "WORKSPACE_DIR = './workspace'\n\n"
        "OUTPUT_DIR = './outputs'\n\n"
        "IF_CLONE_EXISTS = 'reuse'\n\n"
        "CLONE_DEPTH = 1\n\n"
        "RAW_OUTPUT_PREVIEW_LINES = 150\n\n"
        "# User-supplied Halstead Volume for MI formula. None => Maintainability_Index = Not Computed\n"
        "HALSTEAD_VOLUME = None\n\n"
        "# Fast validation benchmark:\n"
        "# USE_GIT_URL = False\n"
        "# LOCAL_REPO_PATH = './workspace/sqale_rating_benchmark'\n"
        "# HALSTEAD_VOLUME = 5000.0"
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
        "JAVA_FILES = discover_java_files(REPO_PATH)\n"
        "if not JAVA_FILES:\n"
        "    logger.error('No Java source files found in repository.', file=str(REPO_PATH))\n"
        "    raise FileNotFoundError('No Java source files found.')\n\n"
        "REPO_STATS = compute_repository_stats(REPO_PATH, JAVA_FILES)\n"
        "logger.info(f'Repository ready at: {REPO_PATH}')\n"
        "print(f\"Repository: {REPO_STATS['repository_name']}\")\n"
        "print(f\"Size (Java files): {REPO_STATS['repository_size_bytes']:,} bytes\")\n"
        "print(f\"Directories: {REPO_STATS['directory_count']:,}\")\n"
        "print(f\"Java files: {REPO_STATS['java_file_count']:,}\")"
    ),
    md("## Section 5 — Discover Java Files"),
    code(
        "INVENTORY_CSV = OUTPUT_PATH / 'java_files_inventory.csv'\n"
        "save_java_inventory(JAVA_FILES, INVENTORY_CSV)\n\n"
        "print(f'Total Java Files Found: {len(JAVA_FILES)}')\n"
        "print(f'Saved inventory to: {INVENTORY_CSV}')"
    ),
    md("## Section 6 — Create PMD Ruleset\n\nGenerate `custom_ruleset.xml` with design, codestyle, errorprone, and bestpractices categories."),
    code(
        "RULESET_PATH = write_custom_ruleset(OUTPUT_PATH / 'custom_ruleset.xml')\n"
        "logger.info(f'Generated PMD ruleset: {RULESET_PATH}')\n"
        "print(RULESET_PATH.read_text(encoding='utf-8')[:800])"
    ),
    md("## Section 7 — Execute PMD\n\nRun PMD in text, CSV, and JSON formats. Preserve stdout/stderr exactly as emitted."),
    code(
        "PMD_CONSOLE_CHUNKS: list[str] = []\n"
        "PMD_RAW: dict[str, str] = {}\n\n"
        "for label, fmt in [('text', 'text'), ('csv', 'csv'), ('json', 'json')]:\n"
        "    stdout, stderr, code = run_pmd_command(PMD_HOME, REPO_PATH, RULESET_PATH, fmt, logger)\n"
        "    PMD_CONSOLE_CHUNKS.append(f'===== pmd check ({label}) =====\\n' + combine_raw_streams(stdout, stderr))\n"
        "    PMD_RAW[label] = stdout\n"
        "    if code not in PMD_SUCCESS_CODES and not stdout.strip():\n"
        "        logger.error(f'PMD {label} run exited with code {code}', file=label)\n\n"
        "logger.info('PMD execution complete.')"
    ),
    md("## Section 8 — Raw Output Extraction"),
    code(
        "CONSOLE_PATH = OUTPUT_PATH / 'pmd_raw_console_output.txt'\n"
        "CSV_PATH = OUTPUT_PATH / 'pmd_output.csv'\n"
        "JSON_PATH = OUTPUT_PATH / 'pmd_output.json'\n\n"
        "CONSOLE_PATH.write_text('\\n'.join(PMD_CONSOLE_CHUNKS), encoding='utf-8')\n"
        "CSV_PATH.write_text(PMD_RAW.get('csv', ''), encoding='utf-8')\n"
        "JSON_PATH.write_text(PMD_RAW.get('json', ''), encoding='utf-8')\n\n"
        "logger.info('Saved PMD raw console, CSV, and JSON outputs.')\n"
        "preview_raw_output(CONSOLE_PATH.read_text(encoding='utf-8'), RAW_OUTPUT_PREVIEW_LINES, CONSOLE_PATH)"
    ),
    md("## Section 9 — Parse Findings"),
    code(
        "VIOLATIONS_DF = merge_violations(\n"
        "    violations_from_csv(parse_pmd_csv(PMD_RAW.get('csv', ''))),\n"
        "    parse_pmd_json(PMD_RAW.get('json', '')),\n"
        "    parse_pmd_text_violations(PMD_RAW.get('text', '')),\n"
        ")\n"
        "FINDINGS_CSV = OUTPUT_PATH / 'pmd_findings.csv'\n"
        "VIOLATIONS_DF.to_csv(FINDINGS_CSV, index=False)\n\n"
        "logger.info(f'Parsed {len(VIOLATIONS_DF)} total PMD findings')"
    ),
    md("## Section 10 — Metric Computation"),
    code(
        "MAINTAINABILITY_DF = extract_maintainability_findings(VIOLATIONS_DF)\n"
        "code_smells_count = len(MAINTAINABILITY_DF)\n\n"
        "CODE_SMELLS_CSV = OUTPUT_PATH / 'code_smells_summary.csv'\n"
        "pd.DataFrame([{'metric_name': 'Code_Smells_Count', 'metric_value': code_smells_count}]).to_csv(CODE_SMELLS_CSV, index=False)\n\n"
        "ccn_values = extract_cyclomatic_complexity_values(VIOLATIONS_DF)\n"
        "avg_ccn = round(sum(ccn_values) / len(ccn_values), 4) if ccn_values else 0.0\n"
        "total_loc = count_loc(JAVA_FILES)\n"
        "mi_value = compute_maintainability_index(avg_ccn, total_loc, HALSTEAD_VOLUME)\n"
        "rating = mi_to_sqale_rating(mi_value)\n\n"
        "rating_rows = [{'metric_name': 'Maintainability_Rating', 'metric_value': rating}]\n"
        "if isinstance(mi_value, (int, float)):\n"
        "    rating_rows.insert(0, {'metric_name': 'Maintainability_Index', 'metric_value': mi_value})\n"
        "RATING_SUMMARY_DF = pd.DataFrame(rating_rows)\n"
        "RATING_SUMMARY_CSV = OUTPUT_PATH / 'maintainability_rating_summary.csv'\n"
        "RATING_SUMMARY_DF.to_csv(RATING_SUMMARY_CSV, index=False)\n\n"
        "logger.info(f'Code Smells={code_smells_count}, MI={mi_value}, Rating={rating}')\n"
        "display(RATING_SUMMARY_DF)"
    ),
    md("## Section 11 — Summary Dashboard"),
    code(
        "summary_df = pd.DataFrame([\n"
        "    {'Metric': 'Total Java Files', 'Value': len(JAVA_FILES)},\n"
        "    {'Metric': 'Total PMD Findings', 'Value': len(VIOLATIONS_DF)},\n"
        "    {'Metric': 'Code Smells Count', 'Value': code_smells_count},\n"
        "    {'Metric': 'Average Cyclomatic Complexity', 'Value': avg_ccn},\n"
        "    {'Metric': 'Maintainability Index', 'Value': mi_value},\n"
        "    {'Metric': 'Maintainability Rating', 'Value': rating},\n"
        "])\n"
        "display(summary_df)\n\n"
        "deliverables = [\n"
        "    CONSOLE_PATH, JSON_PATH, CSV_PATH, FINDINGS_CSV, CODE_SMELLS_CSV,\n"
        "    RATING_SUMMARY_CSV, INVENTORY_CSV, ERROR_LOG_PATH,\n"
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
        "├── pmd_raw_console_output.txt\n"
        "├── pmd_output.json\n"
        "├── pmd_output.csv\n"
        "├── pmd_findings.csv\n"
        "├── code_smells_summary.csv\n"
        "├── maintainability_rating_summary.csv\n"
        "├── java_files_inventory.csv\n"
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
