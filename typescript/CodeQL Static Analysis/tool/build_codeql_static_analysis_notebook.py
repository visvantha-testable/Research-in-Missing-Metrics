"""Generate codeql_static_analysis_extraction.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "codeql_static_analysis_extraction.ipynb"
UTILS = (ROOT / "_codeql_static_analysis_utils.py").read_text(encoding="utf-8")


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "outputs": [], "source": source.splitlines(keepends=True)}


cells = [
    md(
        "# CodeQL Static Analysis — Raw Tool Output Extraction\n\n"
        "Execute CodeQL CLI against a TypeScript repository, preserve raw SARIF output, "
        "and map findings to white-box testing metrics without modifying repository source code."
    ),
    md("## Cell 1 – Project Information"),
    code(
        "# Display project metadata and execution context.\n"
        "import subprocess\n"
        "import sys\n"
        "from datetime import datetime, timezone\n"
        "from pathlib import Path\n\n"
        "REPO_URL = 'https://github.com/visvantha-testable/typescript-tool-testing-vitest-coverage-v8'\n"
        "PROGRAMMING_LANGUAGE = 'TypeScript'\n"
        "TOOL_NAME = 'CodeQL CLI'\n"
        "EXECUTION_DATE = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')\n"
        "CURRENT_WORKING_DIRECTORY = str(Path('.').resolve())\n\n"
        "PROJECT_INFO = {\n"
        "    'Repository URL': REPO_URL,\n"
        "    'Programming Language': PROGRAMMING_LANGUAGE,\n"
        "    'Tool Name': TOOL_NAME,\n"
        "    'Notebook Execution Date': EXECUTION_DATE,\n"
        "    'Current Working Directory': CURRENT_WORKING_DIRECTORY,\n"
        "}\n"
        "for key, value in PROJECT_INFO.items():\n"
        "    print(f'{key}: {value}')"
    ),
    md("## Cell 2 – Clone Repository"),
    code(
        "# Install Python dependencies and clone the target repository.\n"
        "subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', '-r', 'requirements.txt'])\n\n"
        + UTILS
        + "\n\n"
        "from IPython.display import display\n\n"
        "METRIC_ROOT = resolve_metric_root(Path('.').resolve())\n"
        "DIRS = ensure_output_dirs(METRIC_ROOT)\n"
        "OUTPUT_DIR = DIRS['output']\n"
        "RAW_DIR = DIRS['raw']\n"
        "PARSED_DIR = DIRS['parsed']\n"
        "REPORTS_DIR = DIRS['reports']\n"
        "WORKSPACE_DIR = DIRS['workspace']\n"
        "LOGGER = NotebookLogger(REPORTS_DIR / 'error_log.txt')\n\n"
        "REPO_PATH, CLONE_STATUS = clone_repository(REPO_URL + '.git', WORKSPACE_DIR, reuse=True)\n"
        "print(CLONE_STATUS)\n"
        "display(list_repository_structure(REPO_PATH))"
    ),
    md("## Cell 3 – Install Prerequisites"),
    code(
        "# Verify Git, Node.js, npm, archive tools, jq, and Python dependencies.\n"
        "PREREQ_DF = collect_prerequisite_versions()\n"
        "display(PREREQ_DF)\n"
        "PREREQ_DF.to_csv(PARSED_DIR / 'prerequisite_versions.csv', index=False)"
    ),
    md("## Cell 4 – Download and Configure CodeQL"),
    code(
        "# Download the latest CodeQL CLI, configure PATH, and verify installation.\n"
        "CODEQL_EXE = download_codeql_cli(DIRS['codeql_home'], LOGGER)\n"
        "CODEQL_VERSION = verify_codeql(CODEQL_EXE)\n"
        "print(CODEQL_VERSION['stdout'] or CODEQL_VERSION['stderr'])\n"
        "if not CODEQL_VERSION['success']:\n"
        "    raise RuntimeError('CodeQL CLI verification failed.')"
    ),
    md("## Cell 5 – Install Project Dependencies"),
    code(
        "# Install repository npm dependencies without modifying repository source files.\n"
        "INSTALL_RESULT = run_command(['npm', 'install'], REPO_PATH, 'npm install')\n"
        "print('--- stdout ---')\n"
        "print(INSTALL_RESULT['stdout'])\n"
        "print('--- stderr ---')\n"
        "print(INSTALL_RESULT['stderr'])\n"
        "(RAW_DIR / 'npm_install.log').write_text(\n"
        "    f\"--- stdout ---\\n{INSTALL_RESULT['stdout']}\\n\\n--- stderr ---\\n{INSTALL_RESULT['stderr']}\",\n"
        "    encoding='utf-8',\n"
        ")\n"
        "if not INSTALL_RESULT['success']:\n"
        "    raise RuntimeError('npm install failed.')"
    ),
    md("## Cell 6 – Create the CodeQL Database"),
    code(
        "# Create a JavaScript/TypeScript CodeQL database from the cloned repository.\n"
        "DATABASE_PATH = OUTPUT_DIR / 'codeql-db'\n"
        "DB_RESULT = create_codeql_database(CODEQL_EXE, REPO_PATH, DATABASE_PATH, RAW_DIR, LOGGER)\n"
        "print(f\"Build status: {'success' if DB_RESULT['success'] else 'failed'}\")\n"
        "print(f\"Source files indexed: {DB_RESULT['source_files_indexed']}\")\n"
        "print(read_text(Path(DB_RESULT['log_path'])))"
    ),
    md("## Cell 7 – Execute CodeQL Analysis"),
    code(
        "# Run the standard JavaScript/TypeScript CodeQL query suite and generate SARIF.\n"
        "SARIF_PATH = OUTPUT_DIR / 'results.sarif'\n"
        "ANALYZE_RESULT = analyze_codeql_database(CODEQL_EXE, DATABASE_PATH, SARIF_PATH, RAW_DIR, LOGGER)\n"
        "print(f\"Queries executed: {ANALYZE_RESULT['queries_executed']}\")\n"
        "print(f\"Execution duration ms: {ANALYZE_RESULT['elapsed_ms']}\")\n"
        "print(read_text(Path(ANALYZE_RESULT['log_path'])))"
    ),
    md("## Cell 8 – Preserve Raw Tool Output"),
    code(
        "# Preserve CodeQL CLI logs and SARIF output exactly as produced.\n"
        "RAW_CONSOLE_PATH = RAW_DIR / 'codeql_cli_execution.log'\n"
        "RAW_CONSOLE_PATH.write_text(\n"
        "    read_text(Path(DB_RESULT['log_path'])) + '\\n\\n' + read_text(Path(ANALYZE_RESULT['log_path'])),\n"
        "    encoding='utf-8',\n"
        ")\n"
        "copy_file_verbatim(SARIF_PATH, RAW_DIR / 'results.sarif')\n"
        "print('===== Raw CLI execution log (verbatim) =====')\n"
        "print(read_text(RAW_CONSOLE_PATH))\n"
        "print('===== Raw SARIF output (verbatim) =====')\n"
        "print(read_text(SARIF_PATH))"
    ),
    md("## Cell 9 – Parse SARIF Results"),
    code(
        "# Parse every SARIF finding into a structured Pandas DataFrame.\n"
        "FINDINGS_DF = parse_sarif_findings(SARIF_PATH)\n"
        "display(FINDINGS_DF)\n"
        "FINDINGS_DF.to_csv(PARSED_DIR / 'parsed_findings.csv', index=False)"
    ),
    md("## Cell 10 – Metric Mapping"),
    code(
        "# Map CodeQL SARIF findings to the requested white-box testing metrics.\n"
        "METRIC_MAPPINGS = build_metric_mapping(FINDINGS_DF, SARIF_PATH)\n"
        "for mapping in METRIC_MAPPINGS:\n"
        "    print(f\"\\nMetric: {mapping['metric']}\")\n"
        "    print(f\"Classification: {mapping['classification']}\")\n"
        "    print(f\"Technique: {mapping['technique']}\")\n"
        "    print(f\"Supporting CodeQL rules: {', '.join(mapping['supporting_rule_ids']) or mapping['evidence_status']}\")\n"
        "    print(f\"Rationale: {mapping['rationale']}\")"
    ),
    md("## Cell 11 – Evidence Table"),
    code(
        "# Build the metric evidence table directly from SARIF findings.\n"
        "EVIDENCE_DF = build_evidence_table(FINDINGS_DF, METRIC_MAPPINGS)\n"
        "display(EVIDENCE_DF)\n"
        "EVIDENCE_DF.to_csv(PARSED_DIR / 'metric_evidence_mapping.csv', index=False)"
    ),
    md("## Cell 12 – Export Results"),
    code(
        "# Export raw and parsed outputs to the dedicated output/ directory.\n"
        "SUMMARY = build_final_summary(REPO_PATH, FINDINGS_DF, METRIC_MAPPINGS, DB_RESULT, ANALYZE_RESULT)\n"
        "EXPORTED = export_results(OUTPUT_DIR, SARIF_PATH, FINDINGS_DF, EVIDENCE_DF, METRIC_MAPPINGS, SUMMARY)\n"
        "for name, path in EXPORTED.items():\n"
        "    print(f'{name}: {path}')"
    ),
    md("## Cell 13 – Final Analysis Summary"),
    code(
        "# Display the final execution summary derived from CodeQL output.\n"
        "print(f\"Repository Name: {SUMMARY['repository_name']}\")\n"
        "print(f\"Programming Language: {SUMMARY['programming_language']}\")\n"
        "print(f\"Tool Used: {SUMMARY['tool_used']}\")\n"
        "print(f\"Total Source Files Analysed: {SUMMARY['total_source_files_analysed']}\")\n"
        "print(f\"Total CodeQL Queries Executed: {SUMMARY['total_codeql_queries_executed']}\")\n"
        "print(f\"Total Findings: {SUMMARY['total_findings']}\")\n"
        "print(f\"Findings by Severity: {SUMMARY['findings_by_severity']}\")\n"
        "print(f\"Findings by Rule: {SUMMARY['findings_by_rule']}\")\n"
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
