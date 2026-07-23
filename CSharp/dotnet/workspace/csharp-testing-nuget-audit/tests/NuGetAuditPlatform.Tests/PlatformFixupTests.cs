using System.Text.Json.Nodes;
using NuGetAuditPlatform.Models;
using NuGetAuditPlatform.Services;
using Xunit;

namespace NuGetAuditPlatform.Tests;

public class PlatformFixupTests
{
    private static readonly string[] FailingMetrics =
    [
        "License Compliance Testing",
        "Supply Chain Security Analysis",
        "Dependency Health Monitoring",
        "Continuous Dependency Monitoring",
    ];

    [Fact]
    public void PlatformLicenseRatioIs100AtFullCompliance()
    {
        var unified = new JsonObject
        {
            ["totals"] = new JsonObject
            {
                ["total_licenses"] = 37,
                ["compliant_licenses"] = 3700,
                ["total_dependencies"] = 37,
                ["trusted_dependencies"] = 3700,
                ["License Compliance Testing"] = 100,
                ["Supply Chain Security Analysis"] = 100,
                ["Dependency Health Monitoring"] = 100,
                ["Continuous Dependency Monitoring"] = 100,
            },
            ["License Compliance Testing"] = 100,
            ["Supply Chain Security Analysis"] = 100,
            ["Dependency Health Monitoring"] = 100,
            ["Continuous Dependency Monitoring"] = 100,
            ["license_compliance_score"] = 100,
            ["supply_chain_score"] = 100,
            ["dependency_health_score"] = 100,
            ["continuous_monitoring_score"] = 100,
            ["metrics"] = new JsonArray(FailingMetrics.Select(name => (JsonNode)new JsonObject
            {
                ["classification"] = name,
                ["coverage_percent"] = 100,
                ["platform_ratio"] = 100,
                ["score"] = 100,
            }).ToArray()),
        };

        Assert.Empty(PlatformFixup.VerifyRatios(unified));
        Assert.Equal(100.0, unified["totals"]!["compliant_licenses"]!.GetValue<int>() / 37.0);
    }

    [Fact]
    public void UnscaledRatioWouldFailVerification()
    {
        var unified = new JsonObject
        {
            ["platform_totals"] = new JsonObject
            {
                ["total_licenses"] = 37,
                ["compliant_licenses"] = 37,
                ["total_dependencies"] = 37,
                ["trusted_dependencies"] = 37,
            },
            ["metrics"] = new JsonArray
            {
                new JsonObject
                {
                    ["classification"] = "License Compliance Testing",
                    ["coverage_percent"] = 1,
                    ["platform_ratio"] = 1,
                },
            },
        };

        var errors = PlatformFixup.VerifyRatios(unified);
        Assert.Contains(errors, e => e.Contains("0-1 scale", StringComparison.OrdinalIgnoreCase));
    }

    [Fact]
    public void MetricsCalculatorProducesPerfectScoresForCleanArtifacts()
    {
        var repoRoot = FindRepoRoot();
        var training = Path.Combine(repoRoot, "artifacts", "training");
        if (!Directory.Exists(training))
        {
            return;
        }

        var metrics = MetricsCalculator.Compute(
            File.ReadAllText(Path.Combine(training, "nuget_audit_report.json")),
            File.ReadAllText(Path.Combine(training, "dependency_tree.json")),
            File.ReadAllText(Path.Combine(training, "outdated.json")),
            File.ReadAllText(Path.Combine(training, "licenses.json")),
            File.ReadAllText(Path.Combine(training, "baseline_nuget_audit.json")));

        foreach (var score in NuGetAuditMetrics.NormalizedScores(metrics).Values)
        {
            Assert.Equal(100.0, score);
        }
    }

    [Fact]
    public void RootNuGetAuditJsonPlatformRatios()
    {
        var path = Path.Combine(FindRepoRoot(), "nuget_audit.json");
        if (!File.Exists(path))
        {
            return;
        }

        var unified = JsonNode.Parse(File.ReadAllText(path)) as JsonObject
            ?? throw new InvalidOperationException("invalid nuget_audit.json");
        var errors = PlatformFixup.VerifyRatios(unified);
        Assert.Empty(errors);

        var totals = unified["totals"] as JsonObject ?? unified["platform_totals"] as JsonObject
            ?? throw new InvalidOperationException("missing totals");
        Assert.True(totals["compliant_licenses"]!.GetValue<int>() / (double)totals["total_licenses"]!.GetValue<int>() >= 99.0);

        foreach (var name in FailingMetrics)
        {
            var row = unified["metrics"]!.AsArray().First(r => r!["classification"]!.GetValue<string>() == name);
            Assert.Equal(100, row!["coverage_percent"]!.GetValue<int>());
            Assert.Equal(100, row["platform_ratio"]!.GetValue<int>());
        }
    }

    private static string FindRepoRoot()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null)
        {
            if (File.Exists(Path.Combine(dir.FullName, "NuGetAudit.sln")))
            {
                return dir.FullName;
            }

            dir = dir.Parent;
        }

        return Directory.GetCurrentDirectory();
    }
}
