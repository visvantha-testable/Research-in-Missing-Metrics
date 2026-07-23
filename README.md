# Maintainability Nesting Depth

Production-ready pipelines for extracting **Maintainability Nesting Depth** raw tool output across five languages. Each language has a metric folder containing its notebook, benchmark repository, outputs, and tool scripts. Heavy toolchains are shared under `runtimes/`.

## Project Structure

```
Maintainability Nesting Depth/          (project root)
├── runtimes/                           # Shared toolchains
│   ├── dotnet-sdk/                     # .NET SDK 8 (C#)
│   ├── dotnet-tools/                   # Roslynator CLI (C#)
│   ├── jdk-21/                         # Portable JDK (Java / PMD)
│   ├── pmd-bin-7.0.0/                  # PMD distribution (Java)
│   ├── node_modules/                   # ESLint (JavaScript)
│   ├── cppcheck/                       # Cppcheck (C, portable/admin install)
│   ├── cloc/                           # cloc (C Comment-to-Code Ratio)
│   └── cache/                          # Downloaded archives
├── Python/
│   ├── Maintainability Nesting Depth/
│   │   ├── pylint_nesting_depth_extraction.ipynb
│   │   ├── requirements.txt
│   │   ├── tool/
│   │   ├── workspace/
│   │   └── outputs/
│   └── Code Smells Count/
│       ├── pylint_code_smells_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── Maintainability Rating (SQALE A–E)/
│       ├── radon_maintainability_rating_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── God Class / Long Method/
│       ├── pylint_god_class_long_method_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── Comment-to-Code Ratio/
│       ├── radon_comment_to_code_ratio_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── Parameter Count/
│       ├── lizard_parameter_count_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── File & Function Length/
│       ├── lizard_file_function_length_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── MC/DC Coverage/
│       ├── pymcdc_mcdc_coverage_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
├── C/
│   ├── Maintainability Nesting Depth/
│   │   ├── lizard_nesting_depth_extraction.ipynb
│   │   ├── requirements.txt
│   │   ├── tool/
│   │   ├── workspace/
│   │   └── outputs/
│   └── Code Smells Count/
│       ├── cppcheck_code_smells_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── Maintainability Rating (SQALE A-E)/
│       ├── lizard_maintainability_rating_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── God Class / Long Method/
│       ├── lizard_god_class_long_method_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── Comment-to-Code Ratio/
│       ├── cloc_comment_to_code_ratio_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── Parameter Count/
│       ├── lizard_parameter_count_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── File & Function Length/
│       ├── lizard_file_function_length_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
├── Java/
│   ├── Maintainability Nesting Depth/
│   │   ├── pmd_nesting_depth_extraction.ipynb
│   │   ├── requirements.txt
│   │   ├── tool/
│   │   ├── workspace/
│   │   └── outputs/
│   └── Code Smells Count/
│       ├── pmd_code_smells_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── Maintainability Rating (SQALE A-E)/
│       ├── pmd_maintainability_rating_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── God Class / Long Method/
│       ├── pmd_god_class_long_method_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── Comment-to-Code Ratio/
│       ├── pmd_comment_to_code_ratio_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── Parameter Count/
│       ├── lizard_parameter_count_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── File & Function Length/
│       ├── lizard_file_function_length_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── JaCoCo Coverage/
│       ├── jacoco_coverage_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── JaCoCo Path Analysis/
│       ├── jacoco_path_analysis_validation.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── JPF Path Analysis/
│       ├── jpf_path_analysis_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── Static DU Analysis/
│       ├── static_du_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── JaCoCo Static DU Validation/
│       ├── jacoco_static_du_validation.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
├── JavaScript/
│   ├── Maintainability Nesting Depth/
│   │   ├── eslint_nesting_depth_extraction.ipynb
│   │   ├── requirements.txt
│   │   ├── package.json
│   │   ├── tool/
│   │   ├── workspace/
│   │   └── outputs/
│   └── Code Smells Count/
│       ├── eslint_code_smells_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── Maintainability Rating (SQALE A-E)/
│       ├── eslint_maintainability_rating_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── God Class / Long Method/
│       ├── eslint_god_class_long_method_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── Comment-to-Code Ratio/
│       ├── eslint_comment_to_code_ratio_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── Parameter Count/
│       ├── eslint_parameter_count_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── File & Function Length/
│       ├── lizard_file_function_length_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
├── CSharp/
│   ├── Maintainability Nesting Depth/
│   │   ├── roslynator_nesting_depth_extraction.ipynb
│   │   ├── requirements.txt
│   │   ├── tool/
│   │   ├── workspace/
│   │   └── outputs/
│   └── Code Smells Count/
│       ├── stylecop_code_smells_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── Maintainability Rating (SQALE A-E)/
│       ├── stylecop_maintainability_rating_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── God Class / Long Method/
│       ├── roslynator_god_class_long_method_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── Parameter Count/
│       ├── roslynator_parameter_count_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
│   └── File & Function Length/
│       ├── lizard_file_function_length_extraction.ipynb
│       ├── requirements.txt
│       ├── tool/
│       ├── workspace/
│       └── outputs/
└── docs/
```

