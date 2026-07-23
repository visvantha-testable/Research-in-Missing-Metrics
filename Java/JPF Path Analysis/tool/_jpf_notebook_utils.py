"""Java PathFinder (JPF) raw output extraction helpers."""
from __future__ import annotations

import csv
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

TOOL_ROOT = Path(__file__).resolve().parent
JACOCO_TOOL_ROOT = TOOL_ROOT.parent.parent / "JaCoCo Coverage" / "tool"
if str(JACOCO_TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(JACOCO_TOOL_ROOT))

from _jacoco_notebook_utils import (  # noqa: E402
    EXCLUDED_DIR_NAMES,
    CommandResult,
    combine_streams,
    configure_java_runtime,
    detect_build_tool,
    discover_java_files,
    ensure_output_dir,
    extract_package_name,
    project_runtimes_root,
    resolve_gradle_command,
    resolve_maven_command,
    resolve_repository_path,
    run_shell_command,
)

MAIN_METHOD_RE = re.compile(
    r"public\s+static\s+void\s+main\s*\(\s*String(?:\s*\[\s*\])?\s+\w+\s*\)",
    re.MULTILINE,
)
CLASS_NAME_RE = re.compile(r"(?:public\s+)?(?:final\s+)?class\s+(\w+)")
STATISTICS_BLOCK_RE = re.compile(
    r"={50,}\s*statistics\s*(.*?)\s*={50,}\s*search finished",
    re.IGNORECASE | re.DOTALL,
)
STATES_RE = re.compile(
    r"states:\s*new=(\d+),visited=(\d+),backtracked=(\d+),end=(\d+)",
    re.IGNORECASE,
)
SEARCH_DEPTH_RE = re.compile(r"search:\s*maxDepth=(\d+)", re.IGNORECASE)
CHOICE_GENERATORS_RE = re.compile(r"choice generators:\s*(.+)", re.IGNORECASE)
TRANSITION_COUNT_RE = re.compile(r"transition #(\d+)", re.IGNORECASE)
ERROR_STATE_RE = re.compile(r"error #(\d+):", re.IGNORECASE)
EXCEPTION_RE = re.compile(
    r"(?:gov\.nasa\.jpf\.vm\.NoUncaughtExceptionsProperty|java\.lang\.\w+Exception|java\.lang\.\w+Error)",
    re.IGNORECASE,
)
DEADLOCK_RE = re.compile(r"deadlock", re.IGNORECASE)
TRACE_SECTION_RE = re.compile(r"(={50,}\s*trace #\d+.*?)(?=={50,}|\Z)", re.DOTALL | re.IGNORECASE)

PATH_METRICS = [
    "Path Execution Tracking",
    "Complete Coverage Path Verification",
    "Partial Path Coverage Detection",
    "Nested Condition Path Testing",
    "Loop Path Detection",
    "Unreachable Path Detection",
    "Exception Path Handling",
    "Multi-Function Path Tracking",
    "Path Detection Testing",
]

