from __future__ import annotations

import csv
import os
import platform
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

import pandas as pd
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

EXCLUDED_DIR_NAMES = {
    ".git", "target", "build", "bin", ".idea", ".gradle", ".mvn", "out", "node_modules",
}
COUNTER_TYPES = ["INSTRUCTION", "BRANCH", "LINE", "METHOD", "CLASS", "COMPLEXITY"]
PY = sys.executable
PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)


@dataclass
class CommandResult:
    command: list[str]
    stdout: str
    stderr: str
    exit_code: int
    execution_time_seconds: float


@dataclass
class BuildStatus:
    build_tool: str
    build_command: list[str]
    jacoco_command: list[str]
    build_result: CommandResult | None = None
    jacoco_result: CommandResult | None = None
    build_success: bool = False
    test_success: bool = False
    report_generated: bool = False
    report_dir: Path | None = None
    jacoco_exec: Path | None = None
    jacoco_xml: Path | None = None
    jacoco_csv: Path | None = None
    index_html: Path | None = None


class NotebookLogger:
    def __init__(self, error_log_path: Path) -> None:
        self.error_log_path = error_log_path
        self.error_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._errors: list[dict[str, str]] = []
        self.write_errors()

    def info(self, message: str) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"[{timestamp}] INFO: {message}")

    def error(self, message: str, step: str = "notebook") -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        line = f"[{timestamp}] ERROR: {message}\n"
        print(line, end="")
        self._errors.append({"timestamp": timestamp, "step": step, "error": message})
        self.write_errors()

    def write_errors(self) -> None:
        with self.error_log_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["timestamp", "step", "error"])
            writer.writeheader()
            writer.writerows(self._errors)


def ensure_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)


def project_runtimes_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    candidates: list[Path] = []
    for parent in [current, *current.parents]:
        candidate = parent / "runtimes"
        if candidate.is_dir():
            candidates.append(candidate)
    for candidate in candidates:
        if (candidate / "jdk-21").exists() or any(candidate.glob("apache-maven-*")):
            return candidate
    return candidates[0] if candidates else current / "runtimes"


def configure_java_runtime(logger: NotebookLogger) -> dict[str, str]:
    runtimes = project_runtimes_root()
    env = os.environ.copy()
    jdk_candidates = [
        runtimes / "jdk-21",
        Path(env.get("JAVA_HOME", "")),
        Path(r"C:\Program Files\Eclipse Adoptium\jdk-17.0.19.10-hotspot"),
    ]
    for candidate in jdk_candidates:
        java_bin = candidate / "bin"
        java_exe = java_bin / ("java.exe" if platform.system() == "Windows" else "java")
        if java_exe.exists():
            env["JAVA_HOME"] = str(candidate)
            env["PATH"] = str(java_bin) + os.pathsep + env.get("PATH", "")
            logger.info(f"Using JAVA_HOME={candidate}")
            break
    else:
        logger.info("Using system Java from PATH.")
    return env


