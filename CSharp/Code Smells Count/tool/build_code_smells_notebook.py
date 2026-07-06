"""Generate stylecop_code_smells_extraction.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "stylecop_code_smells_extraction.ipynb"

DOTNET_SETUP = r'''
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

os.environ.pop("PYTHONPATH", None)

DOTNET_CHANNEL = "8.0"
RUNTIMES_ROOT = Path("../../runtimes").resolve()
DOTNET_ROOT = (RUNTIMES_ROOT / "dotnet-sdk").resolve()


def dotnet_executable(dotnet_root: Path) -> Path:
    return dotnet_root / ("dotnet.exe" if sys.platform.startswith("win") else "dotnet")


def download_dotnet_sdk(install_dir: Path, channel: str = DOTNET_CHANNEL) -> Path:
    install_dir = install_dir.resolve()
    install_dir.mkdir(parents=True, exist_ok=True)
    dotnet = dotnet_executable(install_dir)
    if dotnet.exists():
        print(f".NET SDK already installed at: {install_dir}")
        return install_dir

    if sys.platform.startswith("win"):
        script_path = install_dir / "dotnet-install.ps1"
        urllib.request.urlretrieve("https://dot.net/v1/dotnet-install.ps1", script_path)
        subprocess.run([
            "powershell", "-ExecutionPolicy", "Bypass", "-File", str(script_path),
            "-InstallDir", str(install_dir), "-Channel", channel, "-Architecture", "x64", "-Quality", "ga",
        ], check=True)
    else:
        script_path = install_dir / "dotnet-install.sh"
        urllib.request.urlretrieve("https://dot.net/v1/dotnet-install.sh", script_path)
        script_path.chmod(0o755)
        subprocess.run([str(script_path), "--install-dir", str(install_dir), "--channel", channel, "--quality", "ga"], check=True)

    if not dotnet.exists():
        raise RuntimeError(f".NET SDK installation failed; expected executable at {dotnet}")
    print(f".NET SDK installed at: {install_dir}")
    return install_dir


DOTNET_ROOT = download_dotnet_sdk(DOTNET_ROOT)
subprocess.run([str(dotnet_executable(DOTNET_ROOT)), "--version"], check=False)
'''

UTILS = r'''
from __future__ import annotations

import json
import os
import re
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

EXCLUDED_DIR_NAMES = {".git", "bin", "obj", "packages", "artifacts", "TestResults", "node_modules"}
STYLECOP_PACKAGE = "StyleCop.Analyzers"
STYLECOP_VERSION = "1.2.0-beta.556"
EXPLICIT_CODE_SMELL_RULES = {
    "SA1401", "SA1500", "SA1513", "SA1515", "SA1600", "SA1601", "SA1101", "SA1124", "SA1127",
}
BUILD_DIAGNOSTIC_PATTERN = re.compile(
    r"^(?P<file>.+?)\((?P<line>\d+),(?P<column>\d+)\):\s*(?P<severity>\w+)\s+(?P<rule_id>SA\d+):\s*(?P<message>.*)$"
)
RESULTS_COLUMNS = ["project", "file", "line", "column", "severity", "rule_id", "message", "category"]
SMELLS_COLUMNS = ["project", "file", "line", "rule_id", "severity", "message", "category"]
BUILD_SUCCESS_CODES = {0, 1}


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


def dotnet_executable(dotnet_root: Path) -> Path:
    return dotnet_root / ("dotnet.exe" if sys.platform.startswith("win") else "dotnet")


def dotnet_env(dotnet_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["DOTNET_ROOT"] = str(dotnet_root)
    env["PATH"] = str(dotnet_root) + os.pathsep + env.get("PATH", "")
    env.pop("PYTHONPATH", None)
    return env


def run_command(command: list[str], env: dict[str, str], stream_raw: bool = False) -> tuple[str, str, int]:
    if stream_raw:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", env=env,
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
        command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, env=env,
    )
    return completed.stdout, completed.stderr, completed.returncode


def combine_raw_streams(stdout: str, stderr: str) -> str:
    raw = stdout
    if stderr:
        if raw and not raw.endswith("\n"):
            raw += "\n"
        raw += stderr
    return raw


def should_exclude_path(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def discover_csharp_files(repo_path: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo_path.rglob("*.cs"):
        if should_exclude_path(path.relative_to(repo_path)):
            continue
        files.append(path.resolve())
    return sorted(files)


def discover_solutions_and_projects(repo_path: Path) -> tuple[list[Path], list[Path]]:
    solutions: list[Path] = []
    projects: list[Path] = []
    for path in repo_path.rglob("*"):
        if not path.is_file() or should_exclude_path(path.relative_to(repo_path)):
            continue
        if path.suffix.lower() == ".sln":
            solutions.append(path.resolve())
        elif path.suffix.lower() == ".csproj":
            projects.append(path.resolve())
    return sorted(solutions), sorted(projects)


def compute_repository_stats(repo_path: Path, csharp_files: list[Path]) -> dict[str, int]:
    total_size = sum(path.stat().st_size for path in csharp_files)
    directories = {path.parent for path in csharp_files}
    return {"repository_size_bytes": total_size, "directory_count": len(directories)}


def save_csharp_file_list(csharp_files: list[Path], repo_path: Path, output_csv: Path) -> None:
    pd.DataFrame(
        [{"absolute_path": str(path), "relative_path": str(path.relative_to(repo_path))} for path in csharp_files]
    ).to_csv(output_csv, index=False)


def build_inventory(repo_path: Path, solutions: list[Path], projects: list[Path]) -> pd.DataFrame:
    rows = []
    for solution in solutions:
        rows.append({"kind": "solution", "absolute_path": str(solution), "relative_path": str(solution.relative_to(repo_path))})
    for project in projects:
        rows.append({"kind": "project", "absolute_path": str(project), "relative_path": str(project.relative_to(repo_path))})
    return pd.DataFrame(rows, columns=["kind", "absolute_path", "relative_path"])


def resolve_analysis_targets(solutions: list[Path], projects: list[Path]) -> list[Path]:
    return solutions if solutions else projects


def has_stylecop_package(project_path: Path) -> bool:
    return STYLECOP_PACKAGE in project_path.read_text(encoding="utf-8", errors="replace")


def inject_stylecop(project_path: Path, dotnet_root: Path, env: dict[str, str], logger: NotebookLogger) -> bool:
    if has_stylecop_package(project_path):
        logger.info(f"StyleCop already installed in {project_path.name}")
        return True
    command = [str(dotnet_executable(dotnet_root)), "add", str(project_path), "package", STYLECOP_PACKAGE, "--version", STYLECOP_VERSION]
    stdout, stderr, code = run_command(command, env)
    if code != 0:
        logger.error(f"Failed to add StyleCop to {project_path}: {combine_raw_streams(stdout, stderr).strip()}")
        return False
    logger.info(f"Added StyleCop.Analyzers to {project_path.name}")
    return True


def collect_projects_from_solution(solution_path: Path) -> list[Path]:
    projects: list[Path] = []
    content = solution_path.read_text(encoding="utf-8", errors="replace")
    for match in re.finditer(r'Project\("[^"]+"\)\s*=\s*"[^"]+",\s*"([^"]+\.csproj)"', content):
        project_path = (solution_path.parent / match.group(1).replace("\\", os.sep)).resolve()
        if project_path.exists():
            projects.append(project_path)
    return projects


def collect_projects_for_targets(targets: list[Path]) -> list[Path]:
    projects: list[Path] = []
    seen: set[str] = set()
    for target in targets:
        if target.suffix.lower() == ".csproj":
            key = str(target)
            if key not in seen:
                projects.append(target)
                seen.add(key)
            continue
        for project in collect_projects_from_solution(target):
            key = str(project)
            if key not in seen:
                projects.append(project)
                seen.add(key)
    return projects


def build_target(target: Path, dotnet_root: Path, env: dict[str, str], sarif_path: Path, logger: NotebookLogger, stream_raw: bool = False) -> tuple[bool, str]:
    restore_cmd = [str(dotnet_executable(dotnet_root)), "restore", str(target)]
    restore_stdout, restore_stderr, restore_code = run_command(restore_cmd, env, stream_raw=stream_raw)
    restore_raw = combine_raw_streams(restore_stdout, restore_stderr)
    if restore_code != 0:
        logger.error(f"dotnet restore failed for {target}")
        return False, restore_raw

    clean_cmd = [str(dotnet_executable(dotnet_root)), "clean", str(target)]
    clean_stdout, clean_stderr, _ = run_command(clean_cmd, env, stream_raw=False)

    sarif_path.parent.mkdir(parents=True, exist_ok=True)
    build_cmd = [
        str(dotnet_executable(dotnet_root)), "build", str(target), "--no-incremental",
        "-p:RunAnalyzers=true", f"-p:ErrorLog={sarif_path}", "--no-restore",
    ]
    build_stdout, build_stderr, build_code = run_command(build_cmd, env, stream_raw=stream_raw)
    build_raw = combine_raw_streams(clean_stdout + clean_stderr, combine_raw_streams(build_stdout, build_stderr))
    if build_code not in BUILD_SUCCESS_CODES:
        logger.error(f"dotnet build failed for {target} (continuing)")
    return build_code in BUILD_SUCCESS_CODES, restore_raw + build_raw


def parse_build_diagnostics(raw_text: str, project: str) -> list[dict[str, Any]]:
    rows = []
    for line in raw_text.splitlines():
        match = BUILD_DIAGNOSTIC_PATTERN.match(line.strip())
        if not match:
            continue
        rows.append({
            "project": project,
            "file": match.group("file").strip(),
            "line": int(match.group("line")),
            "column": int(match.group("column")),
            "severity": match.group("severity").lower(),
            "rule_id": match.group("rule_id"),
            "message": match.group("message").strip(),
            "category": "StyleCop",
        })
    return rows


def parse_sarif(sarif_path: Path, project: str) -> list[dict[str, Any]]:
    if not sarif_path.exists() or sarif_path.stat().st_size == 0:
        return []
    try:
        payload = json.loads(sarif_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    rows = []
    for run in payload.get("runs", []):
        for result in run.get("results", []):
            rule_id = str(result.get("ruleId", ""))
            if not rule_id.startswith("SA"):
                continue
            message = result.get("message", {})
            text = message.get("text", "") if isinstance(message, dict) else str(message)
            for location in result.get("locations", []):
                physical = location.get("physicalLocation", {})
                artifact = physical.get("artifactLocation", {})
                region = physical.get("region", {})
                file_uri = artifact.get("uri", "")
                if not file_uri:
                    continue
                rows.append({
                    "project": project,
                    "file": file_uri,
                    "line": region.get("startLine", ""),
                    "column": region.get("startColumn", ""),
                    "severity": str(result.get("level", "warning")).lower(),
                    "rule_id": rule_id,
                    "message": text,
                    "category": "StyleCop",
                })
    return rows


def merge_findings(*groups: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for group in groups:
        for item in group:
            file_value = str(item.get("file", "")).strip()
            if not file_value:
                continue
            key = (str(item.get("project", "")), file_value, str(item.get("line", "")), str(item.get("rule_id", "")), str(item.get("message", "")))
            if key in seen:
                continue
            seen.add(key)
            rows.append(item)
    return pd.DataFrame(rows, columns=RESULTS_COLUMNS)


def is_code_smell(rule_id: str) -> bool:
    return rule_id in EXPLICIT_CODE_SMELL_RULES or bool(re.fullmatch(r"SA\d{4}", rule_id))


def extract_code_smells_findings(findings: pd.DataFrame) -> pd.DataFrame:
    if findings.empty:
        return pd.DataFrame(columns=SMELLS_COLUMNS)
    return findings[findings["rule_id"].map(is_code_smell)][SMELLS_COLUMNS].reset_index(drop=True)


def compute_code_smells_summary(findings_df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame([{"metric_name": "Code_Smells_Count", "metric_value": len(findings_df)}])


def preview_raw_output(raw_text: str, preview_lines: int, output_path: Path) -> None:
    lines = raw_text.splitlines()
    print(f"\n{'=' * 80}")
    print(f"RAW STYLECOP OUTPUT PREVIEW (first {preview_lines} lines)")
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
        "# StyleCop Analyzers — Code Smells Count Raw Output Extraction (C#)\n\n"
        "This notebook analyzes **C# repositories** with **StyleCop Analyzers** and captures the complete raw tool output "
        "for maintainability code-smells metric derivation and validation.\n\n"
        "**Default benchmark repository:** [dotnet/aspnetcore](https://github.com/dotnet/aspnetcore)\n\n"
        "Supports Git URL cloning and local repository analysis. All deliverables are written to `OUTPUT_DIR`."
    ),
    md("## Section 1 — Install Dependencies\n\nInstall Python packages and bootstrap the open-source .NET SDK."),
    code("!pip install -q pandas gitpython jupyter"),
    code(DOTNET_SETUP.strip()),
    md(
        "## Section 2 — Configuration\n\n"
        "Set execution mode, repository source, and output location.\n\n"
        "- `USE_GIT_URL = True` clones from `REPO_URL`.\n"
        "- `USE_GIT_URL = False` analyzes `LOCAL_REPO_PATH` directly."
    ),
    code(
        "USE_GIT_URL = True\n\n"
        "REPO_URL = 'https://github.com/dotnet/aspnetcore.git'\n\n"
        "LOCAL_REPO_PATH = '/content/aspnetcore'\n\n"
        "OUTPUT_DIR = './outputs'\n\n"
        "DOTNET_ROOT = Path('../../runtimes/dotnet-sdk').resolve()\n\n"
        "IF_CLONE_EXISTS = 'reuse'\n\n"
        "CLONE_DEPTH = 1\n\n"
        "WORKSPACE_DIR = './workspace'\n\n"
        "STREAM_RAW_OUTPUT = True\n\n"
        "RAW_OUTPUT_PREVIEW_LINES = 150\n\n"
        "# Fast validation benchmark:\n"
        "# USE_GIT_URL = False\n"
        "# LOCAL_REPO_PATH = './workspace/cs_code_smells_benchmark'"
    ),
    md("## Section 3 — Imports and Utility Functions\n\nModular helpers for repository setup, project discovery, StyleCop injection, and analysis."),
    code("from pathlib import Path\n\n" + UTILS.strip()),
    md("## Section 4 — Repository Setup\n\nResolve the repository path and initialize output directories."),
    code(
        "OUTPUT_PATH = Path(OUTPUT_DIR).resolve()\n"
        "WORKSPACE_PATH = Path(WORKSPACE_DIR).resolve()\n"
        "ERROR_LOG_PATH = OUTPUT_PATH / 'error_log.txt'\n\n"
        "ensure_output_dir(OUTPUT_PATH)\n"
        "logger = NotebookLogger(ERROR_LOG_PATH)\n"
        "ENV = dotnet_env(DOTNET_ROOT)\n\n"
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
    md("## Section 5 — Discover C# Files\n\nRecursively discover `.cs` files while excluding build artifacts."),
    code(
        "CSHARP_FILES = discover_csharp_files(REPO_PATH)\n"
        "REPO_STATS = compute_repository_stats(REPO_PATH, CSHARP_FILES)\n\n"
        "CSHARP_FILES_CSV = OUTPUT_PATH / 'csharp_files.csv'\n"
        "save_csharp_file_list(CSHARP_FILES, REPO_PATH, CSHARP_FILES_CSV)\n\n"
        "print(f'Total C# Files Found: {len(CSHARP_FILES)}')\n"
        "print(f'Repository Size (C# files only): {REPO_STATS[\"repository_size_bytes\"]:,} bytes')\n"
        "print(f'Total Directories: {REPO_STATS[\"directory_count\"]:,}')\n"
        "print(f'Saved file list to: {CSHARP_FILES_CSV}')"
    ),
    md("## Section 6 — Discover Solutions and Projects\n\nDiscover `.sln` and `.csproj` files for analysis."),
    code(
        "SOLUTIONS, PROJECTS = discover_solutions_and_projects(REPO_PATH)\n"
        "INVENTORY_DF = build_inventory(REPO_PATH, SOLUTIONS, PROJECTS)\n"
        "INVENTORY_CSV = OUTPUT_PATH / 'solution_project_inventory.csv'\n"
        "INVENTORY_DF.to_csv(INVENTORY_CSV, index=False)\n\n"
        "ANALYSIS_TARGETS = resolve_analysis_targets(SOLUTIONS, PROJECTS)\n"
        "PROJECT_PATHS = collect_projects_for_targets(ANALYSIS_TARGETS)\n\n"
        "print(f'Solutions found: {len(SOLUTIONS)}')\n"
        "print(f'Projects found: {len(PROJECTS)}')\n"
        "print(f'Analysis targets: {len(ANALYSIS_TARGETS)}')\n"
        "print(f'Saved inventory to: {INVENTORY_CSV}')"
    ),
    md("## Section 7 — Inject StyleCop Analyzers\n\nAdd `StyleCop.Analyzers` to each discovered project when missing."),
    code(
        "INJECTION_FAILURES = 0\n"
        "for project_path in PROJECT_PATHS:\n"
        "    if not inject_stylecop(project_path, DOTNET_ROOT, ENV, logger):\n"
        "        INJECTION_FAILURES += 1\n\n"
        "logger.info(f'StyleCop injection complete. Failures={INJECTION_FAILURES}')"
    ),
    md(
        "## Section 8 — Execute Analysis\n\n"
        "Run `dotnet build` with analyzers enabled and SARIF logging.\n\n"
        "```bash\n"
        "dotnet build -p:RunAnalyzers=true -p:ErrorLog=stylecop.sarif\n"
        "```"
    ),
    code(
        "RAW_CHUNKS: list[str] = []\n"
        "BUILD_FINDINGS: list[dict] = []\n"
        "SARIF_FINDINGS: list[dict] = []\n"
        "PROJECTS_SUCCESS = 0\n"
        "PROJECTS_FAILED = 0\n"
        "SARIF_PATHS: list[Path] = []\n\n"
        "if not ANALYSIS_TARGETS:\n"
        "    logger.error('No solution or project files discovered; skipping analysis.')\n"
        "else:\n"
        "    for target in ANALYSIS_TARGETS:\n"
        "        sarif_path = OUTPUT_PATH / f'{target.stem}.sarif'\n"
        "        build_ok, build_raw = build_target(\n"
        "            target, DOTNET_ROOT, ENV, sarif_path, logger, stream_raw=STREAM_RAW_OUTPUT\n"
        "        )\n"
        "        RAW_CHUNKS.append(build_raw)\n"
        "        BUILD_FINDINGS.extend(parse_build_diagnostics(build_raw, str(target)))\n"
        "        SARIF_FINDINGS.extend(parse_sarif(sarif_path, str(target)))\n"
        "        if sarif_path.exists():\n"
        "            SARIF_PATHS.append(sarif_path)\n"
        "        if build_ok:\n"
        "            PROJECTS_SUCCESS += 1\n"
        "        else:\n"
        "            PROJECTS_FAILED += 1\n\n"
        "logger.info(f'Analysis complete. Projects success={PROJECTS_SUCCESS}, failed={PROJECTS_FAILED}')"
    ),
    md("## Section 9 — Raw Output Extraction\n\nPersist raw build output, SARIF report, and CSV findings."),
    code(
        "RAW_OUTPUT_PATH = OUTPUT_PATH / 'stylecop_raw_output.txt'\n"
        "SARIF_OUTPUT_PATH = OUTPUT_PATH / 'stylecop_output.sarif'\n"
        "RESULTS_CSV_PATH = OUTPUT_PATH / 'stylecop_results.csv'\n\n"
        "RAW_TEXT = ''.join(chunk if chunk.endswith('\\n') else chunk + '\\n' for chunk in RAW_CHUNKS if chunk)\n"
        "RAW_OUTPUT_PATH.write_text(RAW_TEXT, encoding='utf-8')\n\n"
        "if SARIF_PATHS:\n"
        "    shutil.copy2(SARIF_PATHS[0], SARIF_OUTPUT_PATH)\n"
        "else:\n"
        "    SARIF_OUTPUT_PATH.write_text('{\"version\": \"2.1.0\", \"runs\": []}', encoding='utf-8')\n\n"
        "ALL_FINDINGS_DF = merge_findings(BUILD_FINDINGS, SARIF_FINDINGS)\n"
        "ALL_FINDINGS_DF.to_csv(RESULTS_CSV_PATH, index=False)\n\n"
        "logger.info(f'Saved raw output: {RAW_OUTPUT_PATH}')\n"
        "logger.info(f'Saved SARIF output: {SARIF_OUTPUT_PATH}')\n"
        "logger.info(f'Saved CSV results: {RESULTS_CSV_PATH}')\n"
        "logger.info(f'Total StyleCop findings: {len(ALL_FINDINGS_DF)}')\n\n"
        "preview_raw_output(RAW_TEXT, RAW_OUTPUT_PREVIEW_LINES, RAW_OUTPUT_PATH)"
    ),
    md("## Section 10 — Code Smell Extraction\n\nExtract maintainability-related StyleCop diagnostics (SA#### rules)."),
    code(
        "CODE_SMELLS_DF = extract_code_smells_findings(ALL_FINDINGS_DF)\n"
        "CODE_SMELLS_CSV = OUTPUT_PATH / 'code_smells_findings.csv'\n"
        "CODE_SMELLS_DF.to_csv(CODE_SMELLS_CSV, index=False)\n\n"
        "logger.info(f'Saved code smells findings: {CODE_SMELLS_CSV}')\n"
        "logger.info(f'Code smells count: {len(CODE_SMELLS_DF)}')\n\n"
        "if not CODE_SMELLS_DF.empty:\n"
        "    display(CODE_SMELLS_DF.head(15))\n"
        "else:\n"
        "    print('No code smell findings detected.')"
    ),
    md("## Section 11 — Metric Computation\n\n**Code_Smells_Count** = count(all maintainability-related StyleCop findings)"),
    code(
        "SUMMARY_DF = compute_code_smells_summary(CODE_SMELLS_DF)\n"
        "SUMMARY_CSV = OUTPUT_PATH / 'code_smells_summary.csv'\n"
        "SUMMARY_DF.to_csv(SUMMARY_CSV, index=False)\n\n"
        "logger.info(f'Saved code smells summary: {SUMMARY_CSV}')\n"
        "display(SUMMARY_DF)"
    ),
    md("## Section 12 — Summary Dashboard\n\nOverview of analysis coverage and code-smell metrics."),
    code(
        "code_smells_count = int(SUMMARY_DF.loc[SUMMARY_DF['metric_name'] == 'Code_Smells_Count', 'metric_value'].iloc[0])\n\n"
        "summary_df = pd.DataFrame([\n"
        "    {'Metric': 'Total C# Files', 'Value': len(CSHARP_FILES)},\n"
        "    {'Metric': 'Total Projects', 'Value': len(PROJECT_PATHS)},\n"
        "    {'Metric': 'Projects Successfully Analyzed', 'Value': PROJECTS_SUCCESS},\n"
        "    {'Metric': 'Projects Failed', 'Value': PROJECTS_FAILED},\n"
        "    {'Metric': 'Total StyleCop Findings', 'Value': len(ALL_FINDINGS_DF)},\n"
        "    {'Metric': 'Total Code Smells', 'Value': code_smells_count},\n"
        "])\n\n"
        "display(summary_df)\n\n"
        "deliverables = [\n"
        "    RAW_OUTPUT_PATH, SARIF_OUTPUT_PATH, RESULTS_CSV_PATH, CSHARP_FILES_CSV,\n"
        "    INVENTORY_CSV, CODE_SMELLS_CSV, SUMMARY_CSV, ERROR_LOG_PATH,\n"
        "]\n\n"
        "print('\\nDeliverables:')\n"
        "for deliverable in deliverables:\n"
        "    status = 'OK' if deliverable.exists() else 'MISSING'\n"
        "    print(f'  [{status}] {deliverable}')"
    ),
    md("## Section 13 — Error Handling\n\nFailures are appended to `outputs/error_log.txt`."),
    code(
        "if ERROR_LOG_PATH.exists() and ERROR_LOG_PATH.stat().st_size > 0:\n"
        "    print(ERROR_LOG_PATH.read_text(encoding='utf-8'))\n"
        "else:\n"
        "    print('No errors logged.')"
    ),
    md(
        "## Section 14 — Deliverables\n\n"
        "```text\n"
        "outputs/\n"
        "├── stylecop_raw_output.txt\n"
        "├── stylecop_output.sarif\n"
        "├── stylecop_results.csv\n"
        "├── csharp_files.csv\n"
        "├── solution_project_inventory.csv\n"
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
