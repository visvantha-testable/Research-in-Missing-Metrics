"""Generate nuget_audit_sca_extraction.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "nuget_audit_sca_extraction.ipynb"

IMPORT_BLOCK = """
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from IPython.display import display

subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', '-r', 'requirements.txt'])

METRIC_ROOT = Path('.').resolve()
if not (METRIC_ROOT / 'tool' / '_nuget_audit_sca_utils.py').exists():
    METRIC_ROOT = Path('..').resolve()
sys.path.insert(0, str(METRIC_ROOT / 'tool'))

from _nuget_audit_sca_utils import (
    ANALYSIS_TYPE,
    AUDIT_PROJECT_RELATIVE,
    NO_EVIDENCE_MESSAGE,
    PROGRAMMING_LANGUAGE,
    REPO_URL,
    TOOL_NAME,
    NotebookLogger,
    build_evidence_table,
    build_final_summary,
    build_metric_mapping,
    clone_repository,
    collect_prerequisite_versions,
    discover_solution,
    dotnet_env,
    download_dotnet_sdk,
    ensure_output_dirs,
    export_results,
    list_repository_structure,
    parse_audit_json,
    preserve_raw_audit_output,
    read_text,
    resolve_metric_root,
    run_dotnet_build,
    run_dotnet_restore,
    run_nuget_audit,
)

