"""StyleCop maintainability rating benchmark execution helpers."""
from __future__ import annotations

import csv
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

os.environ.pop("PYTHONPATH", None)

EXCLUDED = {".git", "bin", "obj", "packages", "TestResults", "node_modules", "docs", "artifacts"}
DOTNET_CHANNEL = "8.0"
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
                "powershell", "-ExecutionPolicy", "Bypass", "-File", str(script_path),
                "-InstallDir", str(install_dir), "-Channel", channel, "-Architecture", "x64", "-Quality", "ga",
            ],
            check=True,
        )
    else:
        script_path = install_dir / "dotnet-install.sh"
        urllib.request.urlretrieve("https://dot.net/v1/dotnet-install.sh", script_path)
        script_path.chmod(0o755)
        subprocess.run([str(script_path), "--install-dir", str(install_dir), "--channel", channel, "--quality", "ga"], check=True)

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
        command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, env=env,
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


def save_csharp_inventory(csharp_files: list[Path], output: Path) -> None:
    rows = [
        {"file_path": str(path), "file_name": path.name, "directory": str(path.parent)}
        for path in csharp_files
    ]
    pd.DataFrame(rows, columns=["file_path", "file_name", "directory"]).to_csv(output, index=False)


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


def resolve_analysis_targets(solutions: list[Path], projects: list[Path]) -> list[Path]:
    return solutions if solutions else projects


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
        updated = content.replace("</Project>", insert + "</Project>", 1)
        project_path.write_text(updated, encoding="utf-8")


def has_stylecop_package(project_path: Path) -> bool:
    return STYLECOP_PACKAGE in project_path.read_text(encoding="utf-8", errors="replace")


def inject_stylecop(project_path: Path, dotnet_root: Path, env: dict[str, str]) -> tuple[bool, str]:
    ensure_stylecop_json_reference(project_path)
    if has_stylecop_package(project_path):
        return True, "already_installed"
    command = [
        str(dotnet_executable(dotnet_root)), "add", str(project_path), "package",
        STYLECOP_PACKAGE, "--version", STYLECOP_VERSION,
    ]
    stdout, stderr, code = run_command(command, env)
    if code != 0:
        return False, combine_raw(stdout, stderr)
    return True, combine_raw(stdout, stderr)


def restore_target(target: Path, dotnet_root: Path, env: dict[str, str]) -> tuple[bool, str]:
    stdout, stderr, code = run_command([str(dotnet_executable(dotnet_root)), "restore", str(target)], env)
    return code == 0, combine_raw(stdout, stderr)


def build_target(target: Path, dotnet_root: Path, env: dict[str, str], sarif_path: Path) -> tuple[bool, str, Path]:
    sarif_path.parent.mkdir(parents=True, exist_ok=True)
    clean_stdout, clean_stderr, _ = run_command([str(dotnet_executable(dotnet_root)), "clean", str(target)], env)
    command = [
        str(dotnet_executable(dotnet_root)), "build", str(target), "--no-incremental",
        "-p:RunAnalyzers=true", f"-p:ErrorLog={sarif_path}", "--no-restore", "-v", "normal",
    ]
    stdout, stderr, code = run_command(command, env)
    raw = combine_raw(clean_stdout + clean_stderr, combine_raw(stdout, stderr))
    return code in BUILD_SUCCESS_CODES, raw, sarif_path


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
                "diagnostic_id": match.group("rule_id"),
                "message": match.group("message").strip(),
            }
        )
    return rows


def _sarif_level_to_severity(level: str) -> str:
    return {"error": "error", "warning": "warning", "note": "info", "none": "info"}.get(level.lower(), level.lower())


def parse_sarif(sarif_path: Path, project: str) -> list[dict[str, Any]]:
    if not sarif_path.exists() or sarif_path.stat().st_size == 0:
        return []
    try:
        payload = json.loads(sarif_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    rows: list[dict[str, Any]] = []
    for run in payload.get("runs", []):
        for result in run.get("results", []):
            rule_id = str(result.get("ruleId", ""))
            if not rule_id.startswith("SA"):
                continue
            message = result.get("message", {})
            text = message.get("text", "") if isinstance(message, dict) else str(message)
            severity = _sarif_level_to_severity(str(result.get("level", "warning")))
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
                        "diagnostic_id": rule_id,
                        "message": text,
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
                str(item.get("project", "")), file_value,
                str(item.get("line", "")), str(item.get("diagnostic_id", "")),
                str(item.get("message", "")),
            )
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
    if 1000 <= number <= 1068:
        return "Style"
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


