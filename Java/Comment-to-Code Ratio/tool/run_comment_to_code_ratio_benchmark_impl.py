"""PMD Comment-to-Code Ratio benchmark execution helpers."""
from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
import sys
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
    "category/java/codestyle.xml",
    "category/java/design.xml",
    "category/java/documentation.xml",
    "category/java/bestpractices.xml",
    "category/java/errorprone.xml",
]
DOCUMENTATION_RULES = {
    "CommentRequired",
    "CommentSize",
    "UncommentedEmptyConstructor",
    "UncommentedEmptyMethodBody",
    "UncommentedEmptyMethod",
    "UncommentedEmptyClass",
}
COMPLEXITY_RULES = {"CyclomaticComplexity", "NPathComplexity", "ExcessiveMethodLength", "ExcessiveClassLength"}
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
}
FINDINGS_COLUMNS = ["file", "line", "column", "rule", "ruleset", "priority", "description"]
COMMENT_METRICS_COLUMNS = [
    "file",
    "total_lines",
    "comment_lines",
    "javadoc_lines",
    "block_comment_lines",
    "single_comment_lines",
    "code_lines",
]
PMD_SUCCESS_CODES = {0, 4}
TEXT_PATTERN = re.compile(r"^(?P<file>.+):(?P<line>\d+):\s*(?P<rule>[^:]+):\s*(?P<message>.*)$")
PMD_VERSION = "7.14.0"


def resolve_project_root(metric_root: Path) -> Path:
    current = metric_root.resolve()
    for _ in range(8):
        runtimes = current / "runtimes"
        if runtimes.is_dir() and (runtimes / "jdk-21").is_dir():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return metric_root.resolve().parent.parent


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


