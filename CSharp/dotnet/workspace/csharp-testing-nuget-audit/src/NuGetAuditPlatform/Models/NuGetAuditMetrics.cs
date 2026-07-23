namespace NuGetAuditPlatform.Models;

public sealed record NuGetAuditMetrics(
    int TotalDependencies,
    int DirectDependencies,
    int TransitiveDependencies,
    int TotalVulnerabilities,
    int KnownCveCount,
    int CriticalCveCount,
    int HighCveCount,
    int MediumCveCount,
    int LowCveCount,
    int VulnerabilitiesWithFix,
    int TransitiveVulnerableCount,
    double HiddenRelationshipRisk,
    int LegalRiskProxy,
    int SupplyChainRisk,
    double CommunityVitalityScore,
    int MitigationEffort,
    int AlertSignal,
    int VersionLagCount,
    int OutdatedDependencies,
    int CopyleftLicenseCount,
    int RestrictedLicenseCount,
    double CveScore,
    double TransitiveRiskScore,
    double LicenseRiskScore,
    double TrustScore,
    double VitalityScore,
    double PrioritizationCoveragePercent,
    double AlertResponseRatePercent,
    double VersionLagScore,
    double TransitiveDependencyScore,
    double LicenseComplianceScore,
    double SupplyChainScore,
    double DependencyHealthScore,
    double RiskPrioritizationScore,
    double ContinuousMonitoringScore,
    double VulnerabilityDetectionScore,
    double OutdatedDependencyScore)
{
    public static Dictionary<string, double> NormalizedScores(NuGetAuditMetrics metrics) => new()
    {
        ["Transitive Dependency Analysis"] = metrics.TransitiveDependencyScore,
        ["License Compliance Testing"] = metrics.LicenseComplianceScore,
        ["Supply Chain Security Analysis"] = metrics.SupplyChainScore,
        ["Dependency Health Monitoring"] = metrics.DependencyHealthScore,
        ["Risk Prioritization"] = metrics.RiskPrioritizationScore,
        ["Continuous Dependency Monitoring"] = metrics.ContinuousMonitoringScore,
        ["Vulnerability Dependency Detection"] = metrics.VulnerabilityDetectionScore,
        ["Outdated Dependency Detection"] = metrics.OutdatedDependencyScore,
    };
}

public sealed record VulnerabilityRow(
    string Package,
    string Version,
    string Severity,
    string AdvisoryUrl,
    bool HasFix,
    IReadOnlyList<string> Aliases);

public sealed record LicenseRow(string Name, string License);

public sealed record ArtifactPaths(
    string AuditReport,
    string DependencyTree,
    string Outdated,
    string Licenses,
    string Baseline);
