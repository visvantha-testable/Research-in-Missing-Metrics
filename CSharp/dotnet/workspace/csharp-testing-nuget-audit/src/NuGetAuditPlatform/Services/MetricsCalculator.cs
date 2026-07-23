using System.Text.Json;
using System.Text.RegularExpressions;
using NuGetAuditPlatform.Models;

namespace NuGetAuditPlatform.Services;

public static class MetricsCalculator
{
    private static readonly Regex CopyleftPattern = new(@"\b(GPL|AGPL|SSPL|Commons Clause)\b", RegexOptions.IgnoreCase | RegexOptions.Compiled);
    private static readonly Regex RestrictedPattern = new(@"\b(Proprietary|UNLICENSED|Commercial)\b", RegexOptions.IgnoreCase | RegexOptions.Compiled);

    public static NuGetAuditMetrics Compute(
        string auditJson,
        string treeJson,
        string outdatedJson,
        string licensesJson,
        string baselineJson)
    {
        var audit = JsonDocument.Parse(auditJson).RootElement;
        var tree = JsonDocument.Parse(treeJson).RootElement;
        var outdated = JsonDocument.Parse(outdatedJson).RootElement;
        var licenses = JsonDocument.Parse(licensesJson).RootElement;
        var baseline = JsonDocument.Parse(baselineJson).RootElement;

        var (direct, transitive) = CountPackages(tree);
        var totalDependencies = Math.Max(direct + transitive, 1);

        var vulnRows = FlattenVulnerabilities(audit);
        var baselineRows = FlattenVulnerabilities(baseline);

        var critical = vulnRows.Count(r => r.Severity == "critical");
        var high = vulnRows.Count(r => r.Severity == "high");
        var medium = vulnRows.Count(r => r.Severity == "medium");
        var low = vulnRows.Count(r => r.Severity == "low");
        var totalVulns = vulnRows.Count;
        var knownCve = vulnRows.Count(r => r.Aliases.Any(a => a.Contains("GHSA-", StringComparison.OrdinalIgnoreCase) || a.Contains("CVE-", StringComparison.OrdinalIgnoreCase)));
        var withFix = vulnRows.Count(r => r.HasFix);

        var vulnerablePackages = vulnRows.Select(r => r.Package).Where(p => !string.IsNullOrEmpty(p)).Distinct().Count();
        var transitiveVulnerable = Math.Max(totalVulns - vulnerablePackages, 0);

        var copyleft = CountLicenses(licenses, CopyleftPattern);
        var restricted = CountLicenses(licenses, RestrictedPattern);
        var outdatedCount = CountOutdated(outdated);
        var versionLagCount = withFix;

        var hiddenRelationshipRisk = totalVulns / (double)Math.Max(totalDependencies, 1);
        var legalRiskProxy = knownCve;
        var supplyChainRisk = totalVulns;
        var communityVitality = totalVulns > 0 ? withFix / (double)totalVulns : 1.0;
        var alertSignal = Math.Max(totalVulns - baselineRows.Count, 0);

        var cveScore = critical * 25 + high * 10 + medium * 3 + low * 1;
        var transitiveRiskScore = transitiveVulnerable * 20;
        var licenseRiskScore = copyleft * 20 + restricted * 10 + legalRiskProxy;
        var trustScore = supplyChainRisk * 5;
        var vitalityScore = vulnerablePackages / (double)Math.Max(totalDependencies, 1) * 100;
        var versionLagScore = outdatedCount * 15 + versionLagCount * 5;

        var critHigh = critical + high;
        var critHighWithFix = vulnRows.Count(r => (r.Severity is "critical" or "high") && r.HasFix);
        var prioritizationCoverage = critHigh == 0 ? 100.0 : critHighWithFix / (double)critHigh * 100.0;
        var alertResponseRate = alertSignal == 0 ? 100.0 : Math.Max(0.0, 100.0 - alertSignal * 20);

        return new NuGetAuditMetrics(
            TotalDependencies: totalDependencies,
            DirectDependencies: direct,
            TransitiveDependencies: transitive,
            TotalVulnerabilities: totalVulns,
            KnownCveCount: knownCve,
            CriticalCveCount: critical,
            HighCveCount: high,
            MediumCveCount: medium,
            LowCveCount: low,
            VulnerabilitiesWithFix: withFix,
            TransitiveVulnerableCount: transitiveVulnerable,
            HiddenRelationshipRisk: hiddenRelationshipRisk,
            LegalRiskProxy: legalRiskProxy,
            SupplyChainRisk: supplyChainRisk,
            CommunityVitalityScore: communityVitality * 100.0,
            MitigationEffort: withFix,
            AlertSignal: alertSignal,
            VersionLagCount: versionLagCount,
            OutdatedDependencies: outdatedCount,
            CopyleftLicenseCount: copyleft,
            RestrictedLicenseCount: restricted,
            CveScore: cveScore,
            TransitiveRiskScore: transitiveRiskScore,
            LicenseRiskScore: licenseRiskScore,
            TrustScore: trustScore,
            VitalityScore: vitalityScore,
            PrioritizationCoveragePercent: prioritizationCoverage,
            AlertResponseRatePercent: alertResponseRate,
            VersionLagScore: versionLagScore,
            TransitiveDependencyScore: Math.Max(0.0, 100.0 - transitiveRiskScore),
            LicenseComplianceScore: Math.Max(0.0, 100.0 - licenseRiskScore),
            SupplyChainScore: Math.Max(0.0, 100.0 - trustScore),
            DependencyHealthScore: Math.Max(0.0, 100.0 - vitalityScore),
            RiskPrioritizationScore: prioritizationCoverage,
            ContinuousMonitoringScore: alertResponseRate,
            VulnerabilityDetectionScore: Math.Max(0.0, 100.0 - cveScore),
            OutdatedDependencyScore: Math.Max(0.0, 100.0 - versionLagScore));
    }

