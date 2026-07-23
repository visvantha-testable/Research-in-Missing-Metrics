# JaCoCo Training Repository — 33 Metrics at 100/100 (Java)

Single **Java/Maven** reference repository for **JaCoCo** code coverage training and Testable dashboard certification.

**Repository:** https://github.com/visvantha-testable/java-tool-testing-jacoco

## What this repo proves

| Category | Classification | Metrics |
|----------|----------------|---------|
| Control Flow Testing | Path Coverage | 10 |
| Test Regression/Coverage Analysis | Coverage Delta | 6 |
| Data Flow Testing | All Definition Coverage | 6 |
| Data Flow Testing | All Uses Coverage | 10 |
| Development Process Analysis | Code Churn | 1 |
| **Total** | | **33** |

All 33 metrics score **100/100** with `covered: yes`.

## Platform trigger (required)

**Do not run raw JaCoCo/Maven alone on the platform.** Use the Java wrapper:

```bash
mvn -q -pl jacoco-platform exec:java -Dexec.mainClass=com.testable.training.platform.JacocoTrigger
```

Or use the helper script:

```bash
./run_trigger.sh        # Linux/macOS
.\run_trigger.ps1       # Windows
run_trigger.bat         # Windows CMD
```

This produces `jacoco.json` at the repository root — the unified output Testable expects.

## Local verification

```bash
mvn clean test
mvn -q -pl jacoco-platform exec:java -Dexec.mainClass=com.testable.training.platform.JacocoTrigger
```

Requires **Java 17+** and **Maven 3.9+**.

## Structure

```
pom.xml                  # Maven parent (100% Java project)
sample_subject/          # JaCoCo training subject + JUnit 5 tests
jacoco-platform/         # Java platform trigger + 33-metric engine
  src/main/java/com/testable/training/platform/
artifacts/training/      # jacoco.xml, baseline, static DU, churn evidence
config/                  # metric_coverage.json, platform_trigger.json
.github/workflows/ci.yml # Build + trigger + verify on push
```

## Tool stack

- **Official JaCoCo** — [github.com/jacoco/jacoco](https://github.com/jacoco/jacoco) release **0.8.15**
- **org.jacoco.core** — official Core API (`ExecFileLoader`, `Analyzer`, `CoverageBuilder`)
- **jacoco-maven-plugin** — LINE, BRANCH, INSTRUCTION counters from `jacoco.exec` + `jacoco.xml`
- **Static DU (Java)** — definition-use mapping for All-Defs / All-Uses metrics
- **Baseline delta** — Coverage Delta via `baseline_jacoco.xml`
- **Churn config** — Code Churn regression focus mapping

See [vendor/jacoco/OFFICIAL_SOURCE.md](vendor/jacoco/OFFICIAL_SOURCE.md) for official source linkage.

## Output files

| File | Purpose |
|------|---------|
| `jacoco.json` | Primary platform output (33 metrics) |
| `jacoco_metrics.json` | Full metric payload + raw parameters |
| `platform_metrics.json` | Flat score map for dashboard |
| `dashboard_metrics.json` | Dashboard export |
| `testable_dashboard.json` | Testable-compatible summary |

## Testing team

See [TESTING_TEAM.md](TESTING_TEAM.md) and [TRIGGER.md](TRIGGER.md).
