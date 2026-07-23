from __future__ import annotations

import ast
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.dom import minidom

import pandas as pd
from IPython.display import display
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

EXCLUDED_DIR_NAMES = {
    ".git", "venv", ".venv", "env", "__pycache__", "build", "dist", ".tox",
    "node_modules", "site-packages",
}
PY = sys.executable
SUMMARY_RE = re.compile(
    r"Covered\s+(\d+)\s+out\s+of\s+(\d+)\s+requirements\s+in\s+(\d+)\s+decisions\s+\((\d+)%\)",
    re.IGNORECASE,
)
RUNTIME_RE = re.compile(r"Run time:\s+([\d.]+)")
LINE_NUMBER_RE = re.compile(r"Line number:\s+\((\d+),\s*(\d+)\)")
DECISION_TEXT_RE = re.compile(r"^Decision:\s*(.+)$", re.MULTILINE)


@dataclass
class PymcdcDecision:
    line: int
    column: int
    decision_text: str
    conditions: list[str]
    requirements_total: int
    requirements_covered: int
    function_name: str = ""


@dataclass
class PymcdcFileResult:
    file_path: str
    raw_output: str
    stdout: str
    stderr: str
    exit_code: int
    execution_time_seconds: float
    covered_requirements: int = 0
    total_requirements: int = 0
    decision_count: int = 0
    mcdc_coverage_percent: int = 0
    condition_count: int = 0
    covered_conditions: int = 0
    decisions: list[PymcdcDecision] = field(default_factory=list)
    functions_analyzed: int = 0
    error: str = ""


class NotebookLogger:
    def __init__(self, error_log_path: Path) -> None:
        self.error_log_path = error_log_path
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._errors: list[dict[str, str]] = []
        self.write_errors()

    def info(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"[{timestamp}] INFO: {message}")

    def error(self, message: str, file: str = "notebook") -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        line = f"[{timestamp}] ERROR: {message}\n"
        print(line, end="")
        self._errors.append({"timestamp": timestamp, "file": file, "error": message})
        self.write_errors()

    def write_errors(self) -> None:
        with self.error_log_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["timestamp", "file", "error"])
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
    use_git_repo: bool,
    repo_url: str,
    local_repo: str | Path,
    workspace_dir: Path,
    if_clone_exists: str,
    logger: NotebookLogger,
    clone_depth: int | None = None,
) -> Path:
    if use_git_repo:
        return clone_or_reuse_repository(repo_url, workspace_dir, if_clone_exists, logger, clone_depth)
    return validate_local_repo_path(Path(local_repo), logger)


