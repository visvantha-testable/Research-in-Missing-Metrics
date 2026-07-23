"""Path coverage evidence analysis helpers for JaCoCo artifacts."""
from __future__ import annotations

import csv
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pandas as pd

TOOL_ROOT = Path(__file__).resolve().parent
JACOCO_TOOL_ROOT = TOOL_ROOT.parent.parent / "JaCoCo Coverage" / "tool"
if str(JACOCO_TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(JACOCO_TOOL_ROOT))

from _jacoco_notebook_utils import (  # noqa: E402
    BuildStatus,
    copy_artifact,
    ensure_output_dir,
)

PATH_KEYWORDS = [
    "PATH",
    "Execution Path",
    "Path Coverage",
    "Traversal",
    "Loop Path",
    "Nested Path",
    "Exception Path",
    "Call Path",
    "Call Graph",
    "Function Path",
    "Route",
    "CFG",
    "Control Flow Graph",
    "Path ID",
    "Execution Trace",
    "Visited Path",
    "Unique Path",
]

PATH_METRICS = [
    "Path Execution Tracking",
    "Complete Coverage Path Verification",
    "Partial Path Coverage Detection",
    "Nested Condition Path Testing",
    "Loop Path Detection",
    "Unreachable Path Detection",
    "Exception Path Handling",
    "Multi-Function Path Tracking",
    "CI/CD Integration Test",
    "Path Detection Testing",
]

METRIC_KEYWORD_MAP: dict[str, list[str]] = {
    "Path Execution Tracking": ["path execution", "execution path", "execution trace", "visited path", "path id"],
    "Complete Coverage Path Verification": ["path coverage", "complete coverage path", "unique path"],
    "Partial Path Coverage Detection": ["partial path", "path coverage"],
    "Nested Condition Path Testing": ["nested path", "nested condition path"],
    "Loop Path Detection": ["loop path"],
    "Unreachable Path Detection": ["unreachable path"],
    "Exception Path Handling": ["exception path"],
    "Multi-Function Path Tracking": ["function path", "call path", "call graph", "multi-function"],
    "CI/CD Integration Test": ["ci/cd", "cicd integration"],
    "Path Detection Testing": ["path detection", "path coverage", "control flow graph", "cfg"],
}

JACOCO_COUNTER_TYPES = {"INSTRUCTION", "BRANCH", "LINE", "METHOD", "CLASS", "COMPLEXITY"}
IDENTIFIER_ATTRS = {"name", "sourcefilename", "desc", "class", "method"}


def copy_raw_jacoco_artifacts(status: BuildStatus, output_dir: Path) -> dict[str, bool]:
    ensure_output_dir(output_dir)
    return {
        "jacoco.exec": copy_artifact(status.jacoco_exec, output_dir / "jacoco.exec"),
        "jacoco.xml": copy_artifact(status.jacoco_xml, output_dir / "jacoco.xml"),
        "jacoco.csv": copy_artifact(status.jacoco_csv, output_dir / "jacoco.csv"),
        "index.html": copy_artifact(status.index_html, output_dir / "index.html"),
    }


def element_path(parent_path: str, element: ET.Element) -> str:
    tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag
    return f"{parent_path}/{tag}" if parent_path else tag


def dump_jacoco_xml_nodes(xml_path: Path, output_csv: Path) -> pd.DataFrame:
    root = ET.parse(xml_path).getroot()
    rows: list[dict[str, Any]] = []

    def walk(element: ET.Element, parent: str, depth: int) -> None:
        path = element_path(parent, element)
        attributes = "; ".join(f"{key}={value}" for key, value in sorted(element.attrib.items()))
        text = (element.text or "").strip()
        rows.append(
            {
                "element_path": path,
                "tag": element.tag.split("}")[-1] if "}" in element.tag else element.tag,
                "depth": depth,
                "attributes": attributes,
                "text": text,
            }
        )
        for counter in element.findall("counter"):
            counter_type = counter.get("type", "")
            rows.append(
                {
                    "element_path": f"{path}/counter[@type={counter_type}]",
                    "tag": "counter",
                    "depth": depth + 1,
                    "attributes": f"type={counter_type}; missed={counter.get('missed', '')}; covered={counter.get('covered', '')}",
                    "text": "",
                }
            )
        for child in element:
            if child.tag.endswith("counter"):
                continue
            walk(child, path, depth + 1)

    walk(root, "", 0)
    frame = pd.DataFrame(rows)
    frame.to_csv(output_csv, index=False)
    return frame


def extract_xml_counter_types(xml_path: Path) -> set[str]:
    root = ET.parse(xml_path).getroot()
    return {counter.get("type", "") for counter in root.iter() if counter.tag.endswith("counter")}