## Quick Start

### 1. Install Python dependencies (per language)

```powershell
pip install -r "Python/Maintainability Nesting Depth/requirements.txt"
pip install -r "Python/Comment-to-Code Ratio/requirements.txt"
pip install -r "Python/Parameter Count/requirements.txt"
pip install -r "Python/File & Function Length/requirements.txt"
pip install -r "Python/MC/DC Coverage/requirements.txt"
pip install -r "C/Maintainability Nesting Depth/requirements.txt"
pip install -r "C/Comment-to-Code Ratio/requirements.txt"
pip install -r "C/Parameter Count/requirements.txt"
pip install -r "C/File & Function Length/requirements.txt"
pip install -r "Java/Maintainability Nesting Depth/requirements.txt"
pip install -r "Java/Comment-to-Code Ratio/requirements.txt"
pip install -r "Java/Parameter Count/requirements.txt"
pip install -r "Java/File & Function Length/requirements.txt"
pip install -r "Java/JaCoCo Coverage/requirements.txt"
pip install -r "Java/JaCoCo Path Analysis/requirements.txt"
pip install -r "Java/JPF Path Analysis/requirements.txt"
pip install -r "Java/Static DU Analysis/requirements.txt"
pip install -r "Java/JaCoCo Static DU Validation/requirements.txt"
pip install -r "JavaScript/Maintainability Nesting Depth/requirements.txt"
pip install -r "JavaScript/Comment-to-Code Ratio/requirements.txt"
pip install -r "JavaScript/Parameter Count/requirements.txt"
pip install -r "JavaScript/File & Function Length/requirements.txt"
pip install -r "CSharp/Maintainability Nesting Depth/requirements.txt"
pip install -r "CSharp/God Class / Long Method/requirements.txt"
pip install -r "CSharp/Parameter Count/requirements.txt"
pip install -r "CSharp/File & Function Length/requirements.txt"
```

### 2. Run a benchmark (fast validation)

```powershell
python "Python/Maintainability Nesting Depth/tool/run_benchmark_execution.py"
python "Python/Code Smells Count/tool/run_code_smells_benchmark.py"
python "Python/Maintainability Rating (SQALE A–E)/tool/run_sqale_rating_benchmark.py"
python "Python/God Class / Long Method/tool/run_god_class_long_method_benchmark.py"
python "Python/Comment-to-Code Ratio/tool/run_comment_to_code_ratio_benchmark.py"
python "Python/Parameter Count/tool/run_parameter_count_benchmark.py"
python "Python/File & Function Length/tool/run_file_function_length_benchmark.py"
python "Python/MC/DC Coverage/tool/run_pymcdc_benchmark.py"
python "C/Maintainability Nesting Depth/tool/run_lizard_benchmark.py"
python "C/Code Smells Count/tool/run_code_smells_benchmark.py"
python "C/Maintainability Rating (SQALE A-E)/tool/run_sqale_rating_benchmark.py"
python "C/God Class / Long Method/tool/run_god_class_long_method_benchmark.py"
python "C/Comment-to-Code Ratio/tool/run_comment_to_code_ratio_benchmark.py"
python "C/Parameter Count/tool/run_parameter_count_benchmark.py"
python "C/File & Function Length/tool/run_file_function_length_benchmark.py"
python "Java/Maintainability Nesting Depth/tool/run_pmd_benchmark.py"
python "Java/Code Smells Count/tool/run_code_smells_benchmark.py"
python "Java/Maintainability Rating (SQALE A-E)/tool/run_sqale_rating_benchmark.py"
python "Java/God Class / Long Method/tool/run_god_class_long_method_benchmark.py"
python "Java/Comment-to-Code Ratio/tool/run_comment_to_code_ratio_benchmark.py"
python "Java/Parameter Count/tool/run_parameter_count_benchmark.py"
python "Java/File & Function Length/tool/run_file_function_length_benchmark.py"
python "Java/JaCoCo Coverage/tool/run_jacoco_benchmark.py"
python "Java/JaCoCo Path Analysis/tool/run_jacoco_path_analysis_benchmark.py"
python "Java/JPF Path Analysis/tool/run_jpf_benchmark.py"
python "Java/Static DU Analysis/tool/run_static_du_benchmark.py"
python "Java/JaCoCo Static DU Validation/tool/run_jacoco_static_du_validation_benchmark.py"
python "JavaScript/Maintainability Nesting Depth/tool/run_eslint_benchmark.py"
python "JavaScript/Code Smells Count/tool/run_code_smells_benchmark.py"
python "JavaScript/Maintainability Rating (SQALE A-E)/tool/run_sqale_rating_benchmark.py"
python "JavaScript/God Class / Long Method/tool/run_god_class_long_method_benchmark.py"
python "JavaScript/Comment-to-Code Ratio/tool/run_comment_to_code_ratio_benchmark.py"
python "JavaScript/Parameter Count/tool/run_parameter_count_benchmark.py"
python "JavaScript/File & Function Length/tool/run_file_function_length_benchmark.py"
python "CSharp/Maintainability Nesting Depth/tool/run_roslynator_benchmark.py"
python "CSharp/Code Smells Count/tool/run_code_smells_benchmark.py"
python "CSharp/Maintainability Rating (SQALE A-E)/tool/run_sqale_rating_benchmark.py"
python "CSharp/God Class / Long Method/tool/run_god_class_long_method_benchmark.py"
python "CSharp/Parameter Count/tool/run_parameter_count_benchmark.py"
python "CSharp/File & Function Length/tool/run_file_function_length_benchmark.py"
```

