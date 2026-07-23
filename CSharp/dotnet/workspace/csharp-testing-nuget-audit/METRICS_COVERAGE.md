# NuGet Audit — 8 SCA Metrics Coverage

## Verdict: **COVERED** ✅

| Metrics | 8/8 at 100/100 |
|---------|----------------|
| Tool | `dotnet list package --include-transitive --vulnerable --format json` |
| Owner repo | [NuGet/Home](https://github.com/NuGet/Home) |
| Platform runner | `src/NuGetAuditPlatform` (C#) |
| Output | `nuget_audit.json` |

## Trigger

```powershell
dotnet restore NuGetAudit.sln
dotnet run --project src/NuGetAuditPlatform -- trigger
```

## Verify

```powershell
dotnet run --project src/NuGetAuditPlatform -- verify --nuget-audit-json nuget_audit.json
dotnet test NuGetAudit.sln
```

## Expected sample metrics (clean subject)

| Field | Value |
|-------|-------|
| Direct dependencies | 2 |
| Transitive dependencies | 4 |
| Vulnerabilities | 0 |
| Outdated packages | 0 |
| All 8 L4 scores | 100 |

## C# implementation map

| Component | File |
|-----------|------|
| Trigger + verify CLI | `src/NuGetAuditPlatform/Program.cs` |
| dotnet collector | `src/NuGetAuditPlatform/Services/DotnetPackageCollector.cs` |
| 8-metric scoring | `src/NuGetAuditPlatform/Services/MetricsCalculator.cs` |
| Platform ratio fixup | `src/NuGetAuditPlatform/Services/PlatformFixup.cs` |
| Bundle export | `src/NuGetAuditPlatform/Services/PlatformExporter.cs` |
| JSON verification | `src/NuGetAuditPlatform/Services/NuGetAuditVerifier.cs` |
| Unit tests | `tests/NuGetAuditPlatform.Tests/` |
