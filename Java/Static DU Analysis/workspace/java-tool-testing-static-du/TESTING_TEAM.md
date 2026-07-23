# Testing Team — Static DU Re-Verification

Use this checklist to confirm **100/100** on all **5 Data Flow Testing** metrics.

## Prerequisites

- Java 17+
- Maven 3.9+
- Clone: `git clone https://github.com/visvantha-testable/java-tool-testing-static-du.git`

## Steps

1. **Build and test the subject**

   ```bash
   mvn clean test
   ```

   All JUnit tests in `sample_subject` must pass.

2. **Run the platform trigger** (do not use raw file scanning alone)

   ```bash
   mvn -q -pl static-du-platform exec:java -Dexec.mainClass=com.testable.training.platform.StaticDuTrigger
   ```

3. **Verify output**

   ```bash
   mvn -q -pl static-du-platform exec:java -Dexec.mainClass=com.testable.training.platform.StaticDuJsonVerifierCli
   ```

   Expected: `PASS: static_du.json has all 5 Static DU metrics covered=yes with 100/100 score`

4. **Inspect `static_du.json`**

   | Field | Expected |
   |-------|----------|
   | `tool` | `Static DU` |
   | `metrics_total` | `5` |
   | `metrics_covered` | `5` |
   | `metric_coverage_complete` | `true` |

5. **Confirm all 5 metric rows**

   | Metric | KPI | Score |
   |--------|-----|-------|
   | Variable Definition Detection | All-Defs Coverage % | 100 |
   | Definition-Use Mapping | Data Path Correlation | 100 |
   | Coverage Measurement | DU-Path Validation | 100 |
   | Uncovered Definition Detection | Dead Data Identification | 100 |
   | Variable Use Detection | All-Uses Coverage % | 100 |

6. **Confirm raw Static DU evidence**

   In `supplemental_raw_data.static_du_summary`:

   - `definitions_covered` = `definitions_total`
   - `du_pairs_covered` = `du_pairs_total`
   - `uncovered_definitions` = `0`
   - `all_defs_percent` = `100`
   - `all_uses_percent` = `100`

## CI

GitHub Actions runs the same trigger on every push to `master`. Check the Actions tab for green build status.