METRIC_EVIDENCE_PATTERNS: dict[str, list[tuple[str, re.Pattern[str]]]] = {
    "Path Execution Tracking": [
        ("transition", re.compile(r"transition #\d+", re.IGNORECASE)),
        ("trace", re.compile(r"trace #\d+", re.IGNORECASE)),
        ("instructions", re.compile(r"instructions:\s*\d+", re.IGNORECASE)),
    ],
    "Complete Coverage Path Verification": [
        ("states end", re.compile(r"states:.*end=\d+", re.IGNORECASE)),
        ("search finished", re.compile(r"search finished", re.IGNORECASE)),
    ],
    "Partial Path Coverage Detection": [
        ("visited states", re.compile(r"states:.*visited=\d+", re.IGNORECASE)),
        ("backtracked", re.compile(r"backtracked=\d+", re.IGNORECASE)),
    ],
    "Nested Condition Path Testing": [
        ("choice generators", re.compile(r"choice generators:", re.IGNORECASE)),
        ("constraints", re.compile(r"constraints=\d+", re.IGNORECASE)),
    ],
    "Loop Path Detection": [
        ("backtracked", re.compile(r"backtracked=\d+", re.IGNORECASE)),
        ("maxDepth", re.compile(r"maxDepth=\d+", re.IGNORECASE)),
    ],
    "Unreachable Path Detection": [
        ("end states", re.compile(r"states:.*end=\d+", re.IGNORECASE)),
        ("backtracked", re.compile(r"backtracked=\d+", re.IGNORECASE)),
    ],
    "Exception Path Handling": [
        ("NoUncaughtExceptionsProperty", re.compile(r"NoUncaughtExceptionsProperty", re.IGNORECASE)),
        ("Exception trace", re.compile(r"java\.lang\.\w+Exception", re.IGNORECASE)),
    ],
    "Multi-Function Path Tracking": [
        ("transition stack", re.compile(r"at\s+[\w.$]+\([\w/$.]+:\d+\)", re.IGNORECASE)),
        ("loaded methods", re.compile(r"loaded code:\s*classes=\d+,methods=\d+", re.IGNORECASE)),
    ],
    "Path Detection Testing": [
        ("visited states", re.compile(r"visited=\d+", re.IGNORECASE)),
        ("new states", re.compile(r"new=\d+", re.IGNORECASE)),
        ("statistics", re.compile(r"statistics", re.IGNORECASE)),
    ],
}

JPF_OPTIONAL_ARTIFACTS = [
    "search_graph.txt",
    "error_trace.txt",
    "visited_states.txt",
    "path_report.txt",
]


@dataclass
class JavaClassInfo:
    file_path: Path
    package: str
    class_name: str
    qualified_name: str
    has_main: bool


@dataclass
class JpfInstallStatus:
    jpf_home: Path
    run_jpf_jar: Path
    site_properties: Path
    install_command: list[str]
    build_command: list[str]
    install_result: CommandResult | None = None
    build_result: CommandResult | None = None
    install_success: bool = False
    build_success: bool = False


@dataclass
class JpfClassRun:
    qualified_name: str
    jpf_file: Path
    command: list[str]
    stdout: str
    stderr: str
    exit_code: int
    execution_time_seconds: float
    success: bool
    metrics: list[dict[str, str]] = field(default_factory=list)


class JpfNotebookLogger:
    def __init__(self, error_log_path: Path) -> None:
        self.error_log_path = error_log_path
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._errors: list[dict[str, str]] = []
        self.write_errors()

    def info(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"[{timestamp}] INFO: {message}")

    def error(self, message: str, step: str = "notebook", class_name: str = "") -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        line = f"[{timestamp}] ERROR: {message}\n"
        print(line, end="")
        self._errors.append(
            {
                "timestamp": timestamp,
                "step": step,
                "class": class_name,
                "error": message,
            }
        )
        self.write_errors()

    def write_errors(self) -> None:
        with self.error_log_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["timestamp", "step", "class", "error"])
            writer.writeheader()
            writer.writerows(self._errors)


def jpf_path(value: Path | str) -> str:
    return str(value).replace("\\", "/")


def resolve_jpf_home(logger: JpfNotebookLogger, workspace_dir: Path) -> Path:
    candidates = [
        project_runtimes_root() / "jpf-core",
        workspace_dir / "jpf-core",
        Path.home() / ".jpf" / "jpf-core",
    ]
    for candidate in candidates:
        if (candidate / "build" / "RunJPF.jar").exists():
            logger.info(f"Using existing JPF installation: {candidate}")
            return candidate.resolve()
    return candidates[0].resolve()


def resolve_gradle_wrapper(jpf_home: Path) -> list[str]:
    if platform.system() == "Windows":
        wrapper = jpf_home / "gradlew.bat"
    else:
        wrapper = jpf_home / "gradlew"
    if wrapper.exists():
        if platform.system() != "Windows":
            wrapper.chmod(wrapper.stat().st_mode | 0o111)
        return [str(wrapper)]
    return ["gradle"]