METRIC_ROOT = resolve_metric_root(METRIC_ROOT)
DIRS = ensure_output_dirs(METRIC_ROOT)
OUTPUT_DIR = DIRS['output']
WORKSPACE_DIR = DIRS['workspace']
LOGGER = NotebookLogger(OUTPUT_DIR / 'error_log.txt')
""".strip()


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "outputs": [], "source": source.splitlines(keepends=True)}


cells = [
    md(
        "# NuGet Audit SCA — Raw Tool Output Extraction\n\n"
        "Clone the C# training repository, execute "
        "`dotnet package list --include-transitive --vulnerable --format json`, "
        "preserve the raw JSON output, and map findings to Dependency Risk (SCA) metrics."
    ),
    md("## Cell 1 – Project Information"),
    code(
        "# Display repository metadata and execution context.\n"
        "from datetime import datetime, timezone\n"
        "from pathlib import Path\n\n"
        "REPO_URL = 'https://github.com/visvantha-testable/csharp-testing-nuget-audit'\n"
        "PROGRAMMING_LANGUAGE = 'C#'\n"
        "TOOL_NAME = 'dotnet package list --include-transitive --vulnerable --format json'\n"
        "ANALYSIS_TYPE = 'Software Composition Analysis (SCA)'\n"
        "EXECUTION_DATE = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')\n"
        "WORKING_DIRECTORY = str(Path('.').resolve())\n\n"
        "PROJECT_INFO = {\n"
        "    'Repository URL': REPO_URL,\n"
        "    'Programming Language': PROGRAMMING_LANGUAGE,\n"
        "    'Tool Name': TOOL_NAME,\n"
        "    'Analysis Type': ANALYSIS_TYPE,\n"
        "    'Execution Date': EXECUTION_DATE,\n"
        "    'Working Directory': WORKING_DIRECTORY,\n"
        "}\n"
        "for key, value in PROJECT_INFO.items():\n"
        "    print(f'{key}: {value}')"
    ),
    md("## Cell 2 – Clone Repository"),
    code("# Install dependencies, import helpers, and clone the repository.\n" + IMPORT_BLOCK + "\n\n"
         "REPO_PATH, CLONE_STATUS = clone_repository(REPO_URL, WORKSPACE_DIR, reuse=True)\n"
         "print(CLONE_STATUS)\n"
         "display(list_repository_structure(REPO_PATH))"),
    md("## Cell 3 – Install Prerequisites"),
    code(
        "# Verify .NET SDK, Git, Python, and notebook dependencies.\n"
        "DOTNET_ROOT = download_dotnet_sdk(DIRS['runtimes'], tmp_dir=DIRS['tmp'])\n"
        "DOTNET_ENV = dotnet_env(DOTNET_ROOT, tmp_dir=DIRS['tmp'])\n"
        "PREREQ_DF = collect_prerequisite_versions(DOTNET_ROOT, DOTNET_ENV)\n"
        "display(PREREQ_DF)\n"
        "PREREQ_DF.to_csv(OUTPUT_DIR / 'prerequisite_versions.csv', index=False)"
    ),
    md("## Cell 4 – Restore NuGet Packages"),
    code(
        "# Restore NuGet packages for the cloned solution.\n"
        "SOLUTION_PATH = discover_solution(REPO_PATH)\n"
        "RESTORE_RESULT = run_dotnet_restore(REPO_PATH, SOLUTION_PATH, DOTNET_ROOT, DOTNET_ENV)\n"
        "print('--- restore logs ---')\n"
        "print(RESTORE_RESULT['raw'])\n"
        "print(f\"Number of restored packages: {RESTORE_RESULT['restored_packages']}\")\n"
        "print(f\"Restore status: {RESTORE_RESULT['restore_status']}\")\n"
        "(OUTPUT_DIR / 'dotnet_restore.log').write_text(RESTORE_RESULT['raw'], encoding='utf-8')\n"
        "if not RESTORE_RESULT['success']:\n"
        "    raise RuntimeError('dotnet restore failed.')"
    ),
    md("## Cell 5 – Build the Project"),
    code(
        "# Build the cloned solution without modifying repository source code.\n"
        "BUILD_RESULT = run_dotnet_build(REPO_PATH, SOLUTION_PATH, DOTNET_ROOT, DOTNET_ENV)\n"
        "print('--- build logs ---')\n"
        "print(BUILD_RESULT['raw'])\n"
        "print(f\"Number of projects: {BUILD_RESULT['project_count']}\")\n"
        "print(f\"Build status: {BUILD_RESULT['build_status']}\")\n"
        "(OUTPUT_DIR / 'dotnet_build.log').write_text(BUILD_RESULT['raw'], encoding='utf-8')\n"
        "if not BUILD_RESULT['success']:\n"
        "    raise RuntimeError('dotnet build failed.')"
    ),
    md("## Cell 6 – Execute NuGet Audit"),
    code(
        "# Run the native NuGet Audit command and capture raw JSON output.\n"
        "AUDIT_RESULT = run_nuget_audit(REPO_PATH, AUDIT_PROJECT_RELATIVE, DOTNET_ROOT, DOTNET_ENV)\n"
        "print('--- console output ---')\n"
        "print(AUDIT_RESULT['raw'])\n"
        "print('--- raw JSON output ---')\n"
        "print(AUDIT_RESULT['stdout'])\n"
        "print(f\"Audit status: {AUDIT_RESULT.get('audit_status')}\")\n"
        "if not AUDIT_RESULT['success'] or not AUDIT_RESULT['stdout'].strip():\n"
        "    raise RuntimeError('NuGet audit command failed.')"
    ),
    md("## Cell 7 – Preserve Raw Tool Output"),
    code(
        "# Save raw JSON, console output, and audit logs without modification.\n"
        "RAW_PATHS = preserve_raw_audit_output(AUDIT_RESULT, OUTPUT_DIR)\n"
        "print('===== Raw JSON (verbatim) =====')\n"
        "print(read_text(RAW_PATHS['raw_json']))\n"
        "print('===== Raw console output (verbatim) =====')\n"
        "print(read_text(RAW_PATHS['raw_console']))\n"
        "print('===== Audit execution log (verbatim) =====')\n"
        "print(read_text(RAW_PATHS['audit_log']))"
    ),
    md("## Cell 8 – Parse JSON Output"),
    code(
        "# Parse every dependency and vulnerability record from the audit JSON.\n"
        "AUDIT_PAYLOAD = json.loads(AUDIT_RESULT['stdout'])\n"
        "FINDINGS_DF = parse_audit_json(AUDIT_RESULT['stdout'], AUDIT_PAYLOAD)\n"
        "display(FINDINGS_DF)"
    ),
    md("## Cell 9 – Metric Mapping"),
    code(
        "# Map NuGet Audit JSON fields to Dependency Risk (SCA) metrics.\n"
        "METRIC_MAPPINGS = build_metric_mapping(FINDINGS_DF, AUDIT_PAYLOAD)\n"
        "for mapping in METRIC_MAPPINGS:\n"
        "    print(f\"\\nMetric: {mapping['metric']}\")\n"
        "    print(f\"Classification: {mapping['classification']}\")\n"
        "    print(f\"Technique: {mapping['technique']}\")\n"
        "    if mapping['has_evidence']:\n"
        "        print('Supporting dependency entries:')\n"
        "        display(mapping['supporting_rows'])\n"
        "        print(f\"Rationale: {mapping['rationale']}\")\n"
        "    else:\n"
        "        print(NO_EVIDENCE_MESSAGE)\n"
        "        print(f\"Rationale: {mapping['rationale']}\")"
    ),
    md("## Cell 10 – Evidence Table"),
    code(
        "# Build the metric evidence table directly from parsed audit JSON rows.\n"
        "EVIDENCE_DF = build_evidence_table(FINDINGS_DF, METRIC_MAPPINGS)\n"
        "display(EVIDENCE_DF)"
    ),
    md("## Cell 11 – Export Results"),
    code(
        "# Export raw and parsed outputs to the output/ directory.\n"
        "SUMMARY = build_final_summary(\n"
        "    REPO_PATH,\n"
        "    FINDINGS_DF,\n"
        "    METRIC_MAPPINGS,\n"
        "    AUDIT_PAYLOAD,\n"
        "    RESTORE_RESULT,\n"
        "    BUILD_RESULT,\n"
        ")\n"
        "EXPORTED = export_results(\n"
        "    OUTPUT_DIR,\n"
        "    RAW_PATHS,\n"
        "    FINDINGS_DF,\n"
        "    EVIDENCE_DF,\n"
        "    METRIC_MAPPINGS,\n"
        "    SUMMARY,\n"
        ")\n"
        "for name, path in EXPORTED.items():\n"
        "    print(f'{name}: {path}')"
    ),
    md("## Cell 12 – Final Summary"),
    code(
        "# Display the final execution summary derived from NuGet Audit output.\n"
        "print(f\"Repository Name: {SUMMARY['repository_name']}\")\n"
        "print(f\"Programming Language: {SUMMARY['programming_language']}\")\n"
        "print(f\"Tool Used: {SUMMARY['tool_used']}\")\n"
        "print(f\"Total Projects Analysed: {SUMMARY['total_projects_analysed']}\")\n"
        "print(f\"Total Dependencies: {SUMMARY['total_dependencies']}\")\n"
        "print(f\"Direct Dependencies: {SUMMARY['direct_dependencies']}\")\n"
        "print(f\"Transitive Dependencies: {SUMMARY['transitive_dependencies']}\")\n"
        "print(f\"Vulnerable Packages: {SUMMARY['vulnerable_packages']}\")\n"
        "print(f\"Critical Vulnerabilities: {SUMMARY['critical_vulnerabilities']}\")\n"
        "print(f\"High Vulnerabilities: {SUMMARY['high_vulnerabilities']}\")\n"
        "print(f\"Medium Vulnerabilities: {SUMMARY['medium_vulnerabilities']}\")\n"
        "print(f\"Low Vulnerabilities: {SUMMARY['low_vulnerabilities']}\")\n"
        "print(f\"Metrics Evaluated: {SUMMARY['metrics_evaluated']}\")\n"
        "print(f\"Metrics with Supporting Evidence: {SUMMARY['metrics_with_supporting_evidence']}\")\n"
        "print(f\"Metrics without Supporting Evidence: {SUMMARY['metrics_without_supporting_evidence']}\")\n"
        "LOGGER.write_errors()"
    ),
]

NOTEBOOK.write_text(
    json.dumps(
        {
            "cells": cells,
            "metadata": {
                "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                "language_info": {"name": "python", "pygments_lexer": "ipython3"},
            },
            "nbformat": 4,
            "nbformat_minor": 5,
        },
        indent=1,
    ),
    encoding="utf-8",
)
print(f"Wrote {NOTEBOOK}")