def append_error(errors: list[dict[str, str]], file: str, message: str) -> None:
    errors.append(
        {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "file": file,
            "error_message": message,
        }
    )


def write_error_log(errors: list[dict[str, str]], output: Path) -> None:
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["timestamp", "file", "error_message"])
        writer.writeheader()
        writer.writerows(errors)


def run_pipeline(repo: Path, output: Path, dotnet_root: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    env = dotnet_env(dotnet_root)
    errors: list[dict[str, str]] = []

    csharp_files = discover_csharp_files(repo)
    save_csharp_inventory(csharp_files, output / "csharp_files_inventory.csv")

    solutions, projects = discover_solutions_and_projects(repo)
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
            append_error(errors, str(project_path), f"StyleCop injection failed: {detail.strip()}")
            projects_failed += 1
            continue
        if detail != "already_installed":
            raw_chunks.append(detail)

    for target in targets:
        target_label = str(target)
        restore_ok, restore_output = restore_target(target, dotnet_root, env)
        raw_chunks.append(restore_output)
        if not restore_ok:
            append_error(errors, target_label, "dotnet restore failed")
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
            append_error(errors, target_label, "dotnet build failed (continuing)")
            projects_failed += 1

    raw_text = "".join(chunk if chunk.endswith("\n") else chunk + "\n" for chunk in raw_chunks if chunk)
    (output / "stylecop_raw_console_output.txt").write_text(raw_text, encoding="utf-8")

    findings_df = merge_findings(build_findings, sarif_findings)
    findings_df.to_csv(output / "stylecop_findings.csv", index=False)

    maintainability_df = findings_df[findings_df["diagnostic_id"].map(is_maintainability_violation)].copy()
    violation_count = len(maintainability_df)
    code_smells_count = violation_count

    pd.DataFrame([{"metric_name": "Code_Smells_Count", "metric_value": code_smells_count}]).to_csv(
        output / "code_smells_summary.csv", index=False
    )

    violation_rows = [{"metric_name": "Maintainability_Violations_Count", "metric_value": violation_count}]
    if not maintainability_df.empty:
        maintainability_df = maintainability_df.copy()
        maintainability_df["category"] = maintainability_df["diagnostic_id"].map(categorize_violation)
        for category in ["Documentation", "Naming", "Ordering", "Readability", "Design", "Layout", "Style"]:
            count = int((maintainability_df["category"] == category).sum())
            if count:
                violation_rows.append({"metric_name": f"{category}_Violations", "metric_value": count})
    pd.DataFrame(violation_rows).to_csv(output / "maintainability_violations_summary.csv", index=False)

    maintainability_score = compute_maintainability_score(violation_count, len(csharp_files))
    pd.DataFrame([{"metric_name": "Maintainability_Score", "metric_value": maintainability_score}]).to_csv(
        output / "maintainability_score_summary.csv", index=False
    )

    rating = score_to_sqale_rating(maintainability_score)
    pd.DataFrame([{"metric_name": "Maintainability_Rating", "metric_value": rating}]).to_csv(
        output / "maintainability_rating_summary.csv", index=False
    )

    write_error_log(errors, output / "error_log.txt")

    category_counts = {}
    if not maintainability_df.empty:
        category_counts = maintainability_df["category"].value_counts().to_dict()

    return {
        "benchmark_ready": len(csharp_files) > 0 and violation_count > 0,
        "csharp_files": len(csharp_files),
        "total_findings": len(findings_df),
        "code_smells_count": code_smells_count,
        "maintainability_violations": violation_count,
        "maintainability_score": maintainability_score,
        "maintainability_rating": rating,
        "projects_success": max(projects_success, 0),
        "projects_failed": projects_failed,
        "category_counts": category_counts,
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