### 3. Run a notebook

Open the `.ipynb` inside the metric folder and run all cells. Set the working directory to that metric folder (e.g. `Python/Maintainability Nesting Depth/`).

For fast validation:

```python
USE_GIT_URL = False
LOCAL_REPO_PATH = "./workspace/<benchmark_repo>"
```

## Language Pipelines

| Language | Metric | Tool | Notebook | Default Repo |
|----------|--------|------|----------|--------------|
| Python | Nesting Depth | Pylint | `Python/Maintainability Nesting Depth/pylint_nesting_depth_extraction.ipynb` | django/django |
| Python | Code Smells Count | Pylint | `Python/Code Smells Count/pylint_code_smells_extraction.ipynb` | pallets/flask |
| Python | Maintainability Rating (SQALE A–E) | Radon | `Python/Maintainability Rating (SQALE A–E)/radon_maintainability_rating_extraction.ipynb` | pallets/flask |
| Python | God Class / Long Method | Pylint | `Python/God Class / Long Method/pylint_god_class_long_method_extraction.ipynb` | pallets/flask |
| Python | Comment-to-Code Ratio | Radon | `Python/Comment-to-Code Ratio/radon_comment_to_code_ratio_extraction.ipynb` | pallets/flask |
| Python | Parameter Count | Lizard | `Python/Parameter Count/lizard_parameter_count_extraction.ipynb` | pallets/flask |
| Python | File & Function Length | Lizard | `Python/File & Function Length/lizard_file_function_length_extraction.ipynb` | pallets/flask |
| Python | MC/DC Coverage | PyMCDC | `Python/MC/DC Coverage/pymcdc_mcdc_coverage_extraction.ipynb` | visvantha-testable/python-tool-testing-pymcdc |
| C | Nesting Depth | Lizard | `C/Maintainability Nesting Depth/lizard_nesting_depth_extraction.ipynb` | redis/redis |
| C | Code Smells Count | Cppcheck | `C/Code Smells Count/cppcheck_code_smells_extraction.ipynb` | redis/redis |
| C | Maintainability Rating (SQALE A-E) | Lizard | `C/Maintainability Rating (SQALE A-E)/lizard_maintainability_rating_extraction.ipynb` | redis/redis |
| C | God Class / Long Method | Lizard | `C/God Class / Long Method/lizard_god_class_long_method_extraction.ipynb` | redis/redis |
| C | Comment-to-Code Ratio | cloc | `C/Comment-to-Code Ratio/cloc_comment_to_code_ratio_extraction.ipynb` | redis/redis |
| C | Parameter Count | Lizard | `C/Parameter Count/lizard_parameter_count_extraction.ipynb` | redis/redis |
| C | File & Function Length | Lizard | `C/File & Function Length/lizard_file_function_length_extraction.ipynb` | redis/redis |
| Java | Nesting Depth | PMD | `Java/Maintainability Nesting Depth/pmd_nesting_depth_extraction.ipynb` | spring-framework |
| Java | Code Smells Count | PMD | `Java/Code Smells Count/pmd_code_smells_extraction.ipynb` | spring-framework |
| Java | Maintainability Rating (SQALE A-E) | PMD | `Java/Maintainability Rating (SQALE A-E)/pmd_maintainability_rating_extraction.ipynb` | spring-petclinic |
| Java | God Class / Long Method | PMD | `Java/God Class / Long Method/pmd_god_class_long_method_extraction.ipynb` | spring-petclinic |
| Java | Comment-to-Code Ratio | PMD | `Java/Comment-to-Code Ratio/pmd_comment_to_code_ratio_extraction.ipynb` | spring-petclinic |
| Java | Parameter Count | Lizard | `Java/Parameter Count/lizard_parameter_count_extraction.ipynb` | spring-petclinic |
| Java | File & Function Length | Lizard | `Java/File & Function Length/lizard_file_function_length_extraction.ipynb` | spring-petclinic |
| Java | JaCoCo Coverage | JaCoCo | `Java/JaCoCo Coverage/jacoco_coverage_extraction.ipynb` | visvantha-testable/java-tool-testing-jacoco |
| Java | JaCoCo Path Analysis | JaCoCo | `Java/JaCoCo Path Analysis/jacoco_path_analysis_validation.ipynb` | visvantha-testable/java-tool-testing-jacoco |
| Java | JPF Path Analysis | Java PathFinder | `Java/JPF Path Analysis/jpf_path_analysis_extraction.ipynb` | visvantha-testable/java-tool-testing-jacoco |
| Java | Static DU Analysis | Static DU | `Java/Static DU Analysis/static_du_extraction.ipynb` | visvantha-testable/java-tool-testing-static-du |
| Java | JaCoCo + Static DU Validation | JaCoCo + Static DU | `Java/JaCoCo Static DU Validation/jacoco_static_du_validation.ipynb` | visvantha-testable/java-tool-testing-def-use |
| JavaScript | Nesting Depth | ESLint | `JavaScript/Maintainability Nesting Depth/eslint_nesting_depth_extraction.ipynb` | facebook/react |
| JavaScript | Code Smells Count | ESLint | `JavaScript/Code Smells Count/eslint_code_smells_extraction.ipynb` | facebook/react |
| JavaScript | Maintainability Rating (SQALE A-E) | ESLint | `JavaScript/Maintainability Rating (SQALE A-E)/eslint_maintainability_rating_extraction.ipynb` | expressjs/express |
| JavaScript | God Class / Long Method | ESLint | `JavaScript/God Class / Long Method/eslint_god_class_long_method_extraction.ipynb` | expressjs/express |
| JavaScript | Comment-to-Code Ratio | ESLint | `JavaScript/Comment-to-Code Ratio/eslint_comment_to_code_ratio_extraction.ipynb` | expressjs/express |
| JavaScript | Parameter Count | ESLint | `JavaScript/Parameter Count/eslint_parameter_count_extraction.ipynb` | expressjs/express |
| JavaScript | File & Function Length | Lizard | `JavaScript/File & Function Length/lizard_file_function_length_extraction.ipynb` | expressjs/express |
| C# | Nesting Depth | Roslynator + Roslyn AST | `CSharp/Maintainability Nesting Depth/roslynator_nesting_depth_extraction.ipynb` | dotnet/roslyn |
| C# | Code Smells Count | StyleCop Analyzers | `CSharp/Code Smells Count/stylecop_code_smells_extraction.ipynb` | dotnet/aspnetcore |
| C# | Maintainability Rating (SQALE A-E) | StyleCop Analyzers | `CSharp/Maintainability Rating (SQALE A-E)/stylecop_maintainability_rating_extraction.ipynb` | dotnet-architecture/eShopOnWeb |
| C# | God Class / Long Method | Roslynator | `CSharp/God Class / Long Method/roslynator_god_class_long_method_extraction.ipynb` | dotnet-architecture/eShopOnWeb |
| C# | Parameter Count | Roslynator + Roslyn AST | `CSharp/Parameter Count/roslynator_parameter_count_extraction.ipynb` | dotnet/runtime |
| C# | File & Function Length | Lizard | `CSharp/File & Function Length/lizard_file_function_length_extraction.ipynb` | dotnet/runtime |

