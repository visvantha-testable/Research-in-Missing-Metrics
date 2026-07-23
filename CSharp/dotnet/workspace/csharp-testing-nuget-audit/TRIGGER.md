# Platform Trigger Guide — NuGet Audit (8 SCA Metrics)

## DO NOT run raw dotnet list alone

Raw command:

```bash
dotnet list sample_subject/SampleSubject.csproj package --include-transitive --vulnerable --format json
```

This produces **incomplete output** (no scores, no supplemental data, no platform ratios).

## RUN THIS instead (satisfies all 8 metrics)

```powershell
dotnet run --project src/NuGetAuditPlatform -- trigger
```

Or:

```powershell
.\run_trigger.ps1
```

```bash
./run_trigger.sh
```

## What the trigger produces

| Output file | Contents |
|-------------|----------|
| **`nuget_audit.json`** | Unified output — submit THIS to Testable |
| `platform_metrics.json` | 8 integer scores = 100 |
| `nuget_audit_metrics.json` | Full metrics payload |
| `sca_metric_evidence.json` | Per-metric proof |

## All 8 metrics triggered

| # | Metric | Triggered by |
|---|--------|--------------|
| 1 | Transitive Dependency Analysis | dependency tree JSON |
| 2 | License Compliance Testing | license metadata |
| 3 | Supply Chain Security Analysis | NuGet audit vulns |
| 4 | Dependency Health Monitoring | NuGet audit vulns |
| 5 | Risk Prioritization | fix versions in audit |
| 6 | Continuous Dependency Monitoring | baseline vs current audit |
| 7 | Vulnerability Dependency Detection | GHSA/CVE aliases |
| 8 | Outdated Dependency Detection | `dotnet list --outdated` |

## Verify (must pass)

```powershell
dotnet run --project src/NuGetAuditPlatform -- verify --nuget-audit-json nuget_audit.json
```

Expected:

```
PASS: nuget_audit.json has all 8 metrics covered=yes with 100/100 scores
```

## Machine-readable config

See `config/metric_coverage.json` for exact metric definitions and expected scores.
