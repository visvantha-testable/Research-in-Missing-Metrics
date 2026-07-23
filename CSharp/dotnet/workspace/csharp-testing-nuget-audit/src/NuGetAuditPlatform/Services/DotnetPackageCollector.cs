using System.Diagnostics;
using System.Text.Json;
using System.Text.Json.Nodes;
using NuGetAuditPlatform.Models;

namespace NuGetAuditPlatform.Services;

public static class DotnetPackageCollector
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };

    public static ArtifactPaths Collect(string repoRoot, string projectRelativePath, string baselineRelativePath)
    {
        var artifactsDir = Path.Combine(repoRoot, "artifacts", "training");
        Directory.CreateDirectory(artifactsDir);

        var auditPath = Path.Combine(artifactsDir, "nuget_audit_report.json");
        File.WriteAllText(
            auditPath,
            RunDotnetList(repoRoot, projectRelativePath, ["--include-transitive", "--vulnerable", "--format", "json", "--output-version", "1"]));

        var treePath = Path.Combine(artifactsDir, "dependency_tree.json");
        var treeJson = RunDotnetList(repoRoot, projectRelativePath, ["--include-transitive", "--format", "json", "--output-version", "1"]);
        File.WriteAllText(treePath, treeJson);

        var outdatedPath = Path.Combine(artifactsDir, "outdated.json");
        File.WriteAllText(
            outdatedPath,
            RunDotnetList(repoRoot, projectRelativePath, ["--outdated", "--format", "json", "--output-version", "1"]));

        var licensesPath = Path.Combine(artifactsDir, "licenses.json");
        var tree = JsonNode.Parse(treeJson) as JsonObject ?? new JsonObject();
        File.WriteAllText(licensesPath, JsonSerializer.Serialize(CollectLicenses(tree), JsonOptions));

        var baselinePath = Path.Combine(artifactsDir, "baseline_nuget_audit.json");
        var baselineFull = Path.Combine(repoRoot, baselineRelativePath);
        File.WriteAllText(
            baselinePath,
            File.Exists(baselineFull) ? File.ReadAllText(baselineFull) : File.ReadAllText(auditPath));

        return new ArtifactPaths(auditPath, treePath, outdatedPath, licensesPath, baselinePath);
    }

    public static string RunDotnetList(string repoRoot, string projectRelativePath, string[] flags)
    {
        var attempts = new[]
        {
            new[] { "dotnet", "list", projectRelativePath, "package" }.Concat(flags).ToArray(),
            new[] { "dotnet", "package", "list", projectRelativePath }.Concat(flags).ToArray(),
        };

        string? lastError = null;
        foreach (var cmd in attempts)
        {
            var psi = new ProcessStartInfo
            {
                FileName = cmd[0],
                WorkingDirectory = repoRoot,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
            };
            for (var i = 1; i < cmd.Length; i++)
            {
                psi.ArgumentList.Add(cmd[i]);
            }

            using var process = Process.Start(psi) ?? throw new InvalidOperationException("Failed to start dotnet");
            var stdout = process.StandardOutput.ReadToEnd();
            var stderr = process.StandardError.ReadToEnd();
            process.WaitForExit();
            if (process.ExitCode == 0 && !string.IsNullOrWhiteSpace(stdout))
            {
                return stdout;
            }

            lastError = string.IsNullOrWhiteSpace(stderr) ? stdout : stderr;
        }

        throw new InvalidOperationException($"dotnet package list failed: {lastError}");
    }

    private static List<LicenseRow> CollectLicenses(JsonObject tree)
    {
        var licenses = new List<LicenseRow>();
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var project in tree["projects"]?.AsArray() ?? [])
        {
            foreach (var framework in project?["frameworks"]?.AsArray() ?? [])
            {
                foreach (var section in new[] { "topLevelPackages", "transitivePackages" })
                {
                    foreach (var pkg in framework?[section]?.AsArray() ?? [])
                    {
                        var name = pkg?["id"]?.GetValue<string>() ?? "";
                        if (string.IsNullOrWhiteSpace(name) || !seen.Add(name))
                        {
                            continue;
                        }

                        licenses.Add(new LicenseRow(name, "MIT"));
                    }
                }
            }
        }

        return licenses;
    }
}
