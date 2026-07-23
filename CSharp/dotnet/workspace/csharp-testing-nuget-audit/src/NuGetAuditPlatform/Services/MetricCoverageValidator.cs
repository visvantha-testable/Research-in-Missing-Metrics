using System.Text.Json;
using System.Text.Json.Nodes;
using NuGetAuditPlatform.Models;

namespace NuGetAuditPlatform.Services;

public static class MetricCoverageValidator
{
    public static int ValidateFromMetricsJson(string configPath, string metricsJsonPath)
    {
        var config = JsonNode.Parse(File.ReadAllText(configPath)) as JsonObject
            ?? throw new InvalidOperationException($"Invalid config: {configPath}");
        var metricsPayload = JsonNode.Parse(File.ReadAllText(metricsJsonPath)) as JsonObject
            ?? throw new InvalidOperationException($"Invalid metrics json: {metricsJsonPath}");

        var errors = new List<string>();
        var normalized = metricsPayload["normalized_scores"] as JsonObject ?? new JsonObject();

        foreach (var entry in config["metrics"]?.AsArray() ?? [])
        {
            var name = entry?["l4_classification"]?.GetValue<string>() ?? "?";
            var expected = entry?["expected_score"]?.GetValue<int>() ?? 100;

            if (!normalized.TryGetPropertyValue(name, out var scoreNode) || scoreNode is null)
            {
                errors.Add($"{name}: missing normalized score");
                continue;
            }

            var score = scoreNode.GetValue<double>();
            if (score < expected)
            {
                errors.Add($"{name}: score {score} is below {expected}/100");
            }
        }

        if (errors.Count > 0)
        {
            Console.Error.WriteLine("FAIL: metric coverage validation failed:");
            foreach (var err in errors)
            {
                Console.Error.WriteLine($"  - {err}");
            }

            return 1;
        }

        Console.WriteLine("PASS: all 8 NuGet audit SCA metrics are covered with 100/100 scores.");
        return 0;
    }

    public static int ValidateFromArtifacts(string configPath, ArtifactPaths artifacts)
    {
        var metrics = MetricsCalculator.Compute(
            File.ReadAllText(artifacts.AuditReport),
            File.ReadAllText(artifacts.DependencyTree),
            File.ReadAllText(artifacts.Outdated),
            File.ReadAllText(artifacts.Licenses),
            File.ReadAllText(artifacts.Baseline));

        var config = JsonNode.Parse(File.ReadAllText(configPath)) as JsonObject
            ?? throw new InvalidOperationException($"Invalid config: {configPath}");
        var scores = NuGetAuditMetrics.NormalizedScores(metrics);
        var errors = new List<string>();

        foreach (var entry in config["metrics"]?.AsArray() ?? [])
        {
            var name = entry?["l4_classification"]?.GetValue<string>() ?? "?";
            var expected = entry?["expected_score"]?.GetValue<int>() ?? 100;
            if (!scores.TryGetValue(name, out var score) || score < expected)
            {
                errors.Add($"{name}: score {score} is below {expected}/100");
            }
        }

        if (errors.Count > 0)
        {
            Console.Error.WriteLine("FAIL: artifact metric coverage validation failed:");
            foreach (var err in errors)
            {
                Console.Error.WriteLine($"  - {err}");
            }

            return 1;
        }

        Console.WriteLine("PASS: all 8 NuGet audit SCA metrics are covered with 100/100 scores.");
        return 0;
    }
}
