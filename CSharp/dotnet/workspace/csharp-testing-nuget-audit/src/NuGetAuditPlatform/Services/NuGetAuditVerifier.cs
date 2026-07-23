using System.Text.Json.Nodes;

namespace NuGetAuditPlatform.Services;

public static class NuGetAuditVerifier
{
    private static readonly string[] RequiredSupplementalKeys =
    [
        "dependency_tree",
        "outdated_packages",
        "licenses",
        "baseline_audit",
    ];

    public static int Verify(string nugetAuditJsonPath)
    {
        var payload = JsonNode.Parse(File.ReadAllText(nugetAuditJsonPath)) as JsonObject
            ?? throw new InvalidOperationException("Invalid nuget_audit.json");

        var errors = new List<string>();

        if (payload["output_complete"]?.GetValue<bool>() != true)
        {
            errors.Add("output_complete is not true");
        }

        if (payload["metric_coverage_complete"]?.GetValue<bool>() != true)
        {
            errors.Add("metric_coverage_complete is not true");
        }

        if (payload["metrics_covered"]?.GetValue<int>() != 8)
        {
            errors.Add($"metrics_covered is {payload["metrics_covered"]} not 8");
        }

        var supplemental = payload["supplemental_raw_data"] as JsonObject ?? new JsonObject();
        foreach (var key in RequiredSupplementalKeys)
        {
            if (!supplemental.ContainsKey(key))
            {
                errors.Add($"missing supplemental_raw_data.{key}");
            }
        }

        var metrics = payload["metrics"] as JsonArray ?? [];
        if (metrics.Count != 8)
        {
            errors.Add($"expected 8 metric rows, got {metrics.Count}");
        }

        foreach (var rowNode in metrics)
        {
            if (rowNode is not JsonObject row)
            {
                continue;
            }

            var name = row["classification"]?.GetValue<string>() ?? "?";
            if (row["covered"]?.GetValue<string>() != "yes")
            {
                errors.Add($"{name}: covered is not 'yes'");
            }

            if ((row["score"]?.GetValue<int>() ?? 0) < 100)
            {
                errors.Add($"{name}: score {row["score"]} below 100");
            }

            if (row["result"]?.GetValue<string>() != "PASS")
            {
                errors.Add($"{name}: result is not PASS");
            }
        }

        if (errors.Count > 0)
        {
            Console.Error.WriteLine("FAIL: nuget_audit.json incomplete:");
            foreach (var err in errors)
            {
                Console.Error.WriteLine($"  - {err}");
            }

            return 1;
        }

        Console.WriteLine("PASS: nuget_audit.json has all 8 metrics covered=yes with 100/100 scores");
        return 0;
    }

    public static int VerifyHundredPercent(string metricsJsonPath, string dashboardJsonPath)
    {
        var metrics = JsonNode.Parse(File.ReadAllText(metricsJsonPath)) as JsonObject
            ?? throw new InvalidOperationException("Invalid metrics json");
        var dashboard = JsonNode.Parse(File.ReadAllText(dashboardJsonPath)) as JsonObject
            ?? throw new InvalidOperationException("Invalid dashboard json");

        var normalized = metrics["normalized_scores"] as JsonObject ?? new JsonObject();
        var errors = new List<string>();
        foreach (var pair in normalized)
        {
            if (pair.Value!.GetValue<double>() < 100.0)
            {
                errors.Add($"{pair.Key}: normalized score {pair.Value} below 100");
            }
        }

        foreach (var rowNode in dashboard["metrics"]?.AsArray() ?? [])
        {
            if (rowNode is not JsonObject row)
            {
                continue;
            }

            var name = row["classification"]?.GetValue<string>() ?? "?";
            var coverage = row["coverage_percent"]?.GetValue<double>() ?? 0;
            if (coverage < 100.0)
            {
                errors.Add($"{name}: dashboard coverage {coverage} below 100");
            }
        }

        if (errors.Count > 0)
        {
            Console.Error.WriteLine("FAIL: 100 percent verification failed:");
            foreach (var err in errors)
            {
                Console.Error.WriteLine($"  - {err}");
            }

            return 1;
        }

        Console.WriteLine("PASS: all normalized scores and dashboard metrics are 100/100");
        return 0;
    }
}