def ensure_jpf_installed(
    env: dict[str, str],
    logger: JpfNotebookLogger,
    workspace_dir: Path,
    jpf_repo_url: str = "https://github.com/javapathfinder/jpf-core.git",
    jpf_branch: str = "java-17",
) -> JpfInstallStatus:
    workspace_dir.mkdir(parents=True, exist_ok=True)
    jpf_home = resolve_jpf_home(logger, workspace_dir)
    run_jpf_jar = jpf_home / "build" / "RunJPF.jar"
    site_properties = workspace_dir / "jpf_site.properties"

    status = JpfInstallStatus(
        jpf_home=jpf_home,
        run_jpf_jar=run_jpf_jar,
        site_properties=site_properties,
        install_command=["git", "clone", "--depth", "1", "--branch", jpf_branch, jpf_repo_url, str(jpf_home)],
        build_command=[*resolve_gradle_wrapper(jpf_home), "buildJars", "-x", "test"],
    )

    if not run_jpf_jar.exists():
        if jpf_home.exists():
            shutil.rmtree(jpf_home)
        install_result = run_shell_command(status.install_command, workspace_dir.parent, env, logger, "jpf_install")
        status.install_result = install_result
        status.install_success = install_result.exit_code == 0
        if not status.install_success:
            return status
    else:
        status.install_success = True

    if not run_jpf_jar.exists():
        build_result = run_shell_command(status.build_command, jpf_home, env, logger, "jpf_build")
        status.build_result = build_result
        status.build_success = build_result.exit_code == 0 and run_jpf_jar.exists()
    else:
        status.build_success = True

    site_properties.write_text(f"jpf-core = {jpf_path(jpf_home)}\n", encoding="utf-8")
    return status


def extract_class_name(java_path: Path) -> str:
    try:
        text = java_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return java_path.stem
    match = CLASS_NAME_RE.search(text)
    return match.group(1) if match else java_path.stem


def has_main_method(java_path: Path) -> bool:
    try:
        text = java_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return bool(MAIN_METHOD_RE.search(text))


def build_java_inventory(java_files: list[Path]) -> list[JavaClassInfo]:
    rows: list[JavaClassInfo] = []
    for path in java_files:
        package = extract_package_name(path)
        class_name = extract_class_name(path)
        qualified = f"{package}.{class_name}" if package else class_name
        rows.append(
            JavaClassInfo(
                file_path=path,
                package=package,
                class_name=class_name,
                qualified_name=qualified,
                has_main=has_main_method(path),
            )
        )
    return rows


def save_java_inventory(java_classes: list[JavaClassInfo], output_csv: Path) -> None:
    rows = [
        {
            "file_path": str(item.file_path),
            "package": item.package,
            "class_name": item.class_name,
        }
        for item in java_classes
    ]
    pd.DataFrame(rows).to_csv(output_csv, index=False)


def count_packages(java_classes: list[JavaClassInfo]) -> int:
    return len({item.package for item in java_classes if item.package})


def compute_repository_summary(
    repo_path: Path,
    java_classes: list[JavaClassInfo],
    build_tool: str,
    java_version: str,
) -> dict[str, Any]:
    total_size = sum(item.file_path.stat().st_size for item in java_classes if item.file_path.exists())
    return {
        "repository_name": repo_path.name,
        "repository_path": str(repo_path),
        "java_version": java_version.replace("\n", " | "),
        "build_tool": build_tool,
        "total_packages": count_packages(java_classes),
        "total_classes": len(java_classes),
        "repository_size_bytes": total_size,
    }


