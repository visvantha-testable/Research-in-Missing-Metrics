"""Generate codecov_differential_coverage_extraction.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "codecov_differential_coverage_extraction.ipynb"
UTILS = (ROOT / "_codecov_differential_coverage_utils.py").read_text(encoding="utf-8")


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "outputs": [], "source": source.splitlines(keepends=True)}


cells = [
    md("# Codecov Differential Coverage — Raw Tool Output Extraction\n\nExtract raw Codecov upload logs and API responses for TypeScript differential coverage metrics."),
    md("## Cell 1 – Project Information"),
    code(
        "# Display project metadata and execution context.\n"
        "import os\n"
        "import subprocess\n"
        "import sys\n"
        "from datetime import datetime, timezone\n"
        "from pathlib import Path\n\n"
        "REPO_URL = 'https://github.com/visvantha-testable/typescript-tool-testing-vitest-coverage-v8'\n"
        "PROGRAMMING_LANGUAGE = 'TypeScript'\n"
        "TOOL_NAME = 'Codecov'\n"
        "TEST_FRAMEWORK = 'Vitest'\n"
        "COVERAGE_PROVIDER = '@vitest/coverage-v8'\n"
        "ANALYSIS_DATE = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')\n"
        "CURRENT_WORKING_DIRECTORY = str(Path('.').resolve())\n\n"
        "for label, value in {\n"
        "    'Repository URL': REPO_URL,\n"
        "    'Programming Language': PROGRAMMING_LANGUAGE,\n"
        "    'Tool Name': TOOL_NAME,\n"
        "    'Test Framework': TEST_FRAMEWORK,\n"
        "    'Coverage Provider': COVERAGE_PROVIDER,\n"
        "    'Analysis Date': ANALYSIS_DATE,\n"
        "    'Current Working Directory': CURRENT_WORKING_DIRECTORY,\n"
        "}.items():\n"
        "    print(f'{label}: {value}')"
    ),
    md("## Cell 2 – Clone Repository"),
    code(
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
        "PREREQ_DF = collect_prerequisite_versions()\n"
        "display(PREREQ_DF)\n"
        "PREREQ_DF.to_csv(PARSED_DIR / 'prerequisite_versions.csv', index=False)"
    ),
    md("## Cell 4 – Install Project Dependencies"),
    code(
        "INSTALL_RESULT = run_command(['npm', 'install'], REPO_PATH, 'npm install')\n"
        "print('--- stdout ---')\n"
        "print(INSTALL_RESULT['stdout'])\n"
        "print('--- stderr ---')\n"
        "print(INSTALL_RESULT['stderr'])\n"
        "PACKAGES_DF = verify_required_packages(REPO_PATH)\n"
        "display(PACKAGES_DF)"
    ),
    md("## Cell 5 – Execute Test Suite with Coverage"),
    code(
        "COVERAGE_RESULT = run_coverage_tests(REPO_PATH)\n"
        "print('--- stdout ---')\n"
        "print(COVERAGE_RESULT['stdout'])\n"
        "print('--- stderr ---')\n"
        "print(COVERAGE_RESULT['stderr'])\n"
        "(RAW_DIR / 'vitest_coverage.log').write_text(\n"
        "    f\"--- stdout ---\\n{COVERAGE_RESULT['stdout']}\\n\\n--- stderr ---\\n{COVERAGE_RESULT['stderr']}\",\n"
        "    encoding='utf-8',\n"
        ")"
    ),
    md("## Cell 6 – Locate Coverage Reports"),
    code(
        "ARTIFACTS = locate_coverage_artifacts(REPO_PATH)\n"
        "ARTIFACTS_DF = describe_coverage_tree(ARTIFACTS)\n"
        "display(ARTIFACTS_DF)\n"
        "LOCAL_SUMMARY = parse_local_coverage_summary(ARTIFACTS.get('coverage-summary.json'))\n"
        "print('Local coverage summary:', LOCAL_SUMMARY)"
    ),
    md("## Cell 7 – Upload Coverage to Codecov"),
    code(
        "GIT_META = get_git_metadata(REPO_PATH)\n"
        "CODECOV_CLI = download_codecov_cli(DIRS['codecov_cli'], LOGGER)\n"
        "print('Codecov token present:', bool(os.environ.get('CODECOV_TOKEN', '').strip()))\n"
        "UPLOAD_RESULT = upload_coverage_to_codecov(CODECOV_CLI, REPO_PATH, ARTIFACTS['lcov.info'], GIT_META, LOGGER) if ARTIFACTS.get('lcov.info') else {'success': False, 'stdout': '', 'stderr': 'lcov.info not found', 'token_present': bool(os.environ.get('CODECOV_TOKEN', '').strip())}\n"
        "print('--- upload stdout ---')\n"
        "print(UPLOAD_RESULT['stdout'])\n"
        "print('--- upload stderr ---')\n"
        "print(UPLOAD_RESULT['stderr'])\n"
        "(RAW_DIR / 'codecov_upload.log').write_text(\n"
        "    f\"--- stdout ---\\n{UPLOAD_RESULT['stdout']}\\n\\n--- stderr ---\\n{UPLOAD_RESULT['stderr']}\",\n"
        "    encoding='utf-8',\n"
        ")"
    ),
    md("## Cell 8 – Retrieve Raw Codecov Results"),
    code(
        "CODECOV_RESPONSES = fetch_codecov_results(GIT_META, RAW_DIR, LOGGER)\n"
        "for name, payload in CODECOV_RESPONSES.items():\n"
        "    print(f\"\\n===== {name} (status {payload.get('status_code')}) =====\")\n"
        "    print(json.dumps(payload.get('body'), indent=2))"
    ),
    md("## Cell 9 – Parse Codecov Output"),
    code(
        "FINDINGS_DF = parse_codecov_findings(CODECOV_RESPONSES, GIT_META)\n"
        "display(FINDINGS_DF)\n"
        "FINDINGS_DF.to_csv(PARSED_DIR / 'parsed_findings.csv', index=False)"
    ),
    md("## Cell 10 – Metric Mapping"),
    code(
        "METRIC_MAPPINGS = build_metric_mappings(FINDINGS_DF, CODECOV_RESPONSES)\n"
        "for mapping in METRIC_MAPPINGS:\n"
        "    print(f\"\\nMetric: {mapping['metric']}\")\n"
        "    print(f\"Classification: {mapping['classification']}\")\n"
        "    print(f\"Technique: {mapping['technique']}\")\n"
        "    print(f\"Status: {mapping['evidence_status']}\")\n"
        "    print(f\"Rationale: {mapping['rationale']}\")"
    ),
    md("## Cell 11 – Evidence Table"),
    code(
        "EVIDENCE_DF = build_evidence_table(METRIC_MAPPINGS, FINDINGS_DF)\n"
        "display(EVIDENCE_DF)\n"
        "EVIDENCE_DF.to_csv(PARSED_DIR / 'metric_evidence_mapping.csv', index=False)"
    ),
    md("## Cell 12 – Export Results"),
    code(
        "SUMMARY = build_final_summary(REPO_PATH, FINDINGS_DF, METRIC_MAPPINGS, LOCAL_SUMMARY)\n"
        "EXPORTED = export_results(OUTPUT_DIR, RAW_DIR, FINDINGS_DF, EVIDENCE_DF, METRIC_MAPPINGS, SUMMARY)\n"
        "for name, path in EXPORTED.items():\n"
        "    print(f'{name}: {path}')"
    ),
    md("## Cell 13 – Final Summary"),
    code(
        "print(f\"Repository Name: {SUMMARY['repository_name']}\")\n"
        "print(f\"Programming Language: {SUMMARY['programming_language']}\")\n"
        "print(f\"Tool Used: {SUMMARY['tool_used']}\")\n"
        "print(f\"Total Files Analysed: {SUMMARY['total_files_analysed']}\")\n"
        "print(f\"Total Covered Files: {SUMMARY['total_covered_files']}\")\n"
        "print(f\"Total Uncovered Files: {SUMMARY['total_uncovered_files']}\")\n"
        "print(f\"Project Coverage: {SUMMARY['project_coverage']}\")\n"
        "print(f\"Patch Coverage: {SUMMARY['patch_coverage']}\")\n"
        "print(f\"Coverage Delta: {SUMMARY['coverage_delta']}\")\n"
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
