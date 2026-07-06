"""Roslynator + Roslyn Parameter Count benchmark execution helpers."""
from __future__ import annotations

import csv
import json
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

TOOL_ROOT = Path(__file__).resolve().parent
EXCLUDED = {".git", "bin", "obj", "packages", "artifacts", "TestResults", "node_modules", "docs"}
DOTNET_CHANNEL = "8.0"
ANALYZER_PROJECT = TOOL_ROOT / "ParameterCountAnalyzer" / "ParameterCountAnalyzer.csproj"
FINDINGS_COLUMNS = ["project", "file", "line", "column", "severity", "diagnostic_id", "message"]
INVENTORY_COLUMNS = ["file_path", "file_name", "directory"]
PARAMETER_COUNT_COLUMNS = ["file", "namespace", "class", "method", "line", "parameter_count", "parameter_names"]
LONG_PARAMETER_LIST_COLUMNS = ["file", "class", "method", "parameter_count", "status"]
LONG_PARAMETER_THRESHOLD = 5
TEXT_DIAGNOSTIC_PATTERN = re.compile(
    r"^(?P<file>.+?)\((?P<line>\d+),(?P<column>\d+)\):\s*(?P<severity>\w+)\s+(?P<diagnostic_id>[A-Z0-9]+):\s*(?P<message>.*)$"
)


def resolve_project_root(metric_root: Path) -> Path:
    current = metric_root.resolve()
    for _ in range(8):
        if (current / "runtimes").is_dir():
            return current
        if (current / "README.md").is_file():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return metric_root.resolve().parent.parent


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


def build_parameter_count_analyzer(dotnet_root: Path) -> Path:
    subprocess.run(
        [str(dotnet_executable(dotnet_root)), "build", str(ANALYZER_PROJECT), "-c", "Release"],
        env=dotnet_env(dotnet_root),
        check=True,
    )
    dll = ANALYZER_PROJECT.parent / "bin" / "Release" / "net8.0" / "ParameterCountAnalyzer.dll"
    if not dll.exists():
        raise RuntimeError(f"ParameterCountAnalyzer build failed; expected {dll}")
    return dll


def discover_csharp_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo.rglob("*.cs"):
        if any(part in EXCLUDED for part in path.parts):
            continue
        files.append(path.resolve())
    return sorted(files)


def save_csharp_inventory(csharp_files: list[Path], output: Path) -> None:
    rows = [
        {"file_path": str(path), "file_name": path.name, "directory": str(path.parent)}
        for path in csharp_files
    ]
    pd.DataFrame(rows, columns=INVENTORY_COLUMNS).to_csv(output, index=False)


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


def analyze_targets(solutions: list[Path], projects: list[Path]) -> list[Path]:
    if solutions:
        return solutions
    return projects


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


def run_roslynator_suite(
    roslynator: Path,
    targets: list[Path],
    output_dir: Path,
    env: dict[str, str],
) -> tuple[str, list[Path], Path | None]:
    raw_sections: list[str] = []
    xml_paths: list[Path] = []
    gitlab_path: Path | None = None

    if not targets:
        return "", xml_paths, gitlab_path

    for index, target in enumerate(targets):
        header = f"===== Roslynator analyze (text): {target} ====="
        raw_sections.append(header)
        text_stdout, text_stderr, _ = run_command([str(roslynator), "analyze", str(target)], env=env)
        raw_sections.append(text_stdout)
        if text_stderr.strip():
            raw_sections.append(text_stderr)

        xml_output = output_dir / ("roslynator_output.xml" if len(targets) == 1 else f"roslynator_output_{index + 1}.xml")
        xml_stdout, xml_stderr, _ = run_command(
            [
                str(roslynator),
                "analyze",
                str(target),
                "-o",
                str(xml_output),
                "--output-format",
                "xml",
            ],
            env=env,
        )
        raw_sections.append(f"===== Roslynator analyze (xml): {target} =====")
        raw_sections.append(xml_stdout)
        if xml_stderr.strip():
            raw_sections.append(xml_stderr)
        if xml_output.exists():
            xml_paths.append(xml_output)
        elif xml_stdout.strip().startswith("<?xml"):
            xml_output.write_text(xml_stdout, encoding="utf-8")
            xml_paths.append(xml_output)

        gitlab_output = output_dir / (
            "roslynator_output.gitlab.json" if len(targets) == 1 else f"roslynator_output_{index + 1}.gitlab.json"
        )
        gitlab_stdout, gitlab_stderr, _ = run_command(
            [
                str(roslynator),
                "analyze",
                str(target),
                "-o",
                str(gitlab_output),
                "--output-format",
                "gitlab",
            ],
            env=env,
        )
        raw_sections.append(f"===== Roslynator analyze (gitlab): {target} =====")
        raw_sections.append(gitlab_stdout)
        if gitlab_stderr.strip():
            raw_sections.append(gitlab_stderr)
        if gitlab_output.exists():
            gitlab_path = gitlab_output

    return "\n".join(raw_sections), xml_paths, gitlab_path