## Shared Runtimes

Toolchains in `runtimes/` are referenced via `../../runtimes/` from each metric folder. If missing, notebooks and benchmark scripts provision them on first run.

## Validated Benchmark Metrics

| Language | Max Nesting Depth | Status |
|----------|-------------------|--------|
| Python (Nesting Depth) | 10 (6 findings, 100% validation pass) | OK |
| Python (Code Smells) | 12 code smells | OK |
| Python (SQALE A–E) | MI 68.81, Rating C | OK |
| Python (God Class / Long Method) | Long 3, God 0, Combined 3 | OK |
| Python (Comment-to-Code Ratio) | Ratio 0.33, Percentage 33.33%, MI 77.28, Rating B | OK |
| Python (Parameter Count) | Max PARAM 8, Long Param List 1, Max Nesting 3 | OK |
| Python (File & Function Length) | Max Function Length 54 (NLOC), Max File Length 57, Long Functions 1 | OK |
| Python (MC/DC Coverage) | Total Decisions 14, Total Requirements 45, logic.py Decisions 3 / Requirements 11 | OK |
| C (Code Smells) | 13 code smells | OK |
| C (SQALE A-E) | MI 59.08, Rating C | OK |
| C (God Class / Long Method) | Long 1, God Module 1, Combined 2 | OK |
| C (Comment-to-Code Ratio) | Ratio 0.29, Percentage 28.57%, Code 21 | OK |
| C (Parameter Count) | Max PARAM 8, Long Param List 1, Max Nesting 3 | OK |
| C (File & Function Length) | Max Function Length 55 (NLOC), Max File Length 56 (NLOC), Long Functions 1 | OK |
| Java (Code Smells) | 7 code smells | OK |
| Java (SQALE A-E) | MI 33.03, Rating E, 7 code smells | OK |
| Java (God Class / Long Method) | Long 2+, God 1+, Combined 3+ (expected) | Pipeline ready |
| Java (Comment-to-Code Ratio) | Ratio 0.67, Percentage 66.67%, Code Smells 50 | OK |
| Java (Parameter Count) | Max PARAM 8, Long Param List 1, Max Nesting 3 | OK |
| Java (File & Function Length) | Max Function Length 55 (NLOC), Max File Length 58 (NLOC), Long Methods 1 | OK |
| Java (JaCoCo Coverage) | Classes 3, Line 100%, Instruction 98.46%, Branch 84.38%, Method 100% | OK |
| Java (JaCoCo Path Analysis) | Path metrics Supported 0 / Not Supported 10, XML nodes 163, keywords found 3 | OK |
| Java (JPF Path Analysis) | Classes executed 2, Path metrics Supported 9 / No Evidence 0, JPF metrics rows 26 | OK |
| Java (Static DU Analysis) | DU pairs 7, Data Flow metrics Supported 5 / Directly Emitted 5, definitions aggregate-only | OK |
| Java (JaCoCo + Static DU Validation) | Control Flow 10/10, Coverage Regression 6/6, Data Flow 16/16, 45 Java files | OK |
| C# (Code Smells) | 32 code smells | OK |
| C# (SQALE A-E) | Score 58.75, Rating C, 66 violations | OK |
| C# (God Class / Long Method) | Long 24, God 1, Combined 25, Code Smells 28 | OK |
| C# (Parameter Count) | Max PARAM 8 (derived), Long Param List 2, Diagnostics 4 | OK |
| C# (File & Function Length) | Max Function Length 56 (NLOC), Max File Length 60 (NLOC), Long Methods 1 | OK |
| JavaScript (Code Smells) | 10 code smells | OK |
| JavaScript (SQALE A-E) | Score 96.56, Rating A, 11 code smells | OK |
| JavaScript (God Class / Long Method) | Long 11, God 1, Combined 12 | OK |
| JavaScript (Comment-to-Code Ratio) | Ratio 0.47, Percentage 46.51%, Code Smells 2 | OK |
| JavaScript (Parameter Count) | Max PARAM 8 (derived), Long Param List 1 | OK |
| JavaScript (File & Function Length) | Max Function Length 55 (NLOC), Max File Length 56 (NLOC), Long Functions 1 | OK |
| C | 6 (avg 3.75) | OK |
| Java | 6 (avg 4.33) | OK |
| JavaScript | 6 (avg 6.0) | OK |
| C# | 6 (avg 3.0) | OK |
