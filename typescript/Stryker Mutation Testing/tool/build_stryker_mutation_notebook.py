"""Generate stryker_mutation_raw_output_extraction.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "stryker_mutation_raw_output_extraction.ipynb"
UTILS = (ROOT / "_stryker_mutation_utils.py").read_text(encoding="utf-8")


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "outputs": [], "source": source.splitlines(keepends=True)}


cells = [
    md(
        "# Mutation Testing Raw Tool Output Extraction using @stryker-mutator/core\n\n"
        "| Property | Value |\n"
        "| --- | --- |\n"
        "| Language | TypeScript |\n"
        "| Tool | `@stryker-mutator/core` |\n"
        "| Technique | Mutation Testing |\n"
        "| Classification | Mutation Score |\n"
        "| Repository | [typescript-tool-testing-stryker-mutator-core]"
        "(https://github.com/visvantha-testable/typescript-tool-testing-stryker-mutator-core) |\n\n"
        "> This notebook clones the repository, executes Stryker, and preserves every generated report "
        "exactly as emitted. No repository edits. No derived metrics."
    ),
    md("## 2. Install Required Packages"),
    code(
        "# Install Python dependencies used by this notebook (git, pandas, GitPython).\n"
        "import subprocess\n"
        "import sys\n\n"
        "subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', '-r', 'requirements.txt'])"
    ),
    md("## 3. Clone Repository"),
    code(
        "# Configure repository source and clone behavior.\n"
        "USE_GIT_REPO = True\n"
        'REPO_URL = "https://github.com/visvantha-testable/typescript-tool-testing-stryker-mutator-core.git"\n'
        'LOCAL_REPO = "./workspace/typescript-tool-testing-stryker-mutator-core"\n'
        'IF_CLONE_EXISTS = "reuse"\n'
        "CLONE_DEPTH = 1\n"
    ),
    md("## 4. Install Dependencies"),
    code(
        UTILS
        + "\n\n"
        "# Load helper utilities and initialize artifact directories.\n"
        "import json\n"
        "import time\n"
        "from pathlib import Path\n"
        "from IPython.display import Markdown, display\n\n"
        "METRIC_ROOT = resolve_metric_root(Path('.').resolve())\n"
        "DIRS = ensure_artifact_dirs(METRIC_ROOT)\n"
        "RAW_TOOL_OUTPUT_DIR = DIRS['raw_tool_output']\n"
        "PARSED_DIR = DIRS['parsed']\n"
        "REPORTS_DIR = DIRS['reports']\n"
        "WORKSPACE_DIR = DIRS['workspace']\n"
        "ERROR_LOG_PATH = REPORTS_DIR / 'error_log.txt'\n"
        "logger = NotebookLogger(ERROR_LOG_PATH)\n"
        "PIPELINE_STARTED = time.perf_counter()\n\n"
        "# Clone or reuse the target TypeScript repository.\n"
        "REPO_PATH = resolve_repository_path(\n"
        "    USE_GIT_REPO,\n"
        "    REPO_URL,\n"
        "    Path(LOCAL_REPO),\n"
        "    WORKSPACE_DIR,\n"
        "    IF_CLONE_EXISTS,\n"
        "    logger,\n"
        "    CLONE_DEPTH,\n"
        ")\n\n"
        "REPO_VALIDATION = validate_repository_layout(REPO_PATH, logger)\n"
        "display(pd.DataFrame([REPO_VALIDATION]))\n"
        "if not REPO_VALIDATION['repository_valid']:\n"
        "    raise RuntimeError('Repository validation failed.')\n\n"
        "# Display repository structure and key configuration files.\n"
        "display(list_repository_structure(REPO_PATH))\n"
        "print('===== package.json (verbatim) =====')\n"
        "print(read_text(REPO_PATH / 'package.json'))\n"
        "print('\\n===== tsconfig.json (verbatim) =====')\n"
        "print(read_text(REPO_PATH / 'tsconfig.json'))\n"
        "STRYKER_CONFIG_PATH = locate_stryker_config(REPO_PATH)\n"
        "print('\\n===== Stryker configuration (verbatim) =====')\n"
        "print(read_text(STRYKER_CONFIG_PATH) if STRYKER_CONFIG_PATH else 'No Stryker config found.')\n"
        "VITEST_CONFIG = next((REPO_PATH / name for name in ('vitest.config.ts', 'vitest.config.js') if (REPO_PATH / name).exists()), None)\n"
        "print('\\n===== Vitest configuration (verbatim) =====')\n"
        "print(read_text(VITEST_CONFIG) if VITEST_CONFIG else 'No Vitest config found.')"
    ),
    code(
        "# Install repository npm dependencies without modifying repository source files.\n"
        "INSTALL_RESULT = run_command(['npm', 'install'], REPO_PATH, 'npm install')\n"
        "print(f\"Command: {INSTALL_RESULT['command']}\")\n"
        "print(f\"Return code: {INSTALL_RESULT['returncode']}\")\n"
        "print(f\"Elapsed ms: {INSTALL_RESULT['elapsed_ms']}\")\n"
        "print('--- stdout ---')\n"
        "print(INSTALL_RESULT['stdout'])\n"
        "print('--- stderr ---')\n"
        "print(INSTALL_RESULT['stderr'])\n"
        "if not INSTALL_RESULT['success']:\n"
        "    raise RuntimeError('npm install failed.')\n\n"
        "# Ensure @stryker-mutator/core is available and record package versions.\n"
        "STRYKER_PACKAGES_DF = ensure_stryker_package(REPO_PATH, logger)\n"
        "display(STRYKER_PACKAGES_DF)\n"
        "ENVIRONMENT = collect_environment(REPO_PATH)\n"
        "display(pd.DataFrame([ENVIRONMENT]))\n"
        "(REPORTS_DIR / 'environment.json').write_text(json.dumps(ENVIRONMENT, indent=2), encoding='utf-8')"
    ),
    md("## 5. Verify Stryker Configuration"),
    code(
        "# Extract selected Stryker settings directly from the repository config file.\n"
        "CONFIG_FIELDS_DF = extract_stryker_config_fields(STRYKER_CONFIG_PATH) if STRYKER_CONFIG_PATH else pd.DataFrame()\n"
        "display(CONFIG_FIELDS_DF)\n"
        "CONFIG_FIELDS_DF.to_csv(PARSED_DIR / 'stryker_config_fields.csv', index=False)"
    ),
    md("## 6. Execute Baseline Test Suite"),
    code(
        "# Run the repository baseline test command before mutation testing.\n"
        "BASELINE_RESULT = run_command(['npm', 'test'], REPO_PATH, 'baseline tests')\n"
        "print(f\"Command: {BASELINE_RESULT['command']}\")\n"
        "print(f\"Return code: {BASELINE_RESULT['returncode']}\")\n"
        "print(f\"Elapsed ms: {BASELINE_RESULT['elapsed_ms']}\")\n"
        "print('--- stdout ---')\n"
        "print(BASELINE_RESULT['stdout'])\n"
        "print('--- stderr ---')\n"
        "print(BASELINE_RESULT['stderr'])"
    ),
    md("## 7. Execute Mutation Testing"),
    code(
        "# Execute Stryker and capture the complete raw console output without filtering.\n"
        "STRYKER_RESULT = run_command(['npx', 'stryker', 'run'], REPO_PATH, 'stryker run')\n"
        "print(f\"Command: {STRYKER_RESULT['command']}\")\n"
        "print(f\"Return code: {STRYKER_RESULT['returncode']}\")\n"
        "print(f\"Elapsed ms: {STRYKER_RESULT['elapsed_ms']}\")\n"
        "print('--- stdout ---')\n"
        "print(STRYKER_RESULT['stdout'])\n"
        "print('--- stderr ---')\n"
        "print(STRYKER_RESULT['stderr'])\n"
        "# Continue even if surviving mutants are reported; do not abort on non-zero thresholds unless execution failed.\n"
        "if not STRYKER_RESULT['stdout'] and not STRYKER_RESULT['stderr']:\n"
        "    raise RuntimeError('Stryker produced no console output.')"
    ),
    md("## 8. Extract Raw Tool Output"),
    code(
        "# Copy every Stryker-generated artifact exactly as produced into raw_tool_output/.\n"
        "PRESERVED = preserve_stryker_artifacts(REPO_PATH, RAW_TOOL_OUTPUT_DIR)\n"
        "EXPORTED_PATHS = export_execution_bundle(RAW_TOOL_OUTPUT_DIR, BASELINE_RESULT, STRYKER_RESULT, PRESERVED)\n"
        "print('Preserved raw artifacts:')\n"
        "for name, path in sorted(EXPORTED_PATHS.items()):\n"
        "    print(f'  [{\"OK\" if Path(path).exists() else \"MISSING\"}] {name}: {path}')\n"
        "if PRESERVED['missing']:\n"
        "    print('\\nArtifacts not generated by this repository configuration:')\n"
        "    for item in PRESERVED['missing']:\n"
        "        print(f'  - {item}')"
    ),
    md("## 9. Extract Mutation Score"),
    code(
        "# Read mutation score and summary counts only from raw Stryker console/JSON fields.\n"
        "REPORT_PATH = RAW_TOOL_OUTPUT_DIR / 'mutation-report.json'\n"
        "if not REPORT_PATH.exists():\n"
        "    candidate = REPO_PATH / 'artifacts' / 'training' / 'mutation' / 'mutation-report.json'\n"
        "    if candidate.exists():\n"
        "        copy_file_verbatim(candidate, REPORT_PATH)\n"
        "REPORT_JSON = load_json(REPORT_PATH)\n"
        "REPORT_DICT = REPORT_JSON if isinstance(REPORT_JSON, dict) else {}\n"
        "SUMMARY_DF = build_mutation_summary(STRYKER_RESULT['stdout'], REPORT_DICT)\n"
        "SCORE_TABLE_DF = parse_console_score_table(STRYKER_RESULT['stdout'])\n"
        "display(SUMMARY_DF)\n"
        "display(SCORE_TABLE_DF)\n"
        "SUMMARY_DF.to_csv(PARSED_DIR / 'mutation_summary_raw.csv', index=False)\n"
        "SCORE_TABLE_DF.to_csv(PARSED_DIR / 'mutation_score_table_raw.csv', index=False)"
    ),
    md("## 10. Extract Mutant Information"),
    code(
        "# Flatten mutant records directly from mutation-report.json without modifying values.\n"
        "MUTANTS_DF = flatten_mutants(REPORT_DICT)\n"
        "display(MUTANTS_DF)\n"
        "MUTANTS_DF.to_csv(PARSED_DIR / 'mutants_raw.csv', index=False)"
    ),
    md("## 11. Extract Mutator Types"),
    code(
        "# List mutator categories exactly as emitted in the raw JSON report.\n"
        "MUTATOR_TYPES_DF = extract_mutator_types(MUTANTS_DF)\n"
        "display(MUTATOR_TYPES_DF)\n"
        "MUTATOR_TYPES_DF.to_csv(PARSED_DIR / 'mutator_types_raw.csv', index=False)"
    ),
    md("## 12. Extract Coverage Information"),
    code(
        "# Capture coverage-related fields emitted by Stryker in mutation-report.json.\n"
        "COVERAGE_DF = extract_coverage_fields(REPORT_DICT)\n"
        "display(COVERAGE_DF)\n"
        "COVERAGE_DF.to_csv(PARSED_DIR / 'coverage_fields_raw.csv', index=False)"
    ),
    md("## 13. Preserve Raw JSON"),
    code(
        "# Print every JSON artifact verbatim without editing.\n"
        "TAXONOMY_METRICS_PATH = RAW_TOOL_OUTPUT_DIR / 'taxonomy_metrics.json'\n"
        "TAXONOMY_METRICS = load_taxonomy_metrics(TAXONOMY_METRICS_PATH)\n"
        "JSON_ARTIFACTS = [path for path in RAW_TOOL_OUTPUT_DIR.glob('*.json')]\n"
        "for path in sorted(JSON_ARTIFACTS):\n"
        "    print(f'===== {path.name} (verbatim) =====')\n"
        "    print(read_text(path))\n"
        "    print()"
    ),
    md("## 14. Preserve HTML Reports"),
    code(
        "# Print HTML artifacts verbatim when generated by the repository configuration.\n"
        "HTML_ARTIFACTS = list(RAW_TOOL_OUTPUT_DIR.glob('*.html'))\n"
        "if not HTML_ARTIFACTS:\n"
        "    print('No HTML report was generated by this repository Stryker configuration.')\n"
        "else:\n"
        "    for path in sorted(HTML_ARTIFACTS):\n"
        "        print(f'===== {path.name} (verbatim) =====')\n"
        "        print(read_text(path))"
    ),
    md("## 15. Preserve Console Output"),
    code(
        "# Confirm complete stdout/stderr files were saved without truncation.\n"
        "CONSOLE_PATH = RAW_TOOL_OUTPUT_DIR / 'console_output.txt'\n"
        "STDERR_PATH = RAW_TOOL_OUTPUT_DIR / 'stderr_output.txt'\n"
        "print(f'console_output.txt bytes: {CONSOLE_PATH.stat().st_size if CONSOLE_PATH.exists() else 0}')\n"
        "print(f'stderr_output.txt bytes: {STDERR_PATH.stat().st_size if STDERR_PATH.exists() else 0}')\n"
        "print('\\n===== console_output.txt (verbatim) =====')\n"
        "print(read_text(CONSOLE_PATH))\n"
        "print('\\n===== stderr_output.txt (verbatim) =====')\n"
        "print(read_text(STDERR_PATH))"
    ),
    md("## 16. Export Results"),
    code(
        "# List final deliverables stored under raw_tool_output/.\n"
        "DELIVERABLES = [\n"
        "    'execution.log',\n"
        "    'console_output.txt',\n"
        "    'stderr_output.txt',\n"
        "    'mutation-report.json',\n"
        "    'taxonomy_metrics.json',\n"
        "    'mutation-report.html',\n"
        "    'dashboard.json',\n"
        "    'event-recorder.json',\n"
        "]\n"
        "print(f'Raw tool output folder: {RAW_TOOL_OUTPUT_DIR.resolve()}')\n"
        "for name in DELIVERABLES:\n"
        "    path = RAW_TOOL_OUTPUT_DIR / name\n"
        "    print(f\"  [{'OK' if path.exists() else 'NOT GENERATED'}] {name}\")\n"
        "print('\\nAdditional preserved files:')\n"
        "for path in sorted(RAW_TOOL_OUTPUT_DIR.iterdir()):\n"
        "    if path.name not in DELIVERABLES:\n"
        "        print(f'  [OK] {path.name}')"
    ),
    md("## 17. Raw Output Tables"),
    code(
        "# Display notebook tables built directly from raw Stryker output.\n"
        "display(Markdown('### Mutation Summary'))\n"
        "display(SUMMARY_DF)\n"
        "display(SCORE_TABLE_DF)\n"
        "display(Markdown('### Mutant List'))\n"
        "display(MUTANTS_DF)\n"
        "display(Markdown('### Mutator Types'))\n"
        "display(MUTATOR_TYPES_DF)"
    ),
    md("## 18. Native Stryker Output Coverage"),
    code(
        "# Confirm native Stryker artifacts expose all taxonomy metric names.\n"
        "NATIVE_COVERAGE_DF = build_native_coverage_table(REPORT_DICT, read_text(RAW_TOOL_OUTPUT_DIR / 'console_output.txt'))\n"
        "display(NATIVE_COVERAGE_DF)\n"
        "NATIVE_COVERAGE_DF.to_csv(PARSED_DIR / 'native_output_coverage.csv', index=False)"
    ),
    md("## 19. Mapping to White-box Testing Metrics"),
    code(
        "# Identify which raw Stryker outputs provide evidence for each taxonomy metric.\n"
        "MAPPING_DF = build_whitebox_mapping_table(TAXONOMY_METRICS)\n"
        "display(MAPPING_DF)\n"
        "MAPPING_DF.to_csv(PARSED_DIR / 'whitebox_metric_mapping.csv', index=False)"
    ),
    md("## 20. Final Deliverables"),
    code(
        "# Record notebook completion status and total execution time.\n"
        "TOTAL_SECONDS = round(time.perf_counter() - PIPELINE_STARTED, 2)\n"
        "FINAL_STATUS = {\n"
        "    'notebook': 'Mutation Testing Raw Tool Output Extraction using @stryker-mutator/core',\n"
        "    'repository': REPO_URL,\n"
        "    'tool': '@stryker-mutator/core',\n"
        "    'baseline_returncode': BASELINE_RESULT['returncode'],\n"
        "    'stryker_returncode': STRYKER_RESULT['returncode'],\n"
        "    'raw_tool_output_dir': str(RAW_TOOL_OUTPUT_DIR.resolve()),\n"
        "    'elapsed_seconds': TOTAL_SECONDS,\n"
        "    'derived_metrics_used': False,\n"
        "    'repository_modified': False,\n"
        "    'tool_output_modified': False,\n"
        "}\n"
        "(REPORTS_DIR / 'final_status.json').write_text(json.dumps(FINAL_STATUS, indent=2), encoding='utf-8')\n"
        "display(pd.DataFrame([FINAL_STATUS]))\n"
        "logger.write_errors()\n"
        "print('\\nNotebook finished. All raw Stryker outputs were preserved without modification.')"
    ),
]

NOTEBOOK.write_text(
    json.dumps(
        {
            "cells": cells,
            "metadata": {
                "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                "language_info": {"name": "python", "version": "3.11.0"},
            },
            "nbformat": 4,
            "nbformat_minor": 5,
        },
        indent=1,
    ),
    encoding="utf-8",
)
print(f"Wrote {NOTEBOOK}")
