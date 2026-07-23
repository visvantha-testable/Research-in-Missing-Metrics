namespace SampleSubject;

using System.Text.Json;
using Microsoft.Extensions.Logging;

/// <summary>
/// C# training subject for NuGet audit — aligned with NuGet/Home audit patterns.
/// </summary>
public static class AuditSubject
{
    private static readonly JsonSerializerOptions JsonOptions = new() { WriteIndented = true };

    public static string Serialize(object value) => JsonSerializer.Serialize(value, JsonOptions);

    public static T? Deserialize<T>(string json) => JsonSerializer.Deserialize<T>(json, JsonOptions);

    public static void LogSample(ILogger logger) =>
        logger.LogInformation("NuGet audit sample subject ready");

    public static IReadOnlyList<PackageDescriptor> DescribePinnedPackages() =>
    [
        new("Microsoft.Extensions.Logging.Abstractions", "10.0.10"),
        new("System.Text.Json", "10.0.10"),
    ];
}

public sealed record PackageDescriptor(string Id, string Version);
