"""Generate roslynator_nesting_depth_extraction.ipynb."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
METRIC_ROOT = ROOT.parent
NOTEBOOK = METRIC_ROOT / "roslynator_nesting_depth_extraction.ipynb"
UTILS = (ROOT / "_roslynator_notebook_utils.py").read_text(encoding="utf-8")


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": [line + "\n" for line in source.split("\n")]}


def code(source: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": [line + "\n" for line in source.split("\n")]}


cells = [
    md(
        "# Roslynator Maintainability — Nesting Depth Raw Output Extraction (C#)\n\n"
        "This notebook analyzes **C# repositories** with **Roslynator** and a custom **Roslyn AST nesting-depth analyzer**, "
        "capturing complete raw tool output for maintainability metric derivation and validation.\n\n"
        "**Default benchmark repository:** [dotnet/roslyn](https://github.com/dotnet/roslyn)\n\n"
        "The notebook supports:\n"
        "- **Mode 1:** Clone from a Git repository URL\n"
        "- **Mode 2:** Analyze an already-cloned local repository path\n\n"
        "All deliverables are written to the configured `OUTPUT_DIR`.\n\n"
        "**Prerequisites:** .NET SDK 8+ and Roslynator CLI (installed automatically when missing)."
    ),
    md("## Section 1 — Install Dependencies\n\nInstall open-source Python packages, bootstrap the .NET SDK, and install Roslynator CLI."),
    code("!pip install -q pandas gitpython jupyter"),
    code(
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n\n"
        "os.environ.pop('PYTHONPATH', None)\n"
        "METRIC_ROOT = Path('.').resolve()\n"
        "TOOL_ROOT = METRIC_ROOT / 'tool'\n"
        "PROJECT_ROOT = METRIC_ROOT.parent.parent\n"
        "RUNTIMES_ROOT = PROJECT_ROOT / 'runtimes'\n"
        "if str(TOOL_ROOT) not in sys.path:\n"
        "    sys.path.insert(0, str(TOOL_ROOT))\n\n"
        "from run_roslynator_benchmark_impl import (\n"
        "    DOTNET_CHANNEL,\n"
        "    build_nesting_analyzer,\n"
        "    download_dotnet_sdk,\n"
        "    dotnet_env,\n"
        "    dotnet_executable,\n"
        "    install_roslynator,\n"
        "    run_command,\n"
        ")\n\n"
        "DOTNET_ROOT = (RUNTIMES_ROOT / 'dotnet-sdk').resolve()\n"
        "DOTNET_TOOLS_DIR = (RUNTIMES_ROOT / 'dotnet-tools').resolve()\n\n"
        "DOTNET_ROOT = download_dotnet_sdk(DOTNET_ROOT, channel=DOTNET_CHANNEL)\n"
        "ROSLYNATOR_PATH = install_roslynator(DOTNET_ROOT, DOTNET_TOOLS_DIR)\n"
        "ANALYZER_DLL = build_nesting_analyzer(DOTNET_ROOT)\n\n"
        "version_stdout, version_stderr, _ = run_command(\n"
        "    [str(ROSLYNATOR_PATH), '--version'],\n"
        "    env=dotnet_env(DOTNET_ROOT),\n"
        ")\n"
        "print((version_stdout or version_stderr).strip())\n"
        "print(f'.NET SDK: {dotnet_executable(DOTNET_ROOT)}')\n"
        "print(f'Roslynator: {ROSLYNATOR_PATH}')\n"
        "print(f'NestingDepthAnalyzer: {ANALYZER_DLL}')"
    ),
    md(
        "## Section 2 — Configuration\n\n"
        "Set execution mode, repository source, and output location.\n\n"
        "- Set `USE_GIT_URL = True` to clone from `REPO_URL`.\n"
        "- Set `USE_GIT_URL = False` to analyze `LOCAL_REPO_PATH` directly.\n"
        "- When cloning, use `IF_CLONE_EXISTS` to choose between reusing or re-cloning an existing local copy."
    ),
    code(
        "USE_GIT_URL = True\n\n"
        "REPO_URL = 'https://github.com/dotnet/roslyn.git'\n\n"
        "LOCAL_REPO_PATH = '/content/roslyn'\n\n"
        "OUTPUT_DIR = './outputs'\n\n"
        "IF_CLONE_EXISTS = 'reuse'\n\n"
        "CLONE_DEPTH = 1\n\n"
        "WORKSPACE_DIR = './workspace'\n\n"
        "STREAM_RAW_OUTPUT = True\n\n"
        "RAW_OUTPUT_PREVIEW_LINES = 150\n\n"
        "# Fast validation benchmark (100% predictable nesting outcomes):\n"
        "# USE_GIT_URL = False\n"
        "# LOCAL_REPO_PATH = './workspace/cs_nesting_benchmark'"
    ),
    md("## Utility Functions\n\nModular helpers for logging, repository setup, Roslynator execution, and nesting-depth extraction."),
    code(UTILS),
    md("## Section 3 — Repository Setup\n\nResolve the repository path based on configuration and initialize output directories."),
    code(
        "OUTPUT_PATH = Path(OUTPUT_DIR).resolve()\n"
        "WORKSPACE_PATH = Path(WORKSPACE_DIR).resolve()\n"
        "ERROR_LOG_PATH = OUTPUT_PATH / 'error_log.txt'\n\n"
        "ensure_output_dir(OUTPUT_PATH)\n"
        "logger = NotebookLogger(ERROR_LOG_PATH)\n\n"
        "try:\n"
        "    REPO_PATH = resolve_repository_path(\n"
        "        use_git_url=USE_GIT_URL,\n"
        "        repo_url=REPO_URL,\n"
        "        local_repo_path=LOCAL_REPO_PATH,\n"
        "        workspace_dir=WORKSPACE_PATH,\n"
        "        if_clone_exists=IF_CLONE_EXISTS,\n"
        "        logger=logger,\n"
        "        clone_depth=CLONE_DEPTH,\n"
        "    )\n"
        "except Exception as exc:\n"
        "    logger.error(f'Repository setup failed: {exc}')\n"
        "    raise\n\n"
        "logger.info(f'Repository ready at: {REPO_PATH}')"
    ),
    md("## Section 4 — Discover C# Files\n\nRecursively discover `.cs` files while excluding build and dependency directories."),
    code(
        "CS_FILES = discover_csharp_files(REPO_PATH)\n"
        "REPO_STATS = compute_repository_stats(REPO_PATH, CS_FILES)\n\n"
        "CSHARP_FILES_CSV = OUTPUT_PATH / 'csharp_files.csv'\n"
        "save_csharp_file_list(CS_FILES, REPO_PATH, CSHARP_FILES_CSV)\n\n"
        "print(f'Total C# Files Found: {len(CS_FILES)}')\n"
        "print(f'Repository Size (C# files only): {REPO_STATS[\"repository_size_bytes\"]:,} bytes')\n"
        "print(f'Total Directories (excluding filtered paths): {REPO_STATS[\"directory_count\"]:,}')\n"
        "print(f'Saved file list to: {CSHARP_FILES_CSV}')"
    ),
    md(
        "## Section 5 — Execute Roslynator\n\n"
        "Discover `.sln` and `.csproj` files and analyze each solution/project sequentially.\n\n"
        "Example equivalent command:\n\n"
        "```bash\n"
        "roslynator analyze <solution_or_project_path>\n"
        "```\n\n"
        "Raw stdout and stderr are preserved without suppression."
    ),
    code(
        "SOLUTIONS, PROJECTS = discover_solution_and_project_files(REPO_PATH)\n"
        "ANALYSIS_TARGETS = analyze_targets(SOLUTIONS, PROJECTS)\n"
        "ENV = dotnet_env(DOTNET_ROOT)\n\n"
        "if not CS_FILES:\n"
        "    logger.error('No C# files discovered; skipping Roslynator execution.')\n"
        "    ROSLYNATOR_RAW_TEXT = ''\n"
        "    ROSLYNATOR_XML_PATHS = []\n"
        "elif not ANALYSIS_TARGETS:\n"
        "    logger.error('No .sln or .csproj files discovered; Roslynator analysis skipped.')\n"
        "    ROSLYNATOR_RAW_TEXT = ''\n"
        "    ROSLYNATOR_XML_PATHS = []\n"
        "else:\n"
        "    logger.info(f'Roslynator targets: {len(ANALYSIS_TARGETS)}')\n"
        "    for target in ANALYSIS_TARGETS:\n"
        "        logger.info(f'  - {target}')\n"
        "    if STREAM_RAW_OUTPUT:\n"
        "        print('\\nStreaming Roslynator raw output...\\n')\n"
        "    ROSLYNATOR_RAW_TEXT, ROSLYNATOR_XML_PATHS = run_roslynator_suite(\n"
        "        roslynator=ROSLYNATOR_PATH,\n"
        "        targets=ANALYSIS_TARGETS,\n"
        "        xml_output=OUTPUT_PATH / 'roslynator_output.xml',\n"
        "        env=ENV,\n"
        "    )\n"
        "    if STREAM_RAW_OUTPUT:\n"
        "        print(ROSLYNATOR_RAW_TEXT)\n\n"
        "logger.info(f'Roslynator execution complete. Raw output size: {len(ROSLYNATOR_RAW_TEXT):,} characters')"
    ),
    md("## Section 6 — Raw Output Extraction\n\nPersist complete raw Roslynator text output, XML output, and a CSV representation of all diagnostics."),
    code(
        "import xml.etree.ElementTree as ET\n\n"
        "RAW_OUTPUT_PATH = OUTPUT_PATH / 'roslynator_raw_output.txt'\n"
        "XML_OUTPUT_PATH = OUTPUT_PATH / 'roslynator_output.xml'\n"
        "RESULTS_CSV_PATH = OUTPUT_PATH / 'roslynator_results.csv'\n\n"
        "RAW_OUTPUT_PATH.write_text(ROSLYNATOR_RAW_TEXT, encoding='utf-8')\n\n"
        "if ROSLYNATOR_XML_PATHS:\n"
        "    if len(ROSLYNATOR_XML_PATHS) == 1 and ROSLYNATOR_XML_PATHS[0] != XML_OUTPUT_PATH:\n"
        "        XML_OUTPUT_PATH.write_text(ROSLYNATOR_XML_PATHS[0].read_text(encoding='utf-8'), encoding='utf-8')\n"
        "    elif len(ROSLYNATOR_XML_PATHS) > 1:\n"
        "        combined_root = ET.Element('Roslynator')\n"
        "        code_analysis = ET.SubElement(combined_root, 'CodeAnalysis')\n"
        "        projects = ET.SubElement(code_analysis, 'Projects')\n"
        "        for xml_path in ROSLYNATOR_XML_PATHS:\n"
        "            parsed_root = ET.parse(xml_path).getroot()\n"
        "            for project_node in parsed_root.iter():\n"
        "                if str(project_node.tag).endswith('Project'):\n"
        "                    projects.append(project_node)\n"
        "        ET.ElementTree(combined_root).write(XML_OUTPUT_PATH, encoding='utf-8', xml_declaration=True)\n"
        "elif not XML_OUTPUT_PATH.exists():\n"
        "    XML_OUTPUT_PATH.write_text('<?xml version=\"1.0\" encoding=\"utf-8\"?><Roslynator/>', encoding='utf-8')\n\n"
        "xml_df = parse_roslynator_xml([XML_OUTPUT_PATH] if XML_OUTPUT_PATH.exists() else [])\n"
        "text_df = parse_roslynator_text(ROSLYNATOR_RAW_TEXT)\n"
        "ROSLYNATOR_RESULTS_DF = merge_roslynator_results(xml_df, text_df)\n"
        "ROSLYNATOR_RESULTS_DF.to_csv(RESULTS_CSV_PATH, index=False)\n\n"
        "logger.info(f'Saved raw output: {RAW_OUTPUT_PATH}')\n"
        "logger.info(f'Saved XML output: {XML_OUTPUT_PATH}')\n"
        "logger.info(f'Saved CSV results: {RESULTS_CSV_PATH}')\n"
        "logger.info(f'Total Roslynator findings: {len(ROSLYNATOR_RESULTS_DF)}')\n\n"
        "preview_raw_output(ROSLYNATOR_RAW_TEXT, RAW_OUTPUT_PREVIEW_LINES, RAW_OUTPUT_PATH)"
    ),
    md(
        "## Section 7 — Maintainability Nesting Depth Extraction\n\n"
        "Roslynator does not emit nesting depth directly. A custom Roslyn AST analyzer traverses control-flow "
        "syntax nodes and computes `max_nesting_depth` per method."
    ),
    code(
        "NESTING_RESULTS_CSV = OUTPUT_PATH / 'nesting_depth_results.csv'\n\n"
        "try:\n"
        "    NESTING_RESULTS_DF = run_nesting_analyzer(\n"
        "        dotnet_root=DOTNET_ROOT,\n"
        "        analyzer_dll=ANALYZER_DLL,\n"
        "        repo=REPO_PATH,\n"
        "        output_csv=NESTING_RESULTS_CSV,\n"
        "    )\n"
        "except Exception as exc:\n"
        "    logger.error(f'NestingDepthAnalyzer failed: {exc}')\n"
        "    NESTING_RESULTS_DF = pd.DataFrame(\n"
        "        columns=['file', 'class', 'method', 'start_line', 'end_line', 'max_nesting_depth', 'status']\n"
        "    )\n"
        "    NESTING_RESULTS_DF.to_csv(NESTING_RESULTS_CSV, index=False)\n\n"
        "logger.info(f'Saved nesting depth results: {NESTING_RESULTS_CSV}')\n"
        "logger.info(f'Method rows: {len(NESTING_RESULTS_DF)}')\n\n"
        "if not NESTING_RESULTS_DF.empty:\n"
        "    display(NESTING_RESULTS_DF.head(10))\n"
        "else:\n"
        "    print('No nesting depth results produced.')"
    ),
    md(
        "## Section 8 — Metric Computation\n\n"
        "Compute repository-level maintainability nesting depth metrics:\n\n"
        "- **Maintainability_Nesting_Depth** = `max(max_nesting_depth(method_i))`\n"
        "- **Average_Nesting_Depth** = `Σ max_nesting_depth(method_i) / total_methods`"
    ),
    code(
        "SUMMARY_DF = compute_summary(NESTING_RESULTS_DF)\n"
        "SUMMARY_CSV = OUTPUT_PATH / 'maintainability_nesting_depth_summary.csv'\n"
        "SUMMARY_DF.to_csv(SUMMARY_CSV, index=False)\n\n"
        "logger.info(f'Saved maintainability summary: {SUMMARY_CSV}')\n"
        "display(SUMMARY_DF)"
    ),
    md("## Section 9 — Summary Dashboard\n\nOverview of analysis coverage, Roslynator findings, and nesting-depth metrics."),
    code(
        "analyzed_methods = NESTING_RESULTS_DF[NESTING_RESULTS_DF.get('status', pd.Series(dtype=str)) == 'analyzed']\n"
        "max_depth = SUMMARY_DF.loc[\n"
        "    SUMMARY_DF['metric_name'] == 'Maintainability_Nesting_Depth', 'metric_value'\n"
        "].iloc[0]\n"
        "avg_depth = SUMMARY_DF.loc[\n"
        "    SUMMARY_DF['metric_name'] == 'Average_Nesting_Depth', 'metric_value'\n"
        "].iloc[0]\n"
        "files_failed = count_failed_methods(NESTING_RESULTS_DF)\n\n"
        "summary_df = pd.DataFrame(\n"
        "    [\n"
        "        {'Metric': 'Total C# Files', 'Value': len(CS_FILES)},\n"
        "        {'Metric': 'Total Methods', 'Value': len(NESTING_RESULTS_DF)},\n"
        "        {'Metric': 'Methods Analyzed', 'Value': len(analyzed_methods)},\n"
        "        {'Metric': 'Maximum Nesting Depth', 'Value': max_depth},\n"
        "        {'Metric': 'Average Nesting Depth', 'Value': avg_depth},\n"
        "        {'Metric': 'Files Failed', 'Value': files_failed},\n"
        "    ]\n"
        ")\n\n"
        "display(summary_df)\n\n"
        "deliverables = [\n"
        "    RAW_OUTPUT_PATH,\n"
        "    XML_OUTPUT_PATH,\n"
        "    RESULTS_CSV_PATH,\n"
        "    CSHARP_FILES_CSV,\n"
        "    NESTING_RESULTS_CSV,\n"
        "    SUMMARY_CSV,\n"
        "    ERROR_LOG_PATH,\n"
        "]\n\n"
        "print('\\nDeliverables:')\n"
        "for deliverable in deliverables:\n"
        "    status = 'OK' if deliverable.exists() else 'MISSING'\n"
        "    print(f'  [{status}] {deliverable}')"
    ),
    md("## Section 10 — Error Handling\n\nFailures encountered during cloning, validation, Roslynator execution, or AST analysis are appended to `outputs/error_log.txt`."),
    code(
        "if ERROR_LOG_PATH.exists() and ERROR_LOG_PATH.stat().st_size > 0:\n"
        "    print(ERROR_LOG_PATH.read_text(encoding='utf-8'))\n"
        "else:\n"
        "    print('No errors logged.')"
    ),
    md(
        "## Section 11 — Deliverables\n\n"
        "Upon successful completion, the following artifacts are available under `outputs/`:\n\n"
        "```text\n"
        "outputs/\n"
        "├── roslynator_raw_output.txt\n"
        "├── roslynator_output.xml\n"
        "├── roslynator_results.csv\n"
        "├── csharp_files.csv\n"
        "├── nesting_depth_results.csv\n"
        "├── maintainability_nesting_depth_summary.csv\n"
        "└── error_log.txt\n"
        "```\n\n"
        "The notebook is designed to run end-to-end in Jupyter Notebook and Google Colab without manual intervention."
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
