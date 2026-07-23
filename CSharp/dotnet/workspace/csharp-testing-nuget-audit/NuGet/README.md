# NuGet audit owner reference

Official NuGet audit and `dotnet list package --format json` specifications are maintained by the **NuGet team** at [NuGet/Home](https://github.com/NuGet/Home).

| Field | Value |
|-------|-------|
| Owner repo | [NuGet/Home](https://github.com/NuGet/Home) |
| Tool command | `dotnet list package --include-transitive --vulnerable --format json` |
| JSON spec | [Machine readable output for dotnet list package](https://github.com/NuGet/Home/wiki/%5BSpec%5D-Machine-readable-output-for-dotnet-list-package) |
| Audit docs | [Auditing Packages](https://github.com/NuGet/docs.microsoft.com-nuget/blob/main/docs/concepts/Auditing-Packages.md) |

The active scan target is `sample_subject/SampleSubject.csproj` — a minimal C# class library with current NuGet dependencies.
