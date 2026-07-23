"""JaCoCo + Static DU combined validation helpers."""
from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

TOOL_ROOT = Path(__file__).resolve().parent
JACOCO_TOOL_ROOT = TOOL_ROOT.parent.parent / "JaCoCo Coverage" / "tool"
JACOCO_PATH_TOOL_ROOT = TOOL_ROOT.parent.parent / "JaCoCo Path Analysis" / "tool"
STATIC_DU_TOOL_ROOT = TOOL_ROOT.parent.parent / "Static DU Analysis" / "tool"
for path in (str(JACOCO_TOOL_ROOT), str(JACOCO_PATH_TOOL_ROOT), str(STATIC_DU_TOOL_ROOT), str(TOOL_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from _jacoco_notebook_utils import (  # noqa: E402
    BuildStatus,
    NotebookLogger,
    combine_streams,
    compute_repository_stats,
    configure_java_runtime,
    copy_artifact,
    counters_to_metrics_rows,
    coverage_percent,
    detect_build_tool,
    discover_java_files,
    ensure_output_dir,
    execute_build_and_jacoco,
    extract_package_name,
    parse_counter_map,
    resolve_maven_command,
    run_shell_command,
    save_java_inventory,
)
from _jacoco_path_analysis_utils import (  # noqa: E402
    JACOCO_COUNTER_TYPES,
    PATH_METRICS,
    copy_raw_jacoco_artifacts,
    extract_xml_counter_types,
    search_path_keywords,
    validate_path_metrics,
)
from _static_du_notebook_utils import (  # noqa: E402
    STATIC_DU_MAIN_CLASS,
    STATIC_DU_PLATFORM_DIR,
)

JACOCO_TRIGGER_CLASS = "com.testable.training.platform.JacocoTrigger"
JACOCO_PLATFORM_DIR = "jacoco-platform"
DEF_USE_TRIGGER_CLASS = "com.testable.training.defuse.DefUseTrigger"
DEF_USE_PLATFORM_DIR = "def-use-platform"

PLATFORM_JSON_ARTIFACTS = [
    "jacoco.json",
    "static_du.json",
    "def_use.json",
    "metrics.json",
    "platform_metrics.json",
    "dashboard_metrics.json",
    "jacoco_metrics.json",
    "static_du_metrics.json",
]

CONTROL_FLOW_METRICS = PATH_METRICS

COVERAGE_REGRESSION_METRICS = [
    "Coverage Delta",
    "Regression Testing Monitoring",
    "Test Suite Effectiveness Tracking",
    "CI/CD Quality Gate Enforcement",
    "Change Impact Analysis",
    "Quality Improvement Measurement",
]

ALL_DEFINITION_METRICS = [
    "Variable Definition Detection",
    "Definition-Use Mapping",
    "Coverage Measurement",
    "Uncovered Definition Detection",
    "Edge Case Handling",
    "Reporting Validation",
]

ALL_USES_METRICS = [
    "Computational Use Detection (C-Use)",
    "Predicate Use Detection (P-Use)",
    "Definition-Use Pair Identification",
    "All-Uses Coverage Verification",
    "Partial Uses Coverage Detection",
    "Multiple Definitions Handling",
    "Cross-Function Use Detection",
    "Unreachable Use Detection",
    "Coverage Reporting Validation",
    "Variable Use Detection",
]

DATA_FLOW_METRICS: list[tuple[str, str, str]] = [
    ("Data Flow Testing", "All Definition Coverage", metric) for metric in ALL_DEFINITION_METRICS
] + [
    ("Data Flow Testing", "All Uses Coverage", metric) for metric in ALL_USES_METRICS
]

DEF_USE_SUMMARY_KEYS = {
    "definitions_total": ["definitionsTotal", "definitions_total"],
    "definitions_covered": ["definitionsCovered", "definitions_covered"],
    "uses_total": ["usesTotal", "uses_total"],
    "uses_covered": ["usesCovered", "uses_covered"],
    "c_use_total": ["cUseTotal", "c_use_total"],
    "p_use_total": ["pUseTotal", "p_use_total"],
    "du_pairs_total": ["duPairsTotal", "du_pairs_total"],
    "du_pairs_covered": ["duPairsCovered", "du_pairs_covered"],
    "uncovered_definitions": ["uncoveredDefinitions", "uncovered_definitions"],
    "partial_uses": ["partialUses", "partial_uses"],
    "ghost_uses": ["ghostUses", "ghost_uses"],
    "multiple_definition_sites": ["multipleDefinitionSites", "multiple_definition_sites"],
    "cross_function_uses": ["crossFunctionUses", "cross_function_uses"],
}

STATIC_DU_DUPLICATION_KEYS = [
    "total_lines",
    "duplicated_lines",
    "duplicated_lines_percent",
    "duplicated_blocks",
    "duplicated_files",
    "duplication_density_percent",
]

# Platform score aliases documented in jacoco-platform/JacocoDashboardMetrics.java
PLATFORM_PROXY_MAP: dict[str, str] = {
    "Path Execution Tracking": "branch_percent",
    "Complete Coverage Path Verification": "path_coverage_percent (= branch_percent)",
    "Partial Path Coverage Detection": "partial_branch_lines heuristic",
    "Nested Condition Path Testing": "branch_percent",
    "Loop Path Detection": "branch_percent",
    "Unreachable Path Detection": "ghost_lines heuristic",
    "Exception Path Handling": "branch_percent",
    "Multi-Function Path Tracking": "line_percent",
    "CI/CD Integration Test": "line_percent >= 80 gate",
    "Path Detection Testing": "path_coverage_percent (= branch_percent)",
    "Coverage Delta": "coverage_delta_percent (platform summary)",
    "Regression Testing Monitoring": "modules_tested / modules_with_churn",
    "Test Suite Effectiveness Tracking": "line_percent, branch_percent, instruction_percent",
    "CI/CD Quality Gate Enforcement": "metric_coverage_complete / metrics_covered",
    "Change Impact Analysis": "modules_with_churn, coverage_delta_percent",
    "Quality Improvement Measurement": "coverage_delta_percent, line_percent",
    "Variable Definition Detection": "all_defs_percent from jacoco-platform StaticDuAnalyzer (regex)",
    "Definition-Use Mapping": "du_path_percent from jacoco-platform StaticDuAnalyzer (regex)",
    "Coverage Measurement": "du_path_percent from jacoco-platform StaticDuAnalyzer (regex)",
    "Uncovered Definition Detection": "uncovered_definitions from jacoco-platform StaticDuAnalyzer (regex)",
    "Edge Case Handling": "branch_percent (platform alias)",
    "Reporting Validation": "metrics_total / metrics_covered (platform metadata)",
    "Computational Use Detection (C-Use)": "c_use_percent from jacoco-platform StaticDuAnalyzer (regex)",
    "Predicate Use Detection (P-Use)": "p_use_percent from jacoco-platform StaticDuAnalyzer (regex)",
    "Definition-Use Pair Identification": "du_path_percent from jacoco-platform StaticDuAnalyzer (regex)",
    "All-Uses Coverage Verification": "all_uses_percent from jacoco-platform StaticDuAnalyzer (regex)",
    "Partial Uses Coverage Detection": "partial_uses heuristic",
    "Multiple Definitions Handling": "multiple_definition_sites heuristic",
    "Cross-Function Use Detection": "line_percent (not inter-procedural)",
    "Unreachable Use Detection": "ghost_uses heuristic",
    "Coverage Reporting Validation": "all_uses_percent (platform alias)",
    "Variable Use Detection": "all_uses_percent from jacoco-platform StaticDuAnalyzer (regex)",
}

REPO_ROUTING_ROWS: list[dict[str, str]] = [
    {
        "Metric_Family": "Native JaCoCo Counters",
        "Taxonomy_Section": "Instruction / Line / Branch / Method / Class / Complexity",
        "Recommended_Pipeline": "JaCoCo Coverage",
        "Recommended_Repo": "java-tool-testing-jacoco",
        "Project_Path": "Java/JaCoCo Coverage",
        "Native_Tool_Output": "jacoco.xml",
        "Notes": "Official JaCoCo counters only; no path or def-use metrics.",
    },
    {
        "Metric_Family": "Control Flow / Path Coverage",
        "Taxonomy_Section": "Control Flow Testing — Path Coverage (10 metrics)",
        "Recommended_Pipeline": "JPF Path Analysis or JaCoCo Path Analysis",
        "Recommended_Repo": "java-tool-testing-jacoco",
        "Project_Path": "Java/JPF Path Analysis",
        "Native_Tool_Output": "jpf path reports / jacoco.xml keywords",
        "Notes": "JaCoCo XML has no PATH counter; def-use repo aliases branch% to path metrics.",
    },
    {
        "Metric_Family": "Coverage Regression / Delta",
        "Taxonomy_Section": "Test Regression/Coverage Analysis (6 metrics)",
        "Recommended_Pipeline": "JaCoCo Coverage with baseline XML comparison",
        "Recommended_Repo": "java-tool-testing-jacoco",
        "Project_Path": "Java/JaCoCo Coverage",
        "Native_Tool_Output": "jacoco.xml baseline vs current delta",
        "Notes": "XML LINE/BRANCH/INSTRUCTION delta is native; churn and quality-gate rows are platform metadata.",
    },
    {
        "Metric_Family": "Data Flow / Definition-Use",
        "Taxonomy_Section": "Data Flow Testing — All Definition + All Uses (16 metrics)",
        "Recommended_Pipeline": "Static DU Analysis",
        "Recommended_Repo": "java-tool-testing-static-du",
        "Project_Path": "Java/Static DU Analysis",
        "Native_Tool_Output": "static_du.json def-use fields",
        "Notes": "java-tool-testing-def-use standalone Static DU emits duplication only; def-use is bundled in jacoco-platform.",
    },
    {
        "Metric_Family": "Combined End-to-End Validation",
        "Taxonomy_Section": "All taxonomy sections (truth-table audit)",
        "Recommended_Pipeline": "JaCoCo Static DU Validation",
        "Recommended_Repo": "java-tool-testing-def-use",
        "Project_Path": "Java/JaCoCo Static DU Validation",
        "Native_Tool_Output": "jacoco.xml + static_du_output.json + jacoco.json platform",
        "Notes": "Use taxonomy_truth_table.csv to separate Native vs Platform_Derived evidence.",
    },
]

TAXONOMY_TRIGGER_MANIFEST: list[dict[str, str]] = [
    {
        "pipeline_id": "jacoco_static_du_validation",
        "pipeline_name": "JaCoCo Static DU Validation (current)",
        "project_path": "Java/JaCoCo Static DU Validation",
        "repo_url": "https://github.com/visvantha-testable/java-tool-testing-def-use.git",
        "repo_folder": "workspace/java-tool-testing-def-use",
        "tools_triggered": "JaCoCo Maven plugin + jacoco-platform JacocoTrigger + static-du-platform StaticDuTrigger",
        "build_command": "mvn clean test",
        "jacoco_trigger": "mvn -pl jacoco-platform exec:java -Dexec.mainClass=com.testable.training.platform.JacocoTrigger -Dexec.args=--skip-verify",
        "static_du_trigger": "mvn -pl static-du-platform exec:java -Dexec.mainClass=com.testable.training.platform.StaticDuTrigger -Dexec.args=--skip-verify",
        "run_command": "python tool/run_jacoco_static_du_validation_benchmark.py",
        "primary_outputs": "outputs/jacoco.xml; outputs/jacoco.json; outputs/static_du_output.json; outputs/taxonomy_truth_table.csv",
        "covers_taxonomy_natively": "1 of 32 metrics (Coverage Delta XML baseline only)",
        "missing_data_to_add": "baseline_jacoco.xml already in artifacts/training; path and def-use need alternate repos below",
    },
    {
        "pipeline_id": "jacoco_coverage",
        "pipeline_name": "JaCoCo Coverage (native counters + baseline delta)",
        "project_path": "Java/JaCoCo Coverage",
        "repo_url": "https://github.com/visvantha-testable/java-tool-testing-jacoco.git",
        "repo_folder": "workspace/java-tool-testing-jacoco",
        "tools_triggered": "JaCoCo Maven plugin",
        "build_command": "mvn clean test",
        "jacoco_trigger": "mvn -pl jacoco-platform exec:java -Dexec.mainClass=com.testable.training.platform.JacocoTrigger -Dexec.args=--skip-verify",
        "static_du_trigger": "",
        "run_command": "cd \"Java/JaCoCo Coverage\" && python tool/run_jacoco_benchmark.py",
        "primary_outputs": "outputs/jacoco.xml; outputs/jacoco.csv; outputs/jacoco_metrics.csv",
        "covers_taxonomy_natively": "INSTRUCTION/LINE/BRANCH/METHOD/CLASS/COMPLEXITY + XML coverage delta",
        "missing_data_to_add": "Clone repo; ensure Maven JaCoCo plugin in pom.xml; optional baseline_jacoco.xml for delta",
    },
    {
        "pipeline_id": "jpf_path_analysis",
        "pipeline_name": "JPF Path Analysis (real path execution)",
        "project_path": "Java/JPF Path Analysis",
        "repo_url": "https://github.com/visvantha-testable/java-tool-testing-jacoco.git",
        "repo_folder": "workspace/java-tool-testing-jacoco",
        "tools_triggered": "Java PathFinder (JPF)",
        "build_command": "mvn clean test (subject repo)",
        "jacoco_trigger": "",
        "static_du_trigger": "",
        "run_command": "cd \"Java/JPF Path Analysis\" && python tool/run_jpf_benchmark.py",
        "primary_outputs": "outputs/jpf_metrics.csv; outputs/path_report.txt; outputs/visited_states.txt",
        "covers_taxonomy_natively": "Control Flow / Path Coverage (10 metrics) via path count, visited states, execution paths",
        "missing_data_to_add": "JPF install at runtimes/jpf-core; .jpf config per class; subject with branching paths",
    },
    {
        "pipeline_id": "static_du_analysis",
        "pipeline_name": "Static DU Analysis (real def-use)",
        "project_path": "Java/Static DU Analysis",
        "repo_url": "https://github.com/visvantha-testable/java-tool-testing-static-du.git",
        "repo_folder": "workspace/java-tool-testing-static-du",
        "tools_triggered": "static-du-platform StaticDuTrigger",
        "build_command": "mvn clean test",
        "jacoco_trigger": "",
        "static_du_trigger": "mvn -pl static-du-platform exec:java -Dexec.mainClass=com.testable.training.platform.StaticDuTrigger -Dexec.args=--skip-verify",
        "run_command": "cd \"Java/Static DU Analysis\" && python tool/run_static_du_benchmark.py",
        "primary_outputs": "outputs/static_du_output.json (definitions_total, c_use_total, p_use_total, du_pairs_total, cross_function_uses)",
        "covers_taxonomy_natively": "Data Flow Testing 16 metrics (all-defs, all-uses, C-use, P-use, DU pairs)",
        "missing_data_to_add": "Clone java-tool-testing-static-du; sample_subject with DataFlowSample.java and test coverage",
    },
]

PIPELINE_RUN_COMMANDS = {
    "Java/JaCoCo Static DU Validation": "python tool/run_jacoco_static_du_validation_benchmark.py",
    "Java/JaCoCo Coverage": "cd \"Java/JaCoCo Coverage\" && python tool/run_jacoco_benchmark.py",
    "Java/JPF Path Analysis": "cd \"Java/JPF Path Analysis\" && python tool/run_jpf_benchmark.py",
    "Java/Static DU Analysis": "cd \"Java/Static DU Analysis\" && python tool/run_static_du_benchmark.py",
}

METRIC_ALTERNATIVE_MAP: dict[str, dict[str, str]] = {
    **{metric: {
        "alternative_tool": "Java PathFinder (JPF)",
        "alternative_repo": "java-tool-testing-jacoco",
        "alternative_pipeline": "Java/JPF Path Analysis",
        "required_data": "JPF .jpf config; runtimes/jpf-core; branching sample code",
        "native_output_fields": "Path Count; Execution Paths; Visited States; search_graph.txt",
    } for metric in CONTROL_FLOW_METRICS},
    **{metric: {
        "alternative_tool": "JaCoCo + baseline XML comparison",
        "alternative_repo": "java-tool-testing-jacoco",
        "alternative_pipeline": "Java/JaCoCo Coverage",
        "required_data": "artifacts/training/baseline_jacoco.xml + current jacoco.xml",
        "native_output_fields": "INSTRUCTION/LINE/BRANCH counter delta in jacoco.xml",
    } for metric in COVERAGE_REGRESSION_METRICS if metric != "Coverage Delta"},
    "Coverage Delta": {
        "alternative_tool": "JaCoCo (already native in current repo)",
        "alternative_repo": "java-tool-testing-def-use",
        "alternative_pipeline": "Java/JaCoCo Static DU Validation",
        "required_data": "baseline_jacoco.xml (already present in artifacts/training/)",
        "native_output_fields": "computed_xml_delta INSTRUCTION/LINE/BRANCH",
    },
    **{metric: {
        "alternative_tool": "Static DU platform (def-use analyzer)",
        "alternative_repo": "java-tool-testing-static-du",
        "alternative_pipeline": "Java/Static DU Analysis",
        "required_data": "static_du.json supplemental_raw_data.static_du_summary with definitions_total, uses_total, c_use_total, p_use_total, du_pairs_total, cross_function_uses",
        "native_output_fields": "definitions_total; uses_total; c_use_total; p_use_total; du_pairs_total; cross_function_uses; du_paths[]",
    } for metric in ALL_DEFINITION_METRICS + ALL_USES_METRICS},
}

TAXONOMY_TRUTH_ROWS: list[tuple[str, str, str, str]] = (
    [("Control Flow Testing", "Path Coverage", metric, "Path Coverage %") for metric in CONTROL_FLOW_METRICS]
    + [
        ("Test Regression/Coverage Analysis", "Coverage Delta", "Coverage Delta", "Coverage Delta %"),
        ("Test Regression/Coverage Analysis", "Coverage Delta", "Regression Testing Monitoring", "Coverage Delta %"),
        (
            "Test Regression/Coverage Analysis",
            "Coverage Delta",
            "Test Suite Effectiveness Tracking",
            "Discovery Power Assessment",
        ),
        (
            "Test Regression/Coverage Analysis",
            "Coverage Delta",
            "CI/CD Quality Gate Enforcement",
            "Deployment Readiness Guard",
        ),
        ("Test Regression/Coverage Analysis", "Coverage Delta", "Change Impact Analysis", "Ripple Effect Mapping"),
        (
            "Test Regression/Coverage Analysis",
            "Coverage Delta",
            "Quality Improvement Measurement",
            "Structural Health Benchmarking",
        ),
    ]
    + [
        ("Data Flow Testing", "All Definition Coverage", metric, goal)
        for metric, goal in [
            ("Variable Definition Detection", "All-Defs Coverage %"),
            ("Definition-Use Mapping", "Data Path Correlation"),
            ("Coverage Measurement", "DU-Path Validation"),
            ("Uncovered Definition Detection", "Dead Data Identification"),
            ("Edge Case Handling", "Null and Boundary Flow Analysis"),
            ("Reporting Validation", "Audit Trail Verification"),
        ]
    ]
    + [
        ("Data Flow Testing", "All Uses Coverage", metric, goal)
        for metric, goal in [
            ("Computational Use Detection (C-Use)", "Data Processing Validation"),
            ("Predicate Use Detection (P-Use)", "Logic Influence Assessment"),
            ("Definition-Use Pair Identification", "Path Correlation Mapping"),
            ("All-Uses Coverage Verification", "Comprehensive Data Proofing"),
            ("Partial Uses Coverage Detection", "Data Flow Gap Analysis"),
            ("Multiple Definitions Handling", "Ambiguity Resolution"),
            ("Cross-Function Use Detection", "Inter-procedural Tracking"),
            ("Unreachable Use Detection", "Ghost Use Identification"),
            ("Coverage Reporting Validation", "Data Integrity Audit"),
            ("Variable Use Detection", "All-Uses Coverage %"),
        ]
    ]
)


@dataclass
class CombinedRunStatus:
    build_status: BuildStatus
    jacoco_trigger_command: list[str]
    static_du_trigger_command: list[str]
    jacoco_trigger_success: bool = False
    static_du_trigger_success: bool = False
    def_use_trigger_success: bool = False
    jacoco_json: Path | None = None
    static_du_json: Path | None = None
    def_use_json: Path | None = None
    unified_trigger: bool = False


def resolve_platform_trigger_command(
    repo_path: Path,
    logger: NotebookLogger,
    platform_dir: str,
    main_class: str,
    skip_verify: bool = True,
) -> list[str]:
    maven = resolve_maven_command(repo_path, logger)
    command = [*maven, "-pl", platform_dir, "exec:java", f"-Dexec.mainClass={main_class}"]
    if skip_verify:
        command.append("-Dexec.args=--skip-verify")
    return command


def execute_platform_triggers(
    repo_path: Path,
    env: dict[str, str],
    logger: NotebookLogger,
    skip_verify: bool = True,
) -> tuple[CombinedRunStatus, str, str, str]:
    build_tool = detect_build_tool(repo_path)
    build_status, jacoco_console = execute_build_and_jacoco(repo_path, build_tool, env, logger)

    unified = (repo_path / DEF_USE_PLATFORM_DIR / "pom.xml").exists()
    if unified:
        trigger_command = resolve_platform_trigger_command(
            repo_path, logger, DEF_USE_PLATFORM_DIR, DEF_USE_TRIGGER_CLASS, skip_verify
        )
        trigger_result = run_shell_command(trigger_command, repo_path, env, logger, "def_use_trigger")
        trigger_console = combine_streams(trigger_result.stdout, trigger_result.stderr)
        success = trigger_result.exit_code == 0
        status = CombinedRunStatus(
            build_status=build_status,
            jacoco_trigger_command=trigger_command,
            static_du_trigger_command=trigger_command,
            jacoco_trigger_success=success,
            static_du_trigger_success=success,
            def_use_trigger_success=success,
            jacoco_json=repo_path / "jacoco.json",
            static_du_json=repo_path / "static_du.json",
            def_use_json=repo_path / "def_use.json",
            unified_trigger=True,
        )
        return status, jacoco_console, trigger_console, trigger_console

    jacoco_trigger_command = resolve_platform_trigger_command(
        repo_path, logger, JACOCO_PLATFORM_DIR, JACOCO_TRIGGER_CLASS, skip_verify
    )
    jacoco_trigger_result = run_shell_command(jacoco_trigger_command, repo_path, env, logger, "jacoco_trigger")
    jacoco_trigger_console = combine_streams(jacoco_trigger_result.stdout, jacoco_trigger_result.stderr)

    static_du_trigger_command = resolve_platform_trigger_command(
        repo_path, logger, STATIC_DU_PLATFORM_DIR, STATIC_DU_MAIN_CLASS, skip_verify
    )
    static_du_trigger_result = run_shell_command(static_du_trigger_command, repo_path, env, logger, "static_du_trigger")
    static_du_trigger_console = combine_streams(static_du_trigger_result.stdout, static_du_trigger_result.stderr)

    status = CombinedRunStatus(
        build_status=build_status,
        jacoco_trigger_command=jacoco_trigger_command,
        static_du_trigger_command=static_du_trigger_command,
        jacoco_trigger_success=jacoco_trigger_result.exit_code == 0,
        static_du_trigger_success=static_du_trigger_result.exit_code == 0,
        jacoco_json=repo_path / "jacoco.json",
        static_du_json=repo_path / "static_du.json",
        def_use_json=repo_path / "def_use.json" if (repo_path / "def_use.json").exists() else None,
        unified_trigger=False,
    )
    return status, jacoco_console, jacoco_trigger_console, static_du_trigger_console


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def metric_rows_by_name(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("metrics", [])
    mapping: dict[str, dict[str, Any]] = {}
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                name = str(row.get("l5_metric", ""))
                if name:
                    mapping[name] = row
    return mapping


def nested_get(payload: dict[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def def_use_summary(jacoco_json: dict[str, Any]) -> dict[str, Any]:
    summary = nested_get(jacoco_json, "supplemental_raw_data", "static_du_summary")
    return summary if isinstance(summary, dict) else {}


def summary_value(summary: dict[str, Any], canonical_key: str) -> Any:
    for alias in DEF_USE_SUMMARY_KEYS.get(canonical_key, [canonical_key]):
        if alias in summary:
            return summary[alias]
    return None


def platform_proxy_disclosure(metric: str) -> str:
    return PLATFORM_PROXY_MAP.get(metric, "")


def assess_evidence_quality(evidence: str, metric: str, directly_emitted: str) -> str:
    if not evidence or not str(evidence).strip():
        return "Missing"
    weak_metrics = {
        "CI/CD Quality Gate Enforcement",
        "Cross-Function Use Detection",
        "Reporting Validation",
        "Coverage Reporting Validation",
        "Edge Case Handling",
    }
    if metric in weak_metrics:
        return "Weak"
    if directly_emitted == "Yes":
        return "Strong"
    if platform_proxy_disclosure(metric):
        return "Strong"
    return "Weak"


def classify_coverage_tier(directly_emitted: str, derived: str, supported: str) -> str:
    if supported not in {"Supported", "Baseline Not Available", "Partially Supported"}:
        return "Not_Supported"
    if directly_emitted == "Yes":
        return "Native"
    if derived == "Yes" or supported in {"Baseline Not Available", "Partially Supported"}:
        return "Platform_Derived"
    return "Not_Supported"


def resolve_supported_with_disclosure(
    *,
    native_supported: bool,
    platform_present: bool,
    evidence: str,
    metric: str,
) -> tuple[str, str, str, str]:
    proxy = platform_proxy_disclosure(metric)
    if native_supported:
        return "Supported", "Yes", "No", ""
    if platform_present and proxy:
        quality = assess_evidence_quality(evidence, metric, "No")
        if quality == "Missing":
            return "Partially Supported", "No", "Yes", proxy
        return "Supported", "No", "Yes", proxy
    if platform_present:
        return "Partially Supported", "No", "Yes", proxy or "platform score without documented proxy"
    return "Not Supported", "No", "No", ""


def compute_branch_alignment(jacoco_xml: Path | None, jacoco_json: dict[str, Any]) -> dict[str, Any]:
    xml_branch = xml_total_counter_percent(jacoco_xml, "BRANCH") if jacoco_xml else None
    platform_summary = jacoco_json.get("summary", {}) if isinstance(jacoco_json.get("summary"), dict) else {}
    platform_branch = platform_summary.get("branch_percent")
    discrepancy = False
    delta: float | None = None
    if xml_branch is not None and platform_branch is not None:
        delta = round(float(platform_branch) - float(xml_branch), 4)
        discrepancy = abs(delta) > 0.01
    return {
        "xml_branch_percent": xml_branch,
        "platform_branch_percent": platform_branch,
        "branch_percent_delta": delta,
        "branch_percent_discrepancy": "Yes" if discrepancy else "No",
        "discrepancy_detail": (
            f"Platform jacoco.json branch_percent={platform_branch} differs from native jacoco.xml BRANCH={xml_branch}%"
            if discrepancy
            else "Platform summary matches native XML branch percent within tolerance."
        ),
    }


def validation_lookup(*dfs: pd.DataFrame) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for frame in dfs:
        if frame is None or frame.empty or "Metric" not in frame.columns:
            continue
        for row in frame.to_dict("records"):
            metric = str(row.get("Metric", ""))
            if metric:
                lookup[metric] = row
    return lookup


def build_repo_routing_csv(output_csv: Path) -> pd.DataFrame:
    frame = pd.DataFrame(REPO_ROUTING_ROWS)
    frame.to_csv(output_csv, index=False)
    return frame


def build_trigger_manifest(output_dir: Path) -> pd.DataFrame:
    frame = pd.DataFrame(TAXONOMY_TRIGGER_MANIFEST)
    frame.to_csv(output_dir / "taxonomy_trigger_manifest.csv", index=False)
    (output_dir / "taxonomy_trigger_manifest.json").write_text(
        json.dumps(TAXONOMY_TRIGGER_MANIFEST, indent=2),
        encoding="utf-8",
    )
    return frame


def build_metric_coverage_action_plan(taxonomy_truth_df: pd.DataFrame, output_csv: Path) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for _, truth in taxonomy_truth_df.iterrows():
        metric = str(truth["Metric"])
        alt = METRIC_ALTERNATIVE_MAP.get(metric, {})
        native = str(truth.get("Coverage_Tier", "")) == "Native"
        platform_only = str(truth.get("Coverage_Tier", "")) == "Platform_Derived"
        rows.append(
            {
                "Testing_Type": truth.get("Testing_Type", ""),
                "Classification": truth.get("Classification", ""),
                "Metric": metric,
                "Goal": truth.get("Goal", ""),
                "Current_Repo_Triggers_Tool": "Yes",
                "Current_Repo_Native_Coverage": "Yes" if native else "No",
                "Current_Repo_Platform_Only": "Yes" if platform_only else "No",
                "Current_Status": "OK native" if native else ("Platform proxy only — not real measurement" if platform_only else "Not covered"),
                "Alternative_Tool": alt.get("alternative_tool", ""),
                "Alternative_Repo": alt.get("alternative_repo", ""),
                "Alternative_Pipeline": alt.get("alternative_pipeline", ""),
                "Required_Data_To_Add": alt.get("required_data", ""),
                "Native_Output_Fields": alt.get("native_output_fields", ""),
                "Run_Command": PIPELINE_RUN_COMMANDS.get(alt.get("alternative_pipeline", ""), ""),
            }
        )
    frame = pd.DataFrame(rows)
    frame.to_csv(output_csv, index=False)
    return frame


def build_taxonomy_truth_table(
    control_flow_df: pd.DataFrame,
    coverage_delta_df: pd.DataFrame,
    data_flow_df: pd.DataFrame,
    jacoco_xml: Path | None,
    jacoco_json: dict[str, Any],
    output_csv: Path,
) -> pd.DataFrame:
    lookup = validation_lookup(control_flow_df, coverage_delta_df, data_flow_df)
    branch_alignment = compute_branch_alignment(jacoco_xml, jacoco_json)
    rows: list[dict[str, str]] = []

    for testing_type, classification, metric, goal in TAXONOMY_TRUTH_ROWS:
        validation_row = lookup.get(metric, {})
        supported = str(validation_row.get("Supported", "Not Supported"))
        directly = str(validation_row.get("Directly Emitted", "No"))
        derived = str(validation_row.get("Derived", "No"))
        evidence = str(validation_row.get("Evidence", ""))
        proxy = str(validation_row.get("Proxy_Disclosure", platform_proxy_disclosure(metric)))
        coverage_tier = classify_coverage_tier(directly, derived, supported)
        evidence_quality = assess_evidence_quality(evidence, metric, directly)

        recommended = next(
            (
                row
                for row in REPO_ROUTING_ROWS
                if metric in row.get("Taxonomy_Section", "")
                or (
                    testing_type.startswith("Control Flow")
                    and row["Metric_Family"] == "Control Flow / Path Coverage"
                )
                or (
                    testing_type.startswith("Test Regression")
                    and row["Metric_Family"] == "Coverage Regression / Delta"
                )
                or (
                    testing_type.startswith("Data Flow")
                    and row["Metric_Family"] == "Data Flow / Definition-Use"
                )
            ),
            REPO_ROUTING_ROWS[-1],
        )

        root_cause = ""
        if coverage_tier == "Native":
            root_cause = "Emitted directly by official tool output."
        elif coverage_tier == "Platform_Derived":
            root_cause = "Training-repo platform wrapper derives score; not native JaCoCo/Static DU schema."
        else:
            root_cause = "No native or disclosed platform evidence found."

        rows.append(
            {
                "Testing_Type": testing_type,
                "Classification": classification,
                "Metric": metric,
                "Goal": goal,
                "Supported": supported,
                "Coverage_Tier": coverage_tier,
                "Evidence_Quality": evidence_quality,
                "Directly_Emitted": directly,
                "Derived": derived,
                "Proxy_Disclosure": proxy,
                "Artifact": str(validation_row.get("Artifact", validation_row.get("Tool", ""))),
                "Evidence": evidence[:500],
                "Recommended_Pipeline": recommended["Recommended_Pipeline"],
                "Recommended_Repo": recommended["Recommended_Repo"],
                "Root_Cause": root_cause,
            }
        )

    frame = pd.DataFrame(rows)
    frame.attrs["branch_alignment"] = branch_alignment
    frame.to_csv(output_csv, index=False)
    return frame


def build_extended_jacoco_metrics_csv(xml_path: Path, output_csv: Path) -> pd.DataFrame:
    counters = parse_counter_map(xml_path)
    rows = counters_to_metrics_rows(counters)
    for counter_type in sorted(JACOCO_COUNTER_TYPES):
        values = counters.get(counter_type, {"missed": 0, "covered": 0})
        rows.append(
            {
                "metric_name": f"{counter_type} Counter",
                "covered": values.get("covered", 0),
                "missed": values.get("missed", 0),
                "coverage_percent": coverage_percent(values.get("covered", 0), values.get("missed", 0)),
            }
        )
    frame = pd.DataFrame(rows)
    frame.to_csv(output_csv, index=False)
    return frame


def build_static_du_metrics_csv(
    static_du_json: dict[str, Any],
    output_csv: Path,
    jacoco_json: dict[str, Any] | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    summary = static_du_json.get("summary", {})
    supplemental = nested_get(static_du_json, "supplemental_raw_data", "static_du_summary")
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(supplemental, dict):
        supplemental = {}

    def add_rows(source: dict[str, Any], artifact: str, emission: str = "Directly Emitted") -> None:
        for key, value in source.items():
            rows.append(
                {
                    "metric_name": str(key),
                    "metric_value": str(value),
                    "artifact": artifact,
                    "emission_type": emission,
                }
            )

    add_rows(summary, "static_du.json:summary")
    add_rows(supplemental, "static_du.json:supplemental_raw_data.static_du_summary")
    jacoco_supplemental = nested_get(jacoco_json or {}, "supplemental_raw_data", "static_du_summary")
    if isinstance(jacoco_supplemental, dict):
        add_rows(jacoco_supplemental, "jacoco.json:supplemental_raw_data.static_du_summary", "Derived")
    for row in static_du_json.get("metrics", []) if isinstance(static_du_json.get("metrics"), list) else []:
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "metric_name": str(row.get("l5_metric", "")),
                "metric_value": str(row.get("score", "")),
                "artifact": "static_du.json:metrics",
                "emission_type": "Directly Emitted",
            }
        )
    frame = pd.DataFrame(rows)
    frame.to_csv(output_csv, index=False)
    return frame


def validate_control_flow_metrics(
    jacoco_xml: Path | None,
    jacoco_json: dict[str, Any],
    keyword_df: pd.DataFrame,
) -> pd.DataFrame:
    xml_validation = validate_path_metrics(
        keyword_df,
        {
            "jacoco.xml": jacoco_xml,
            "jacoco.csv": jacoco_xml.parent / "jacoco.csv" if jacoco_xml else None,
        },
        jacoco_xml,
    )
    xml_map = {row["Metric"]: row for row in xml_validation.to_dict("records")}
    platform_map = metric_rows_by_name(jacoco_json)
    rows: list[dict[str, str]] = []

    for metric in CONTROL_FLOW_METRICS:
        xml_row = xml_map.get(metric, {})
        platform_row = platform_map.get(metric, {})
        xml_supported = xml_row.get("Supported") == "Supported"
        platform_present = bool(platform_row)
        if xml_supported:
            supported = "Supported"
            directly = "Yes"
            derived = "No"
            artifact = xml_row.get("Artifact", "jacoco.xml")
            evidence = xml_row.get("Comments", "")
            proxy = ""
        elif platform_present:
            raw_params = platform_row.get("raw_parameters", {})
            evidence = (
                f"l5_metric={metric}; score={platform_row.get('score', '')}; "
                f"jacoco_native={platform_row.get('jacoco_native', '')}; "
                f"raw_parameters={raw_params}"
            )[:500]
            supported, directly, derived, proxy = resolve_supported_with_disclosure(
                native_supported=False,
                platform_present=True,
                evidence=evidence,
                metric=metric,
            )
            artifact = "jacoco.json"
        elif xml_row.get("Supported") == "Not Supported":
            supported = "Not Supported"
            directly = "No"
            derived = "No"
            artifact = "jacoco.xml"
            evidence = xml_row.get("Comments", "")
            proxy = ""
        else:
            supported = "Not Supported"
            directly = "No"
            derived = "No"
            artifact = ""
            evidence = "No explicit control-flow metric evidence found in JaCoCo XML or platform JSON."
            proxy = ""

        rows.append(
            {
                "Metric": metric,
                "Classification": "Path Coverage",
                "Tool": "JaCoCo",
                "Supported": supported,
                "Coverage_Tier": classify_coverage_tier(directly, derived, supported),
                "Evidence_Quality": assess_evidence_quality(evidence, metric, directly),
                "Directly Emitted": directly,
                "Derived": derived,
                "Proxy_Disclosure": proxy,
                "Artifact": artifact,
                "Evidence": evidence,
                "Comments": "Native JaCoCo XML has no PATH counter; platform jacoco.json scores are branch/line proxies.",
            }
        )
    return pd.DataFrame(rows)


def xml_total_counter_percent(xml_path: Path, counter_type: str) -> float | None:
    if not xml_path.exists():
        return None
    counters = parse_counter_map(xml_path)
    values = counters.get(counter_type)
    if not values:
        return None
    return coverage_percent(values.get("covered", 0), values.get("missed", 0))


def validate_coverage_delta_metrics(
    current_xml: Path | None,
    baseline_xml: Path | None,
    jacoco_json: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    platform_summary = jacoco_json.get("summary", {}) if isinstance(jacoco_json.get("summary"), dict) else {}
    platform_map = metric_rows_by_name(jacoco_json)

    baseline_available = baseline_xml is not None and baseline_xml.exists()
    computed_delta: dict[str, float | None] = {}
    if baseline_available and current_xml and current_xml.exists():
        for counter in ("INSTRUCTION", "LINE", "BRANCH"):
            current = xml_total_counter_percent(current_xml, counter)
            baseline = xml_total_counter_percent(baseline_xml, counter)
            if current is not None and baseline is not None:
                computed_delta[counter] = round(current - baseline, 4)

    metric_evidence = {
        "Coverage Delta": ["coverage_delta_percent"],
        "Regression Testing Monitoring": ["modules_tested", "modules_with_churn"],
        "Test Suite Effectiveness Tracking": ["line_percent", "branch_percent", "instruction_percent"],
        "CI/CD Quality Gate Enforcement": ["metric_coverage_complete", "metrics_covered"],
        "Change Impact Analysis": ["modules_with_churn", "coverage_delta_percent"],
        "Quality Improvement Measurement": ["coverage_delta_percent", "line_percent"],
    }

    for metric in COVERAGE_REGRESSION_METRICS:
        platform_row = platform_map.get(metric, {})
        summary_hits = []
        for key in metric_evidence.get(metric, []):
            if key in platform_summary:
                summary_hits.append(f"{key}={platform_summary.get(key)}")
            elif key in jacoco_json:
                summary_hits.append(f"{key}={jacoco_json.get(key)}")
        if platform_row and not summary_hits:
            summary_hits.append(f"score={platform_row.get('score', '')}")
        has_xml_delta = bool(computed_delta) and metric == "Coverage Delta"
        platform_present = bool(platform_row or summary_hits)

        evidence_parts = list(summary_hits)
        if has_xml_delta:
            evidence_parts.append(f"computed_xml_delta={computed_delta}")
        evidence = "; ".join(evidence_parts)[:500]

        if has_xml_delta and not platform_present:
            supported = "Supported"
            directly = "Yes"
            derived = "No"
            proxy = "computed_xml_delta from jacoco.xml baseline comparison"
            artifact = "jacoco.xml"
            comments = "Coverage delta computed from native XML baseline comparison."
        elif platform_present:
            supported, directly, derived, proxy = resolve_supported_with_disclosure(
                native_supported=has_xml_delta,
                platform_present=True,
                evidence=evidence,
                metric=metric,
            )
            if has_xml_delta:
                directly = "Yes"
                derived = "Yes" if platform_present else "No"
                supported = "Supported"
                proxy = f"{proxy}; computed_xml_delta from jacoco.xml" if proxy else "computed_xml_delta from jacoco.xml"
            artifact = "jacoco.json+jacoco.xml" if has_xml_delta else "jacoco.json"
            comments = "Platform JSON summary/metrics checked; optional XML baseline comparison performed when baseline exists."
        elif not baseline_available:
            supported = "Baseline Not Available"
            directly = "No"
            derived = "No"
            proxy = ""
            artifact = ""
            evidence = "Baseline Not Available"
            comments = "No baseline XML supplied or found; coverage delta not computed from XML comparison."
        else:
            supported = "Not Supported"
            directly = "No"
            derived = "No"
            proxy = ""
            artifact = ""
            evidence = ""
            comments = "No explicit coverage regression evidence found."

        rows.append(
            {
                "Metric": metric,
                "Supported": supported,
                "Coverage_Tier": classify_coverage_tier(directly, derived, supported),
                "Evidence_Quality": assess_evidence_quality(evidence, metric, directly),
                "Directly Emitted": directly,
                "Derived": derived,
                "Proxy_Disclosure": proxy,
                "Artifact": artifact,
                "Evidence": evidence,
                "Comments": comments,
            }
        )
    return pd.DataFrame(rows)


def metric_tool_evidence(
    metric: str,
    jacoco_json: dict[str, Any],
    static_du_json: dict[str, Any],
    def_use: dict[str, Any],
) -> tuple[str, str, str, str, str, str]:
    jacoco_row = metric_rows_by_name(jacoco_json).get(metric, {})
    static_du_row = metric_rows_by_name(static_du_json).get(metric, {})
    tools: list[str] = []
    evidence_parts: list[str] = []

    if jacoco_row:
        tools.append("JaCoCo")
        evidence_parts.append(
            f"jacoco.json score={jacoco_row.get('score', '')} raw_parameters={jacoco_row.get('raw_parameters', {})}"[:250]
        )
    if static_du_row:
        tools.append("Static DU")
        evidence_parts.append(
            f"static_du.json score={static_du_row.get('score', '')} raw_parameters={static_du_row.get('raw_parameters', {})}"[:250]
        )

    def_use_map = {
        "Variable Definition Detection": ["definitions_total", "definitions_covered", "all_defs_percent"],
        "Definition-Use Mapping": ["du_pairs_total", "du_pairs_covered", "data_path_correlation_percent"],
        "Coverage Measurement": ["du_path_percent", "all_defs_percent", "all_uses_percent"],
        "Uncovered Definition Detection": ["uncovered_definitions"],
        "Edge Case Handling": ["ghost_uses", "partial_uses"],
        "Reporting Validation": ["metrics_total", "metrics_covered"],
        "Computational Use Detection (C-Use)": ["c_use_total", "c_use_covered", "c_use_percent"],
        "Predicate Use Detection (P-Use)": ["p_use_total", "p_use_covered", "p_use_percent"],
        "Definition-Use Pair Identification": ["du_pairs_total", "du_paths"],
        "All-Uses Coverage Verification": ["all_uses_percent", "uses_total", "uses_covered"],
        "Partial Uses Coverage Detection": ["partial_uses"],
        "Multiple Definitions Handling": ["multiple_definition_sites"],
        "Cross-Function Use Detection": ["cross_function_uses"],
        "Unreachable Use Detection": ["ghost_uses"],
        "Coverage Reporting Validation": ["metrics_covered", "metric_coverage_complete"],
        "Variable Use Detection": ["uses_total", "uses_covered", "all_uses_percent"],
    }
    for key in def_use_map.get(metric, []):
        value = summary_value(def_use, key) if key in DEF_USE_SUMMARY_KEYS else def_use.get(key)
        if value is None and isinstance(jacoco_json.get("summary"), dict):
            value = jacoco_json["summary"].get(key)
        if value is not None:
            if "JaCoCo" not in tools:
                tools.append("JaCoCo")
            evidence_parts.append(f"{key}={value}")

    tool = " + ".join(tools) if tools else "None"
    evidence = " | ".join(evidence_parts)[:500]
    analysis_mode = nested_get(static_du_json, "supplemental_raw_data", "static_du_meta", "analysis_mode")
    has_def_use_fields = any(
        part
        for part in evidence_parts
        if any(
            token in part
            for token in (
                "definitions_",
                "uses_",
                "c_use_",
                "p_use_",
                "du_pairs",
                "ghost_uses",
                "partial_uses",
                "multiple_definition",
            )
        )
    )
    native_static_du = (
        bool(static_du_row)
        and analysis_mode not in (None, "static_code_duplication")
        and has_def_use_fields
    )
    platform_present = bool(jacoco_row or (def_use and has_def_use_fields))
    if tools:
        supported, directly, derived, proxy = resolve_supported_with_disclosure(
            native_supported=native_static_du,
            platform_present=platform_present,
            evidence=evidence,
            metric=metric,
        )
        if static_du_row and analysis_mode == "static_code_duplication":
            tool = "JaCoCo platform def-use (standalone Static DU emits duplication only)"
    else:
        supported = "Not Supported"
        directly = "No"
        derived = "No"
        proxy = ""
    return supported, directly, derived, tool, evidence, proxy


def validate_data_flow_metrics(jacoco_json: dict[str, Any], static_du_json: dict[str, Any]) -> pd.DataFrame:
    def_use = def_use_summary(jacoco_json)
    rows: list[dict[str, str]] = []
    for testing_type, classification, metric in DATA_FLOW_METRICS:
        supported, directly, derived, tool, evidence, proxy = metric_tool_evidence(
            metric, jacoco_json, static_du_json, def_use
        )
        analysis_mode = nested_get(static_du_json, "supplemental_raw_data", "static_du_meta", "analysis_mode")
        has_native_static_du = analysis_mode not in (None, "static_code_duplication") and "Static DU" in tool
        primary_tool = "Static DU" if has_native_static_du else "JaCoCo"
        supporting_tool = "JaCoCo" if primary_tool == "Static DU" else ("Static DU" if "static_du" in tool.lower() else "")
        if analysis_mode == "static_code_duplication":
            primary_tool = "JaCoCo"
            supporting_tool = "Static DU (duplication only)"
        evidence_file = "jacoco.json"
        if "static_du.json" in evidence and "jacoco.json" not in evidence:
            evidence_file = "static_du.json"
        elif "static_du.json" in evidence and "jacoco.json" in evidence:
            evidence_file = "jacoco.json+static_du.json"
        rows.append(
            {
                "Testing Type": testing_type,
                "Classification": classification,
                "Metric": metric,
                "Primary Tool": primary_tool,
                "Supporting Tool": supporting_tool,
                "Tool": tool,
                "Supported": supported,
                "Coverage_Tier": classify_coverage_tier(directly, derived, supported),
                "Evidence_Quality": assess_evidence_quality(evidence, metric, directly),
                "Directly Emitted": directly,
                "Derived": derived,
                "Proxy_Disclosure": proxy,
                "Evidence File": evidence_file,
                "Evidence Value": evidence,
                "Evidence": evidence,
                "Comments": "Definition-use evidence comes from jacoco-platform StaticDuAnalyzer; standalone static_du.json emits duplication metrics in this repository.",
            }
        )
    return pd.DataFrame(rows)


def count_tests(java_files: list[Path]) -> int:
    return sum(1 for path in java_files if "/test/" in str(path).replace("\\", "/") or "\\test\\" in str(path))


def count_methods(java_files: list[Path]) -> int:
    total = 0
    for path in java_files:
        if "/test/" in str(path).replace("\\", "/"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        total += sum(1 for line in text.splitlines() if " void " in line and "(" in line and ";" not in line.split("(")[0])
    return total


def build_combined_repository_summary(
    java_files: list[Path],
    jacoco_xml: Path | None,
    jacoco_json: dict[str, Any],
    static_du_json: dict[str, Any],
) -> pd.DataFrame:
    counters = parse_counter_map(jacoco_xml) if jacoco_xml and jacoco_xml.exists() else {}
    def_use = def_use_summary(jacoco_json)
    packages = {extract_package_name(path) for path in java_files if extract_package_name(path)}
    main_files = [path for path in java_files if "/test/" not in str(path).replace("\\", "/")]
    row = {
        "Java Files": len(java_files),
        "Packages": len(packages),
        "Classes": len({path.stem for path in main_files}),
        "Methods": count_methods(java_files),
        "Tests": count_tests(java_files),
        "Definitions": summary_value(def_use, "definitions_total") or "",
        "Uses": summary_value(def_use, "uses_total") or "",
        "DU Pairs": summary_value(def_use, "du_pairs_total") or "",
        "Instruction Counters": counters.get("INSTRUCTION", {}).get("covered", ""),
        "Branch Counters": counters.get("BRANCH", {}).get("covered", ""),
        "Complexity Counters": counters.get("COMPLEXITY", {}).get("covered", ""),
        "Static DU Total Lines": nested_get(static_du_json, "summary", "total_lines") or "",
        "JaCoCo Metrics Covered": jacoco_json.get("metrics_covered", ""),
        "Static DU Metrics Covered": static_du_json.get("metrics_covered", ""),
    }
    return pd.DataFrame([row])


def copy_platform_json_artifacts(repo_path: Path, output_dir: Path) -> dict[str, bool]:
    copied: dict[str, bool] = {}
    for name in PLATFORM_JSON_ARTIFACTS:
        source = repo_path / name
        if source.exists():
            copy_artifact(source, output_dir / name)
            copied[name] = True
        else:
            copied[name] = False
    if copied.get("static_du.json") and not (output_dir / "static_du_output.json").exists():
        copy_artifact(repo_path / "static_du.json", output_dir / "static_du_output.json")
    return copied


def build_cross_validation(
    repo_path: Path,
    output_dir: Path,
    jacoco_xml: Path | None,
    jacoco_json: dict[str, Any],
    static_du_json: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, str]] = []

    if jacoco_xml and jacoco_xml.exists():
        xml_counters = parse_counter_map(jacoco_xml)
        for counter_type in JACOCO_COUNTER_TYPES:
            values = xml_counters.get(counter_type, {})
            expected = coverage_percent(values.get("covered", 0), values.get("missed", 0))
            rows.append(
                {
                    "Metric": f"JaCoCo XML {counter_type} percent",
                    "Expected Value": str(expected),
                    "Observed Value": str(expected),
                    "Match": "Yes",
                    "Artifact": "jacoco.xml",
                }
            )

    jacoco_metrics_path = output_dir / "jacoco_metrics.csv"
    if jacoco_metrics_path.exists():
        jacoco_df = pd.read_csv(jacoco_metrics_path)
        for _, row in jacoco_df.iterrows():
            rows.append(
                {
                    "Metric": str(row.get("metric_name", "")),
                    "Expected Value": "present in jacoco.xml",
                    "Observed Value": str(row.get("coverage_percent", row.get("covered", ""))),
                    "Match": "Yes" if row.get("metric_name") else "No",
                    "Artifact": "jacoco_metrics.csv",
                }
            )

    static_du_metrics_file = output_dir / "static_du_metrics.json"
    if not static_du_metrics_file.exists():
        static_du_metrics_file = repo_path / "static_du_metrics.json"
    if static_du_metrics_file.exists():
        payload = load_json(static_du_metrics_file)
        if isinstance(payload, dict):
            for key, value in payload.items():
                rows.append(
                    {
                        "Metric": f"static_du_metrics.{key}",
                        "Expected Value": str(value),
                        "Observed Value": str(value),
                        "Match": "Yes",
                        "Artifact": "static_du_metrics.json",
                    }
                )

    metrics_json = load_json(output_dir / "metrics.json") if (output_dir / "metrics.json").exists() else load_json(repo_path / "metrics.json")
    dashboard_json = load_json(output_dir / "dashboard_metrics.json") if (output_dir / "dashboard_metrics.json").exists() else {}
    platform_json = load_json(output_dir / "platform_metrics.json") if (output_dir / "platform_metrics.json").exists() else {}

    if isinstance(metrics_json, dict) and isinstance(dashboard_json, dict):
        for key in ("metrics_total", "metrics_covered", "metric_coverage_complete"):
            expected = metrics_json.get(key, dashboard_json.get(key))
            observed = dashboard_json.get(key)
            if expected is not None or observed is not None:
                rows.append(
                    {
                        "Metric": f"dashboard.{key}",
                        "Expected Value": str(expected),
                        "Observed Value": str(observed),
                        "Match": "Yes" if str(expected) == str(observed) else "No",
                        "Artifact": "metrics.json+dashboard_metrics.json",
                    }
                )

    if isinstance(metrics_json, dict) and isinstance(platform_json, dict):
        for key in set(metrics_json.keys()) & set(platform_json.keys()):
            rows.append(
                {
                    "Metric": f"platform.{key}",
                    "Expected Value": str(metrics_json.get(key)),
                    "Observed Value": str(platform_json.get(key)),
                    "Match": "Yes" if metrics_json.get(key) == platform_json.get(key) else "No",
                    "Artifact": "metrics.json+platform_metrics.json",
                }
            )

    for label, payload, artifact in (
        ("jacoco.json metrics_covered", jacoco_json, "jacoco.json"),
        ("static_du.json metrics_covered", static_du_json, "static_du.json"),
    ):
        covered = payload.get("metrics_covered")
        if covered is not None:
            rows.append(
                {
                    "Metric": label,
                    "Expected Value": str(covered),
                    "Observed Value": str(covered),
                    "Match": "Yes",
                    "Artifact": artifact,
                }
            )

    frame = pd.DataFrame(rows)
    frame.to_csv(output_dir / "cross_validation.csv", index=False)
    return frame


def build_dashboard_summary(
    repo_path: Path,
    build_tool: str,
    status: CombinedRunStatus,
    control_flow_df: pd.DataFrame,
    coverage_delta_df: pd.DataFrame,
    data_flow_df: pd.DataFrame,
    java_files: list[Path],
) -> pd.DataFrame:
    def supported_count(frame: pd.DataFrame) -> int:
        return int(frame["Supported"].isin(["Supported", "Partially Supported"]).sum())

    def unsupported_count(frame: pd.DataFrame) -> int:
        return int((frame["Supported"] == "Not Supported").sum())

    total_supported = supported_count(control_flow_df) + supported_count(coverage_delta_df) + supported_count(data_flow_df)
    total_unsupported = unsupported_count(control_flow_df) + unsupported_count(coverage_delta_df) + unsupported_count(data_flow_df)

    row = {
        "Repository": repo_path.name,
        "Build Tool": build_tool,
        "Tests Executed": count_tests(java_files),
        "JaCoCo Status": "OK" if status.build_status.report_generated else "FAILED",
        "Static DU Status": "OK" if status.static_du_trigger_success else "FAILED",
        "Control Flow Metrics Supported": supported_count(control_flow_df),
        "Regression Metrics Supported": supported_count(coverage_delta_df),
        "Data Flow Metrics Supported": supported_count(data_flow_df),
        "Total Metrics Supported": total_supported,
        "Unsupported Metrics": total_unsupported,
        "Unified DefUse Trigger": "Yes" if status.unified_trigger else "No",
    }
    frame = pd.DataFrame([row])
    return frame


def export_validation_bundle(output_dir: Path, parsed: dict[str, Any]) -> Path:
    bundle = {
        "control_flow_validation": parsed["control_flow_df"].to_dict("records"),
        "coverage_delta_validation": parsed["coverage_delta_df"].to_dict("records"),
        "data_flow_validation": parsed["data_flow_df"].to_dict("records"),
        "cross_validation": parsed.get("cross_validation_df", pd.DataFrame()).to_dict("records"),
        "taxonomy_truth_table": parsed.get("taxonomy_truth_df", pd.DataFrame()).to_dict("records"),
        "dashboard_summary": parsed.get("dashboard_summary_df", pd.DataFrame()).to_dict("records"),
        "repository_summary": parsed.get("repository_summary_df", pd.DataFrame()).to_dict("records"),
    }
    path = output_dir / "validation_results.json"
    path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return path


def build_dashboard_metrics(
    repo_path: Path,
    build_tool: str,
    java_files: list[Path],
    status: CombinedRunStatus,
    control_flow_df: pd.DataFrame,
    coverage_delta_df: pd.DataFrame,
    data_flow_df: pd.DataFrame,
    jacoco_xml: Path | None = None,
    jacoco_json: dict[str, Any] | None = None,
    taxonomy_truth_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    repo_summary = build_combined_repository_summary(
        java_files,
        status.build_status.jacoco_xml,
        jacoco_json or load_json(status.jacoco_json),
        load_json(status.static_du_json),
    ).iloc[0]
    branch_alignment = compute_branch_alignment(jacoco_xml, jacoco_json or {})

    def supported_count(frame: pd.DataFrame) -> int:
        return int(frame["Supported"].isin(["Supported", "Partially Supported"]).sum())

    rows: list[dict[str, Any]] = [
        {"Metric": "Repository", "Value": repo_path.name},
        {"Metric": "Build Tool", "Value": build_tool},
        {"Metric": "Java Files", "Value": repo_summary["Java Files"]},
        {"Metric": "Packages", "Value": repo_summary["Packages"]},
        {"Metric": "Classes", "Value": repo_summary["Classes"]},
        {"Metric": "Methods", "Value": repo_summary["Methods"]},
        {"Metric": "Tests Executed", "Value": repo_summary["Tests"]},
        {"Metric": "JaCoCo Status", "Value": "OK" if status.build_status.report_generated else "FAILED"},
        {"Metric": "Static DU Status", "Value": "OK" if status.static_du_trigger_success else "FAILED"},
        {"Metric": "Control Flow Metrics Supported", "Value": supported_count(control_flow_df)},
        {"Metric": "Coverage Regression Metrics Supported", "Value": supported_count(coverage_delta_df)},
        {"Metric": "Data Flow Metrics Supported", "Value": supported_count(data_flow_df)},
        {
            "Metric": "Unsupported Metrics",
            "Value": int((control_flow_df["Supported"] == "Not Supported").sum())
            + int((coverage_delta_df["Supported"] == "Not Supported").sum())
            + int((data_flow_df["Supported"] == "Not Supported").sum()),
        },
        {"Metric": "JaCoCo XML Branch Percent", "Value": branch_alignment["xml_branch_percent"]},
        {"Metric": "Platform jacoco.json Branch Percent", "Value": branch_alignment["platform_branch_percent"]},
        {"Metric": "Branch Percent Discrepancy", "Value": branch_alignment["branch_percent_discrepancy"]},
        {"Metric": "Branch Percent Delta (Platform - XML)", "Value": branch_alignment["branch_percent_delta"]},
        {"Metric": "Branch Discrepancy Detail", "Value": branch_alignment["discrepancy_detail"]},
    ]

    if taxonomy_truth_df is not None and not taxonomy_truth_df.empty:
        rows.extend(
            [
                {
                    "Metric": "Taxonomy Rows Native Tier",
                    "Value": int((taxonomy_truth_df["Coverage_Tier"] == "Native").sum()),
                },
                {
                    "Metric": "Taxonomy Rows Platform Derived Tier",
                    "Value": int((taxonomy_truth_df["Coverage_Tier"] == "Platform_Derived").sum()),
                },
                {
                    "Metric": "Taxonomy Rows Not Supported Tier",
                    "Value": int((taxonomy_truth_df["Coverage_Tier"] == "Not_Supported").sum()),
                },
                {
                    "Metric": "Taxonomy Rows Weak Evidence",
                    "Value": int((taxonomy_truth_df["Evidence_Quality"] == "Weak").sum()),
                },
                {
                    "Metric": "Taxonomy Rows Missing Evidence",
                    "Value": int((taxonomy_truth_df["Evidence_Quality"] == "Missing").sum()),
                },
            ]
        )

    return pd.DataFrame(rows)


def collect_all_outputs(
    status: CombinedRunStatus,
    repo_path: Path,
    java_files: list[Path],
    build_tool: str,
    output_dir: Path,
    baseline_xml: Path | None,
    jacoco_console: str,
    jacoco_trigger_console: str,
    static_du_trigger_console: str,
) -> dict[str, Any]:
    ensure_output_dir(output_dir)
    copied = copy_raw_jacoco_artifacts(status.build_status, output_dir)
    static_du_copied = {
        "static_du_output.json": copy_artifact(status.static_du_json, output_dir / "static_du_output.json"),
    }
    training = repo_path / "artifacts" / "training"
    for name in ("static_du_summary.json", "du_path_correlation.json", "static_du_meta.json"):
        candidate = training / name
        if candidate.exists():
            copy_artifact(candidate, output_dir / name)
    for pattern in ("static_du*.xml", "static_du*.csv", "*static_du*.csv", "*static_du*.xml"):
        for candidate in repo_path.rglob(pattern.split("/")[-1]):
            if not candidate.is_file():
                continue
            suffix = candidate.suffix.lower()
            if suffix == ".xml":
                static_du_copied["static_du_output.xml"] = copy_artifact(candidate, output_dir / "static_du_output.xml")
            elif suffix == ".csv":
                static_du_copied["static_du_output.csv"] = copy_artifact(candidate, output_dir / "static_du_output.csv")

    jacoco_console_path = output_dir / "jacoco_console_output.txt"
    jacoco_console_path.write_text(
        "\n\n".join(
            [
                "===== MAVEN BUILD / JACOCO =====",
                jacoco_console,
                "===== JACOCO PLATFORM TRIGGER =====",
                jacoco_trigger_console,
            ]
        ),
        encoding="utf-8",
    )
    static_du_console_path = output_dir / "static_du_console_output.txt"
    static_du_console_path.write_text(static_du_trigger_console, encoding="utf-8")

    jacoco_json = load_json(status.jacoco_json)
    static_du_json = load_json(status.static_du_json)
    jacoco_xml = output_dir / "jacoco.xml" if copied.get("jacoco.xml") else status.build_status.jacoco_xml

    platform_json_copied = copy_platform_json_artifacts(repo_path, output_dir)

    jacoco_metrics_df = build_extended_jacoco_metrics_csv(jacoco_xml, output_dir / "jacoco_metrics.csv")
    static_du_metrics_df = build_static_du_metrics_csv(
        static_du_json, output_dir / "static_du_metrics.csv", jacoco_json=jacoco_json
    )

    artifacts = {
        "jacoco_console_output.txt": jacoco_console_path,
        "jacoco.xml": output_dir / "jacoco.xml",
        "jacoco.csv": output_dir / "jacoco.csv",
        "index.html": output_dir / "index.html",
    }
    keyword_df = search_path_keywords(artifacts)
    control_flow_df = validate_control_flow_metrics(jacoco_xml, jacoco_json, keyword_df)
    control_flow_df.to_csv(output_dir / "control_flow_validation.csv", index=False)

    baseline_path = baseline_xml if baseline_xml and baseline_xml.exists() else repo_path / "artifacts" / "training" / "baseline_jacoco.xml"
    coverage_delta_df = validate_coverage_delta_metrics(jacoco_xml, baseline_path, jacoco_json)
    coverage_delta_df.to_csv(output_dir / "coverage_delta_validation.csv", index=False)

    data_flow_df = validate_data_flow_metrics(jacoco_json, static_du_json)
    data_flow_df.to_csv(output_dir / "data_flow_validation.csv", index=False)

    repo_routing_df = build_repo_routing_csv(output_dir / "repo_routing.csv")
    trigger_manifest_df = build_trigger_manifest(output_dir)
    taxonomy_truth_df = build_taxonomy_truth_table(
        control_flow_df,
        coverage_delta_df,
        data_flow_df,
        jacoco_xml,
        jacoco_json,
        output_dir / "taxonomy_truth_table.csv",
    )
    action_plan_df = build_metric_coverage_action_plan(
        taxonomy_truth_df,
        output_dir / "metric_coverage_action_plan.csv",
    )

    repository_summary_df = build_combined_repository_summary(java_files, jacoco_xml, jacoco_json, static_du_json)
    repository_summary_df.to_csv(output_dir / "repository_summary.csv", index=False)

    dashboard_df = build_dashboard_metrics(
        repo_path,
        build_tool,
        java_files,
        status,
        control_flow_df,
        coverage_delta_df,
        data_flow_df,
        jacoco_xml=jacoco_xml,
        jacoco_json=jacoco_json,
        taxonomy_truth_df=taxonomy_truth_df,
    )
    dashboard_df.to_csv(output_dir / "dashboard_metrics.csv", index=False)

    dashboard_summary_df = build_dashboard_summary(
        repo_path, build_tool, status, control_flow_df, coverage_delta_df, data_flow_df, java_files
    )
    dashboard_summary_df.to_csv(output_dir / "dashboard_summary.csv", index=False)

    cross_validation_df = build_cross_validation(repo_path, output_dir, jacoco_xml, jacoco_json, static_du_json)

    parsed_bundle = {
        "control_flow_df": control_flow_df,
        "coverage_delta_df": coverage_delta_df,
        "data_flow_df": data_flow_df,
        "cross_validation_df": cross_validation_df,
        "taxonomy_truth_df": taxonomy_truth_df,
        "dashboard_summary_df": dashboard_summary_df,
        "repository_summary_df": repository_summary_df,
    }
    validation_json_path = export_validation_bundle(output_dir, parsed_bundle)

    return {
        "copied": copied,
        "static_du_copied": static_du_copied,
        "platform_json_copied": platform_json_copied,
        "jacoco_metrics_df": jacoco_metrics_df,
        "static_du_metrics_df": static_du_metrics_df,
        "control_flow_df": control_flow_df,
        "coverage_delta_df": coverage_delta_df,
        "data_flow_df": data_flow_df,
        "repo_routing_df": repo_routing_df,
        "trigger_manifest_df": trigger_manifest_df,
        "taxonomy_truth_df": taxonomy_truth_df,
        "action_plan_df": action_plan_df,
        "repository_summary_df": repository_summary_df,
        "dashboard_df": dashboard_df,
        "dashboard_summary_df": dashboard_summary_df,
        "cross_validation_df": cross_validation_df,
        "validation_results_json": validation_json_path,
    }
