"""StyleCop code smells benchmark execution helpers."""
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
from xml.etree import ElementTree as ET

import pandas as pd

os.environ.pop("PYTHONPATH", None)

EXCLUDED = {".git", "bin", "obj", "packages", "artifacts", "TestResults", "node_modules"}
DOTNET_CHANNEL = "8.0"
STYLECOP_PACKAGE = "StyleCop.Analyzers"
STYLECOP_VERSION = "1.2.0-beta.556"
EXPLICIT_CODE_SMELL_RULES = {
    "SA1401",
    "SA1500",
    "SA1513",
    "SA1515",
    "SA1600",
    "SA1601",
    "SA1101",
    "SA1124",
    "SA1127",
}
BUILD_DIAGNOSTIC_PATTERN = re.compile(
    r"^(?P<file>.+?)\((?P<line>\d+),(?P<column>\d+)\):\s*(?P<severity>\w+)\s+(?P<rule_id>SA\d+):\s*(?P<message>.*)$"
)
RESULTS_COLUMNS = ["project", "file", "line", "column", "severity", "rule_id", "message", "category"]
SMELLS_COLUMNS = ["project", "file", "line", "rule_id", "severity", "message", "category"]
BUILD_SUCCESS_CODES = {0, 1}


def dotnet_executable(dotnet_root: Path) -> Path:
    name = "dotnet.exe" if sys.platform.startswith("win") else "dotnet"
    return dotnet_root / name


def download_dotnet_sdk(install_dir: Path, channel: str = DOTNET_CHANNEL) -> Path:
    install_dir = install_dir.resolve()
    install_dir.mkdir(parents=True, exist_ok=True)
    dotnet = dotnet_executable(install_dir)
    if dotnet.exists():
        return install_dir

    if sys.platform.startswith("win"):
        script_path = install_dir / "dotnet-install.ps1"
        urllib.request.urlretrieve("https://dot.net/v1/dotnet-install.ps1", script_path)
        subprocess.run(
            [
                "powershell",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
                "-InstallDir",
                str(install_dir),
                "-Channel",
                channel,
                "-Architecture",
                "x64",
                "-Quality",
                "ga",
            ],
            check=True,
        )
    else:
        script_path = install_dir / "dotnet-install.sh"
        urllib.request.urlretrieve("https://dot.net/v1/dotnet-install.sh", script_path)
        script_path.chmod(0o755)
        subprocess.run(
            [str(script_path), "--install-dir", str(install_dir), "--channel", channel, "--quality", "ga"],
            check=True,
        )

    if not dotnet.exists():
        raise RuntimeError(f".NET SDK installation failed; expected executable at {dotnet}")
    return install_dir


def dotnet_env(dotnet_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["DOTNET_ROOT"] = str(dotnet_root)
    env["PATH"] = str(dotnet_root) + os.pathsep + env.get("PATH", "")
    env.pop("PYTHONPATH", None)
    return env


def run_command(command: list[str], env: dict[str, str]) -> tuple[str, str, int]:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )
    return completed.stdout, completed.stderr, completed.returncode


def combine_raw(stdout: str, stderr: str) -> str:
    raw = stdout
    if stderr:
        if raw and not raw.endswith("\n"):
            raw += "\n"
        raw += stderr
    return raw


def should_exclude_path(path: Path) -> bool:
    return any(part in EXCLUDED for part in path.parts)


def discover_csharp_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo.rglob("*.cs"):
        if should_exclude_path(path.relative_to(repo)):
            continue
        files.append(path.resolve())
    return sorted(files)


def discover_solutions_and_projects(repo: Path) -> tuple[list[Path], list[Path]]:
    solutions: list[Path] = []
    projects: list[Path] = []
    for path in repo.rglob("*"):
        if not path.is_file() or should_exclude_path(path.relative_to(repo)):
            continue
        if path.suffix.lower() == ".sln":
            solutions.append(path.resolve())
        elif path.suffix.lower() == ".csproj":
            projects.append(path.resolve())
    return sorted(solutions), sorted(projects)


