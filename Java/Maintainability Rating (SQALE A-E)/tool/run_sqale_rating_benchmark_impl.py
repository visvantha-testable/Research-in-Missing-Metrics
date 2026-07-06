"""PMD maintainability rating benchmark execution helpers."""
from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import pandas as pd

os.environ.pop("PYTHONPATH", None)

EXCLUDED = {
    ".git", "target", "build", "out", "bin", ".gradle", ".mvn", "node_modules", "docs", "generated-sources",
}
RULESET_CATEGORIES = [
    "category/java/design.xml",
    "category/java/codestyle.xml",
    "category/java/errorprone.xml",
    "category/java/bestpractices.xml",
]
EXPLICIT_RULES = [
    "CyclomaticComplexity",
    "NPathComplexity",
    "ExcessiveMethodLength",
    "ExcessiveClassLength",
    "ExcessiveParameterList",
    "GodClass",
]
MAINTAINABILITY_RULES = {
    "CyclomaticComplexity",
    "NPathComplexity",
    "ExcessiveMethodLength",
    "ExcessiveClassLength",
    "ExcessiveParameterList",
    "GodClass",
    "TooManyFields",
    "TooManyMethods",
    "AvoidDeeplyNestedIfStmts",
    "CouplingBetweenObjects",
    "DataClass",
    "LongMethod",
    "ExcessivePublicCount",
    "AvoidDuplicateLiterals",
    "DuplicateImports",
}
FINDINGS_COLUMNS = ["file", "rule", "priority", "description", "line", "ruleset"]
PMD_SUCCESS_CODES = {0, 4}
CCN_PATTERN = re.compile(r"cyclomatic complexity of (\d+)", re.IGNORECASE)
TEXT_PATTERN = re.compile(r"^(?P<file>.+):(?P<line>\d+):\s*(?P<rule>[^:]+):\s*(?P<message>.*)$")


def configure_java_runtime(jdk_home: Path | None = None) -> Path | None:
    if jdk_home is not None:
        jdk_home = jdk_home.resolve()
        java_bin = jdk_home / "bin"
        java_exe = java_bin / ("java.exe" if sys.platform.startswith("win") else "java")
        if java_exe.exists():
            os.environ["JAVA_HOME"] = str(jdk_home)
            os.environ["PATH"] = str(java_bin) + os.pathsep + os.environ.get("PATH", "")
            return jdk_home
    return None


