# C# Testing NuGet Audit

**Security White-box Testing → Dependency Risk (SCA) → 8 metrics at 100/100**

Training repo using **`dotnet list package --include-transitive --vulnerable --format json`** (NuGet audit) on a C# sample project aligned with the official **[NuGet/Home](https://github.com/NuGet/Home)** audit specifications.

## Tool + Metric

| Field | Value |
|-------|-------|
| **Tool** | `dotnet list package --include-transitive --vulnerable --format json` |
| **Owner repo** | [NuGet/Home](https://github.com/NuGet/Home) |
| **Strategy** | Security White-box Testing → Dependency Risk (SCA) |
| **Training subject** | `sample_subject/SampleSubject.csproj` (clean pinned NuGet deps — **100/100**) |
| **Platform runner** | `src/NuGetAuditPlatform` (C# only) |
| **GitHub repo** | https://github.com/visvantha-testable/csharp-testing-nuget-audit |

## 8 Dashboard Metrics

| L4 Classification | L5 Metric |
|-------------------|-----------|
| Transitive Dependency Analysis | Hidden Relationship Mapping |
| License Compliance Testing | Legal Risk Validation |
| Supply Chain Security Analysis | Trust Integrity Verification |
| Dependency Health Monitoring | Community Vitality Tracking |
| Risk Prioritization | Mitigation Effort Ranking |
| Continuous Dependency Monitoring | Real-Time Alerting |
| Vulnerability Dependency Detection | Known CVE Count |
| Outdated Dependency Detection | Version Lag Assessment |

## Platform trigger (REQUIRED)

```powershell
dotnet run --project src/NuGetAuditPlatform -- trigger
```

## Primary output

**`nuget_audit.json`** — unified platform file with all 8 metrics at 100/100.

Verify:

```powershell
dotnet run --project src/NuGetAuditPlatform -- verify --nuget-audit-json nuget_audit.json
```

Expected: **`PASS: nuget_audit.json has all 8 metrics covered=yes with 100/100 scores`**

## Quick start

```powershell
dotnet restore NuGetAudit.sln
dotnet run --project src/NuGetAuditPlatform -- trigger
```

## Collector command

```bash
dotnet list sample_subject/SampleSubject.csproj package --include-transitive --vulnerable --format json --output-version 1
```

See **[METRICS_COVERAGE.md](METRICS_COVERAGE.md)** for full validation details.
