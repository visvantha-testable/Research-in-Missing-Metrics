"""Implementation helpers for Cppcheck code smells benchmark execution."""
from __future__ import annotations

import csv
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

C_FILE_EXTENSIONS = {".c", ".h"}
EXCLUDED_DIR_NAMES = {
    ".git", "build", "dist", "out", "bin", "vendor", "third_party", "docs", "tests",
}
CPPCHECK_EXCLUDE_ARGS = [
    "-i.git",
    "-ibuild",
    "-idist",
    "-iout",
    "-ibin",
    "-ivendor",
    "-ithird_party",
    "-idocs",
    "-itests",
]

CODE_SMELL_RULE_IDS = {
    "duplicateExpression",
    "variableScope",
    "functionStatic",
    "staticFunction",
    "constVariable",
    "unreadVariable",
    "unusedFunction",
    "unusedStructMember",
    "shadowVariable",
    "passedByValue",
    "knownConditionTrueFalse",
}

RESULTS_COLUMNS = ["file", "line", "severity", "id", "message", "verbose", "cwe"]
SMELLS_COLUMNS = ["file", "line", "severity", "rule_id", "message", "cwe"]

PROGRESS_RE = re.compile(r"(\d+)/(\d+) files checked")
CHECKING_RE = re.compile(r"^Checking (.+) \.\.\.$")


def should_exclude_path(path: Path) -> bool:
    return any(part in EXCLUDED_DIR_NAMES for part in path.parts)


def discover_c_files(repo_path: Path) -> list[Path]:
    files: list[Path] = []
    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in C_FILE_EXTENSIONS:
            continue
        if should_exclude_path(file_path.relative_to(repo_path)):
            continue
        files.append(file_path.resolve())
    return sorted(files)


def resolve_cppcheck_executable(project_root: Path) -> Path:
    env_path = os.environ.get("CPPCHECK")
    if env_path:
        candidate = Path(env_path)
        if candidate.exists():
            return candidate.resolve()

    which = shutil.which("cppcheck")
    if which:
        return Path(which).resolve()

    runtime_candidates = [
        project_root / "runtimes" / "cppcheck" / "PFiles" / "Cppcheck" / "cppcheck.exe",
        project_root / "runtimes" / "cppcheck" / "PFiles" / "Cppcheck" / "cppcheck",
        project_root / "runtimes" / "cppcheck" / "cppcheck.exe",
        project_root / "runtimes" / "cppcheck" / "cppcheck",
    ]
    for candidate in runtime_candidates:
        if candidate.exists():
            return candidate.resolve()

    raise FileNotFoundError(
        "Cppcheck executable not found. Install Cppcheck and ensure it is on PATH, "
        "set CPPCHECK, or bootstrap to runtimes/cppcheck/."
    )


def build_cppcheck_command(
    cppcheck_exe: Path,
    repo_path: Path,
    *,
    xml_output: bool = False,
) -> list[str]:
    command = [
        str(cppcheck_exe),
        "--enable=all",
        "--inconclusive",
        "--force",
        *CPPCHECK_EXCLUDE_ARGS,
    ]
    if xml_output:
        command.extend(["--xml", "--xml-version=2"])
    command.append(str(repo_path))
    return command


def run_cmd(command: list[str]) -> tuple[str, str, int]:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.stdout, completed.stderr, completed.returncode


def combine_raw(stdout: str, stderr: str) -> str:
    raw = stdout
    if stderr:
        if raw and not raw.endswith("\n"):
            raw += "\n"
        raw += stderr
    return raw


def parse_progress_stats(stdout: str, total_files: int) -> tuple[int, int]:
    checked = 0
    total = total_files
    for match in PROGRESS_RE.finditer(stdout):
        checked = int(match.group(1))
        total = int(match.group(2))
    if checked == 0 and total_files > 0:
        checked = total_files
        total = total_files
    failed = max(total - checked, 0)
    return checked, failed


def parse_cppcheck_xml(xml_text: str) -> list[dict[str, Any]]:
    if not xml_text.strip():
        return []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    rows: list[dict[str, Any]] = []
    for error in root.findall(".//error"):
        rule_id = error.get("id", "")
        if rule_id == "checkersReport":
            continue

        locations = error.findall("location")
        if not locations:
            rows.append(
                {
                    "file": error.get("file0", ""),
                    "line": "",
                    "severity": error.get("severity", ""),
                    "id": rule_id,
                    "message": error.get("msg", ""),
                    "verbose": error.get("verbose", ""),
                    "cwe": error.get("cwe", ""),
                }
            )
            continue

        for location in locations:
            rows.append(
                {
                    "file": location.get("file", error.get("file0", "")),
                    "line": location.get("line", ""),
                    "severity": error.get("severity", ""),
                    "id": rule_id,
                    "message": error.get("msg", ""),
                    "verbose": error.get("verbose", ""),
                    "cwe": error.get("cwe", ""),
                }
            )
    return rows