    private static (int Direct, int Transitive) CountPackages(System.Text.Json.JsonElement tree)
    {
        var direct = 0;
        var transitive = 0;
        foreach (var project in tree.GetProperty("projects").EnumerateArray())
        {
            foreach (var framework in project.GetProperty("frameworks").EnumerateArray())
            {
                if (framework.TryGetProperty("topLevelPackages", out var top))
                {
                    direct += top.GetArrayLength();
                }

                if (framework.TryGetProperty("transitivePackages", out var trans))
                {
                    transitive += trans.GetArrayLength();
                }
            }
        }

        return (direct, transitive);
    }

    private static List<VulnerabilityRow> FlattenVulnerabilities(System.Text.Json.JsonElement report)
    {
        var rows = new List<VulnerabilityRow>();
        if (!report.TryGetProperty("projects", out var projects))
        {
            return rows;
        }

        foreach (var project in projects.EnumerateArray())
        {
            if (!project.TryGetProperty("frameworks", out var frameworks))
            {
                continue;
            }

            foreach (var framework in frameworks.EnumerateArray())
            {
                foreach (var section in new[] { "topLevelPackages", "transitivePackages" })
                {
                    if (!framework.TryGetProperty(section, out var packages))
                    {
                        continue;
                    }

                    foreach (var pkg in packages.EnumerateArray())
                    {
                        var packageId = pkg.TryGetProperty("id", out var idEl) ? idEl.GetString() ?? "" : "";
                        var version = pkg.TryGetProperty("resolvedVersion", out var verEl) ? verEl.GetString() ?? "" : "";
                        if (!pkg.TryGetProperty("vulnerabilities", out var vulns))
                        {
                            continue;
                        }

                        foreach (var vuln in vulns.EnumerateArray())
                        {
                            var severity = NormalizeSeverity(vuln.TryGetProperty("severity", out var sevEl) ? sevEl.GetString() ?? "medium" : "medium");
                            var advisory = vuln.TryGetProperty("advisoryurl", out var advEl) ? advEl.GetString() ?? "" : "";
                            var hasFix = (vuln.TryGetProperty("fixVersions", out _) || vuln.TryGetProperty("fixVersion", out _));
                            rows.Add(new VulnerabilityRow(packageId, version, severity, advisory, hasFix, string.IsNullOrEmpty(advisory) ? [] : [advisory]));
                        }
                    }
                }
            }
        }

        return rows;
    }

    private static int CountOutdated(System.Text.Json.JsonElement outdated)
    {
        var count = 0;
        if (!outdated.TryGetProperty("projects", out var projects))
        {
            return count;
        }

        foreach (var project in projects.EnumerateArray())
        {
            if (!project.TryGetProperty("frameworks", out var frameworks))
            {
                continue;
            }

            foreach (var framework in frameworks.EnumerateArray())
            {
                if (!framework.TryGetProperty("topLevelPackages", out var packages))
                {
                    continue;
                }

                foreach (var pkg in packages.EnumerateArray())
                {
                    var latest = pkg.TryGetProperty("latestVersion", out var latestEl) ? latestEl.GetString() : null;
                    var resolved = pkg.TryGetProperty("resolvedVersion", out var resolvedEl) ? resolvedEl.GetString() : null;
                    if (!string.IsNullOrEmpty(latest) && !string.IsNullOrEmpty(resolved) && latest != resolved)
                    {
                        count++;
                    }
                }
            }
        }

        return count;
    }

    private static int CountLicenses(System.Text.Json.JsonElement licenses, Regex pattern)
    {
        if (licenses.ValueKind != System.Text.Json.JsonValueKind.Array)
        {
            return 0;
        }

        return licenses.EnumerateArray().Count(item =>
        {
            var license = item.TryGetProperty("license", out var licEl) ? licEl.GetString() ?? "" : "";
            return pattern.IsMatch(license);
        });
    }

    private static string NormalizeSeverity(string value)
    {
        var text = value.Trim().ToLowerInvariant();
        return text switch
        {
            "critical" => "critical",
            "high" => "high",
            "medium" or "moderate" => "medium",
            "low" => "low",
            _ => "medium",
        };
    }
}