def discover_compiled_classpath_dirs(repo_path: Path) -> list[Path]:
    dirs: list[Path] = []
    markers = ("/target/classes", "/build/classes/java/main", "/build/classes", "/out/production")
    for path in repo_path.rglob("classes"):
        if path.name != "classes" or not path.is_dir():
            continue
        if ".git" in path.parts:
            continue
        normalized = str(path).replace("\\", "/").lower()
        if any(marker in normalized for marker in markers):
            dirs.append(path.resolve())
    return sorted(set(dirs))


def discover_sourcepath_dirs(repo_path: Path) -> list[Path]:
    dirs: list[Path] = []
    for marker in ("src/main/java", "src"):
        for path in repo_path.rglob(marker):
            if path.is_dir() and ".git" not in path.parts:
                if path.name == "java" or path.name == "src":
                    dirs.append(path.resolve())
    unique: list[Path] = []
    for path in sorted(set(dirs), key=lambda item: len(str(item)), reverse=True):
        if not any(str(path).startswith(str(existing)) for existing in unique):
            unique.append(path)
    return sorted(unique)


def classpath_string(classpath_dirs: list[Path]) -> str:
    return ";".join(jpf_path(path) for path in classpath_dirs)


def sourcepath_string(source_dirs: list[Path]) -> str:
    return ";".join(jpf_path(path) for path in source_dirs)


def write_project_jpf_properties(
    repo_path: Path,
    classpath_dirs: list[Path],
    source_dirs: list[Path],
    module_name: str = "sut",
) -> Path:
    properties_path = repo_path / "jpf.properties"
    content = "\n".join(
        [
            f"{module_name} = {jpf_path(repo_path)}",
            f"{module_name}.classpath = {classpath_string(classpath_dirs)}",
            f"{module_name}.sourcepath = {sourcepath_string(source_dirs)}",
            "listener.autoload = gov.nasa.jpf.listener.CoverageAnalyzer",
            "",
        ]
    )
    properties_path.write_text(content, encoding="utf-8")
    return properties_path


def write_jpf_application_file(
    output_dir: Path,
    qualified_name: str,
    classpath_dirs: list[Path],
    source_dirs: list[Path],
    target_args: str = "",
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = qualified_name.replace(".", "_")
    jpf_path_file = output_dir / f"{safe_name}.jpf"
    lines = [
        "@using = jpf-core",
        f"target = {qualified_name}",
    ]
    if target_args:
        lines.append(f"target.args = {target_args}")
    lines.extend(
        [
            f"classpath = {classpath_string(classpath_dirs)}",
            f"sourcepath = {sourcepath_string(source_dirs)}",
            "report.console.start = jpf,sut",
            "report.console.property_violation = error,trace",
            "search.multiple_errors = true",
            "",
        ]
    )
    jpf_path_file.write_text("\n".join(lines), encoding="utf-8")
    return jpf_path_file


def execute_compile_only(
    repo_path: Path,
    build_tool: str,
    env: dict[str, str],
    logger: JpfNotebookLogger,
) -> tuple[CommandResult, str]:
    if build_tool == "Maven":
        command = [*resolve_maven_command(repo_path, logger), "clean", "compile", "test-compile"]
    else:
        command = [*resolve_gradle_command(repo_path, logger), "clean", "classes", "testClasses"]
    result = run_shell_command(command, repo_path, env, logger, "build")
    raw = "\n".join(
        [
            f"===== {' '.join(command)} =====",
            combine_streams(result.stdout, result.stderr),
        ]
    )
    return result, raw


def run_jpf_for_class(
    install: JpfInstallStatus,
    jpf_file: Path,
    env: dict[str, str],
    logger: JpfNotebookLogger,
    qualified_name: str,
) -> JpfClassRun:
    command = [
        "java",
        "-jar",
        jpf_path(install.run_jpf_jar),
        f"+site={jpf_path(install.site_properties)}",
        jpf_path(jpf_file),
    ]
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
        cwd=str(jpf_file.parent),
    )
    elapsed = round(time.perf_counter() - started, 5)
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    combined = combine_streams(stdout, stderr)
    success = "search finished" in combined.lower() and completed.returncode == 0
    metrics = parse_explicit_jpf_metrics(combined, qualified_name)
    if not success and completed.returncode != 0:
        logger.error(combined or f"JPF failed with exit code {completed.returncode}", step="jpf_run", class_name=qualified_name)
    return JpfClassRun(
        qualified_name=qualified_name,
        jpf_file=jpf_file,
        command=command,
        stdout=stdout,
        stderr=stderr,
        exit_code=completed.returncode,
        execution_time_seconds=elapsed,
        success=success,
        metrics=metrics,
    )


