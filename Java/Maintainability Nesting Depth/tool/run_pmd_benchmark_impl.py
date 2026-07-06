"""PMD benchmark execution helpers."""
from __future__ import annotations

import io
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import os
os.environ.pop("PYTHONPATH", None)

import pandas as pd

EXCLUDED = {".git", "target", "build", "out", "bin", "generated", "node_modules", ".gradle", ".idea"}
NESTING_RULE = "AvoidDeeplyNestedIfStmts"
TEXT_PATTERN = re.compile(
    r"^(?P<file>.+):(?P<line>\d+):\s*(?P<rule>[^:]+):\s*(?P<message>.*)$"
)


def configure_java_runtime(jdk_home: Path | None = None) -> Path | None:
    if jdk_home is not None:
        jdk_home = jdk_home.resolve()
        java_bin = jdk_home / "bin"
        if (java_bin / ("java.exe" if sys.platform.startswith("win") else "java")).exists():
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


def discover_java(repo: Path) -> list[Path]:
    files = []
    for path in repo.rglob("*.java"):
        if any(part in EXCLUDED for part in path.parts):
            continue
        files.append(path.resolve())
    return sorted(files)


def run_pmd(pmd_home: Path, repo: Path, ruleset: str, fmt: str) -> tuple[str, str, int]:
    cmd = [
        str(pmd_exe(pmd_home)), "check", "-d", str(repo), "-R", ruleset, "-f", fmt,
        "--no-cache", "--no-progress",
    ]
    completed = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    return completed.stdout, completed.stderr, completed.returncode


def strip_java(line: str) -> str:
    line = re.sub(r"//.*$", "", line)
    line = re.sub(r"/\*.*?\*/", "", line)
    return line


def derive_depth(source: str, start: int, end: int | None = None) -> int:
    if_pat = re.compile(r"\bif\s*\(")
    return sum(1 for line in source.splitlines() if if_pat.search(strip_java(line)))


def violations_from_csv(csv_df: pd.DataFrame) -> pd.DataFrame:
    if csv_df.empty:
        return pd.DataFrame()
    frame = csv_df.copy()
    frame.columns = [str(col).strip().lower() for col in frame.columns]
    rows = []
    for _, record in frame.iterrows():
        rule = str(record.get("rule", ""))
        if NESTING_RULE not in rule:
            continue
        rows.append({
            "file": str(record.get("file", "")),
            "begin_line": int(record.get("line", 0) or 0),
            "end_line": int(record.get("line", 0) or 0),
            "rule": rule,
            "priority": record.get("priority", ""),
            "message": str(record.get("description", record.get("message", ""))),
        })
    return pd.DataFrame(rows)


def parse_text(raw: str) -> pd.DataFrame:
    rows = []
    for line in raw.splitlines():
        m = TEXT_PATTERN.match(line.strip())
        if m and NESTING_RULE in m.group("rule"):
            rows.append({
                "file": m.group("file"), "begin_line": int(m.group("line")),
                "end_line": int(m.group("line")), "rule": m.group("rule"),
                "priority": "", "message": m.group("message").strip(),
            })
    return pd.DataFrame(rows)


def merge_violations(*frames: pd.DataFrame) -> pd.DataFrame:
    valid = [f for f in frames if f is not None and not f.empty]
    if not valid:
        return pd.DataFrame()
    combined = pd.concat(valid, ignore_index=True)
    return combined.drop_duplicates(subset=["file", "begin_line", "rule"], keep="first")


def parse_xml_endlines(xml_text: str) -> dict[tuple[str, int], int]:
    mapping: dict[tuple[str, int], int] = {}
    if not xml_text.strip():
        return mapping
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return mapping
    for file_node in root.iter():
        if not str(file_node.tag).endswith("file"):
            continue
        file_name = file_node.attrib.get("name", "")
        for violation in file_node:
            if not str(violation.tag).endswith("violation"):
                continue
            begin = int(violation.attrib.get("beginline", 0) or 0)
            end = int(violation.attrib.get("endline", begin) or begin)
            mapping[(file_name, begin)] = end
    return mapping


def build_findings(violations: pd.DataFrame, xml_text: str) -> pd.DataFrame:
    endlines = parse_xml_endlines(xml_text)
    rows = []
    for _, r in violations.iterrows():
        source = Path(str(r["file"])).read_text(encoding="utf-8", errors="replace")
        begin = int(r["begin_line"])
        end = endlines.get((str(r["file"]), begin), begin)
        depth = derive_depth(source, begin, end)
        rows.append({**r.to_dict(), "end_line": end, "detected_nesting_depth": depth, "status": "derived"})
    return pd.DataFrame(rows)


def run_pipeline(repo: Path, output: Path, pmd_home: Path, ruleset: str) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    java_files = discover_java(repo)
    pd.DataFrame([
        {"absolute_path": str(p), "relative_path": str(p.relative_to(repo))} for p in java_files
    ]).to_csv(output / "java_files.csv", index=False)

    try:
        subprocess.run(["java", "-version"], capture_output=True, check=False)
    except FileNotFoundError as exc:
        return {"benchmark_ready": False, "error": "Java runtime not found on PATH", "java_files": len(java_files)}

    raw_out, raw_err, _ = run_pmd(pmd_home, repo, ruleset, "text")
    csv_out, _, _ = run_pmd(pmd_home, repo, ruleset, "csv")
    xml_out, _, _ = run_pmd(pmd_home, repo, ruleset, "xml")

    raw = raw_out + (("\n" + raw_err) if raw_err else "")
    (output / "pmd_raw_output.txt").write_text(raw, encoding="utf-8")
    (output / "pmd_output.csv").write_text(csv_out, encoding="utf-8")
    (output / "pmd_output.xml").write_text(xml_out, encoding="utf-8")
    (output / "error_log.txt").write_text("", encoding="utf-8")

    violations = merge_violations(parse_text(raw), violations_from_csv(pd.read_csv(io.StringIO(csv_out))))
    if violations.empty and csv_out.strip():
        violations = violations_from_csv(pd.read_csv(io.StringIO(csv_out)))
    findings = build_findings(violations, xml_out) if not violations.empty else pd.DataFrame(
        columns=["file", "begin_line", "end_line", "rule", "priority", "message", "detected_nesting_depth", "status"]
    )
    findings.to_csv(output / "nesting_depth_findings.csv", index=False)

    if findings.empty:
        summary = pd.DataFrame([
            {"metric_name": "Maintainability_Nesting_Depth", "metric_value": 0},
            {"metric_name": "Average_Nesting_Depth", "metric_value": 0},
        ])
    else:
        summary = pd.DataFrame([
            {"metric_name": "Maintainability_Nesting_Depth", "metric_value": int(findings["detected_nesting_depth"].max())},
            {"metric_name": "Average_Nesting_Depth", "metric_value": round(float(findings["detected_nesting_depth"].mean()), 4)},
        ])
    summary.to_csv(output / "maintainability_nesting_depth_summary.csv", index=False)

    return {
        "benchmark_ready": len(java_files) > 0,
        "java_files": len(java_files),
        "nesting_findings": len(findings),
        "max_nesting_depth": int(findings["detected_nesting_depth"].max()) if not findings.empty else 0,
        "repo_path": str(repo),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
