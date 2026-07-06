# Nesting Depth Benchmark Repository

Deterministic benchmark for **Maintainability — Nesting Depth** metric validation using Pylint raw output.

## Purpose

This repository produces **100% predictable** Pylint `R1702` (`too-many-nested-blocks`) findings so you can verify that:

1. Raw Pylint text output is captured correctly
2. JSON/CSV extraction is accurate
3. `detected_nesting_depth` values parse correctly from messages like `Too many nested blocks (6/5)`

## Test Cases

| File | Expected R1702 | Detected Depth | Notes |
|------|----------------|----------------|-------|
| `cases/clean_flat.py` | No | — | Flat control flow baseline |
| `cases/depth_5_at_limit.py` | No | — | Exactly at default limit (5 blocks) |
| `cases/depth_6_violation.py` | Yes | 6 | Minimal violation |
| `cases/depth_7_violation.py` | Yes | 7 | |
| `cases/depth_8_violation.py` | Yes | 8 | |
| `cases/mixed_loop_nesting.py` | Yes | 10 | Loop + branch nesting |
| `cases/multi_violation_file.py` | Yes × 2 | 6, 8 | Multiple violations in one file |

## Expected Outcome

- **8** Python files
+ **7** Python files
- **6** nesting-depth findings (`R1702`)
- **2** files with zero nesting violations

See `expected_outcomes.json` for machine-readable validation targets.

## Run

```bash
python run_benchmark_execution.py
```

Outputs are written to `./outputs/` with a validation report in `outputs/benchmark_validation.json`.