def download_pmd(pmd_home: Path, version: str = "7.0.0", cache_dir: Path | None = None) -> Path:
    if (pmd_home / "bin").exists():
        return pmd_home
    root = pmd_home.parent
    root.mkdir(parents=True, exist_ok=True)
    cache_dir = (cache_dir or root / "cache").resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)
    url = (
        f"https://github.com/pmd/pmd/releases/download/"
        f"pmd_releases%2F{version}/pmd-dist-{version}-bin.zip"
    )
    zip_path = cache_dir / f"pmd-dist-{version}-bin.zip"
    if not zip_path.exists():
        with urlopen(url, timeout=120) as response, open(zip_path, "wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(root)
    return pmd_home


def pmd_exe(pmd_home: Path) -> Path:
    return pmd_home / "bin" / ("pmd.bat" if sys.platform.startswith("win") else "pmd")


def discover_java_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo.rglob("*.java"):
        if any(part in EXCLUDED for part in path.parts):
            continue
        files.append(path.resolve())
    return sorted(files)


def save_java_inventory(java_files: list[Path], output: Path) -> None:
    rows = [
        {"file_path": str(path), "file_name": path.name, "directory": str(path.parent)}
        for path in java_files
    ]
    pd.DataFrame(rows, columns=["file_path", "file_name", "directory"]).to_csv(output, index=False)


def write_custom_ruleset(ruleset_path: Path) -> Path:
    explicit_note = ", ".join(EXPLICIT_RULES)
    lines = [
        '<?xml version="1.0"?>',
        '<ruleset name="custom_ruleset"',
        '    xmlns="http://pmd.sourceforge.net/ruleset/2.0.0"',
        '    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        '    xsi:schemaLocation="http://pmd.sourceforge.net/ruleset/2.0.0 https://pmd.sourceforge.io/ruleset_2_0_0.xsd">',
        "    <description>Custom SQALE maintainability ruleset for Java repositories</description>",
        f"    <!-- Explicit rules covered via design.xml: {explicit_note} -->",
    ]
    for category in RULESET_CATEGORIES:
        lines.append(f'    <rule ref="{category}"/>')
    lines.append("</ruleset>")
    ruleset_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ruleset_path


def run_pmd(pmd_home: Path, repo: Path, ruleset: Path, fmt: str) -> tuple[str, str, int]:
    cmd = [
        str(pmd_exe(pmd_home)),
        "check",
        "-d",
        str(repo),
        "-R",
        str(ruleset),
        "-f",
        fmt,
        "--no-cache",
        "--no-progress",
    ]
    completed = subprocess.run(
        cmd,
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


def normalize_pmd_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    renamed = frame.copy()
    renamed.columns = [str(col).strip().lower().replace(" ", "_") for col in renamed.columns]
    return renamed


def parse_pmd_csv(csv_text: str) -> pd.DataFrame:
    if not csv_text.strip():
        return pd.DataFrame()
    return pd.read_csv(io.StringIO(csv_text.strip()))


def violations_from_csv(csv_df: pd.DataFrame) -> pd.DataFrame:
    if csv_df.empty:
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    frame = normalize_pmd_columns(csv_df)
    rows: list[dict[str, Any]] = []
    for _, record in frame.iterrows():
        line_value = record.get("line", record.get("beginline", record.get("begin_line", "")))
        rows.append(
            {
                "file": str(record.get("file", record.get("filename", ""))),
                "rule": str(record.get("rule", "")),
                "priority": record.get("priority", ""),
                "description": str(record.get("description", record.get("message", ""))),
                "line": line_value,
                "ruleset": str(record.get("rule_set", record.get("ruleset", ""))),
            }
        )
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def parse_pmd_json(json_text: str) -> pd.DataFrame:
    if not json_text.strip():
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError:
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    rows: list[dict[str, Any]] = []
    for file_entry in payload.get("files", []):
        file_name = file_entry.get("filename", "")
        for violation in file_entry.get("violations", []):
            rows.append(
                {
                    "file": file_name,
                    "rule": violation.get("rule", ""),
                    "priority": violation.get("priority", ""),
                    "description": violation.get("description", ""),
                    "line": violation.get("beginline", violation.get("beginLine", "")),
                    "ruleset": violation.get("ruleset", ""),
                }
            )
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def parse_pmd_text_violations(raw_text: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for line in raw_text.splitlines():
        match = TEXT_PATTERN.match(line.strip())
        if not match:
            continue
        rows.append(
            {
                "file": match.group("file").strip(),
                "rule": match.group("rule").strip(),
                "priority": "",
                "description": match.group("message").strip(),
                "line": int(match.group("line")),
                "ruleset": "",
            }
        )
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def merge_violations(*frames: pd.DataFrame) -> pd.DataFrame:
    valid = [frame for frame in frames if frame is not None and not frame.empty]
    if not valid:
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    combined = pd.concat(valid, ignore_index=True)
    return combined.drop_duplicates(subset=["file", "line", "rule", "description"], keep="first")


def is_maintainability_finding(rule: str) -> bool:
    return rule in MAINTAINABILITY_RULES


def extract_maintainability_findings(violations: pd.DataFrame) -> pd.DataFrame:
    if violations.empty:
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    smells = violations[violations["rule"].map(is_maintainability_finding)].copy()
    return smells.reset_index(drop=True)


def extract_cyclomatic_complexity_values(violations: pd.DataFrame) -> list[float]:
    values: list[float] = []
    ccn_rows = violations[violations["rule"] == "CyclomaticComplexity"]
    for description in ccn_rows["description"].astype(str):
        match = CCN_PATTERN.search(description)
        if match:
            values.append(float(match.group(1)))
    return values


def count_loc(java_files: list[Path]) -> int:
    total = 0
    for path in java_files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                continue
            total += 1
    return total


def compute_maintainability_index(
    avg_ccn: float,
    loc: int,
    halstead_volume: float | None,
) -> str | float:
    if halstead_volume is None or halstead_volume <= 0:
        return "Not Computed"
    volume = max(float(halstead_volume), 1.0)
    lines = max(int(loc), 1)
    mi = 171 - 5.2 * math.log(volume) - 0.23 * avg_ccn - 16.2 * math.log(lines)
    return round(mi, 4)


def mi_to_sqale_rating(mi: str | float) -> str:
    if isinstance(mi, str):
        return "Not Computed"
    if mi >= 85:
        return "A"
    if mi >= 70:
        return "B"
    if mi >= 55:
        return "C"
    if mi >= 40:
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


def run_pipeline(
    repo: Path,
    output: Path,
    pmd_home: Path,
    halstead_volume: float | None = None,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    errors: list[dict[str, str]] = []

    java_files = discover_java_files(repo)
    save_java_inventory(java_files, output / "java_files_inventory.csv")

    try:
        subprocess.run(["java", "-version"], capture_output=True, check=False)
    except FileNotFoundError:
        append_error(errors, "java", "Java runtime not found on PATH")
        write_error_log(errors, output / "error_log.txt")
        return {"benchmark_ready": False, "error": "Java runtime not found on PATH", "java_files": len(java_files)}

    ruleset_path = write_custom_ruleset(output / "custom_ruleset.xml")

    console_chunks: list[str] = []
    raw_out, raw_err, raw_code = run_pmd(pmd_home, repo, ruleset_path, "text")
    csv_out, csv_err, csv_code = run_pmd(pmd_home, repo, ruleset_path, "csv")
    json_out, json_err, json_code = run_pmd(pmd_home, repo, ruleset_path, "json")

    console_chunks.append("===== pmd check (text) =====\n" + combine_raw(raw_out, raw_err))
    console_chunks.append("===== pmd check (csv) =====\n" + combine_raw(csv_out, csv_err))
    console_chunks.append("===== pmd check (json) =====\n" + combine_raw(json_out, json_err))

    if raw_code not in PMD_SUCCESS_CODES and not raw_out.strip():
        append_error(errors, "pmd_text", f"PMD text run exited with code {raw_code}")
    if csv_code not in PMD_SUCCESS_CODES and not csv_out.strip():
        append_error(errors, "pmd_csv", f"PMD CSV run exited with code {csv_code}")
    if json_code not in PMD_SUCCESS_CODES and not json_out.strip():
        append_error(errors, "pmd_json", f"PMD JSON run exited with code {json_code}")

    (output / "pmd_raw_console_output.txt").write_text("\n".join(console_chunks), encoding="utf-8")
    (output / "pmd_output.csv").write_text(csv_out, encoding="utf-8")
    (output / "pmd_output.json").write_text(json_out, encoding="utf-8")

    violations = merge_violations(
        violations_from_csv(parse_pmd_csv(csv_out)),
        parse_pmd_json(json_out),
        parse_pmd_text_violations(raw_out),
    )
    violations.to_csv(output / "pmd_findings.csv", index=False)

    maintainability_df = extract_maintainability_findings(violations)
    code_smells_count = len(maintainability_df)

    pd.DataFrame([{"metric_name": "Code_Smells_Count", "metric_value": code_smells_count}]).to_csv(
        output / "code_smells_summary.csv", index=False
    )

    ccn_values = extract_cyclomatic_complexity_values(violations)
    avg_ccn = round(sum(ccn_values) / len(ccn_values), 4) if ccn_values else 0.0
    total_loc = count_loc(java_files)
    mi_value = compute_maintainability_index(avg_ccn, total_loc, halstead_volume)
    rating = mi_to_sqale_rating(mi_value)

    rating_rows = [{"metric_name": "Maintainability_Rating", "metric_value": rating}]
    if isinstance(mi_value, (int, float)):
        rating_rows.insert(0, {"metric_name": "Maintainability_Index", "metric_value": mi_value})
    pd.DataFrame(rating_rows).to_csv(output / "maintainability_rating_summary.csv", index=False)

    write_error_log(errors, output / "error_log.txt")

    return {
        "benchmark_ready": len(java_files) > 0,
        "java_files": len(java_files),
        "total_findings": len(violations),
        "code_smells_count": code_smells_count,
        "average_cyclomatic_complexity": avg_ccn,
        "maintainability_index": mi_value,
        "maintainability_rating": rating,
        "total_loc": total_loc,
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
