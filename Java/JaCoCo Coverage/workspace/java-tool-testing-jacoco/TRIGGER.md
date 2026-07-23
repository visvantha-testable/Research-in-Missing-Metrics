# Platform Trigger — JaCoCo (Java)

## Command

```bash
mvn -q -pl jacoco-platform exec:java -Dexec.mainClass=com.testable.training.platform.JacocoTrigger
```

Helper scripts:

```bash
./run_trigger.sh
.\run_trigger.ps1
run_trigger.bat
```

## Configuration

See `config/platform_trigger.json`.

## Pipeline steps (Java)

1. `ArtifactCollector` — Maven test + JaCoCo report (or Java XML synthesis fallback)
2. `PlatformExporter` — derive 33 metrics, write `jacoco.json`
3. `PlatformFixup` — scale platform ratios to 0-100
4. `MetricCoverageValidator` + `JacocoJsonVerifier` — confirm 100/100

## Primary output

`jacoco.json` at repository root.

## Important

The platform must **not** scan the entire repo with raw JaCoCo. The Java wrapper limits analysis to `sample_subject` and produces the unified metric JSON with all required fields.
