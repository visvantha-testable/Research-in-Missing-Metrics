"""PMD code smells benchmark execution helpers."""
from __future__ import annotations

import io
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

EXCLUDED = {".git", "target", "build", "out", "bin", "generated", "node_modules", ".gradle", ".idea"}
DEFAULT_RULESETS = [
    "category/java/bestpractices.xml",
    "category/java/codestyle.xml",
    "category/java/design.xml",
    "category/java/errorprone.xml",
]
CODE_SMELL_RULES = {
    "GodClass",
    "DataClass",
    "LongMethod",
    "ExcessiveMethodLength",
    "ExcessiveClassLength",
    "ExcessiveParameterList",
    "ExcessivePublicCount",
    "CyclomaticComplexity",
    "NPathComplexity",
    "TooManyFields",
    "TooManyMethods",
    "AvoidDeeplyNestedIfStmts",
    "CouplingBetweenObjects",
}
TEXT_PATTERN = re.compile(
    r"^(?P<file>.+):(?P<line>\d+):\s*(?P<rule>[^:]+):\s*(?P<message>.*)$"
)
PARSE_ERROR_PATTERN = re.compile(r"Error (?:while )?processing(?: file)?:?\s*(?P<file>.+)", re.IGNORECASE)
FINDINGS_COLUMNS = ["file", "begin_line", "end_line", "rule", "priority", "message", "ruleset"]
PMD_SUCCESS_CODES = {0, 4}


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


def join_rulesets(rulesets: list[str]) -> str:
    return ",".join(rulesets)


def discover_java_files(repo: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo.rglob("*.java"):
        if any(part in EXCLUDED for part in path.parts):
            continue
        files.append(path.resolve())
    return sorted(files)


def run_pmd(pmd_home: Path, repo: Path, rulesets: list[str], fmt: str) -> tuple[str, str, int]:
    cmd = [
        str(pmd_exe(pmd_home)),
        "check",
        "-d",
        str(repo),
        "-R",
        join_rulesets(rulesets),
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
                "begin_line": line_value,
                "end_line": line_value,
                "rule": str(record.get("rule", "")),
                "priority": record.get("priority", ""),
                "message": str(record.get("description", record.get("message", ""))),
                "ruleset": str(record.get("rule_set", record.get("ruleset", ""))),
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
                "begin_line": int(match.group("line")),
                "end_line": int(match.group("line")),
                "rule": match.group("rule").strip(),
                "priority": "",
                "message": match.group("message").strip(),
                "ruleset": "",
            }
        )
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def parse_pmd_xml_violations(xml_text: str) -> pd.DataFrame:
    if not xml_text.strip():
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    rows: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return pd.DataFrame(columns=FINDINGS_COLUMNS)

    for file_node in root.iter():
        if not str(file_node.tag).endswith("file"):
            continue
        file_name = file_node.attrib.get("name", "")
        for violation in file_node:
            if not str(violation.tag).endswith("violation"):
                continue
            begin_line = int(violation.attrib.get("beginline", violation.attrib.get("beginLine", 0)) or 0)
            end_line = int(violation.attrib.get("endline", violation.attrib.get("endLine", begin_line)) or begin_line)
            rows.append(
                {
                    "file": file_name,
                    "begin_line": begin_line,
                    "end_line": end_line,
                    "rule": violation.attrib.get("rule", ""),
                    "priority": violation.attrib.get("priority", ""),
                    "message": (violation.text or "").strip(),
                    "ruleset": violation.attrib.get("ruleset", ""),
                }
            )
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def merge_violations(*frames: pd.DataFrame) -> pd.DataFrame:
    valid = [frame for frame in frames if frame is not None and not frame.empty]
    if not valid:
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    combined = pd.concat(valid, ignore_index=True)
    return combined.drop_duplicates(subset=["file", "begin_line", "rule", "message"], keep="first")


def is_code_smell(rule: str) -> bool:
    return rule in CODE_SMELL_RULES


def extract_code_smells(violations: pd.DataFrame) -> pd.DataFrame:
    if violations.empty:
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    smells = violations[violations["rule"].map(is_code_smell)].copy()
    return smells.reset_index(drop=True)


def count_failed_files(raw_text: str, java_files: list[Path]) -> int:
    failed: set[str] = set()
    for match in PARSE_ERROR_PATTERN.finditer(raw_text):
        failed.add(str(Path(match.group("file").strip()).resolve()))
    for path in java_files:
        if f"Error processing {path}" in raw_text or f"Error while processing {path}" in raw_text:
            failed.add(str(path))
    return len(failed)


def run_pipeline(
    repo: Path,
    output: Path,
    pmd_home: Path,
    rulesets: list[str] | None = None,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    rulesets = rulesets or DEFAULT_RULESETS
    java_files = discover_java_files(repo)

    pd.DataFrame(
        [{"absolute_path": str(path), "relative_path": str(path.relative_to(repo))} for path in java_files]
    ).to_csv(output / "java_files.csv", index=False)

    error_lines: list[str] = []
    try:
        subprocess.run(["java", "-version"], capture_output=True, check=False)
    except FileNotFoundError:
        error_lines.append("Java runtime not found on PATH")
        (output / "error_log.txt").write_text("\n".join(error_lines), encoding="utf-8")
        return {"benchmark_ready": False, "error": "Java runtime not found on PATH", "java_files": len(java_files)}

    raw_out, raw_err, raw_code = run_pmd(pmd_home, repo, rulesets, "text")
    csv_out, csv_err, csv_code = run_pmd(pmd_home, repo, rulesets, "csv")
    xml_out, xml_err, xml_code = run_pmd(pmd_home, repo, rulesets, "xml")

    raw = combine_raw(raw_out, raw_err)
    (output / "pmd_raw_output.txt").write_text(raw, encoding="utf-8")
    (output / "pmd_output.csv").write_text(csv_out, encoding="utf-8")
    (output / "pmd_output.xml").write_text(xml_out, encoding="utf-8")

    if raw_code not in PMD_SUCCESS_CODES and not raw_out.strip():
        error_lines.append(f"PMD text run exited with code {raw_code}")
    if csv_code not in PMD_SUCCESS_CODES and not csv_out.strip():
        error_lines.append(f"PMD CSV run exited with code {csv_code}")
    if xml_code not in PMD_SUCCESS_CODES and not xml_out.strip():
        error_lines.append(f"PMD XML run exited with code {xml_code}")
    if csv_err.strip():
        error_lines.append(f"PMD CSV stderr: {csv_err.strip()}")
    if xml_err.strip():
        error_lines.append(f"PMD XML stderr: {xml_err.strip()}")

    violations = merge_violations(
        violations_from_csv(parse_pmd_csv(csv_out)),
        parse_pmd_text_violations(raw),
        parse_pmd_xml_violations(xml_out),
    )
    smells_df = extract_code_smells(violations)
    smells_df.to_csv(output / "code_smells_findings.csv", index=False)

    summary_df = pd.DataFrame([{"metric_name": "Code_Smells_Count", "metric_value": len(smells_df)}])
    summary_df.to_csv(output / "code_smells_summary.csv", index=False)
    (output / "error_log.txt").write_text("\n".join(error_lines), encoding="utf-8")

    files_failed = count_failed_files(raw, java_files)
    files_success = max(len(java_files) - files_failed, 0)

    return {
        "benchmark_ready": len(java_files) > 0 and len(smells_df) >= 5,
        "java_files": len(java_files),
        "files_success": files_success,
        "files_failed": files_failed,
        "total_findings": len(violations),
        "code_smells_count": len(smells_df),
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