def discover_python_files(repo_path: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo_path.rglob("*.py"):
        if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            continue
        files.append(path.resolve())
    return sorted(files)


def count_all_files(repo_path: Path) -> int:
    total = 0
    for path in repo_path.rglob("*"):
        if path.is_file() and not any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            total += 1
    return total


def build_directory_tree(repo_path: Path, max_depth: int = 3, max_entries: int = 200) -> str:
    lines: list[str] = []
    root_name = repo_path.name

    def walk(current: Path, prefix: str, depth: int) -> None:
        if depth > max_depth or len(lines) >= max_entries:
            return
        try:
            entries = sorted(current.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        except PermissionError:
            return
        for index, entry in enumerate(entries):
            if entry.name in EXCLUDED_DIR_NAMES:
                continue
            connector = "└── " if index == len(entries) - 1 else "├── "
            lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
            if len(lines) >= max_entries:
                lines.append(f"{prefix}    ... (truncated)")
                return
            if entry.is_dir():
                extension = "    " if index == len(entries) - 1 else "│   "
                walk(entry, prefix + extension, depth + 1)

    lines.append(f"{root_name}/")
    walk(repo_path, "", 1)
    return "\n".join(lines)


def compute_repository_stats(repo_path: Path, python_files: list[Path]) -> dict[str, Any]:
    total_size = sum(path.stat().st_size for path in python_files)
    directories = {path.parent for path in python_files}
    return {
        "repository_name": repo_path.name,
        "repository_location": str(repo_path),
        "total_files": count_all_files(repo_path),
        "total_python_files": len(python_files),
        "directory_count": len(directories),
        "repository_size_bytes": total_size,
        "directory_structure": build_directory_tree(repo_path),
    }


def save_repository_summary(stats: dict[str, Any], output_csv: Path) -> None:
    pd.DataFrame([stats]).to_csv(output_csv, index=False)


def save_python_inventory(python_files: list[Path], output_csv: Path) -> None:
    pd.DataFrame(
        [{"file_path": str(p), "file_name": p.name, "directory": str(p.parent)} for p in python_files]
    ).to_csv(output_csv, index=False)


def detect_pymcdc_cli(logger: NotebookLogger) -> list[str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    for command in ([PY, "-m", "pymcdc", "--help"], ["pymcdc", "--help"]):
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                env=env,
            )
        except FileNotFoundError:
            continue
        if completed.returncode == 0 or "pymcdc" in (completed.stdout + completed.stderr).lower():
            logger.info(f"Detected PyMCDC CLI: {' '.join(command)}")
            return command[:-1]
    raise RuntimeError("PyMCDC CLI not found. Install with: pip install pymcdc")


def install_repository_requirements(repo_path: Path, logger: NotebookLogger) -> None:
    requirements = repo_path / "requirements.txt"
    pyproject = repo_path / "pyproject.toml"
    setup_py = repo_path / "setup.py"
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    if requirements.exists():
        command = [PY, "-m", "pip", "install", "-q", "-r", str(requirements)]
        logger.info(f"Installing repository requirements: {requirements}")
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        if completed.returncode != 0:
            logger.error(completed.stderr or completed.stdout, file=str(requirements))
        return

    if pyproject.exists():
        command = [PY, "-m", "pip", "install", "-q", str(repo_path)]
        logger.info(f"Installing repository from pyproject.toml: {pyproject}")
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        if completed.returncode != 0:
            logger.error(completed.stderr or completed.stdout, file=str(pyproject))
        return

    if setup_py.exists():
        command = [PY, "-m", "pip", "install", "-q", str(repo_path)]
        logger.info(f"Installing repository from setup.py: {setup_py}")
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
        if completed.returncode != 0:
            logger.error(completed.stderr or completed.stdout, file=str(setup_py))
        return

    logger.info("No requirements.txt, pyproject.toml, or setup.py found; skipping repository dependency install.")


def build_pymcdc_command(cli_prefix: list[str], py_file: Path) -> list[str]:
    return [*cli_prefix, str(py_file)]


def build_function_line_map(py_path: Path) -> list[tuple[int, int, str]]:
    try:
        source = py_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    functions: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end_line = getattr(node, "end_lineno", node.lineno)
            functions.append((node.lineno, end_line, node.name))
    return sorted(functions)


def function_for_line(line_number: int, function_map: list[tuple[int, int, str]]) -> str:
    for start, end, name in function_map:
        if start <= line_number <= end:
            return name
    return ""


def parse_table_conditions(header_line: str) -> list[str]:
    if "Result." not in header_line or "Cover." not in header_line:
        return []
    left = header_line.split("Result.", 1)[1]
    middle = left.split("Cover.", 1)[0]
    return [part.strip() for part in middle.split() if part.strip()]


def parse_requirement_rows(table_lines: list[str]) -> tuple[int, int]:
    total = covered = 0
    for line in table_lines:
        stripped = line.strip()
        if not stripped or set(stripped) <= {"-", "|"}:
            continue
        if not stripped[0].isdigit():
            continue
        cells = [cell.strip() for cell in stripped.split("|") if cell.strip()]
        if not cells:
            continue
        total += 1
        cover_value = cells[-1]
        if cover_value.lower() == "true":
            covered += 1
    return covered, total


def parse_pymcdc_output(raw_output: str, function_map: list[tuple[int, int, str]]) -> PymcdcFileResult:
    result = PymcdcFileResult(
        file_path="",
        raw_output=raw_output,
        stdout=raw_output,
        stderr="",
        exit_code=0,
        execution_time_seconds=0.0,
    )
    runtime_match = RUNTIME_RE.search(raw_output)
    if runtime_match:
        result.execution_time_seconds = float(runtime_match.group(1))

    summary_match = SUMMARY_RE.search(raw_output)
    if summary_match:
        result.covered_requirements = int(summary_match.group(1))
        result.total_requirements = int(summary_match.group(2))
        result.decision_count = int(summary_match.group(3))
        result.mcdc_coverage_percent = int(summary_match.group(4))

    blocks = re.split(r"(?=Line number:\s*\()", raw_output)
    for block in blocks:
        line_match = LINE_NUMBER_RE.search(block)
        decision_match = DECISION_TEXT_RE.search(block)
        if not line_match or not decision_match:
            continue
        line_number = int(line_match.group(1))
        column_number = int(line_match.group(2))
        decision_text = decision_match.group(1).strip()
        table_lines = block.split("Combinations to be covered:", 1)
        conditions: list[str] = []
        req_covered = req_total = 0
        if len(table_lines) == 2:
            lines = table_lines[1].splitlines()
            header = next((line for line in lines if "Result." in line and "Cover." in line), "")
            conditions = parse_table_conditions(header)
            req_covered, req_total = parse_requirement_rows(lines)
        covered_conditions = sum(
            1
            for condition in conditions
            for line in table_lines[1].splitlines() if len(table_lines) == 2
            if condition in line and " True " in f" {line} "
        ) if conditions else 0
        result.decisions.append(
            PymcdcDecision(
                line=line_number,
                column=column_number,
                decision_text=decision_text,
                conditions=conditions,
                requirements_total=req_total,
                requirements_covered=req_covered,
                function_name=function_for_line(line_number, function_map),
            )
        )
        result.condition_count += len(conditions)
        result.covered_conditions += covered_conditions

    function_names = {decision.function_name for decision in result.decisions if decision.function_name}
    result.functions_analyzed = len(function_names)
    return result


def combine_raw_streams(stdout: str, stderr: str) -> str:
    raw = stdout
    if stderr:
        if raw and not raw.endswith("\n"):
            raw += "\n"
        raw += stderr
    return raw


def run_pymcdc_on_file(
    cli_prefix: list[str],
    py_file: Path,
    logger: NotebookLogger,
) -> PymcdcFileResult:
    command = build_pymcdc_command(cli_prefix, py_file)
    logger.info(f"Executing: {' '.join(command)}")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )
    elapsed = time.perf_counter() - started
    raw_output = combine_raw_streams(completed.stdout, completed.stderr)
    function_map = build_function_line_map(py_file)
    parsed = parse_pymcdc_output(raw_output, function_map)
    parsed.file_path = str(py_file)
    parsed.stdout = completed.stdout
    parsed.stderr = completed.stderr
    parsed.exit_code = completed.returncode
    parsed.raw_output = raw_output
    parsed.execution_time_seconds = parsed.execution_time_seconds or round(elapsed, 5)
    if completed.returncode != 0:
        parsed.error = raw_output.strip() or f"PyMCDC exited with code {completed.returncode}"
        logger.error(parsed.error, file=str(py_file))
    mdc_path = Path(str(py_file) + ".mdc")
    if mdc_path.exists():
        try:
            mdc_path.unlink()
        except OSError:
            logger.error(f"Unable to remove temporary file: {mdc_path}", file=str(py_file))
    return parsed


def run_pymcdc_on_repository(
    cli_prefix: list[str],
    python_files: list[Path],
    logger: NotebookLogger,
) -> tuple[list[PymcdcFileResult], str, float]:
    chunks: list[str] = []
    results: list[PymcdcFileResult] = []
    started = time.perf_counter()
    for py_file in python_files:
        chunks.append(f"===== pymcdc {py_file} =====")
        try:
            result = run_pymcdc_on_file(cli_prefix, py_file, logger)
        except Exception as exc:
            result = PymcdcFileResult(
                file_path=str(py_file),
                raw_output=str(exc),
                stdout="",
                stderr=str(exc),
                exit_code=1,
                execution_time_seconds=0.0,
                error=str(exc),
            )
            logger.error(str(exc), file=str(py_file))
        results.append(result)
        chunks.append(result.raw_output)
        if not chunks[-1].endswith("\n"):
            chunks.append("")
    total_elapsed = round(time.perf_counter() - started, 5)
    return results, "\n".join(chunks), total_elapsed


def build_metrics_rows(results: list[PymcdcFileResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        file_path = result.file_path
        base_metrics = [
            ("Decision Count", result.decision_count),
            ("Condition Count", result.condition_count),
            ("Covered Requirements", result.covered_requirements),
            ("Total Requirements", result.total_requirements),
            ("MC/DC Coverage", result.mcdc_coverage_percent),
            ("Execution Time", result.execution_time_seconds),
        ]
        for metric_name, metric_value in base_metrics:
            rows.append(
                {"metric_name": metric_name, "metric_value": metric_value, "file": file_path, "function": ""}
            )
        for decision in result.decisions:
            decision_coverage = (
                round(decision.requirements_covered * 100 / decision.requirements_total, 2)
                if decision.requirements_total
                else 100.0
            )
            per_decision_metrics = [
                ("Decision Nodes", 1),
                ("Condition Nodes", len(decision.conditions)),
                ("Covered Decisions", 1 if decision.requirements_covered == decision.requirements_total and decision.requirements_total else 0),
                ("Covered Conditions", decision.requirements_covered),
                ("Decision Coverage", decision_coverage),
                ("Condition Coverage", decision_coverage),
                ("Independent Condition Evaluation", len(decision.conditions)),
            ]
            for metric_name, metric_value in per_decision_metrics:
                rows.append(
                    {
                        "metric_name": metric_name,
                        "metric_value": metric_value,
                        "file": file_path,
                        "function": decision.function_name,
                    }
                )
    return rows


def build_file_summary_rows(results: list[PymcdcFileResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        decision_coverage = (
            round(result.covered_requirements * 100 / result.total_requirements, 2)
            if result.total_requirements
            else 100.0
        )
        condition_coverage = (
            round(result.covered_conditions * 100 / result.condition_count, 2)
            if result.condition_count
            else 100.0
        )
        rows.append(
            {
                "file": result.file_path,
                "functions_analyzed": result.functions_analyzed,
                "decisions": result.decision_count,
                "conditions": result.condition_count,
                "decision_coverage": decision_coverage,
                "condition_coverage": condition_coverage,
                "mcdc_coverage": result.mcdc_coverage_percent,
            }
        )
    return rows


def build_repository_summary_row(
    repo_stats: dict[str, Any],
    results: list[PymcdcFileResult],
    total_execution_time: float,
) -> dict[str, Any]:
    total_functions = sum(result.functions_analyzed for result in results)
    total_decisions = sum(result.decision_count for result in results)
    total_conditions = sum(result.condition_count for result in results)
    covered_requirements = sum(result.covered_requirements for result in results)
    total_requirements = sum(result.total_requirements for result in results)
    decision_coverage = round(covered_requirements * 100 / total_requirements, 2) if total_requirements else 100.0
    return {
        "Repository Name": repo_stats["repository_name"],
        "Total Python Files": repo_stats["total_python_files"],
        "Total Functions": total_functions,
        "Total Decisions": total_decisions,
        "Total Conditions": total_conditions,
        "Decision Coverage %": decision_coverage,
        "Condition Coverage %": decision_coverage,
        "MC/DC Coverage %": decision_coverage,
        "Execution Time (seconds)": total_execution_time,
    }


def export_parsed_json(results: list[PymcdcFileResult], repo_summary: dict[str, Any], output_path: Path) -> None:
    payload = {
        "tool": "pymcdc",
        "note": "Structured export parsed from PyMCDC console output. PyMCDC does not emit native JSON.",
        "repository_summary": repo_summary,
        "files": [
            {
                "file": result.file_path,
                "exit_code": result.exit_code,
                "execution_time_seconds": result.execution_time_seconds,
                "summary": {
                    "covered_requirements": result.covered_requirements,
                    "total_requirements": result.total_requirements,
                    "decision_count": result.decision_count,
                    "mcdc_coverage_percent": result.mcdc_coverage_percent,
                },
                "decisions": [
                    {
                        "line_number": [decision.line, decision.column],
                        "decision_text": decision.decision_text,
                        "function": decision.function_name,
                        "conditions": decision.conditions,
                        "requirements_total": decision.requirements_total,
                        "requirements_covered": decision.requirements_covered,
                    }
                    for decision in result.decisions
                ],
                "raw_output": result.raw_output,
            }
            for result in results
        ],
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def export_parsed_xml(results: list[PymcdcFileResult], repo_summary: dict[str, Any], output_path: Path) -> None:
    root = ET.Element(
        "pymcdc_output",
        attrib={
            "tool": "pymcdc",
            "note": "Structured export parsed from PyMCDC console output. PyMCDC does not emit native XML.",
        },
    )
    summary_el = ET.SubElement(root, "repository_summary")
    for key, value in repo_summary.items():
        item = ET.SubElement(summary_el, "metric", name=key)
        item.text = str(value)
    files_el = ET.SubElement(root, "files")
    for result in results:
        file_el = ET.SubElement(files_el, "file", path=result.file_path, exit_code=str(result.exit_code))
        ET.SubElement(file_el, "execution_time_seconds").text = str(result.execution_time_seconds)
        ET.SubElement(file_el, "covered_requirements").text = str(result.covered_requirements)
        ET.SubElement(file_el, "total_requirements").text = str(result.total_requirements)
        ET.SubElement(file_el, "decision_count").text = str(result.decision_count)
        ET.SubElement(file_el, "mcdc_coverage_percent").text = str(result.mcdc_coverage_percent)
        decisions_el = ET.SubElement(file_el, "decisions")
        for decision in result.decisions:
            decision_el = ET.SubElement(
                decisions_el,
                "decision",
                line=str(decision.line),
                column=str(decision.column),
                function=decision.function_name,
            )
            ET.SubElement(decision_el, "text").text = decision.decision_text
            conditions_el = ET.SubElement(decision_el, "conditions")
            for condition in decision.conditions:
                ET.SubElement(conditions_el, "condition").text = condition
        raw_el = ET.SubElement(file_el, "raw_output")
        raw_el.text = result.raw_output
    xml_bytes = ET.tostring(root, encoding="utf-8")
    pretty = minidom.parseString(xml_bytes).toprettyxml(indent="  ")
    output_path.write_text(pretty, encoding="utf-8")


def preview_raw_output(raw_text: str, preview_lines: int, output_path: Path) -> None:
    lines = raw_text.splitlines()
    print(f"\n{'=' * 80}")
    print(f"RAW PYMCDC OUTPUT PREVIEW (first {preview_lines} lines)")
    print(f"{'=' * 80}\n")
    if not lines:
        print("(empty raw output)")
        return
    print("\n".join(lines[:preview_lines]))
    remaining = len(lines) - preview_lines
    if remaining > 0:
        print(f"\n... ({remaining} more lines saved to {output_path})")
