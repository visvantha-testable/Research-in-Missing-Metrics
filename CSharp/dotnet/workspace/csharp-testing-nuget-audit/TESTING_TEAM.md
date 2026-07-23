# C# Testing — NuGet Audit (Testing Team Guide)

This repo is maintained for **100/100 PASS** on all 8 Dependency Risk (SCA) dashboard metrics.

## Quick verify (must pass before submission)

```powershell
git clone https://github.com/visvantha-testable/csharp-testing-nuget-audit.git
cd csharp-testing-nuget-audit
dotnet restore NuGetAudit.sln
dotnet run --project src/NuGetAuditPlatform -- trigger
.\verify_100_percent.ps1
```

**Do NOT use** raw `dotnet list package --vulnerable --format json` alone — it produces incomplete output (no scores, no supplemental data).

See **[TRIGGER.md](TRIGGER.md)** for platform trigger instructions.

Expected final lines:

```
PASS: all normalized scores and dashboard metrics are 100/100
PASS: nuget_audit.json has all 8 metrics covered=yes with 100/100 scores
TRIGGER COMPLETE: nuget_audit.json ready — all 8 metrics covered=yes 100/100
```

See **[METRICS_COVERAGE.md](METRICS_COVERAGE.md)** for how each metric is derived from raw data.

## Files the Testable platform reads (repository ROOT)

| File | Purpose |
|------|---------|
| **`nuget_audit.json`** | **PRIMARY** — single unified output with all raw data + 8 metrics (`covered: yes`) |
| `platform_metrics.json` | L4 classification → integer score `100` |
| `sca_metric_evidence.json` | **Proof** — per-metric raw parameters + formulas |
| `nuget_audit_report.json` | Raw NuGet audit JSON output |
| `nuget_audit_metrics.json` | Full metrics payload |
| `dashboard_metrics.json` | PASS/FAIL per classification |
| `metrics.json` | Alias of `platform_metrics.json` |
| `testable_dashboard.json` | Explicit dashboard rows |

Copies also live under `platform/` and `artifacts/training/`.

## C# project layout

| Path | Role |
|------|------|
| `src/NuGetAuditPlatform/` | Trigger, verify, metrics, export (C# only) |
| `tests/NuGetAuditPlatform.Tests/` | xUnit tests for platform fixup + metrics |
| `sample_subject/` | Clean C# subject with pinned NuGet packages |
| `config/golden_baseline_nuget_audit.json` | Baseline for continuous monitoring metric |

## Commands

```powershell
dotnet test NuGetAudit.sln
dotnet run --project src/NuGetAuditPlatform -- trigger
dotnet run --project src/NuGetAuditPlatform -- verify --nuget-audit-json nuget_audit.json
```
