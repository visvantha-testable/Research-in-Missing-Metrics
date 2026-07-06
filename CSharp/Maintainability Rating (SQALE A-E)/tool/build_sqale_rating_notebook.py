"""Generate stylecop_maintainability_rating_extraction.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "stylecop_maintainability_rating_extraction.ipynb"

DOTNET_SETUP = r'''
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

os.environ.pop("PYTHONPATH", None)


def download_dotnet_sdk(install_dir: Path, channel: str = "8.0") -> Path:
    install_dir = install_dir.resolve()
    install_dir.mkdir(parents=True, exist_ok=True)
    dotnet = install_dir / ("dotnet.exe" if sys.platform.startswith("win") else "dotnet")
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


PROJECT_RUNTIMES = Path("../../runtimes").resolve()
DOTNET_ROOT = download_dotnet_sdk(PROJECT_RUNTIMES / "dotnet-sdk")
os.environ["DOTNET_ROOT"] = str(DOTNET_ROOT)
os.environ["PATH"] = str(DOTNET_ROOT) + os.pathsep + os.environ.get("PATH", "")
subprocess.run([str(DOTNET_ROOT / ("dotnet.exe" if sys.platform.startswith("win") else "dotnet")), "--version"], check=False)
'''

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

EXCLUDED_DIR_NAMES = {".git", "bin", "obj", "packages", "TestResults", "node_modules", "docs", "artifacts"}
STYLECOP_PACKAGE = "StyleCop.Analyzers"
STYLECOP_VERSION = "1.2.0-beta.556"
FINDINGS_COLUMNS = ["project", "file", "line", "column", "severity", "diagnostic_id", "message"]
BUILD_DIAGNOSTIC_PATTERN = re.compile(
    r"^(?P<file>.+?)\((?P<line>\d+),(?P<column>\d+)\):\s*(?P<severity>\w+)\s+(?P<rule_id>SA\d+):\s*(?P<message>.*)$"
)
BUILD_SUCCESS_CODES = {0, 1}
STYLECOP_JSON = {
    "$schema": "https://raw.githubusercontent.com/DotNetAnalyzers/StyleCopAnalyzers/master/StyleCop.Analyzers/StyleCop.Analyzers/Settings/stylecop.schema.json",
    "settings": {
        "documentationRules": {
            "documentExposedElements": True,
            "documentInternalElements": True,
            "documentPrivateElements": True,
            "documentInterfaces": True,
            "documentPrivateFields": True,
        },
        "orderingRules": {"usingDirectivesPlacement": "outsideNamespace"},
        "namingRules": {"allowCommonHungarianPrefixes": False},
        "layoutRules": {"newlineAtEndOfFile": "require"},
    },
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


def should_exclude_path(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def discover_csharp_files(repo_path: Path) -> list[Path]:
    files = []
    for path in repo_path.rglob("*.cs"):
        if should_exclude_path(path.relative_to(repo_path)):
            continue
        files.append(path.resolve())
    return sorted(files)


def compute_repository_stats(repo_path: Path, csharp_files: list[Path]) -> dict[str, Any]:
    total_size = sum(path.stat().st_size for path in csharp_files)
    directories = {path.parent for path in csharp_files}
    return {
        "repository_name": repo_path.name,
        "repository_size_bytes": total_size,
        "directory_count": len(directories),
        "csharp_file_count": len(csharp_files),
    }


def save_csharp_inventory(csharp_files: list[Path], output_csv: Path) -> None:
    pd.DataFrame(
        [{"file_path": str(p), "file_name": p.name, "directory": str(p.parent)} for p in csharp_files]
    ).to_csv(output_csv, index=False)


def discover_solutions_and_projects(repo_path: Path) -> tuple[list[Path], list[Path]]:
    solutions, projects = [], []
    for path in repo_path.rglob("*"):
        if not path.is_file() or should_exclude_path(path.relative_to(repo_path)):
            continue
        if path.suffix.lower() == ".sln":
            solutions.append(path.resolve())
        elif path.suffix.lower() == ".csproj":
            projects.append(path.resolve())
    return sorted(solutions), sorted(projects)


def resolve_analysis_targets(solutions: list[Path], projects: list[Path]) -> list[Path]:
    return solutions if solutions else projects


def collect_projects_from_solution(solution_path: Path) -> list[Path]:
    projects = []
    content = solution_path.read_text(encoding="utf-8", errors="replace")
    for match in re.finditer(r'Project\("[^"]+"\)\s*=\s*"[^"]+",\s*"([^"]+\.csproj)"', content):
        project_relative = match.group(1).replace("\\", os.sep)
        project_path = (solution_path.parent / project_relative).resolve()
        if project_path.exists():
            projects.append(project_path)
    return projects


def collect_projects_for_targets(targets: list[Path]) -> list[Path]:
    projects, seen = [], set()
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


def dotnet_executable() -> Path:
    dotnet_root = Path(os.environ.get("DOTNET_ROOT", str(DOTNET_ROOT)))
    return dotnet_root / ("dotnet.exe" if sys.platform.startswith("win") else "dotnet")


def run_dotnet_command(command: list[str], logger: NotebookLogger) -> tuple[str, str, int]:
    completed = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        env={**os.environ, "DOTNET_ROOT": os.environ.get("DOTNET_ROOT", str(DOTNET_ROOT))},
    )
    return completed.stdout, completed.stderr, completed.returncode


def combine_raw_streams(stdout: str, stderr: str) -> str:
    raw = stdout
    if stderr:
        if raw and not raw.endswith("\n"):
            raw += "\n"
        raw += stderr
    return raw


def write_stylecop_json(project_dir: Path) -> Path:
    stylecop_path = project_dir / "stylecop.json"
    stylecop_path.write_text(json.dumps(STYLECOP_JSON, indent=2), encoding="utf-8")
    return stylecop_path


def ensure_stylecop_json_reference(project_path: Path) -> None:
    write_stylecop_json(project_path.parent)
    content = project_path.read_text(encoding="utf-8", errors="replace")
    if "stylecop.json" in content:
        return
    insert = '\n  <ItemGroup>\n    <AdditionalFiles Include="stylecop.json" Link="stylecop.json" />\n  </ItemGroup>\n'
    if "</Project>" in content:
        project_path.write_text(content.replace("</Project>", insert + "</Project>", 1), encoding="utf-8")


def has_stylecop_package(project_path: Path) -> bool:
    return STYLECOP_PACKAGE in project_path.read_text(encoding="utf-8", errors="replace")


def inject_stylecop(project_path: Path, logger: NotebookLogger) -> tuple[bool, str]:
    ensure_stylecop_json_reference(project_path)
    if has_stylecop_package(project_path):
        return True, "already_installed"
    stdout, stderr, code = run_dotnet_command([
        str(dotnet_executable()), "add", str(project_path), "package", STYLECOP_PACKAGE, "--version", STYLECOP_VERSION,
    ], logger)
    if code != 0:
        return False, combine_raw_streams(stdout, stderr)
    return True, combine_raw_streams(stdout, stderr)


def parse_build_diagnostics(raw_text: str, project: str) -> list[dict[str, Any]]:
    rows = []
    for line in raw_text.splitlines():
        match = BUILD_DIAGNOSTIC_PATTERN.match(line.strip())
        if not match:
            continue
        rows.append({
            "project": project, "file": match.group("file").strip(),
            "line": int(match.group("line")), "column": int(match.group("column")),
            "severity": match.group("severity").lower(), "diagnostic_id": match.group("rule_id"),
            "message": match.group("message").strip(),
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
            severity = {"error": "error", "warning": "warning", "note": "info"}.get(str(result.get("level", "warning")).lower(), "warning")
            for location in result.get("locations", []):
                physical = location.get("physicalLocation", {})
                artifact = physical.get("artifactLocation", {})
                region = physical.get("region", {})
                rows.append({
                    "project": project, "file": artifact.get("uri", ""),
                    "line": region.get("startLine", ""), "column": region.get("startColumn", ""),
                    "severity": severity, "diagnostic_id": rule_id, "message": text,
                })
    return rows


def merge_findings(*groups: list[dict[str, Any]]) -> pd.DataFrame:
    rows, seen = [], set()
    for group in groups:
        for item in group:
            file_value = str(item.get("file", "")).strip()
            if not file_value:
                continue
            key = (str(item.get("project", "")), file_value, str(item.get("line", "")),
                   str(item.get("diagnostic_id", "")), str(item.get("message", "")))
            if key in seen:
                continue
            seen.add(key)
            rows.append(item)
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def categorize_violation(rule_id: str) -> str:
    if not re.fullmatch(r"SA\d{4}", rule_id):
        return "Style"
    number = int(rule_id[2:])
    if 1600 <= number <= 1655:
        return "Documentation"
    if 1300 <= number <= 1314:
        return "Naming"
    if 1200 <= number <= 1217:
        return "Ordering"
    if 1100 <= number <= 1127:
        return "Readability"
    if 1400 <= number <= 1413:
        return "Design"
    if 1500 <= number <= 1518:
        return "Layout"
    return "Style"


def is_maintainability_violation(rule_id: str) -> bool:
    return bool(re.fullmatch(r"SA\d{4}", str(rule_id)))


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
        "# StyleCop Maintainability Rating (SQALE A–E) — Raw Output Extraction (C#)\n\n"
        "This notebook analyzes **C# repositories** with **StyleCop Analyzers** and captures complete raw tool output "
        "for Code Smells Count, Maintainability Violations, Maintainability Score, and Maintainability Rating (A–E).\n\n"
        "**Default benchmark repository:** [dotnet-architecture/eShopOnWeb](https://github.com/dotnet-architecture/eShopOnWeb)"
    ),
    md("## Section 1 — Install Dependencies\n\nInstall Python packages and verify .NET SDK."),
    code("!pip install -q pandas gitpython jupyter\n\n" + DOTNET_SETUP.strip()),
    md("## Section 2 — Configuration"),
    code(
        "USE_GIT_URL = True\n\n"
        "REPO_URL = 'https://github.com/dotnet-architecture/eShopOnWeb.git'\n\n"
        "LOCAL_REPO_PATH = '/content/eShopOnWeb'\n\n"
        "WORKSPACE_DIR = './workspace'\n\n"
        "OUTPUT_DIR = './outputs'\n\n"
        "IF_CLONE_EXISTS = 'reuse'\n\n"
        "CLONE_DEPTH = 1\n\n"
        "RAW_OUTPUT_PREVIEW_LINES = 150\n\n"
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
        "CSHARP_FILES = discover_csharp_files(REPO_PATH)\n"
        "if not CSHARP_FILES:\n"
        "    logger.error('No C# source files found in repository.', file=str(REPO_PATH))\n"
        "    raise FileNotFoundError('No C# source files found.')\n\n"
        "REPO_STATS = compute_repository_stats(REPO_PATH, CSHARP_FILES)\n"
        "logger.info(f'Repository ready at: {REPO_PATH}')\n"
        "print(f\"Repository: {REPO_STATS['repository_name']}\")\n"
        "print(f\"Size (C# files): {REPO_STATS['repository_size_bytes']:,} bytes\")\n"
        "print(f\"Directories: {REPO_STATS['directory_count']:,}\")\n"
        "print(f\"C# files: {REPO_STATS['csharp_file_count']:,}\")"
    ),
    md("## Section 5 — Discover C# Files"),
    code(
        "INVENTORY_CSV = OUTPUT_PATH / 'csharp_files_inventory.csv'\n"
        "save_csharp_inventory(CSHARP_FILES, INVENTORY_CSV)\n\n"
        "print(f'Total C# Files Found: {len(CSHARP_FILES)}')\n"
        "print(f'Saved inventory to: {INVENTORY_CSV}')"
    ),
    md("## Section 6 — Configure StyleCop Analysis\n\nGenerate `stylecop.json` and inject StyleCop.Analyzers into projects."),
    code(
        "SOLUTIONS, PROJECTS = discover_solutions_and_projects(REPO_PATH)\n"
        "TARGETS = resolve_analysis_targets(SOLUTIONS, PROJECTS)\n"
        "PROJECT_PATHS = collect_projects_for_targets(TARGETS)\n"
        "if not TARGETS and PROJECT_PATHS:\n"
        "    TARGETS = PROJECT_PATHS\n\n"
        "STYLECOP_SETUP_LOG: list[str] = []\n"
        "for project_path in PROJECT_PATHS:\n"
        "    ok, detail = inject_stylecop(project_path, logger)\n"
        "    if not ok:\n"
        "        logger.error(f'StyleCop injection failed for {project_path}: {detail.strip()}', file=str(project_path))\n"
        "    elif detail != 'already_installed':\n"
        "        STYLECOP_SETUP_LOG.append(detail)\n\n"
        "stylecop_json_path = write_stylecop_json(PROJECT_PATHS[0].parent) if PROJECT_PATHS else REPO_PATH / 'stylecop.json'\n"
        "logger.info(f'StyleCop configured. stylecop.json at {stylecop_json_path}')"
    ),
    md("## Section 7 — Execute StyleCop Analysis\n\nRun `dotnet build` with analyzers enabled. Preserve stdout/stderr exactly as emitted."),
    code(
        "CONSOLE_CHUNKS: list[str] = list(STYLECOP_SETUP_LOG)\n\n"
        "for target in TARGETS:\n"
        "    target_label = str(target)\n"
        "    restore_stdout, restore_stderr, restore_code = run_dotnet_command(\n"
        "        [str(dotnet_executable()), 'restore', target_label], logger\n"
        "    )\n"
        "    CONSOLE_CHUNKS.append(combine_raw_streams(restore_stdout, restore_stderr))\n"
        "    if restore_code != 0:\n"
        "        logger.error(f'dotnet restore failed for {target_label}', file=target_label)\n"
        "        continue\n\n"
        "    sarif_path = OUTPUT_PATH / f'{Path(target_label).stem}.sarif'\n"
        "    clean_stdout, clean_stderr, _ = run_dotnet_command([str(dotnet_executable()), 'clean', target_label], logger)\n"
        "    build_stdout, build_stderr, build_code = run_dotnet_command([\n"
        "        str(dotnet_executable()), 'build', target_label, '--no-incremental',\n"
        "        '-p:RunAnalyzers=true', f'-p:ErrorLog={sarif_path}', '--no-restore', '-v', 'normal',\n"
        "    ], logger)\n"
        "    CONSOLE_CHUNKS.append(combine_raw_streams(clean_stdout + clean_stderr, combine_raw_streams(build_stdout, build_stderr)))\n"
        "    if build_code not in BUILD_SUCCESS_CODES:\n"
        "        logger.error(f'dotnet build failed for {target_label} (continuing)', file=target_label)\n\n"
        "logger.info('StyleCop analysis complete.')"
    ),
    md("## Section 8 — Raw Output Extraction"),
    code(
        "CONSOLE_PATH = OUTPUT_PATH / 'stylecop_raw_console_output.txt'\n"
        "CONSOLE_PATH.write_text('\\n'.join(CONSOLE_CHUNKS), encoding='utf-8')\n\n"
        "build_findings: list[dict] = []\n"
        "sarif_findings: list[dict] = []\n"
        "for target in TARGETS:\n"
        "    target_label = str(target)\n"
        "    sarif_path = OUTPUT_PATH / f'{Path(target_label).stem}.sarif'\n"
        "    sarif_findings.extend(parse_sarif(sarif_path, target_label))\n"
        "    build_findings.extend(parse_build_diagnostics(CONSOLE_PATH.read_text(encoding='utf-8'), target_label))\n\n"
        "FINDINGS_DF = merge_findings(build_findings, sarif_findings)\n"
        "FINDINGS_CSV = OUTPUT_PATH / 'stylecop_findings.csv'\n"
        "FINDINGS_DF.to_csv(FINDINGS_CSV, index=False)\n\n"
        "logger.info(f'Extracted {len(FINDINGS_DF)} StyleCop findings.')\n"
        "preview_raw_output(CONSOLE_PATH.read_text(encoding='utf-8'), RAW_OUTPUT_PREVIEW_LINES, CONSOLE_PATH)"
    ),
    md("## Section 9 — Metric Computation"),
    code(
        "MAINTAINABILITY_DF = FINDINGS_DF[FINDINGS_DF['diagnostic_id'].map(is_maintainability_violation)].copy()\n"
        "violation_count = len(MAINTAINABILITY_DF)\n"
        "code_smells_count = violation_count\n\n"
        "CODE_SMELLS_CSV = OUTPUT_PATH / 'code_smells_summary.csv'\n"
        "pd.DataFrame([{'metric_name': 'Code_Smells_Count', 'metric_value': code_smells_count}]).to_csv(CODE_SMELLS_CSV, index=False)\n\n"
        "violation_rows = [{'metric_name': 'Maintainability_Violations_Count', 'metric_value': violation_count}]\n"
        "if not MAINTAINABILITY_DF.empty:\n"
        "    MAINTAINABILITY_DF['category'] = MAINTAINABILITY_DF['diagnostic_id'].map(categorize_violation)\n"
        "    for category in ['Documentation', 'Naming', 'Ordering', 'Readability', 'Design', 'Layout', 'Style']:\n"
        "        count = int((MAINTAINABILITY_DF['category'] == category).sum())\n"
        "        if count:\n"
        "            violation_rows.append({'metric_name': f'{category}_Violations', 'metric_value': count})\n"
        "VIOLATIONS_CSV = OUTPUT_PATH / 'maintainability_violations_summary.csv'\n"
        "pd.DataFrame(violation_rows).to_csv(VIOLATIONS_CSV, index=False)\n\n"
        "maintainability_score = compute_maintainability_score(violation_count, len(CSHARP_FILES))\n"
        "SCORE_CSV = OUTPUT_PATH / 'maintainability_score_summary.csv'\n"
        "pd.DataFrame([{'metric_name': 'Maintainability_Score', 'metric_value': maintainability_score}]).to_csv(SCORE_CSV, index=False)\n\n"
        "rating = score_to_sqale_rating(maintainability_score)\n"
        "RATING_CSV = OUTPUT_PATH / 'maintainability_rating_summary.csv'\n"
        "pd.DataFrame([{'metric_name': 'Maintainability_Rating', 'metric_value': rating}]).to_csv(RATING_CSV, index=False)\n\n"
        "logger.info(f'Code Smells={code_smells_count}, Score={maintainability_score}, Rating={rating}')\n"
        "display(pd.DataFrame(violation_rows + [\n"
        "    {'metric_name': 'Maintainability_Score', 'metric_value': maintainability_score},\n"
        "    {'metric_name': 'Maintainability_Rating', 'metric_value': rating},\n"
        "]))"
    ),
    md("## Section 10 — Summary Dashboard"),
    code(
        "summary_df = pd.DataFrame([\n"
        "    {'Metric': 'Total C# Files', 'Value': len(CSHARP_FILES)},\n"
        "    {'Metric': 'Total StyleCop Findings', 'Value': len(FINDINGS_DF)},\n"
        "    {'Metric': 'Code Smells Count', 'Value': code_smells_count},\n"
        "    {'Metric': 'Maintainability Violations', 'Value': violation_count},\n"
        "    {'Metric': 'Maintainability Score', 'Value': maintainability_score},\n"
        "    {'Metric': 'Maintainability Rating', 'Value': rating},\n"
        "])\n"
        "display(summary_df)\n\n"
        "deliverables = [\n"
        "    CONSOLE_PATH, FINDINGS_CSV, CODE_SMELLS_CSV, VIOLATIONS_CSV,\n"
        "    SCORE_CSV, RATING_CSV, INVENTORY_CSV, ERROR_LOG_PATH,\n"
        "]\n"
        "print('\\nDeliverables:')\n"
        "for path in deliverables:\n"
        "    print(f\"  [{'OK' if path.exists() else 'MISSING'}] {path}\")"
    ),
    md("## Section 11 — Error Handling"),
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
        "├── stylecop_raw_console_output.txt\n"
        "├── stylecop_findings.csv\n"
        "├── code_smells_summary.csv\n"
        "├── maintainability_violations_summary.csv\n"
        "├── maintainability_score_summary.csv\n"
        "├── maintainability_rating_summary.csv\n"
        "├── csharp_files_inventory.csv\n"
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