def execute_jpf_for_classes(
    install: JpfInstallStatus,
    java_classes: list[JavaClassInfo],
    classpath_dirs: list[Path],
    source_dirs: list[Path],
    env: dict[str, str],
    logger: JpfNotebookLogger,
    jpf_config_dir: Path,
) -> tuple[list[JpfClassRun], str]:
    chunks: list[str] = []
    runs: list[JpfClassRun] = []
    for item in java_classes:
        header = f"\n{'=' * 80}\nJPF RUN: {item.qualified_name}\n{'=' * 80}\n"
        chunks.append(header)
        if not item.has_main:
            message = f"Skipping JPF execution: {item.qualified_name} has no public static void main method."
            logger.error(message, step="jpf_config", class_name=item.qualified_name)
            chunks.append(message + "\n")
            continue
        if not classpath_dirs:
            message = f"Skipping JPF execution: no compiled classpath directories found for {item.qualified_name}."
            logger.error(message, step="jpf_config", class_name=item.qualified_name)
            chunks.append(message + "\n")
            continue

        target_args = "--skip-verify" if item.qualified_name.endswith("JacocoTrigger") else ""
        jpf_file = write_jpf_application_file(
            jpf_config_dir,
            item.qualified_name,
            classpath_dirs,
            source_dirs,
            target_args=target_args,
        )
        run = run_jpf_for_class(install, jpf_file, env, logger, item.qualified_name)
        logger.info(f"Executed JPF for {item.qualified_name} in {run.execution_time_seconds}s")
        runs.append(run)
        chunks.append(f"===== {' '.join(run.command)} =====\n")
        chunks.append(combine_streams(run.stdout, run.stderr))
        chunks.append("\n")
    return runs, "".join(chunks)


