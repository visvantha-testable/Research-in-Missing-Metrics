"""Generate stryker_vitest_coverage_extraction.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "stryker_vitest_coverage_extraction.ipynb"
UTILS = (ROOT / "_stryker_vitest_coverage_utils.py").read_text(encoding="utf-8")


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "outputs": [], "source": source.splitlines(keepends=True)}


cells = [
    md(
        "# @stryker-mutator/core Raw Tool Output Extraction — Vitest Coverage v8\n\n"
        "Automated mutation testing extraction for TypeScript using Vitest and @vitest/coverage-v8."
    ),
    md("## Cell 1 – Project Information"),
    code(
        "# Display repository, tool, and execution metadata.\n"
        "import subprocess\n"
        "import sys\n"
        "from datetime import datetime, timezone\n"
        "from pathlib import Path\n\n"
        "REPO_URL = 'https://github.com/visvantha-testable/typescript-tool-testing-vitest-coverage-v8'\n"
        "PROGRAMMING_LANGUAGE = 'TypeScript'\n"
        "MUTATION_TOOL = '@stryker-mutator/core'\n"
        "TEST_FRAMEWORK = 'Vitest'\n"
        "COVERAGE_PROVIDER = '@vitest/coverage-v8'\n"
        "EXECUTION_DATE = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')\n"
        "CURRENT_WORKING_DIRECTORY = str(Path('.').resolve())\n\n"
        "for label, value in {\n"
        "    'Repository URL': REPO_URL,\n"
        "    'Programming Language': PROGRAMMING_LANGUAGE,\n"
        "    'Mutation Testing Tool': MUTATION_TOOL,\n"
        "    'Test Framework': TEST_FRAMEWORK,\n"
        "    'Coverage Provider': COVERAGE_PROVIDER,\n"
        "    'Notebook Execution Date': EXECUTION_DATE,\n"
        "    'Current Working Directory': CURRENT_WORKING_DIRECTORY,\n"
        "}.items():\n"
        "    print(f'{label}: {value}')"
    ),
    md("## Cell 2 – Clone Repository"),
    code(
        "# Install Python dependencies, load helpers, and clone or reuse the repository.\n"
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
        "# Verify Git, Node.js, npm, and Python package versions.\n"
        "PREREQ_DF = collect_prerequisite_versions()\n"
        "display(PREREQ_DF)\n"
        "PREREQ_DF.to_csv(PARSED_DIR / 'prerequisite_versions.csv', index=False)"
    ),
    md("## Cell 4 – Install Project Dependencies"),
    code(
        "# Install repository npm dependencies and verify required packages.\n"
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
        "    raise RuntimeError('npm install failed.')\n\n"
        "PACKAGES_DF = verify_required_packages(REPO_PATH, LOGGER)\n"
        "display(PACKAGES_DF)"
    ),
    md("## Cell 5 – Verify Stryker Configuration"),
    code(
        "# Locate or generate a Stryker configuration without modifying existing repository configs.\n"
        "STRYKER_CONFIG, CONFIG_GENERATED = resolve_stryker_config(REPO_PATH, DIRS['temp'])\n"
        "print(f'Configuration path: {STRYKER_CONFIG}')\n"
        "print(f'Generated outside repository: {CONFIG_GENERATED}')\n"
        "print('===== Stryker configuration (verbatim) =====')\n"
        "print(read_text(STRYKER_CONFIG))"
    ),
    md("## Cell 6 – Execute Baseline Tests"),
    code(
        "# Run baseline tests and coverage before mutation testing.\n"
        "BASELINE_RESULT = run_command(['npm', 'test'], REPO_PATH, 'npm test')\n"
        "print('--- test stdout ---')\n"
        "print(BASELINE_RESULT['stdout'])\n"
        "print('--- test stderr ---')\n"
        "print(BASELINE_RESULT['stderr'])\n\n"
        "COVERAGE_RESULT = run_command(['npm', 'run', 'coverage'], REPO_PATH, 'npm run coverage')\n"
        "print('--- coverage stdout ---')\n"
        "print(COVERAGE_RESULT['stdout'])\n"
        "print('--- coverage stderr ---')\n"
        "print(COVERAGE_RESULT['stderr'])"
    ),
    md("## Cell 7 – Execute Mutation Testing"),
    code(
        "# Execute Stryker and capture complete console output without modification.\n"
        "STRYKER_COMMAND = ['npx', 'stryker', 'run']\n"
        "if CONFIG_GENERATED:\n"
        "    STRYKER_COMMAND.extend(['--config', str(STRYKER_CONFIG)])\n"
        "STRYKER_RESULT = run_command(STRYKER_COMMAND, REPO_PATH, 'stryker run')\n"
        "print('--- stdout ---')\n"
        "print(STRYKER_RESULT['stdout'])\n"
        "print('--- stderr ---')\n"
        "print(STRYKER_RESULT['stderr'])\n"
        "print(f\"Elapsed ms: {STRYKER_RESULT['elapsed_ms']}\")"
    ),
    md("## Cell 8 – Preserve Raw Tool Output"),
    code(
        "# Preserve every raw Stryker artifact and console log exactly as generated.\n"
        "(RAW_DIR / 'console_output.txt').write_text(STRYKER_RESULT.get('stdout', ''), encoding='utf-8')\n"
        "(RAW_DIR / 'stderr_output.txt').write_text(STRYKER_RESULT.get('stderr', ''), encoding='utf-8')\n"
        "(RAW_DIR / 'execution.log').write_text(\n"
        "    BASELINE_RESULT.get('stdout', '') + '\\n\\n' + COVERAGE_RESULT.get('stdout', '') + '\\n\\n' + STRYKER_RESULT.get('stdout', ''),\n"
        "    encoding='utf-8',\n"
        ")\n"
        "PRESERVED = preserve_stryker_artifacts(REPO_PATH, RAW_DIR)\n"
        "SARIF_PATH = RAW_DIR / 'mutation-report.json'\n"
        "if not SARIF_PATH.exists():\n"
        "    candidate = REPO_PATH / 'artifacts' / 'training' / 'mutation' / 'mutation-report.json'\n"
        "    if candidate.exists():\n"
        "        copy_file_verbatim(candidate, SARIF_PATH)\n"
        "for name, path in PRESERVED.items():\n"
        "    print(f'Preserved: {name} -> {path}')\n"
        "print('===== console_output.txt (verbatim) =====')\n"
        "print(read_text(RAW_DIR / 'console_output.txt'))\n"
        "print('===== mutation-report.json (verbatim) =====')\n"
        "print(read_text(SARIF_PATH))"
    ),
    md("## Cell 9 – Parse Stryker JSON Output"),
    code(
        "# Parse mutation-report.json into a complete mutant findings table.\n"
        "REPORT = load_json(SARIF_PATH) or {}\n"
        "MUTANTS_DF = flatten_mutants(REPORT)\n"
        "display(MUTANTS_DF)\n"
        "MUTANTS_DF.to_csv(PARSED_DIR / 'parsed_findings.csv', index=False)"
    ),
    md("## Cell 10 – Metric Mapping"),
    code(
        "# Map Stryker mutant records to the requested white-box testing metrics.\n"
        "METRIC_MAPPINGS = build_metric_mappings(MUTANTS_DF)\n"
        "for mapping in METRIC_MAPPINGS:\n"
        "    print(f\"\\nMetric: {mapping['metric']}\")\n"
        "    print(f\"Classification: {mapping['classification']}\")\n"
        "    print(f\"Technique: {mapping['technique']}\")\n"
        "    print(f\"Mutant IDs: {', '.join(mapping['supporting_mutant_ids'][:10]) or mapping['evidence_status']}\")\n"
        "    print(f\"Mutators: {', '.join(mapping['supporting_mutators']) or 'none'}\")\n"
        "    print(f\"Files: {', '.join(mapping['supporting_files']) or 'none'}\")\n"
        "    print(f\"Statuses: {', '.join(mapping['supporting_statuses']) or 'none'}\")\n"
        "    print(f\"Rationale: {mapping['rationale']}\")"
    ),
    md("## Cell 11 – Evidence Table"),
    code(
        "# Build the structured metric evidence table from Stryker JSON output only.\n"
        "EVIDENCE_DF = build_evidence_table(METRIC_MAPPINGS)\n"
        "display(EVIDENCE_DF)\n"
        "EVIDENCE_DF.to_csv(PARSED_DIR / 'metric_evidence_mapping.csv', index=False)"
    ),
    md("## Cell 12 – Export Results"),
    code(
        "# Export raw and parsed deliverables to the output/ directory.\n"
        "MUTATION_SCORE = parse_mutation_score(STRYKER_RESULT.get('stdout', ''), MUTANTS_DF)\n"
        "SUMMARY = build_final_summary(REPO_PATH, MUTANTS_DF, METRIC_MAPPINGS, MUTATION_SCORE)\n"
        "EXPORTED = export_results(OUTPUT_DIR, RAW_DIR, MUTANTS_DF, EVIDENCE_DF, METRIC_MAPPINGS, SUMMARY)\n"
        "for name, path in EXPORTED.items():\n"
        "    print(f'{name}: {path}')"
    ),
    md("## Cell 13 – Final Summary"),
    code(
        "# Display the final mutation testing summary derived from raw Stryker output.\n"
        "print(f\"Repository Name: {SUMMARY['repository_name']}\")\n"
        "print(f\"Programming Language: {SUMMARY['programming_language']}\")\n"
        "print(f\"Tool Used: {SUMMARY['tool_used']}\")\n"
        "print(f\"Total Files Analysed: {SUMMARY['total_files_analysed']}\")\n"
        "print(f\"Total Mutants Generated: {SUMMARY['total_mutants_generated']}\")\n"
        "print(f\"Total Mutants Killed: {SUMMARY['total_mutants_killed']}\")\n"
        "print(f\"Total Survived Mutants: {SUMMARY['total_survived_mutants']}\")\n"
        "print(f\"Total Timeout Mutants: {SUMMARY['total_timeout_mutants']}\")\n"
        "print(f\"Total Runtime Errors: {SUMMARY['total_runtime_errors']}\")\n"
        "print(f\"Total NoCoverage Mutants: {SUMMARY['total_nocoverage_mutants']}\")\n"
        "print(f\"Mutation Score: {SUMMARY['mutation_score']}\")\n"
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
