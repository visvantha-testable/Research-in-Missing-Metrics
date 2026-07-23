# Static DU Training Repository — 5 Metrics at 100/100 (Java)

Single **Java/Maven** reference repository for **Static DU** data flow testing training and Testable dashboard certification.

**Repository:** https://github.com/visvantha-testable/java-tool-testing-static-du

## What this repo proves

| # | Classification | Metric | KPI |
|---|----------------|--------|-----|
| 1 | All Definition Coverage | Variable Definition Detection | All-Defs Coverage % |
| 2 | All Definition Coverage | Definition-Use Mapping | Data Path Correlation |
| 3 | All Definition Coverage | Coverage Measurement | DU-Path Validation |
| 4 | All Definition Coverage | Uncovered Definition Detection | Dead Data Identification |
| 5 | All Uses Coverage | Variable Use Detection | All-Uses Coverage % |

All **5 metrics** score **100/100** with `covered: yes`.

## Platform trigger (required)

**Do not run raw source scanning alone on the platform.** Use the Java wrapper:

```bash
mvn -q -pl static-du-platform exec:java -Dexec.mainClass=com.testable.training.platform.StaticDuTrigger
```

Or use the helper script:

```bash
./run_trigger.sh        # Linux/macOS
.\run_trigger.ps1       # Windows
run_trigger.bat         # Windows CMD
```

This produces `static_du.json` at the repository root — the unified output Testable expects.

## Local verification

```bash
mvn clean test
mvn -q -pl static-du-platform exec:java -Dexec.mainClass=com.testable.training.platform.StaticDuTrigger
```

Requires **Java 17+** and **Maven 3.9+**.

## Structure

```
pom.xml                  # Maven parent (100% Java project)
sample_subject/          # Data flow training subject + JUnit 5 tests
static-du-platform/      # Java platform trigger + 5-metric engine
artifacts/training/      # static_du_summary.json, du_path_correlation.json
config/                  # metric_coverage.json, platform_trigger.json
.github/workflows/ci.yml # Build + trigger + verify on push
```

## Tool stack

- **Static DU (Java)** — definition-use analysis on `sample_subject/src/main/java`
- **All-Defs Coverage** — variable definition detection and coverage %
- **Data Path Correlation** — definition-to-use mapping across DU paths
- **DU-Path Validation** — percentage of DU pairs exercised by tests
- **Dead Data Identification** — uncovered/zombie variable detection
- **All-Uses Coverage** — computational and predicate use detection

## Output files

| File | Purpose |
|------|---------|
| `static_du.json` | Primary platform output (5 metrics) |
| `static_du_metrics.json` | Full metric payload + raw parameters |
| `platform_metrics.json` | Flat score map for dashboard |
| `dashboard_metrics.json` | Dashboard export |
| `testable_dashboard.json` | Testable-compatible summary |

## Testing team

See [TESTING_TEAM.md](TESTING_TEAM.md) for re-verification steps and [TRIGGER.md](TRIGGER.md) for platform execution details.
