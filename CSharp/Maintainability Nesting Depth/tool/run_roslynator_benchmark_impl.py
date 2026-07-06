"""Roslynator benchmark execution helpers."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

os.environ.pop("PYTHONPATH", None)

import pandas as pd

ROOT = Path(__file__).resolve().parent
EXCLUDED = {".git", "bin", "obj", "packages", "artifacts", "TestResults", "node_modules"}
DOTNET_CHANNEL = "8.0"
ANALYZER_PROJECT = ROOT / "NestingDepthAnalyzer" / "NestingDepthAnalyzer.csproj"
TEXT_DIAGNOSTIC_PATTERN = re.compile(
    r"^(?P<file>.+?)\((?P<line>\d+),(?P<column>\d+)\):\s*(?P<severity>\w+)\s+(?P<diagnostic_id>[A-Z0-9]+):\s*(?P<message>.*)$"
)


def dotnet_executable(dotnet_root: Path) -> Path:
    name = "dotnet.exe" if sys.platform.startswith("win") else "dotnet"
    return dotnet_root / name


def roslynator_executable(tools_dir: Path) -> Path:
    name = "roslynator.exe" if sys.platform.startswith("win") else "roslynator"
    return tools_dir / name


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


def install_roslynator(dotnet_root: Path, tools_dir: Path) -> Path:
    tools_dir = tools_dir.resolve()
    tools_dir.mkdir(parents=True, exist_ok=True)
    roslynator = roslynator_executable(tools_dir)
    if roslynator.exists():
        return roslynator

    subprocess.run(
        [
            str(dotnet_executable(dotnet_root)),
            "tool",
            "install",
            "roslynator.dotnet.cli",
            "--tool-path",
            str(tools_dir),
        ],
        env=dotnet_env(dotnet_root),
        check=True,
    )
    if not roslynator.exists():
        raise RuntimeError(f"Roslynator installation failed; expected executable at {roslynator}")
    return roslynator


def build_nesting_analyzer(dotnet_root: Path) -> Path:
    subprocess.run(
        [str(dotnet_executable(dotnet_root)), "build", str(ANALYZER_PROJECT), "-c", "Release"],
        env=dotnet_env(dotnet_root),
        check=True,
    )
    dll = ANALYZER_PROJECT.parent / "bin" / "Release" / "net8.0" / "NestingDepthAnalyzer.dll"
    if not dll.exists():
        raise RuntimeError(f"NestingDepthAnalyzer build failed; expected {dll}")
    return dll


def discover_csharp_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo.rglob("*.cs"):
        if any(part in EXCLUDED for part in path.parts):
            continue
        files.append(path.resolve())
    return sorted(files)


def discover_solution_and_project_files(repo: Path) -> tuple[list[Path], list[Path]]:
    solutions = sorted(
        path.resolve()
        for path in repo.rglob("*.sln")
        if not any(part in EXCLUDED for part in path.parts)
    )
    projects = sorted(
        path.resolve()
        for path in repo.rglob("*.csproj")
        if not any(part in EXCLUDED for part in path.parts)
    )
    return solutions, projects


def run_command(cmd: list[str], env: dict[str, str] | None = None) -> tuple[str, str, int]:
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )
    return completed.stdout, completed.stderr, completed.returncode


def analyze_targets(solutions: list[Path], projects: list[Path]) -> list[Path]:
    if solutions:
        return solutions
    return projects


def run_roslynator_suite(
    roslynator: Path,
    targets: list[Path],
    xml_output: Path,
    env: dict[str, str],
) -> tuple[str, list[Path]]:
    raw_sections: list[str] = []
    xml_paths: list[Path] = []

    if not targets:
        return "", xml_paths

    for index, target in enumerate(targets):
        section_header = f"===== Roslynator analyze: {target} ====="
        raw_sections.append(section_header)

        text_stdout, text_stderr, _ = run_command([str(roslynator), "analyze", str(target)], env=env)
        raw_sections.append(text_stdout)
        if text_stderr.strip():
            raw_sections.append(text_stderr)

        target_xml = xml_output if len(targets) == 1 else xml_output.with_name(
            f"{xml_output.stem}_{index + 1}{xml_output.suffix}"
        )
        xml_stdout, xml_stderr, _ = run_command(
            [
                str(roslynator),
                "analyze",
                str(target),
                "-o",
                str(target_xml),
                "--output-format",
                "xml",
            ],
            env=env,
        )
        if not target_xml.exists() and xml_stdout.strip().startswith("<?xml"):
            target_xml.write_text(xml_stdout, encoding="utf-8")
        if xml_stderr.strip():
            raw_sections.append(xml_stderr)
        if target_xml.exists():
            xml_paths.append(target_xml)

    return "\n".join(raw_sections), xml_paths


def parse_roslynator_xml(xml_paths: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for xml_path in xml_paths:
        if not xml_path.exists():
            continue
        try:
            root = ET.parse(xml_path).getroot()
        except ET.ParseError:
            continue

        for project_node in root.iter():
            if not str(project_node.tag).endswith("Project"):
                continue
            project_name = project_node.attrib.get("Name", project_node.attrib.get("FilePath", ""))
            for diagnostic_node in project_node:
                if not str(diagnostic_node.tag).endswith("Diagnostic"):
                    continue
                diagnostic_id = diagnostic_node.attrib.get("Id", "")
                severity = _child_text(diagnostic_node, "Severity")
                message = _child_text(diagnostic_node, "Message")
                file_path = _child_text(diagnostic_node, "FilePath")
                line = ""
                column = ""
                for location_node in diagnostic_node:
                    if str(location_node.tag).endswith("Location"):
                        line = location_node.attrib.get("Line", "")
                        column = location_node.attrib.get("Character", "")
                rows.append(
                    {
                        "project": project_name,
                        "file": file_path,
                        "line": line,
                        "column": column,
                        "severity": severity,
                        "diagnostic_id": diagnostic_id,
                        "message": message,
                    }
                )
    columns = ["project", "file", "line", "column", "severity", "diagnostic_id", "message"]
    return pd.DataFrame(rows, columns=columns)


def _child_text(node: ET.Element, local_name: str) -> str:
    for child in node:
        if str(child.tag).endswith(local_name):
            return (child.text or "").strip()
    return ""


def parse_roslynator_text(raw_text: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for line in raw_text.splitlines():
        match = TEXT_DIAGNOSTIC_PATTERN.match(line.strip())
        if not match:
            continue
        rows.append(
            {
                "project": "",
                "file": match.group("file"),
                "line": match.group("line"),
                "column": match.group("column"),
                "severity": match.group("severity"),
                "diagnostic_id": match.group("diagnostic_id"),
                "message": match.group("message"),
            }
        )
    columns = ["project", "file", "line", "column", "severity", "diagnostic_id", "message"]
    return pd.DataFrame(rows, columns=columns)


def merge_roslynator_results(*frames: pd.DataFrame) -> pd.DataFrame:
    valid = [frame for frame in frames if frame is not None and not frame.empty]
    columns = ["project", "file", "line", "column", "severity", "diagnostic_id", "message"]
    if not valid:
        return pd.DataFrame(columns=columns)
    combined = pd.concat(valid, ignore_index=True)
    return combined.drop_duplicates(
        subset=["project", "file", "line", "column", "diagnostic_id", "message"],
        keep="first",
    )


def run_nesting_analyzer(dotnet_root: Path, analyzer_dll: Path, repo: Path, output_csv: Path) -> pd.DataFrame:
    stdout, stderr, return_code = run_command(
        [
            str(dotnet_executable(dotnet_root)),
            str(analyzer_dll),
            "--repo",
            str(repo),
            "--output",
            str(output_csv),
        ],
        env=dotnet_env(dotnet_root),
    )
    if return_code != 0:
        raise RuntimeError(stderr or stdout or "NestingDepthAnalyzer failed")
    if not output_csv.exists():
        raise RuntimeError(f"Expected analyzer output at {output_csv}")
    return pd.read_csv(output_csv)


def compute_summary(nesting_df: pd.DataFrame) -> pd.DataFrame:
    analyzed = nesting_df[nesting_df["status"] == "analyzed"].copy()
    valid = analyzed[pd.to_numeric(analyzed["max_nesting_depth"], errors="coerce").notna()]
    if valid.empty:
        return pd.DataFrame(
            [
                {"metric_name": "Maintainability_Nesting_Depth", "metric_value": 0},
                {"metric_name": "Average_Nesting_Depth", "metric_value": 0},
            ]
        )
    depths = valid["max_nesting_depth"].astype(int)
    return pd.DataFrame(
        [
            {"metric_name": "Maintainability_Nesting_Depth", "metric_value": int(depths.max())},
            {"metric_name": "Average_Nesting_Depth", "metric_value": round(float(depths.mean()), 4)},
        ]
    )


def run_pipeline(
    repo: Path,
    output: Path,
    dotnet_root: Path,
    tools_dir: Path,
    error_log: Path | None = None,
) -> dict[str, Any]:
    repo = repo.resolve()
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    dotnet_root = download_dotnet_sdk(dotnet_root)
    roslynator = install_roslynator(dotnet_root, tools_dir)
    analyzer_dll = build_nesting_analyzer(dotnet_root)
    env = dotnet_env(dotnet_root)

    csharp_files = discover_csharp_files(repo)
    pd.DataFrame(
        [
            {
                "absolute_path": str(path),
                "relative_path": str(path.relative_to(repo)),
            }
            for path in csharp_files
        ]
    ).to_csv(output / "csharp_files.csv", index=False)

    solutions, projects = discover_solution_and_project_files(repo)
    targets = analyze_targets(solutions, projects)

    raw_text = ""
    xml_paths: list[Path] = []
    if targets:
        try:
            raw_text, xml_paths = run_roslynator_suite(
                roslynator,
                targets,
                output / "roslynator_output.xml",
                env,
            )
        except Exception as exc:
            errors.append(f"Roslynator execution failed: {exc}")
    else:
        errors.append("No .sln or .csproj files discovered; Roslynator analysis skipped.")

    (output / "roslynator_raw_output.txt").write_text(raw_text, encoding="utf-8")

    primary_xml = output / "roslynator_output.xml"
    if xml_paths:
        if len(xml_paths) == 1:
            if xml_paths[0] != primary_xml:
                primary_xml.write_text(xml_paths[0].read_text(encoding="utf-8"), encoding="utf-8")
        else:
            combined_root = ET.Element("Roslynator")
            code_analysis = ET.SubElement(combined_root, "CodeAnalysis")
            projects = ET.SubElement(code_analysis, "Projects")
            for xml_path in xml_paths:
                try:
                    parsed_root = ET.parse(xml_path).getroot()
                except ET.ParseError:
                    errors.append(f"Malformed Roslynator XML: {xml_path}")
                    continue
                for project_node in parsed_root.iter():
                    if str(project_node.tag).endswith("Project"):
                        projects.append(project_node)
            ET.ElementTree(combined_root).write(primary_xml, encoding="utf-8", xml_declaration=True)
    elif not primary_xml.exists():
        primary_xml.write_text('<?xml version="1.0" encoding="utf-8"?><Roslynator/>', encoding="utf-8")

    parse_xml_paths = [primary_xml] if primary_xml.exists() else []
    xml_df = parse_roslynator_xml(parse_xml_paths)
    text_df = parse_roslynator_text(raw_text)
    results_df = merge_roslynator_results(xml_df, text_df)
    results_df.to_csv(output / "roslynator_results.csv", index=False)

    nesting_csv = output / "nesting_depth_results.csv"
    try:
        nesting_df = run_nesting_analyzer(dotnet_root, analyzer_dll, repo, nesting_csv)
    except Exception as exc:
        errors.append(f"NestingDepthAnalyzer failed: {exc}")
        nesting_df = pd.DataFrame(
            columns=["file", "class", "method", "start_line", "end_line", "max_nesting_depth", "status"]
        )
        nesting_df.to_csv(nesting_csv, index=False)

    summary_df = compute_summary(nesting_df)
    summary_df.to_csv(output / "maintainability_nesting_depth_summary.csv", index=False)

    error_log_path = error_log or (output / "error_log.txt")
    error_log_path.write_text("\n".join(errors), encoding="utf-8")

    analyzed = nesting_df[nesting_df.get("status", pd.Series(dtype=str)) == "analyzed"]
    max_depth = int(analyzed["max_nesting_depth"].max()) if not analyzed.empty else 0

    return {
        "benchmark_ready": len(csharp_files) > 0 and not analyzed.empty and max_depth >= 6,
        "csharp_files": len(csharp_files),
        "methods_analyzed": len(analyzed),
        "roslynator_targets": len(targets),
        "max_nesting_depth": max_depth,
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "errors": errors,
    }