def download_pmd(pmd_home: Path, version: str = PMD_VERSION, cache_dir: Path | None = None) -> Path:
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
    lines = [
        '<?xml version="1.0"?>',
        '<ruleset name="custom_ruleset"',
        '    xmlns="http://pmd.sourceforge.net/ruleset/2.0.0"',
        '    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        '    xsi:schemaLocation="http://pmd.sourceforge.net/ruleset/2.0.0 https://pmd.sourceforge.io/ruleset_2_0_0.xsd">',
        "    <description>Custom Comment-to-Code Ratio ruleset for Java repositories</description>",
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
        rows.append(
            {
                "file": str(record.get("file", record.get("filename", ""))),
                "line": record.get("line", record.get("beginline", record.get("begin_line", ""))),
                "column": record.get("column", record.get("begincolumn", record.get("begin_column", ""))),
                "rule": str(record.get("rule", "")),
                "ruleset": str(record.get("rule_set", record.get("ruleset", ""))),
                "priority": record.get("priority", ""),
                "description": str(record.get("description", record.get("message", ""))),
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
                    "line": violation.get("beginline", violation.get("beginLine", "")),
                    "column": violation.get("begincolumn", violation.get("beginColumn", "")),
                    "rule": violation.get("rule", ""),
                    "ruleset": violation.get("ruleset", ""),
                    "priority": violation.get("priority", ""),
                    "description": violation.get("description", ""),
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
                "line": int(match.group("line")),
                "column": "",
                "rule": match.group("rule").strip(),
                "ruleset": "",
                "priority": "",
                "description": match.group("message").strip(),
            }
        )
    return pd.DataFrame(rows, columns=FINDINGS_COLUMNS)


def merge_violations(*frames: pd.DataFrame) -> pd.DataFrame:
    valid = [frame for frame in frames if frame is not None and not frame.empty]
    if not valid:
        return pd.DataFrame(columns=FINDINGS_COLUMNS)
    combined = pd.concat(valid, ignore_index=True)
    return combined.drop_duplicates(subset=["file", "line", "column", "rule", "description"], keep="first")


def _strip_strings_and_chars(line: str) -> str:
    result: list[str] = []
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '"':
            i += 1
            while i < len(line):
                if line[i] == "\\":
                    i += 2
                    continue
                if line[i] == '"':
                    i += 1
                    break
                i += 1
            result.append('""')
            continue
        if ch == "'":
            i += 1
            while i < len(line) and line[i] != "'":
                if line[i] == "\\":
                    i += 2
                    continue
                i += 1
            i += 1
            result.append("''")
            continue
        result.append(ch)
        i += 1
    return "".join(result)


def analyze_java_file_metrics(file_path: Path) -> dict[str, int]:
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {
            "total_lines": 0,
            "comment_lines": 0,
            "javadoc_lines": 0,
            "block_comment_lines": 0,
            "single_comment_lines": 0,
            "code_lines": 0,
        }

    lines = text.splitlines()
    total_lines = len(lines)
    javadoc_lines = 0
    block_comment_lines = 0
    single_comment_lines = 0
    code_lines = 0

    in_javadoc = False
    in_block = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if in_javadoc:
            javadoc_lines += 1
            if "*/" in stripped:
                in_javadoc = False
            continue

        if in_block:
            block_comment_lines += 1
            if "*/" in stripped:
                in_block = False
            continue

        if stripped.startswith("/**"):
            in_javadoc = True
            javadoc_lines += 1
            if stripped.count("*/") >= 1 and not stripped.startswith("/**/"):
                in_javadoc = False
            continue

        if stripped.startswith("/*"):
            in_block = True
            block_comment_lines += 1
            if stripped.count("*/") >= 1:
                in_block = False
            continue

        without_strings = _strip_strings_and_chars(line)
        code_part = without_strings.split("//", 1)[0].strip()
        if "//" in without_strings:
            single_comment_lines += 1

        if code_part:
            code_lines += 1

    comment_lines = javadoc_lines + block_comment_lines + single_comment_lines
    return {
        "total_lines": total_lines,
        "comment_lines": comment_lines,
        "javadoc_lines": javadoc_lines,
        "block_comment_lines": block_comment_lines,
        "single_comment_lines": single_comment_lines,
        "code_lines": code_lines,
    }


def build_comment_code_metrics(java_files: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in java_files:
        metrics = analyze_java_file_metrics(path)
        rows.append({"file": str(path), **metrics})
    return pd.DataFrame(rows, columns=COMMENT_METRICS_COLUMNS)


def compute_comment_ratio(metrics_df: pd.DataFrame) -> dict[str, float]:
    javadoc = pd.to_numeric(metrics_df["javadoc_lines"], errors="coerce").fillna(0)
    block = pd.to_numeric(metrics_df["block_comment_lines"], errors="coerce").fillna(0)
    single = pd.to_numeric(metrics_df["single_comment_lines"], errors="coerce").fillna(0)
    comment = pd.to_numeric(metrics_df["comment_lines"], errors="coerce").fillna(0)
    code = pd.to_numeric(metrics_df["code_lines"], errors="coerce").fillna(0)

    total_comment_lines = float((javadoc + block + single).sum())
    if total_comment_lines == 0:
        total_comment_lines = float(comment.sum())
    total_code_lines = float(code.sum())
    ratio = round(total_comment_lines / total_code_lines, 4) if total_code_lines > 0 else 0.0
    percentage = round(ratio * 100, 2)
    return {
        "total_comment_lines": total_comment_lines,
        "total_code_lines": total_code_lines,
        "comment_to_code_ratio": ratio,
        "comment_to_code_percentage": percentage,
    }


def build_maintainability_summary(violations: pd.DataFrame) -> pd.DataFrame:
    total_findings = len(violations)
    cc_violations = int(violations["rule"].isin(COMPLEXITY_RULES).sum()) if not violations.empty else 0
    doc_violations = int(violations["rule"].isin(DOCUMENTATION_RULES).sum()) if not violations.empty else 0
    if not violations.empty:
        doc_ruleset = violations["ruleset"].astype(str).str.contains("Documentation", case=False, na=False)
        doc_violations = max(doc_violations, int(doc_ruleset.sum()))
    maint_violations = int(violations["rule"].isin(MAINTAINABILITY_RULES).sum()) if not violations.empty else 0
    return pd.DataFrame(
        [
            {"metric_name": "Total_Code_Smells", "metric_value": total_findings},
            {"metric_name": "Cyclomatic_Complexity_Violations", "metric_value": cc_violations},
            {"metric_name": "Documentation_Violations", "metric_value": doc_violations},
            {"metric_name": "Maintainability_Violations", "metric_value": maint_violations},
        ]
    )


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


def run_pipeline(repo: Path, output: Path, pmd_home: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    errors: list[dict[str, str]] = []
    repo = repo.resolve()

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
        append_error(errors, "pmd_text", f"PMD text run exited with code {raw_code}: {raw_err.strip()}")
    if csv_code not in PMD_SUCCESS_CODES and not csv_out.strip():
        append_error(errors, "pmd_csv", f"PMD CSV run exited with code {csv_code}: {csv_err.strip()}")
    if json_code not in PMD_SUCCESS_CODES and not json_out.strip():
        append_error(errors, "pmd_json", f"PMD JSON run exited with code {json_code}: {json_err.strip()}")

    (output / "pmd_raw_console_output.txt").write_text("\n".join(console_chunks), encoding="utf-8")
    (output / "pmd_output.csv").write_text(csv_out, encoding="utf-8")
    (output / "pmd_output.json").write_text(json_out, encoding="utf-8")

    violations = merge_violations(
        violations_from_csv(parse_pmd_csv(csv_out)),
        parse_pmd_json(json_out),
        parse_pmd_text_violations(raw_out),
    )
    violations.to_csv(output / "pmd_findings.csv", index=False)

    comment_metrics_df = build_comment_code_metrics(java_files)
    comment_metrics_df.to_csv(output / "comment_code_metrics.csv", index=False)

    comment_ratio = compute_comment_ratio(comment_metrics_df)
    pd.DataFrame(
        [{"metric_name": "Comment_to_Code_Ratio", "metric_value": comment_ratio["comment_to_code_ratio"]}]
    ).to_csv(output / "comment_to_code_ratio_summary.csv", index=False)
    pd.DataFrame(
        [{"metric_name": "Comment_to_Code_Percentage", "metric_value": comment_ratio["comment_to_code_percentage"]}]
    ).to_csv(output / "comment_percentage_summary.csv", index=False)

    maintainability_df = build_maintainability_summary(violations)
    maintainability_df.to_csv(output / "maintainability_summary.csv", index=False)

    write_error_log(errors, output / "error_log.txt")

    code_smells = int(maintainability_df.loc[maintainability_df["metric_name"] == "Total_Code_Smells", "metric_value"].iloc[0])
    maint_violations = int(
        maintainability_df.loc[maintainability_df["metric_name"] == "Maintainability_Violations", "metric_value"].iloc[0]
    )

    return {
        "benchmark_ready": len(java_files) > 0 and comment_ratio["total_code_lines"] > 0,
        "java_files": len(java_files),
        "total_comment_lines": int(comment_ratio["total_comment_lines"]),
        "total_code_lines": int(comment_ratio["total_code_lines"]),
        "comment_to_code_ratio": comment_ratio["comment_to_code_ratio"],
        "comment_to_code_percentage": comment_ratio["comment_to_code_percentage"],
        "total_findings": len(violations),
        "code_smells": code_smells,
        "maintainability_violations": maint_violations,
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