def findings_to_dataframe(findings: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(findings, columns=RESULTS_COLUMNS)


def is_code_smell(rule_id: str) -> bool:
    return rule_id in CODE_SMELL_RULE_IDS


def extract_code_smells(findings: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for finding in findings:
        rule_id = str(finding.get("id", ""))
        if not is_code_smell(rule_id):
            continue
        key = (
            str(finding.get("file", "")),
            str(finding.get("line", "")),
            rule_id,
            str(finding.get("message", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "file": finding.get("file", ""),
                "line": finding.get("line", ""),
                "severity": finding.get("severity", ""),
                "rule_id": rule_id,
                "message": finding.get("message", ""),
                "cwe": finding.get("cwe", ""),
            }
        )
    return pd.DataFrame(rows, columns=SMELLS_COLUMNS)


def count_failed_files(findings: list[dict[str, Any]]) -> int:
    failure_ids = {"syntaxError", "internalError", "unknownMacro", "preprocessorErrorDirective"}
    failed_files = {
        str(item.get("file", ""))
        for item in findings
        if str(item.get("id", "")) in failure_ids and str(item.get("file", ""))
    }
    return len(failed_files)


def run_pipeline(repo: Path, output: Path, project_root: Path | None = None) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    project_root = project_root or repo.parent.parent.parent.parent

    cppcheck_exe = resolve_cppcheck_executable(project_root)
    c_files = discover_c_files(repo)

    pd.DataFrame(
        [{"absolute_path": str(path), "relative_path": str(path.relative_to(repo))} for path in c_files]
    ).to_csv(output / "c_files.csv", index=False)

    text_cmd = build_cppcheck_command(cppcheck_exe, repo, xml_output=False)
    text_stdout, text_stderr, text_code = run_cmd(text_cmd)
    raw_text = combine_raw(text_stdout, text_stderr)
    (output / "cppcheck_raw_output.txt").write_text(raw_text, encoding="utf-8")

    xml_cmd = build_cppcheck_command(cppcheck_exe, repo, xml_output=True)
    xml_stdout, xml_stderr, xml_code = run_cmd(xml_cmd)
    xml_payload = xml_stderr if xml_stderr.strip().startswith("<?xml") else xml_stderr
    if not xml_payload.strip().startswith("<?xml") and xml_stdout.strip().startswith("<?xml"):
        xml_payload = xml_stdout
    (output / "cppcheck_output.xml").write_text(xml_payload, encoding="utf-8")

    findings = parse_cppcheck_xml(xml_payload)
    results_df = findings_to_dataframe(findings)
    results_df.to_csv(output / "cppcheck_results.csv", index=False)

    smells_df = extract_code_smells(findings)
    smells_df.to_csv(output / "code_smells_findings.csv", index=False)

    summary_df = pd.DataFrame([{"metric_name": "Code_Smells_Count", "metric_value": len(smells_df)}])
    summary_df.to_csv(output / "code_smells_summary.csv", index=False)

    error_lines: list[str] = []
    if text_code not in (0, 1) and not findings:
        error_lines.append(f"Cppcheck text run exited with code {text_code}")
    if xml_code not in (0, 1) and not findings:
        error_lines.append(f"Cppcheck XML run exited with code {xml_code}")
    (output / "error_log.txt").write_text("\n".join(error_lines), encoding="utf-8")

    files_success, files_failed_progress = parse_progress_stats(text_stdout, len(c_files))
    files_failed = max(files_failed_progress, count_failed_files(findings))
    if files_success == 0 and len(c_files) > 0:
        files_success = len(c_files) - files_failed

    return {
        "benchmark_ready": len(c_files) > 0 and len(smells_df) >= 5,
        "c_files": len(c_files),
        "files_success": files_success,
        "files_failed": files_failed,
        "total_findings": len(results_df),
        "code_smells_count": len(smells_df),
        "repo_path": str(repo),
        "cppcheck_exe": str(cppcheck_exe),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
