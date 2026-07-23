# Testing Team Checklist — JaCoCo 33 Metrics (Java Repo)

Use this **100% Java** repo to re-verify **100/100** on all JaCoCo dashboard metrics.

## Quick verify

```bash
git clone https://github.com/visvantha-testable/java-tool-testing-jacoco.git
cd java-tool-testing-jacoco
mvn -q -pl jacoco-platform exec:java -Dexec.mainClass=com.testable.training.platform.JacocoTrigger
```

Expected final line:

```
TRIGGER COMPLETE: jacoco.json ready — all 33 JaCoCo metrics covered=yes 100/100
```

## Pass criteria

1. `jacoco.json` exists at repo root
2. `metrics_total` = 33, `metrics_covered` = 33
3. `metric_coverage_complete` = true
4. Every row in `metrics[]` has `covered: "yes"`, `score: 100`, `result: "PASS"`, `platform_ratio: 100`
5. `totals.line_percent` = 100, `totals.branch_percent` = 100

## Platform trigger

| Setting | Value |
|---------|-------|
| Command | `mvn -q -pl jacoco-platform exec:java -Dexec.mainClass=com.testable.training.platform.JacocoTrigger` |
| Output | `jacoco.json` |
| Scope | `sample_subject` only |
| Language | **Java 100%** (no Python wrapper) |

## Automated CI

GitHub Actions workflow `.github/workflows/ci.yml` runs on every push:

- `mvn clean test`
- JaCoCo platform trigger
- `jacoco.json` verification

## Metric breakdown

- **Path Coverage:** 10 metrics
- **Coverage Delta:** 6 metrics
- **All Definition Coverage:** 6 metrics
- **All Uses Coverage:** 10 metrics
- **Code Churn:** 1 metric

See [METRICS_COVERAGE.md](METRICS_COVERAGE.md) for the full table.