def parse_explicit_jpf_metrics(raw_output: str, source_class: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    stats_match = STATISTICS_BLOCK_RE.search(raw_output)
    stats_text = stats_match.group(1) if stats_match else raw_output

    def add(metric_name: str, metric_value: str, method: str = "") -> None:
        rows.append(
            {
                "metric_name": metric_name,
                "metric_value": metric_value,
                "source_class": source_class,
                "method": method,
            }
        )

    states_match = STATES_RE.search(stats_text)
    if states_match:
        add("Visited States", states_match.group(2), "statistics.states")
        add("New States", states_match.group(1), "statistics.states")
        add("Backtracked States", states_match.group(3), "statistics.states")
        add("End States", states_match.group(4), "statistics.states")

    depth_match = SEARCH_DEPTH_RE.search(stats_text)
    if depth_match:
        add("Search Depth", depth_match.group(1), "statistics.search")

    choice_match = CHOICE_GENERATORS_RE.search(stats_text)
    if choice_match:
        add("Choice Generators", choice_match.group(1).strip(), "statistics.choice_generators")

    transitions = TRANSITION_COUNT_RE.findall(raw_output)
    if transitions:
        add("Transition Count", str(len(transitions)), "trace.transition")
        add("Path Count", str(len(set(transitions))), "trace.transition")

    errors = ERROR_STATE_RE.findall(raw_output)
    if errors:
        add("Error States", str(len(errors)), "results.error")

    exceptions = EXCEPTION_RE.findall(raw_output)
    if exceptions:
        add("Exception States", str(len(set(exceptions))), "results.exception")

    if DEADLOCK_RE.search(raw_output):
        add("Deadlocks", "1", "results.deadlock")

    if "search started" in raw_output.lower():
        add("Execution Paths", str(len(TRACE_SECTION_RE.findall(raw_output)) or len(transitions)), "search")

    if stats_match:
        add("Search Statistics", stats_match.group(1).strip(), "statistics")

    elapsed_match = re.search(r"elapsed time:\s*(.+)", stats_text, re.IGNORECASE)
    if elapsed_match:
        add("Elapsed Time", elapsed_match.group(1).strip(), "statistics.elapsed_time")

    return rows


def extract_verbatim_sections(raw_console: str, output_dir: Path) -> dict[str, bool]:
    ensure_output_dir(output_dir)
    created: dict[str, bool] = {}

    traces = TRACE_SECTION_RE.findall(raw_console)
    if traces:
        path = output_dir / "error_trace.txt"
        path.write_text("\n".join(traces), encoding="utf-8")
        created["error_trace.txt"] = True

    transitions = [line for line in raw_console.splitlines() if "transition #" in line.lower()]
    if transitions:
        path = output_dir / "path_report.txt"
        path.write_text("\n".join(transitions) + "\n", encoding="utf-8")
        created["path_report.txt"] = True

    state_lines = [line for line in raw_console.splitlines() if line.strip().lower().startswith("states:")]
    if state_lines:
        path = output_dir / "visited_states.txt"
        path.write_text("\n".join(state_lines) + "\n", encoding="utf-8")
        created["visited_states.txt"] = True

    graph_lines = [
        line
        for line in raw_console.splitlines()
        if "choice generators" in line.lower() or "gov.nasa.jpf.vm.choice" in line
    ]
    if graph_lines:
        path = output_dir / "search_graph.txt"
        path.write_text("\n".join(graph_lines) + "\n", encoding="utf-8")
        created["search_graph.txt"] = True

    for name in JPF_OPTIONAL_ARTIFACTS:
        created.setdefault(name, (output_dir / name).exists())
    return created


def copy_generated_jpf_artifacts(search_dirs: list[Path], output_dir: Path) -> dict[str, bool]:
    copied: dict[str, bool] = {}
    for artifact in JPF_OPTIONAL_ARTIFACTS:
        destination = output_dir / artifact
        if destination.exists():
            copied[artifact] = True
            continue
        for directory in search_dirs:
            source = directory / artifact
            if source.exists():
                shutil.copy2(source, destination)
                copied[artifact] = True
                break
        copied.setdefault(artifact, destination.exists())
    return copied


def build_class_summary(runs: list[JpfClassRun]) -> pd.DataFrame:
    columns = [
        "Class",
        "Visited States",
        "Execution Paths",
        "Error States",
        "Exceptions",
        "Loops",
        "Search Depth",
        "Transitions",
        "JPF Success",
        "Raw Output Contains Statistics",
    ]
    if not runs:
        return pd.DataFrame(columns=columns)
    rows: list[dict[str, Any]] = []
    for run in runs:
        metric_map = {item["metric_name"]: item["metric_value"] for item in run.metrics}
        combined = combine_streams(run.stdout, run.stderr)
        rows.append(
            {
                "Class": run.qualified_name,
                "Visited States": metric_map.get("Visited States", ""),
                "Execution Paths": metric_map.get("Execution Paths", ""),
                "Error States": metric_map.get("Error States", ""),
                "Exceptions": metric_map.get("Exception States", ""),
                "Loops": metric_map.get("Backtracked States", ""),
                "Search Depth": metric_map.get("Search Depth", ""),
                "Transitions": metric_map.get("Transition Count", ""),
                "JPF Success": "Yes" if run.success else "No",
                "Raw Output Contains Statistics": "Yes" if "statistics" in combined.lower() else "No",
            }
        )
    return pd.DataFrame(rows)


def build_repository_metrics(
    java_classes: list[JavaClassInfo],
    runs: list[JpfClassRun],
    total_execution_time: float,
) -> pd.DataFrame:
    metrics_rows = [metric for run in runs for metric in run.metrics]
    metric_map: dict[str, list[str]] = {}
    for row in metrics_rows:
        metric_map.setdefault(row["metric_name"], []).append(row["metric_value"])

    def sum_numeric(name: str) -> int:
        total = 0
        for value in metric_map.get(name, []):
            try:
                total += int(value)
            except ValueError:
                continue
        return total

    summary = {
        "Total Classes": len(java_classes),
        "Total Methods": "",
        "Total Execution Paths": sum_numeric("Execution Paths"),
        "Visited States": sum_numeric("Visited States"),
        "Error States": sum_numeric("Error States"),
        "Exceptions": sum_numeric("Exception States"),
        "Loop Paths": sum_numeric("Backtracked States"),
        "Execution Time": total_execution_time,
        "Classes With Main": sum(1 for item in java_classes if item.has_main),
        "Classes Executed By JPF": len(runs),
    }
    return pd.DataFrame([summary])


def validate_path_metrics(raw_console: str, source_file: str = "jpf_console_output.txt") -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for metric in PATH_METRICS:
        evidence_parts: list[str] = []
        for label, pattern in METRIC_EVIDENCE_PATTERNS.get(metric, []):
            match = pattern.search(raw_console)
            if match:
                evidence_parts.append(f"{label}: {match.group(0)[:180]}")
        if evidence_parts:
            status = "Supported"
            evidence = " | ".join(evidence_parts)
            comments = "Explicit JPF output matched without inference."
        else:
            status = "No Evidence Found"
            evidence = ""
            comments = "No explicit JPF output matched this metric keyword/pattern."
        rows.append(
            {
                "Metric": metric,
                "Supported": status,
                "Evidence": evidence,
                "Source File": source_file,
                "Comments": comments,
            }
        )
    return pd.DataFrame(rows)


def preview_raw_output(raw_text: str, max_lines: int, source_path: Path) -> None:
    lines = raw_text.splitlines()
    print(f"Saved raw output: {source_path} ({len(lines)} lines)")
    preview = "\n".join(lines[:max_lines])
    print(preview)
    if len(lines) > max_lines:
        print(f"... truncated preview ({len(lines) - max_lines} additional lines in file)")


def build_dashboard_table(
    repo_stats: dict[str, Any],
    class_summary: pd.DataFrame,
    repository_metrics: pd.DataFrame,
) -> pd.DataFrame:
    repo_metric_row = repository_metrics.iloc[0].to_dict() if not repository_metrics.empty else {}
    depth_value = ""
    if not class_summary.empty and "Search Depth" in class_summary.columns:
        depth_values = class_summary["Search Depth"].replace("", pd.NA).dropna()
        if not depth_values.empty:
            depth_value = depth_values.iloc[0]
    return pd.DataFrame(
        [
            {
                "Metric": "Repository",
                "Value": repo_stats.get("repository_name", ""),
            },
            {
                "Metric": "Build Tool",
                "Value": repo_stats.get("build_tool", ""),
            },
            {
                "Metric": "Java Classes",
                "Value": repo_stats.get("total_classes", ""),
            },
            {
                "Metric": "Execution Paths",
                "Value": repo_metric_row.get("Total Execution Paths", ""),
            },
            {
                "Metric": "Visited States",
                "Value": repo_metric_row.get("Visited States", ""),
            },
            {
                "Metric": "Error States",
                "Value": repo_metric_row.get("Error States", ""),
            },
            {
                "Metric": "Exceptions",
                "Value": repo_metric_row.get("Exceptions", ""),
            },
            {
                "Metric": "Loop Paths",
                "Value": repo_metric_row.get("Loop Paths", ""),
            },
            {
                "Metric": "Search Depth",
                "Value": depth_value,
            },
        ]
    )
