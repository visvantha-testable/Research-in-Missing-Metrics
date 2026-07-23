using NuGetAuditPlatform.Services;

namespace NuGetAuditPlatform;

public static class Program
{
    public static int Main(string[] args)
    {
        var repoRoot = FindRepoRoot();
        var command = args.Length > 0 ? args[0].ToLowerInvariant() : "trigger";
        var skipVerify = args.Contains("--skip-verify", StringComparer.OrdinalIgnoreCase);

        return command switch
        {
            "trigger" => RunTrigger(repoRoot, skipVerify),
            "verify" => RunVerify(repoRoot, args.Skip(1).ToArray()),
            "coverage" => RunCoverage(repoRoot, args.Skip(1).ToArray()),
            _ => PrintUsage(),
        };
    }

    private static int RunTrigger(string repoRoot, bool skipVerify)
    {
        Console.WriteLine("Starting NuGet audit platform trigger (8 SCA metrics)");

        var projectRelative = Path.Combine("sample_subject", "SampleSubject.csproj");
        var projectFull = Path.Combine(repoRoot, projectRelative);
        if (!File.Exists(projectFull))
        {
            Console.Error.WriteLine($"Missing sample project: {projectFull}");
            return 1;
        }

        var baselineRelative = Path.Combine("config", "golden_baseline_nuget_audit.json");
        var artifacts = DotnetPackageCollector.Collect(repoRoot, projectRelative, baselineRelative);

        var metrics = MetricsCalculator.Compute(
            File.ReadAllText(artifacts.AuditReport),
            File.ReadAllText(artifacts.DependencyTree),
            File.ReadAllText(artifacts.Outdated),
            File.ReadAllText(artifacts.Licenses),
            File.ReadAllText(artifacts.Baseline));

        Directory.CreateDirectory(Path.Combine(repoRoot, "reports"));
        var dashboard = PlatformExporter.ExportDashboardPayload(metrics);
        File.WriteAllText(
            Path.Combine(repoRoot, "reports", "sample_dashboard.json"),
            dashboard.ToJsonString(new System.Text.Json.JsonSerializerOptions { WriteIndented = true }));
        JsonSerializerDump(metrics, Path.Combine(repoRoot, "reports", "sample_metrics.json"));
        PlatformExporter.ExportBundle(repoRoot, metrics, artifacts);

        if (skipVerify)
        {
            return 0;
        }

        var configPath = Path.Combine(repoRoot, "config", "metric_coverage.json");
        var exit = MetricCoverageValidator.ValidateFromMetricsJson(
            configPath,
            Path.Combine(repoRoot, "nuget_audit_metrics.json"));
        if (exit != 0)
        {
            return exit;
        }

        exit = NuGetAuditVerifier.VerifyHundredPercent(
            Path.Combine(repoRoot, "nuget_audit_metrics.json"),
            Path.Combine(repoRoot, "dashboard_metrics.json"));
        if (exit != 0)
        {
            return exit;
        }

        exit = NuGetAuditVerifier.Verify(Path.Combine(repoRoot, "nuget_audit.json"));
        if (exit != 0)
        {
            return exit;
        }

        Console.WriteLine();
        Console.WriteLine("TRIGGER COMPLETE: nuget_audit.json ready — all 8 metrics covered=yes 100/100");
        return 0;
    }

    private static int RunVerify(string repoRoot, string[] args)
    {
        var path = Path.Combine(repoRoot, "nuget_audit.json");
        for (var i = 0; i < args.Length - 1; i++)
        {
            if (args[i] == "--nuget-audit-json")
            {
                path = Path.IsPathRooted(args[i + 1]) ? args[i + 1] : Path.Combine(repoRoot, args[i + 1]);
            }
        }

        return NuGetAuditVerifier.Verify(path);
    }

    private static int RunCoverage(string repoRoot, string[] args)
    {
        var configPath = Path.Combine(repoRoot, "config", "metric_coverage.json");
        var metricsPath = Path.Combine(repoRoot, "nuget_audit_metrics.json");
        for (var i = 0; i < args.Length - 1; i++)
        {
            if (args[i] == "--metrics-json")
            {
                metricsPath = Path.IsPathRooted(args[i + 1]) ? args[i + 1] : Path.Combine(repoRoot, args[i + 1]);
            }
        }

        if (!File.Exists(metricsPath))
        {
            Console.Error.WriteLine($"Missing metrics json: {metricsPath}");
            return 1;
        }

        return MetricCoverageValidator.ValidateFromMetricsJson(configPath, metricsPath);
    }

    private static int PrintUsage()
    {
        Console.WriteLine("Usage:");
        Console.WriteLine("  dotnet run --project src/NuGetAuditPlatform -- trigger [--skip-verify]");
        Console.WriteLine("  dotnet run --project src/NuGetAuditPlatform -- verify [--nuget-audit-json nuget_audit.json]");
        Console.WriteLine("  dotnet run --project src/NuGetAuditPlatform -- coverage [--metrics-json nuget_audit_metrics.json]");
        return 1;
    }

    private static string FindRepoRoot()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null)
        {
            if (File.Exists(Path.Combine(dir.FullName, "NuGetAudit.sln"))
                || File.Exists(Path.Combine(dir.FullName, "global.json")))
            {
                return dir.FullName;
            }

            dir = dir.Parent;
        }

        return Directory.GetCurrentDirectory();
    }

    private static void JsonSerializerDump(object value, string path)
    {
        File.WriteAllText(path, System.Text.Json.JsonSerializer.Serialize(value, new System.Text.Json.JsonSerializerOptions { WriteIndented = true }));
    }
}