def read_artifact_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    if path.suffix.lower() == ".exec":
        try:
            raw = path.read_bytes()
            return raw.decode("utf-8", errors="ignore")
        except OSError:
            return ""
    return path.read_text(encoding="utf-8", errors="replace")


def find_keyword_matches(text: str, keyword: str) -> list[str]:
    if not text:
        return []
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    matches: list[str] = []
    for line in text.splitlines():
        if pattern.search(line):
            matches.append(line.strip()[:300])
    if not matches and pattern.search(text):
        start = pattern.search(text).start()
        matches.append(text[max(0, start - 40) : start + 80].replace("\n", " ")[:300])
    return matches


def is_schema_level_evidence(keyword: str, matched_text: str, artifact: str) -> bool:
    lowered = matched_text.lower()
    keyword_lower = keyword.lower()
    if artifact == "jacoco.xml":
        if 'type="PATH"' in matched_text or "type=PATH" in matched_text:
            return True
        if keyword_lower == "path coverage" and "path coverage" in lowered and "counter" in lowered:
            return True
        if keyword_lower in {"cfg", "control flow graph"} and "control flow graph" in lowered:
            return True
        if keyword_lower == "route" and ('name="route"' in matched_text or "name=route" in matched_text):
            return False
        if any(attr in matched_text for attr in ('name="', "sourcefilename=", "desc=")):
            return False
        if "<counter" in matched_text and keyword_lower == "path":
            return 'type="PATH"' in matched_text or "type=PATH" in matched_text
    if artifact == "jacoco.csv":
        return keyword_lower in lowered.split(",")[0:1] or keyword_lower in lowered[:120]
    if artifact == "index.html":
        return keyword_lower in {"path coverage", "execution path", "control flow graph", "cfg"} and keyword_lower in lowered
    if artifact == "jacoco_console_output.txt":
        return keyword_lower in {"path coverage", "execution path", "jacoco"} and keyword_lower in lowered
    return False


def search_path_keywords(artifacts: dict[str, Path | None]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for artifact_name, artifact_path in artifacts.items():
        text = read_artifact_text(artifact_path)
        for keyword in PATH_KEYWORDS:
            matches = find_keyword_matches(text, keyword)
            rows.append(
                {
                    "Artifact": artifact_name,
                    "Keyword": keyword,
                    "Found (Yes/No)": "Yes" if matches else "No",
                    "Matched Text": matches[0] if matches else "",
                }
            )
    return pd.DataFrame(rows, columns=["Artifact", "Keyword", "Found (Yes/No)", "Matched Text"])


def validate_path_metrics(
    keyword_df: pd.DataFrame,
    artifacts: dict[str, Path | None],
    xml_path: Path | None,
) -> pd.DataFrame:
    counter_types = extract_xml_counter_types(xml_path) if xml_path and xml_path.exists() else set()
    rows: list[dict[str, str]] = []

    for metric in PATH_METRICS:
        keywords = METRIC_KEYWORD_MAP.get(metric, [])
        supported = False
        evidence_source = ""
        artifact_name = ""
        comments = ""

        if "PATH" in counter_types or any("PATH" in value for value in counter_types):
            supported = True
            evidence_source = "JaCoCo XML counter type"
            artifact_name = "jacoco.xml"
            comments = f"Found counter types: {sorted(counter_types)}"

        if not supported:
            for keyword in keywords:
                hits = keyword_df[
                    (keyword_df["Keyword"].str.lower() == keyword.lower())
                    & (keyword_df["Found (Yes/No)"] == "Yes")
                ]
                for _, hit in hits.iterrows():
                    if is_schema_level_evidence(keyword, str(hit["Matched Text"]), str(hit["Artifact"])):
                        supported = True
                        evidence_source = "Keyword match in JaCoCo artifact schema/report text"
                        artifact_name = str(hit["Artifact"])
                        comments = str(hit["Matched Text"])[:300]
                        break
                if supported:
                    break

        if supported:
            status = "Supported"
        elif xml_path and xml_path.exists():
            status = "Not Supported"
            comments = (
                comments
                or f"JaCoCo emits counters {sorted(counter_types)} only; no explicit Path Coverage metric found."
            )
        else:
            status = "No Evidence Found"
            comments = comments or "Required JaCoCo artifacts were not available for validation."

        rows.append(
            {
                "Metric": metric,
                "Supported": status,
                "Evidence Source": evidence_source,
                "Artifact": artifact_name,
                "Comments": comments,
            }
        )
    return pd.DataFrame(rows, columns=["Metric", "Supported", "Evidence Source", "Artifact", "Comments"])
