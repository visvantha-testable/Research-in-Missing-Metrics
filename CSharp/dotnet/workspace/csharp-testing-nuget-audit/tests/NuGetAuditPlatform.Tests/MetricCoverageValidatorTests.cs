using NuGetAuditPlatform.Services;
using Xunit;

namespace NuGetAuditPlatform.Tests;

public class MetricCoverageValidatorTests
{
    [Fact]
    public void ValidatesEightMetricsFromGeneratedMetricsJson()
    {
        var repoRoot = FindRepoRoot();
        var metricsPath = Path.Combine(repoRoot, "nuget_audit_metrics.json");
        if (!File.Exists(metricsPath))
        {
            return;
        }

        var exit = MetricCoverageValidator.ValidateFromMetricsJson(
            Path.Combine(repoRoot, "config", "metric_coverage.json"),
            metricsPath);

        Assert.Equal(0, exit);
    }

    [Fact]
    public void ValidatesEightMetricsFromTrainingArtifacts()
    {
        var repoRoot = FindRepoRoot();
        var training = Path.Combine(repoRoot, "artifacts", "training");
        if (!Directory.Exists(training))
        {
            return;
        }

        var artifacts = new NuGetAuditPlatform.Models.ArtifactPaths(
            Path.Combine(training, "nuget_audit_report.json"),
            Path.Combine(training, "dependency_tree.json"),
            Path.Combine(training, "outdated.json"),
            Path.Combine(training, "licenses.json"),
            Path.Combine(training, "baseline_nuget_audit.json"));

        var exit = MetricCoverageValidator.ValidateFromArtifacts(
            Path.Combine(repoRoot, "config", "metric_coverage.json"),
            artifacts);

        Assert.Equal(0, exit);
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