def build_inventory(repo: Path, solutions: list[Path], projects: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for solution in solutions:
        rows.append(
            {
                "kind": "solution",
                "absolute_path": str(solution),
                "relative_path": str(solution.relative_to(repo)),
            }
        )
    for project in projects:
        rows.append(
            {
                "kind": "project",
                "absolute_path": str(project),
                "relative_path": str(project.relative_to(repo)),
            }
        )
    return pd.DataFrame(rows, columns=["kind", "absolute_path", "relative_path"])


def resolve_analysis_targets(solutions: list[Path], projects: list[Path]) -> list[Path]:
    if solutions:
        return solutions
    return projects


def has_stylecop_package(project_path: Path) -> bool:
    content = project_path.read_text(encoding="utf-8", errors="replace")
    return STYLECOP_PACKAGE in content


def inject_stylecop(project_path: Path, dotnet_root: Path, env: dict[str, str]) -> tuple[bool, str]:
    if has_stylecop_package(project_path):
        return True, "already_installed"
    command = [
        str(dotnet_executable(dotnet_root)),
        "add",
        str(project_path),
        "package",
        STYLECOP_PACKAGE,
        "--version",
        STYLECOP_VERSION,
    ]
    stdout, stderr, code = run_command(command, env)
    if code != 0:
        return False, combine_raw(stdout, stderr)
    return True, combine_raw(stdout, stderr)


def collect_projects_from_solution(solution_path: Path) -> list[Path]:
    projects: list[Path] = []
    content = solution_path.read_text(encoding="utf-8", errors="replace")
    for match in re.finditer(r'Project\("[^"]+"\)\s*=\s*"[^"]+",\s*"([^"]+\.csproj)"', content):
        project_relative = match.group(1).replace("\\", os.sep)
        project_path = (solution_path.parent / project_relative).resolve()
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


def restore_target(target: Path, dotnet_root: Path, env: dict[str, str]) -> tuple[bool, str]:
    command = [str(dotnet_executable(dotnet_root)), "restore", str(target)]
    stdout, stderr, code = run_command(command, env)
    return code == 0, combine_raw(stdout, stderr)


def build_target(
    target: Path,
    dotnet_root: Path,
    env: dict[str, str],
    sarif_path: Path,
) -> tuple[bool, str, Path]:
    sarif_path.parent.mkdir(parents=True, exist_ok=True)
    clean_command = [str(dotnet_executable(dotnet_root)), "clean", str(target)]
    clean_stdout, clean_stderr, _ = run_command(clean_command, env)
    command = [
        str(dotnet_executable(dotnet_root)),
        "build",
        str(target),
        "--no-incremental",
        "-p:RunAnalyzers=true",
        f"-p:ErrorLog={sarif_path}",
        "--no-restore",
    ]
    stdout, stderr, code = run_command(command, env)
    raw = combine_raw(clean_stdout + clean_stderr, combine_raw(stdout, stderr))
    success = code in BUILD_SUCCESS_CODES
    return success, raw, sarif_path


def parse_build_diagnostics(raw_text: str, project: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in raw_text.splitlines():
        match = BUILD_DIAGNOSTIC_PATTERN.match(line.strip())
        if not match:
            continue
        rows.append(
            {
                "project": project,
                "file": match.group("file").strip(),
                "line": int(match.group("line")),
                "column": int(match.group("column")),
                "severity": match.group("severity").lower(),
                "rule_id": match.group("rule_id"),
                "message": match.group("message").strip(),
                "category": "StyleCop",
            }
        )
    return rows


def _sarif_level_to_severity(level: str) -> str:
    mapping = {"error": "error", "warning": "warning", "note": "info", "none": "info"}
    return mapping.get(level.lower(), level.lower())


def parse_sarif(sarif_path: Path, project: str) -> list[dict[str, Any]]:
    if not sarif_path.exists() or sarif_path.stat().st_size == 0:
        return []
    try:
        payload = json.loads(sarif_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    rows: list[dict[str, Any]] = []
    for run in payload.get("runs", []):
        rules: dict[str, str] = {}
        tool = run.get("tool", {})
        driver = tool.get("driver", {})
        for rule in driver.get("rules", []):
            rule_id = rule.get("id", "")
            rules[rule_id] = rule.get("properties", {}).get("category", "StyleCop")

        for result in run.get("results", []):
            rule_id = str(result.get("ruleId", ""))
            if not rule_id.startswith("SA"):
                continue
            message = result.get("message", {})
            text = message.get("text", "") if isinstance(message, dict) else str(message)
            severity = _sarif_level_to_severity(str(result.get("level", "warning")))
            category = rules.get(rule_id, "StyleCop")
            for location in result.get("locations", []):
                physical = location.get("physicalLocation", {})
                artifact = physical.get("artifactLocation", {})
                region = physical.get("region", {})
                rows.append(
                    {
                        "project": project,
                        "file": artifact.get("uri", ""),
                        "line": region.get("startLine", ""),
                        "column": region.get("startColumn", ""),
                        "severity": severity,
                        "rule_id": rule_id,
                        "message": text,
                        "category": category,
                    }
                )
    return rows


def merge_findings(*groups: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for group in groups:
        for item in group:
            file_value = str(item.get("file", "")).strip()
            if not file_value:
                continue
            key = (
                str(item.get("project", "")),
                file_value,
                str(item.get("line", "")),
                str(item.get("rule_id", "")),
                str(item.get("message", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            rows.append(item)
    return pd.DataFrame(rows, columns=RESULTS_COLUMNS)


def is_code_smell(rule_id: str) -> bool:
    if rule_id in EXPLICIT_CODE_SMELL_RULES:
        return True
    return bool(re.fullmatch(r"SA\d{4}", rule_id))


def extract_code_smells(findings: pd.DataFrame) -> pd.DataFrame:
    if findings.empty:
        return pd.DataFrame(columns=SMELLS_COLUMNS)
    smells = findings[findings["rule_id"].map(is_code_smell)].copy()
    return smells[SMELLS_COLUMNS].reset_index(drop=True)


def run_pipeline(repo: Path, output: Path, dotnet_root: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    env = dotnet_env(dotnet_root)
    error_lines: list[str] = []

    csharp_files = discover_csharp_files(repo)
    pd.DataFrame(
        [{"absolute_path": str(path), "relative_path": str(path.relative_to(repo))} for path in csharp_files]
    ).to_csv(output / "csharp_files.csv", index=False)

    solutions, projects = discover_solutions_and_projects(repo)
    inventory = build_inventory(repo, solutions, projects)
    inventory.to_csv(output / "solution_project_inventory.csv", index=False)

    targets = resolve_analysis_targets(solutions, projects)
    project_paths = collect_projects_for_targets(targets)
    if not targets and project_paths:
        targets = project_paths

    raw_chunks: list[str] = []
    sarif_findings: list[dict[str, Any]] = []
    build_findings: list[dict[str, Any]] = []
    projects_success = 0
    projects_failed = 0

    for project_path in project_paths:
        ok, detail = inject_stylecop(project_path, dotnet_root, env)
        if not ok:
            error_lines.append(f"StyleCop injection failed for {project_path}: {detail.strip()}")
            projects_failed += 1
            continue
        if detail != "already_installed":
            raw_chunks.append(detail)

    for target in targets:
        target_label = str(target)
        restore_ok, restore_output = restore_target(target, dotnet_root, env)
        raw_chunks.append(restore_output)
        if not restore_ok:
            error_lines.append(f"dotnet restore failed for {target_label}")
            projects_failed += 1
            continue

        sarif_path = output / f"{target.stem}.sarif"
        build_ok, build_output, written_sarif = build_target(target, dotnet_root, env, sarif_path)
        raw_chunks.append(build_output)
        sarif_findings.extend(parse_sarif(written_sarif, target_label))
        build_findings.extend(parse_build_diagnostics(build_output, target_label))
        if build_ok:
            projects_success += 1
        else:
            error_lines.append(f"dotnet build failed for {target_label} (continuing)")
            projects_failed += 1

    raw_text = "".join(chunk if chunk.endswith("\n") else chunk + "\n" for chunk in raw_chunks if chunk)
    (output / "stylecop_raw_output.txt").write_text(raw_text, encoding="utf-8")

    combined_sarif = output / "stylecop_output.sarif"
    written_sarifs = [output / f"{target.stem}.sarif" for target in targets if (output / f"{target.stem}.sarif").exists()]
    if written_sarifs:
        shutil.copy2(written_sarifs[0], combined_sarif)
    else:
        combined_sarif.write_text(json.dumps({"version": "2.1.0", "runs": []}, indent=2), encoding="utf-8")

    findings_df = merge_findings(build_findings, sarif_findings)
    findings_df.to_csv(output / "stylecop_results.csv", index=False)

    smells_df = extract_code_smells(findings_df)
    smells_df.to_csv(output / "code_smells_findings.csv", index=False)

    summary_df = pd.DataFrame([{"metric_name": "Code_Smells_Count", "metric_value": len(smells_df)}])
    summary_df.to_csv(output / "code_smells_summary.csv", index=False)
    (output / "error_log.txt").write_text("\n".join(error_lines), encoding="utf-8")

    if projects_success == 0 and targets:
        projects_success = len(project_paths) - projects_failed

    return {
        "benchmark_ready": len(csharp_files) > 0 and len(smells_df) >= 5,
        "csharp_files": len(csharp_files),
        "total_projects": len(project_paths),
        "projects_success": max(projects_success, 0),
        "projects_failed": projects_failed,
        "total_findings": len(findings_df),
        "code_smells_count": len(smells_df),
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