def java_version_text(env: dict[str, str]) -> str:
    completed = subprocess.run(
        ["java", "-version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )
    return combine_streams(completed.stdout, completed.stderr).strip()


def resolve_maven_command(repo_path: Path, logger: NotebookLogger) -> list[str]:
    if platform.system() == "Windows":
        wrapper = repo_path / "mvnw.cmd"
        if wrapper.exists():
            return [str(wrapper)]
    else:
        wrapper = repo_path / "mvnw"
        if wrapper.exists():
            return [str(wrapper)]
    runtimes = project_runtimes_root(repo_path)
    bundled = runtimes / "apache-maven-3.9.6" / "bin" / ("mvn.cmd" if platform.system() == "Windows" else "mvn")
    if bundled.exists():
        logger.info(f"Using bundled Maven: {bundled}")
        return [str(bundled)]
    return ["mvn"]


def resolve_gradle_command(repo_path: Path, logger: NotebookLogger) -> list[str]:
    if platform.system() == "Windows":
        wrapper = repo_path / "gradlew.bat"
    else:
        wrapper = repo_path / "gradlew"
    if wrapper.exists():
        if platform.system() != "Windows":
            wrapper.chmod(wrapper.stat().st_mode | 0o111)
        logger.info(f"Using Gradle wrapper: {wrapper}")
        return [str(wrapper)]
    return ["gradle"]


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
    logger.info(f"Cloning {repo_url} into {clone_path}")
    clone_kwargs: dict[str, Any] = {"depth": clone_depth} if clone_depth else {}
    try:
        Repo.clone_from(repo_url, clone_path, **clone_kwargs)
    except GitCommandError as exc:
        logger.error(f"Git clone failed: {exc}", step="clone")
        raise
    return clone_path.resolve()


def validate_local_repo_path(local_repo_path: Path, logger: NotebookLogger) -> Path:
    if not local_repo_path.exists():
        msg = f"Local repository path does not exist: {local_repo_path}"
        logger.error(msg, step="repository")
        raise FileNotFoundError(msg)
    if not local_repo_path.is_dir():
        msg = f"Local repository path is not a directory: {local_repo_path}"
        logger.error(msg, step="repository")
        raise NotADirectoryError(msg)
    build_files = [
        local_repo_path / "pom.xml",
        local_repo_path / "build.gradle",
        local_repo_path / "build.gradle.kts",
    ]
    if not any(path.exists() for path in build_files):
        msg = "No pom.xml, build.gradle, or build.gradle.kts found in repository."
        logger.error(msg, step="repository")
        raise FileNotFoundError(msg)
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


def detect_build_tool(repo_path: Path) -> str:
    if (repo_path / "pom.xml").exists():
        return "Maven"
    if (repo_path / "build.gradle.kts").exists():
        return "Gradle Kotlin DSL"
    if (repo_path / "build.gradle").exists():
        return "Gradle"
    raise FileNotFoundError("Unable to detect Maven or Gradle build files.")


def discover_java_files(repo_path: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo_path.rglob("*.java"):
        if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            continue
        files.append(path.resolve())
    return sorted(files)


def extract_package_name(java_path: Path) -> str:
    try:
        text = java_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    match = PACKAGE_RE.search(text)
    return match.group(1) if match else ""


def save_java_inventory(java_files: list[Path], output_csv: Path) -> None:
    rows = [
        {
            "file_path": str(path),
            "file_name": path.name,
            "package": extract_package_name(path),
            "directory": str(path.parent),
        }
        for path in java_files
    ]
    pd.DataFrame(rows).to_csv(output_csv, index=False)


def count_all_files(repo_path: Path) -> int:
    total = 0
    for path in repo_path.rglob("*"):
        if path.is_file() and not any(part in EXCLUDED_DIR_NAMES for part in path.parts):
            total += 1
    return total


def compute_repository_stats(
    repo_path: Path,
    java_files: list[Path],
    build_tool: str,
    java_version: str,
) -> dict[str, Any]:
    total_size = sum(path.stat().st_size for path in java_files)
    return {
        "repository_name": repo_path.name,
        "repository_location": str(repo_path),
        "build_tool": build_tool,
        "java_version": java_version.replace("\n", " | "),
        "total_java_files": len(java_files),
        "total_files": count_all_files(repo_path),
        "repository_size_bytes": total_size,
    }


def combine_streams(stdout: str, stderr: str) -> str:
    raw = stdout
    if stderr:
        if raw and not raw.endswith("\n"):
            raw += "\n"
        raw += stderr
    return raw


def run_shell_command(
    command: list[str],
    cwd: Path,
    env: dict[str, str],
    logger: NotebookLogger,
    step: str,
) -> CommandResult:
    logger.info(f"Executing ({step}): {' '.join(command)}")
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )
    elapsed = round(time.perf_counter() - started, 5)
    result = CommandResult(
        command=command,
        stdout=completed.stdout,
        stderr=completed.stderr,
        exit_code=completed.returncode,
        execution_time_seconds=elapsed,
    )
    if completed.returncode != 0:
        logger.error(
            combine_streams(completed.stdout, completed.stderr) or f"Command failed with exit code {completed.returncode}",
            step=step,
        )
    return result


def find_jacoco_report_dirs(repo_path: Path) -> list[Path]:
    report_dirs: list[Path] = []
    for xml_path in repo_path.rglob("jacoco.xml"):
        if ".git" in xml_path.parts:
            continue
        parent = str(xml_path.parent).replace("\\", "/")
        if "/site/jacoco" in parent or "/reports/jacoco" in parent or parent.endswith("/jacoco"):
            report_dirs.append(xml_path.parent.resolve())
    return sorted(set(report_dirs))


def find_jacoco_exec_files(repo_path: Path) -> list[Path]:
    exec_files: list[Path] = []
    for exec_path in repo_path.rglob("jacoco.exec"):
        if ".git" in exec_path.parts:
            continue
        exec_files.append(exec_path.resolve())
    return sorted(exec_files)


def choose_primary_report_dir(report_dirs: list[Path]) -> Path | None:
    if not report_dirs:
        return None
    best_dir = report_dirs[0]
    best_score = -1
    for report_dir in report_dirs:
        xml_path = report_dir / "jacoco.xml"
        if not xml_path.exists():
            continue
        counters = parse_counter_map(xml_path)
        score = sum(counters.get(counter, {}).get("covered", 0) + counters.get(counter, {}).get("missed", 0) for counter in COUNTER_TYPES)
        if score > best_score:
            best_score = score
            best_dir = report_dir
    return best_dir


def choose_primary_exec(exec_files: list[Path], report_dir: Path | None) -> Path | None:
    if report_dir is not None:
        maven_exec = report_dir.parent.parent / "jacoco.exec"
        if maven_exec.exists():
            return maven_exec.resolve()
        gradle_exec = report_dir.parent / "jacoco.exec"
        if gradle_exec.exists():
            return gradle_exec.resolve()
    return exec_files[-1] if exec_files else None


def coverage_percent(covered: int, missed: int) -> float:
    total = covered + missed
    if total == 0:
        return 100.0
    return round(covered * 100.0 / total, 2)


def parse_counter_map(xml_path: Path) -> dict[str, dict[str, int]]:
    root = ET.parse(xml_path).getroot()
    counters: dict[str, dict[str, int]] = {}
    for counter in root.findall("counter"):
        counter_type = counter.get("type", "")
        counters[counter_type] = {
            "missed": int(counter.get("missed", "0")),
            "covered": int(counter.get("covered", "0")),
        }
    return counters


def counters_to_metrics_rows(counters: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
    label_map = {
        "INSTRUCTION": "Instruction",
        "BRANCH": "Branch",
        "LINE": "Line",
        "METHOD": "Method",
        "CLASS": "Class",
        "COMPLEXITY": "Complexity",
    }
    rows: list[dict[str, Any]] = []
    for counter_type in COUNTER_TYPES:
        values = counters.get(counter_type, {"missed": 0, "covered": 0})
        covered = values.get("covered", 0)
        missed = values.get("missed", 0)
        rows.append(
            {
                "metric_name": f"{label_map[counter_type]} Covered",
                "covered": covered,
                "missed": missed,
                "coverage_percent": coverage_percent(covered, missed),
            }
        )
    return rows


def element_counters(element: ET.Element) -> dict[str, dict[str, int]]:
    counters: dict[str, dict[str, int]] = {}
    for counter in element.findall("counter"):
        counter_type = counter.get("type", "")
        counters[counter_type] = {
            "missed": int(counter.get("missed", "0")),
            "covered": int(counter.get("covered", "0")),
        }
    return counters


def build_package_summary_rows(xml_path: Path) -> list[dict[str, Any]]:
    root = ET.parse(xml_path).getroot()
    rows: list[dict[str, Any]] = []
    for package in root.findall("package"):
        package_name = package.get("name", "").replace("/", ".")
        counters = element_counters(package)
        rows.append(
            {
                "package": package_name,
                "instruction_coverage": coverage_percent(
                    counters.get("INSTRUCTION", {}).get("covered", 0),
                    counters.get("INSTRUCTION", {}).get("missed", 0),
                ),
                "branch_coverage": coverage_percent(
                    counters.get("BRANCH", {}).get("covered", 0),
                    counters.get("BRANCH", {}).get("missed", 0),
                ),
                "line_coverage": coverage_percent(
                    counters.get("LINE", {}).get("covered", 0),
                    counters.get("LINE", {}).get("missed", 0),
                ),
                "method_coverage": coverage_percent(
                    counters.get("METHOD", {}).get("covered", 0),
                    counters.get("METHOD", {}).get("missed", 0),
                ),
                "class_coverage": coverage_percent(
                    counters.get("CLASS", {}).get("covered", 0),
                    counters.get("CLASS", {}).get("missed", 0),
                ),
                "complexity_coverage": coverage_percent(
                    counters.get("COMPLEXITY", {}).get("covered", 0),
                    counters.get("COMPLEXITY", {}).get("missed", 0),
                ),
            }
        )
    return rows


def build_class_summary_rows(xml_path: Path) -> list[dict[str, Any]]:
    root = ET.parse(xml_path).getroot()
    rows: list[dict[str, Any]] = []
    for package in root.findall("package"):
        package_name = package.get("name", "").replace("/", ".")
        for class_el in package.findall("class"):
            class_name = class_el.get("name", "").split("/")[-1]
            counters = element_counters(class_el)
            rows.append(
                {
                    "package": package_name,
                    "class": class_name,
                    "instruction_coverage": coverage_percent(
                        counters.get("INSTRUCTION", {}).get("covered", 0),
                        counters.get("INSTRUCTION", {}).get("missed", 0),
                    ),
                    "branch_coverage": coverage_percent(
                        counters.get("BRANCH", {}).get("covered", 0),
                        counters.get("BRANCH", {}).get("missed", 0),
                    ),
                    "line_coverage": coverage_percent(
                        counters.get("LINE", {}).get("covered", 0),
                        counters.get("LINE", {}).get("missed", 0),
                    ),
                    "method_coverage": coverage_percent(
                        counters.get("METHOD", {}).get("covered", 0),
                        counters.get("METHOD", {}).get("missed", 0),
                    ),
                    "complexity_coverage": coverage_percent(
                        counters.get("COMPLEXITY", {}).get("covered", 0),
                        counters.get("COMPLEXITY", {}).get("missed", 0),
                    ),
                }
            )
    return rows


def build_repository_metrics_row(
    xml_path: Path,
    repo_stats: dict[str, Any],
    total_execution_time: float,
) -> dict[str, Any]:
    root = ET.parse(xml_path).getroot()
    counters = parse_counter_map(xml_path)
    packages = root.findall("package")
    classes = root.findall(".//class")
    return {
        "Total Packages": len(packages),
        "Total Classes": len(classes),
        "Instruction Coverage %": coverage_percent(
            counters.get("INSTRUCTION", {}).get("covered", 0),
            counters.get("INSTRUCTION", {}).get("missed", 0),
        ),
        "Branch Coverage %": coverage_percent(
            counters.get("BRANCH", {}).get("covered", 0),
            counters.get("BRANCH", {}).get("missed", 0),
        ),
        "Line Coverage %": coverage_percent(
            counters.get("LINE", {}).get("covered", 0),
            counters.get("LINE", {}).get("missed", 0),
        ),
        "Method Coverage %": coverage_percent(
            counters.get("METHOD", {}).get("covered", 0),
            counters.get("METHOD", {}).get("missed", 0),
        ),
        "Class Coverage %": coverage_percent(
            counters.get("CLASS", {}).get("covered", 0),
            counters.get("CLASS", {}).get("missed", 0),
        ),
        "Complexity Coverage %": coverage_percent(
            counters.get("COMPLEXITY", {}).get("covered", 0),
            counters.get("COMPLEXITY", {}).get("missed", 0),
        ),
        "Execution Time (seconds)": total_execution_time,
        "Repository Name": repo_stats["repository_name"],
        "Build Tool": repo_stats["build_tool"],
    }


def copy_artifact(source: Path | None, destination: Path) -> bool:
    if source is None or not source.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return True


def execute_build_and_jacoco(
    repo_path: Path,
    build_tool: str,
    env: dict[str, str],
    logger: NotebookLogger,
) -> tuple[BuildStatus, str]:
    chunks: list[str] = []
    status = BuildStatus(build_tool=build_tool, build_command=[], jacoco_command=[])

    if build_tool == "Maven":
        maven = resolve_maven_command(repo_path, logger)
        status.build_command = [*maven, "clean", "test"]
        status.jacoco_command = [*maven, "clean", "test", "jacoco:report"]
    else:
        gradle = resolve_gradle_command(repo_path, logger)
        status.build_command = [*gradle, "clean", "test"]
        status.jacoco_command = [*gradle, "clean", "test", "jacocoTestReport"]

    build_result = run_shell_command(status.build_command, repo_path, env, logger, "build")
    status.build_result = build_result
    status.build_success = build_result.exit_code == 0
    status.test_success = "BUILD SUCCESS" in combine_streams(build_result.stdout, build_result.stderr) or build_result.exit_code == 0
    chunks.append(f"===== {' '.join(status.build_command)} =====")
    chunks.append(combine_streams(build_result.stdout, build_result.stderr))

    report_dirs = find_jacoco_report_dirs(repo_path)
    if not report_dirs and build_tool == "Maven":
        for module_pom in repo_path.rglob("pom.xml"):
            module_dir = module_pom.parent
            if module_dir == repo_path:
                continue
            module_text = module_pom.read_text(encoding="utf-8", errors="replace")
            if "jacoco-maven-plugin" not in module_text:
                continue
            jacoco_result = run_shell_command(
                [*resolve_maven_command(repo_path, logger), "jacoco:report"],
                module_dir,
                env,
                logger,
                "jacoco",
            )
            status.jacoco_result = jacoco_result
            chunks.append(f"===== module jacoco report {module_dir} =====")
            chunks.append(combine_streams(jacoco_result.stdout, jacoco_result.stderr))
        report_dirs = find_jacoco_report_dirs(repo_path)
        status.test_success = status.test_success or (status.jacoco_result.exit_code == 0 if status.jacoco_result else False)

    exec_files = find_jacoco_exec_files(repo_path)
    status.report_dir = choose_primary_report_dir(report_dirs)
    status.jacoco_exec = choose_primary_exec(exec_files, status.report_dir)
    if status.report_dir is not None:
        status.jacoco_xml = status.report_dir / "jacoco.xml"
        status.jacoco_csv = status.report_dir / "jacoco.csv"
        status.index_html = status.report_dir / "index.html"
        status.report_generated = status.jacoco_xml.exists()
    if not status.report_generated:
        logger.error("JaCoCo report files were not found after build.", step="jacoco")

    return status, "\n".join(chunks)


def collect_outputs(
    status: BuildStatus,
    repo_stats: dict[str, Any],
    output_dir: Path,
    total_execution_time: float,
    logger: NotebookLogger,
) -> dict[str, Any]:
    ensure_output_dir(output_dir)
    copied = {
        "jacoco.exec": copy_artifact(status.jacoco_exec, output_dir / "jacoco.exec"),
        "jacoco.xml": copy_artifact(status.jacoco_xml, output_dir / "jacoco.xml"),
        "jacoco.csv": copy_artifact(status.jacoco_csv, output_dir / "jacoco.csv"),
        "index.html": copy_artifact(status.index_html, output_dir / "index.html"),
    }
    if not copied["jacoco.xml"]:
        raise FileNotFoundError("Unable to copy jacoco.xml to outputs.")

    xml_path = output_dir / "jacoco.xml"
    metrics_df = pd.DataFrame(counters_to_metrics_rows(parse_counter_map(xml_path)))
    metrics_df.to_csv(output_dir / "jacoco_metrics.csv", index=False)

    package_df = pd.DataFrame(build_package_summary_rows(xml_path))
    package_df.to_csv(output_dir / "package_summary.csv", index=False)

    class_df = pd.DataFrame(build_class_summary_rows(xml_path))
    class_df.to_csv(output_dir / "class_summary.csv", index=False)

    repository_metrics = build_repository_metrics_row(xml_path, repo_stats, total_execution_time)
    pd.DataFrame([repository_metrics]).to_csv(output_dir / "repository_metrics.csv", index=False)

    return {
        "copied": copied,
        "metrics_df": metrics_df,
        "package_df": package_df,
        "class_df": class_df,
        "repository_metrics": repository_metrics,
    }


def preview_raw_output(raw_text: str, preview_lines: int, output_path: Path) -> None:
    lines = raw_text.splitlines()
    print(f"\n{'=' * 80}")
    print(f"RAW JACOCO CONSOLE OUTPUT PREVIEW (first {preview_lines} lines)")
    print(f"{'=' * 80}\n")
    if not lines:
        print("(empty raw output)")
        return
    print("\n".join(lines[:preview_lines]))
    remaining = len(lines) - preview_lines
    if remaining > 0:
        print(f"\n... ({remaining} more lines saved to {output_path})")
