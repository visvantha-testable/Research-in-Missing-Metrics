"""Generate vitest_exception_path_analysis.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "vitest_exception_path_analysis.ipynb"
UTILS = (ROOT / "_vitest_exception_path_analysis_utils.py").read_text(encoding="utf-8")


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "outputs": [], "source": source.splitlines(keepends=True)}


cells = [
    md(
        "# Vitest Exception Path Analysis — White-box Control Flow Testing\n\n"
        "| Property | Value |\n"
        "| --- | --- |\n"
        "| Repository | [typescript-tool-testing-knip](https://github.com/visvantha-testable/typescript-tool-testing-knip) |\n"
        "| Language | TypeScript |\n"
        "| Primary Tool | Vitest |\n"
        "| Coverage Tool | `@vitest/coverage-v8` |\n"
        "| White-box Strategy | Control Flow Testing |\n"
        "| Classification | Path Coverage |\n"
        "| Metric | Exception Path Handling |\n\n"
        "**Metric Description:** Measure the application's ability to gracefully handle unexpected errors "
        "and exception paths, ensuring the system does not crash when execution reaches failure states "
        "such as thrown exceptions, try-catch-finally blocks, rejected promises, runtime errors, or other "
        "exceptional control flows.\n\n"
        "> This notebook clones the repository, executes Vitest without modification, preserves raw "
        "outputs exactly as generated, and extracts evidence only from actual tool output."
    ),
    md("## Step 1 — Clone Repository"),
    code(
        "import subprocess\n"
        "import sys\n\n"
        "subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', '-r', 'requirements.txt'])"
    ),
    code(
        UTILS
        + "\n\n"
        "import shlex\n"
        "from pathlib import Path\n"
        "from IPython.display import Markdown, display\n\n"
        "METRIC_ROOT = resolve_metric_root(Path('.').resolve())\n"
        "DIRS = ensure_dirs(METRIC_ROOT)\n"
        "ARTIFACTS_DIR = DIRS['artifacts']\n"
        "WORKSPACE_DIR = DIRS['workspace']\n\n"
        "print('Metric root:', METRIC_ROOT)\n"
        "print('Artifacts directory:', ARTIFACTS_DIR)\n\n"
        "REPO_PATH, CLONE_STATUS = clone_repository(REPO_URL, WORKSPACE_DIR, reuse=True)\n"
        "print('Clone status:', CLONE_STATUS)\n"
        "print('Repository path:', REPO_PATH)\n"
        "if CLONE_STATUS.get('error'):\n"
        "    print('WARNING: clone reported an error; continuing with available path.')"
    ),
    md("## Step 2 — Navigate Into Project Directory"),
    code(
        "import os\n\n"
        "os.chdir(REPO_PATH)\n"
        "print('Current working directory:', os.getcwd())"
    ),
    md("## Step 3 — Display Environment Information"),
    code(
        "ENV = collect_environment(REPO_PATH)\n"
        "for key, value in ENV.items():\n"
        "    print(f'{key}: {value}')"
    ),
    md("## Step 4 — Install Project Dependencies"),
    code(
        "INSTALL_RESULT = npm_install(REPO_PATH)\n"
        "print('Command:', INSTALL_RESULT['command'])\n"
        "print('Return code:', INSTALL_RESULT['returncode'])\n"
        "print('Success:', INSTALL_RESULT['success'])\n"
        "print('--- terminal output ---')\n"
        "print(INSTALL_RESULT['terminal_output'])\n"
        "if not INSTALL_RESULT['success']:\n"
        "    print('WARNING: npm install failed; later steps may also fail, but notebook will continue.')"
    ),
    md("## Step 5 — Verify Vitest and @vitest/coverage-v8"),
    code(
        "VITEST_PACKAGES_DF = ensure_vitest_packages(REPO_PATH)\n"
        "display(VITEST_PACKAGES_DF)\n"
        "if (VITEST_PACKAGES_DF['status'] != 'OK').any():\n"
        "    print('WARNING: one or more Vitest packages are unavailable; continuing with best effort.')"
    ),
    md("## Step 6 — Detect Test Configuration"),
    code(
        "TEST_CONFIG = detect_test_configuration(REPO_PATH)\n"
        "print(json.dumps(TEST_CONFIG, indent=2))"
    ),
    md("## Step 7 — Execute Test Suite (Vitest without coverage)"),
    code(
        "test_command = TEST_CONFIG['test_command'].split()\n"
        "TEST_RESULT = run_command(test_command, REPO_PATH, 'vitest test run')\n"
        "RAW_VITEST_OUTPUT_PATH = ARTIFACTS_DIR / 'raw_vitest_output.txt'\n"
        "RAW_VITEST_OUTPUT_PATH.write_text(TEST_RESULT['terminal_output'], encoding='utf-8')\n"
        "print('Command:', TEST_RESULT['command'])\n"
        "print('Return code:', TEST_RESULT['returncode'])\n"
        "print('Success:', TEST_RESULT['success'])\n"
        "print('Saved:', RAW_VITEST_OUTPUT_PATH)\n"
        "print('--- raw terminal output ---')\n"
        "print(TEST_RESULT['terminal_output'])"
    ),
    md("## Step 8 — Save Raw Vitest Output"),
    code(
        "print(f'raw_vitest_output.txt saved at: {RAW_VITEST_OUTPUT_PATH}')\n"
        "print(f'File size (bytes): {RAW_VITEST_OUTPUT_PATH.stat().st_size if RAW_VITEST_OUTPUT_PATH.exists() else 0}')"
    ),
    md("## Step 9 — Execute Test Suite With Coverage"),
    code(
        "coverage_command = TEST_CONFIG['coverage_command'].split()\n"
        "COVERAGE_RESULT = run_command(coverage_command, REPO_PATH, 'vitest coverage run')\n"
        "RAW_COVERAGE_OUTPUT_PATH = ARTIFACTS_DIR / 'raw_coverage_output.txt'\n"
        "RAW_COVERAGE_OUTPUT_PATH.write_text(COVERAGE_RESULT['terminal_output'], encoding='utf-8')\n"
        "print('Command:', COVERAGE_RESULT['command'])\n"
        "print('Return code:', COVERAGE_RESULT['returncode'])\n"
        "print('Success:', COVERAGE_RESULT['success'])\n"
        "print('Saved:', RAW_COVERAGE_OUTPUT_PATH)\n"
        "print('--- raw coverage terminal output ---')\n"
        "print(COVERAGE_RESULT['terminal_output'])"
    ),
    md("## Step 10 — Save Raw Coverage Output"),
    code(
        "print(f'raw_coverage_output.txt saved at: {RAW_COVERAGE_OUTPUT_PATH}')\n"
        "print(f'File size (bytes): {RAW_COVERAGE_OUTPUT_PATH.stat().st_size if RAW_COVERAGE_OUTPUT_PATH.exists() else 0}')"
    ),
    md("## Step 11 — Locate and Display Coverage Artifacts"),
    code(
        "COVERAGE_DIR = locate_coverage_dir(REPO_PATH, TEST_CONFIG.get('vitest_config_files', []))\n"
        "print('Coverage directory:', COVERAGE_DIR)\n"
        "ARTIFACT_INFO = collect_coverage_artifacts(COVERAGE_DIR, ARTIFACTS_DIR)\n"
        "print('Copied files:')\n"
        "for name, path in ARTIFACT_INFO['files'].items():\n"
        "    print(f'  {name}: {path}')\n"
        "if ARTIFACT_INFO['missing']:\n"
        "    print('Missing optional artifacts:')\n"
        "    for name in ARTIFACT_INFO['missing']:\n"
        "        print(f'  - {name}')"
    ),
    md("## Step 12 — Print coverage-final.json"),
    code(
        "FINAL_PATH = ARTIFACTS_DIR / 'coverage-final.json'\n"
        "FINAL_RAW = read_text(FINAL_PATH)\n"
        "print('===== coverage-final.json (verbatim) =====')\n"
        "if FINAL_RAW:\n"
        "    print(FINAL_RAW)\n"
        "else:\n"
        "    print('coverage-final.json was not generated.')"
    ),
    md("## Step 13 — Print coverage-summary.json"),
    code(
        "SUMMARY_PATH = ARTIFACTS_DIR / 'coverage-summary.json'\n"
        "SUMMARY_RAW = read_text(SUMMARY_PATH)\n"
        "print('===== coverage-summary.json (verbatim) =====')\n"
        "if SUMMARY_RAW:\n"
        "    print(SUMMARY_RAW)\n"
        "else:\n"
        "    print('coverage-summary.json was not generated.')"
    ),
    md("## Step 14 — Print lcov.info"),
    code(
        "LCOV_PATH = ARTIFACTS_DIR / 'lcov.info'\n"
        "LCOV_RAW = read_text(LCOV_PATH)\n"
        "print('===== lcov.info (verbatim) =====')\n"
        "if LCOV_RAW:\n"
        "    print(LCOV_RAW)\n"
        "else:\n"
        "    print('lcov.info was not generated.')"
    ),
    md("## Step 15 — Print taxonomy_metrics.json"),
    code(
        "TAXONOMY_PATH = ARTIFACTS_DIR / 'taxonomy_metrics.json'\n"
        "TAXONOMY_RAW = read_text(TAXONOMY_PATH)\n"
        "TAXONOMY_METRICS = load_taxonomy_metrics(TAXONOMY_PATH)\n"
        "print('===== taxonomy_metrics.json (verbatim) =====')\n"
        "if TAXONOMY_RAW:\n"
        "    print(TAXONOMY_RAW)\n"
        "else:\n"
        "    print('taxonomy_metrics.json was not generated. Re-run npm run coverage in the repository.')"
    ),
    md("## Step 16 — Search Raw Outputs for Exception Path Handling Evidence"),
    code(
        "EVIDENCE_SOURCES = {\n"
        "    'raw_vitest_output.txt': read_text(RAW_VITEST_OUTPUT_PATH),\n"
        "    'raw_coverage_output.txt': read_text(RAW_COVERAGE_OUTPUT_PATH),\n"
        "    'coverage-summary.json': SUMMARY_RAW,\n"
        "    'coverage-final.json': FINAL_RAW,\n"
        "    'lcov.info': LCOV_RAW,\n"
        "    'taxonomy_metrics.json': TAXONOMY_RAW,\n"
        "}\n"
        "EVIDENCE_DF = build_exception_evidence_dataframe(EVIDENCE_SOURCES)\n"
        "if EVIDENCE_DF.empty:\n"
        "    print('No Exception Path Handling evidence found in the raw tool output.')\n"
        "else:\n"
        "    display(EVIDENCE_DF)"
    ),
    md("## Step 17 — Structured Evidence DataFrame"),
    code(
        "display(EVIDENCE_DF if not EVIDENCE_DF.empty else pd.DataFrame(columns=['Source', 'Evidence Type', 'Raw Output']))"
    ),
    md("## Step 18 — Extract Coverage Metrics"),
    code(
        "COVERAGE_METRICS_DF = extract_coverage_metrics(SUMMARY_PATH)\n"
        "display(COVERAGE_METRICS_DF)"
    ),
    md("## Step 19 — White-box Metric Mapping Table"),
    code(
        "METRIC_MAPPING_DF = build_metric_mapping(\n"
        "    EVIDENCE_DF,\n"
        "    COVERAGE_METRICS_DF,\n"
        "    TEST_RESULT,\n"
        "    COVERAGE_RESULT,\n"
        "    ARTIFACT_INFO,\n"
        "    TAXONOMY_METRICS,\n"
        ")\n"
        "display(METRIC_MAPPING_DF)"
    ),
    md("## Step 20 — Save Artifacts"),
    code(
        "EXCEPTION_ANALYSIS_PATH = ARTIFACTS_DIR / 'exception_path_analysis.csv'\n"
        "EVIDENCE_DF.to_csv(EXCEPTION_ANALYSIS_PATH, index=False)\n"
        "SAVED_FILES = [\n"
        "    str(RAW_VITEST_OUTPUT_PATH.resolve()),\n"
        "    str(RAW_COVERAGE_OUTPUT_PATH.resolve()),\n"
        "    str((ARTIFACTS_DIR / 'coverage-final.json').resolve()),\n"
        "    str((ARTIFACTS_DIR / 'coverage-summary.json').resolve()),\n"
        "    str((ARTIFACTS_DIR / 'lcov.info').resolve()),\n"
        "    str((ARTIFACTS_DIR / 'taxonomy_metrics.json').resolve()),\n"
        "    str(EXCEPTION_ANALYSIS_PATH.resolve()),\n"
        "]\n"
        "print('Saved artifacts:')\n"
        "for path in SAVED_FILES:\n"
        "    exists = Path(path).exists()\n"
        "    print(f\"  [{'OK' if exists else 'MISSING'}] {path}\")"
    ),
    md("## Step 21 — Final Execution Summary"),
    code(
        "NOTEBOOK_STATUS = 'COMPLETED'\n"
        "if not TEST_RESULT.get('success') or not COVERAGE_RESULT.get('success'):\n"
        "    NOTEBOOK_STATUS = 'COMPLETED WITH WARNINGS'\n"
        "SUMMARY_DF = build_execution_summary(\n"
        "    REPO_URL,\n"
        "    TEST_RESULT,\n"
        "    COVERAGE_RESULT,\n"
        "    ARTIFACT_INFO,\n"
        "    EVIDENCE_DF,\n"
        "    [Path(p).name for p in SAVED_FILES],\n"
        "    NOTEBOOK_STATUS,\n"
        "    TAXONOMY_METRICS,\n"
        ")\n"
        "display(SUMMARY_DF)\n"
        "print('\\nNotebook finished. All raw outputs were preserved without modification.')"
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