def run_parameter_count_analyzer(
    analyzer_dll: Path,
    repo: Path,
    output_csv: Path,
    dotnet_root: Path,
) -> tuple[str, str, int]:
    return run_command(
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


def _child_text(node: ET.Element, local_name: str) -> str:
    for child in node:
        if str(child.tag).endswith(local_name):
            return (child.text or "").strip()
    return ""


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
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


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
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def merge_roslynator_results(*frames: pd.DataFrame) -> pd.DataFrame:
    valid = [frame for frame in frames if frame is not None and not frame.empty]
    if not valid:
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    combined = pd.concat(valid, ignore_index=True)
    return combined.drop_duplicates(
        subset=["project", "file", "line", "column", "diagnostic_id", "message"],
        keep="first",
    )


def combine_xml_outputs(xml_paths: list[Path], primary_xml: Path) -> None:
    if not xml_paths:
        primary_xml.write_text('<?xml version="1.0" encoding="utf-8"?><Roslynator/>', encoding="utf-8")
        return
    if len(xml_paths) == 1:
        if xml_paths[0] != primary_xml:
            primary_xml.write_text(xml_paths[0].read_text(encoding="utf-8"), encoding="utf-8")
        return

    combined_root = ET.Element("Roslynator")
    code_analysis = ET.SubElement(combined_root, "CodeAnalysis")
    projects = ET.SubElement(code_analysis, "Projects")
    for xml_path in xml_paths:
        try:
            parsed_root = ET.parse(xml_path).getroot()
        except ET.ParseError:
            continue
        for project_node in parsed_root.iter():
            if str(project_node.tag).endswith("Project"):
                projects.append(project_node)
    ET.ElementTree(combined_root).write(primary_xml, encoding="utf-8", xml_declaration=True)


def findings_to_json(findings_df: pd.DataFrame, gitlab_path: Path | None) -> dict[str, Any]:
    if gitlab_path and gitlab_path.exists():
        try:
            payload = json.loads(gitlab_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass
    return {
        "source": "roslynator_findings_csv",
        "diagnostics": findings_df.to_dict(orient="records"),
    }


def build_long_parameter_list(param_df: pd.DataFrame) -> pd.DataFrame:
    if param_df.empty:
        return pd.DataFrame(columns=LONG_PARAMETER_LIST_COLUMNS)
    rows: list[dict[str, Any]] = []
    for _, record in param_df.iterrows():
        param_count = int(record.get("parameter_count", 0) or 0)
        status = "Long Parameter List" if param_count > LONG_PARAMETER_THRESHOLD else "OK"
        rows.append(
            {
                "file": record.get("file", ""),
                "class": record.get("class", ""),
                "method": record.get("method", ""),
                "parameter_count": param_count,
                "status": status,
            }
        )
    return pd.DataFrame(rows, columns=LONG_PARAMETER_LIST_COLUMNS)


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


def run_pipeline(
    repo: Path,
    output: Path,
    dotnet_root: Path,
    tools_dir: Path,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    errors: list[dict[str, str]] = []
    repo = repo.resolve()

    dotnet_root = download_dotnet_sdk(dotnet_root)
    roslynator = install_roslynator(dotnet_root, tools_dir)
    env = dotnet_env(dotnet_root)

    try:
        analyzer_dll = build_parameter_count_analyzer(dotnet_root)
    except Exception as exc:
        append_error(errors, "parameter_count_analyzer", f"Analyzer build failed: {exc}")
        analyzer_dll = None

    csharp_files = discover_csharp_files(repo)
    save_csharp_inventory(csharp_files, output / "csharp_files_inventory.csv")

    solutions, projects = discover_solution_and_project_files(repo)
    targets = analyze_targets(solutions, projects)

    raw_text = ""
    xml_paths: list[Path] = []
    gitlab_path: Path | None = None
    if targets:
        try:
            raw_text, xml_paths, gitlab_path = run_roslynator_suite(roslynator, targets, output, env)
        except Exception as exc:
            append_error(errors, "roslynator", f"Roslynator execution failed: {exc}")
    else:
        append_error(errors, "roslynator", "No .sln or .csproj files discovered; Roslynator analysis skipped.")

    (output / "roslynator_raw_console_output.txt").write_text(raw_text, encoding="utf-8")

    primary_xml = output / "roslynator_output.xml"
    combine_xml_outputs(xml_paths, primary_xml)

    findings_df = merge_roslynator_results(
        parse_roslynator_xml([primary_xml] if primary_xml.exists() else xml_paths),
        parse_roslynator_text(raw_text),
    )
    findings_df.to_csv(output / "roslynator_findings.csv", index=False)

    json_payload = findings_to_json(findings_df, gitlab_path)
    (output / "roslynator_output.json").write_text(json.dumps(json_payload, indent=2), encoding="utf-8")

    param_csv = output / "parameter_count.csv"
    analyzer_stdout = ""
    analyzer_stderr = ""
    if analyzer_dll is not None:
        try:
            analyzer_stdout, analyzer_stderr, analyzer_code = run_parameter_count_analyzer(
                analyzer_dll, repo, param_csv, dotnet_root
            )
            if analyzer_code != 0 and not param_csv.exists():
                append_error(errors, "parameter_count_analyzer", f"Analyzer exited with code {analyzer_code}")
            if analyzer_stderr.strip():
                append_error(errors, "parameter_count_analyzer", analyzer_stderr.strip())
        except Exception as exc:
            append_error(errors, "parameter_count_analyzer", f"Analyzer execution failed: {exc}")

    if param_csv.exists():
        param_df = pd.read_csv(param_csv)
        for col in ["parameter_count"]:
            if col in param_df.columns:
                param_df[col] = pd.to_numeric(param_df[col], errors="coerce")
    else:
        param_df = pd.DataFrame(columns=PARAMETER_COUNT_COLUMNS)
        param_df.to_csv(param_csv, index=False)

    param_values = pd.to_numeric(param_df.get("parameter_count", pd.Series(dtype=float)), errors="coerce").dropna()
    max_param = int(param_values.max()) if not param_values.empty else 0
    avg_param = round(float(param_values.mean()), 4) if not param_values.empty else 0.0

    pd.DataFrame([{"metric_name": "Parameter_Count", "metric_value": max_param}]).to_csv(
        output / "parameter_count_summary.csv", index=False
    )

    long_param_df = build_long_parameter_list(param_df)
    long_param_df.to_csv(output / "long_parameter_list.csv", index=False)
    long_param_count = int((long_param_df["status"] == "Long Parameter List").sum())

    if analyzer_stdout.strip():
        existing = (output / "roslynator_raw_console_output.txt").read_text(encoding="utf-8")
        (output / "roslynator_raw_console_output.txt").write_text(
            existing + "\n===== ParameterCountAnalyzer (stdout) =====\n" + analyzer_stdout,
            encoding="utf-8",
        )

    write_error_log(errors, output / "error_log.txt")

    return {
        "benchmark_ready": len(csharp_files) > 0 and not param_df.empty and max_param >= 8,
        "csharp_files": len(csharp_files),
        "methods": len(param_df),
        "average_parameter_count": avg_param,
        "maximum_parameter_count": max_param,
        "long_parameter_list_count": long_param_count,
        "total_roslynator_diagnostics": len(findings_df),
        "roslynator_targets": len(targets),
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
