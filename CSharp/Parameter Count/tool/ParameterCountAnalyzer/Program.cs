using System.Globalization;
using System.Text;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

static class Program
{
    private static readonly HashSet<string> ExcludedDirectories = new(StringComparer.OrdinalIgnoreCase)
    {
        ".git", "bin", "obj", "packages", "artifacts", "TestResults", "node_modules"
    };

    static int Main(string[] args)
    {
        string? repoPath = null;
        string? outputPath = null;

        for (var index = 0; index < args.Length; index++)
        {
            switch (args[index])
            {
                case "--repo":
                    repoPath = args[++index];
                    break;
                case "--output":
                    outputPath = args[++index];
                    break;
                default:
                    Console.Error.WriteLine($"Unknown argument: {args[index]}");
                    return 2;
            }
        }

        if (string.IsNullOrWhiteSpace(repoPath) || string.IsNullOrWhiteSpace(outputPath))
        {
            Console.Error.WriteLine("Usage: ParameterCountAnalyzer --repo <path> --output <csv_path>");
            return 2;
        }

        var repo = Path.GetFullPath(repoPath);
        if (!Directory.Exists(repo))
        {
            Console.Error.WriteLine($"Repository path not found: {repo}");
            return 1;
        }

        var csharpFiles = DiscoverCSharpFiles(repo);
        var rows = new List<string[]>();

        foreach (var filePath in csharpFiles)
        {
            try
            {
                var sourceText = File.ReadAllText(filePath);
                var tree = CSharpSyntaxTree.ParseText(sourceText, path: filePath);
                var root = tree.GetRoot();
                var fileNamespace = FindFileNamespace(root);

                foreach (var record in root.DescendantNodes().OfType<RecordDeclarationSyntax>())
                {
                    if (record.ParameterList is null)
                    {
                        continue;
                    }

                    AddMemberRow(rows, filePath, fileNamespace, record.Identifier.Text, record.Identifier.Text, record.ParameterList, record);
                }

                foreach (var method in root.DescendantNodes().OfType<MethodDeclarationSyntax>())
                {
                    AddMemberRow(rows, filePath, fileNamespace, FindTypeName(method), method.Identifier.Text, method.ParameterList, method);
                    foreach (var localFunction in method.DescendantNodes().OfType<LocalFunctionStatementSyntax>())
                    {
                        AddMemberRow(rows, filePath, fileNamespace, FindTypeName(localFunction), localFunction.Identifier.Text, localFunction.ParameterList, localFunction);
                    }
                }

                foreach (var constructor in root.DescendantNodes().OfType<ConstructorDeclarationSyntax>())
                {
                    AddMemberRow(rows, filePath, fileNamespace, FindTypeName(constructor), constructor.Identifier.Text, constructor.ParameterList, constructor);
                }

                foreach (var delegateDeclaration in root.DescendantNodes().OfType<DelegateDeclarationSyntax>())
                {
                    AddMemberRow(rows, filePath, fileNamespace, FindTypeName(delegateDeclaration), delegateDeclaration.Identifier.Text, delegateDeclaration.ParameterList, delegateDeclaration);
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"Failed to analyze {filePath}: {ex.Message}");
            }
        }

        WriteCsv(outputPath, rows);
        Console.WriteLine($"Analyzed {csharpFiles.Count} C# files, {rows.Count} member rows written to {outputPath}");
        return 0;
    }

    private static void AddMemberRow(
        List<string[]> rows,
        string filePath,
        string fileNamespace,
        string className,
        string methodName,
        BaseParameterListSyntax? parameterList,
        SyntaxNode memberNode)
    {
        var lineSpan = memberNode.GetLocation().GetLineSpan();
        var line = lineSpan.StartLinePosition.Line + 1;
        var parameters = parameterList?.Parameters ?? default;
        var parameterNames = string.Join(";", parameters.Select(parameter => parameter.Identifier.Text));
        var parameterCount = parameters.Count.ToString(CultureInfo.InvariantCulture);

        rows.Add([
            filePath,
            fileNamespace,
            className,
            methodName,
            line.ToString(CultureInfo.InvariantCulture),
            parameterCount,
            parameterNames
        ]);
    }

    private static List<string> DiscoverCSharpFiles(string repoPath)
    {
        var files = new List<string>();
        foreach (var path in Directory.EnumerateFiles(repoPath, "*.cs", SearchOption.AllDirectories))
        {
            if (ShouldExclude(path, repoPath))
            {
                continue;
            }

            files.Add(path);
        }

        files.Sort(StringComparer.OrdinalIgnoreCase);
        return files;
    }

    private static bool ShouldExclude(string filePath, string repoPath)
    {
        var relative = Path.GetRelativePath(repoPath, filePath);
        foreach (var part in relative.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar))
        {
            if (ExcludedDirectories.Contains(part))
            {
                return true;
            }
        }

        return false;
    }

    private static string FindFileNamespace(SyntaxNode root)
    {
        var namespaceDeclaration = root.DescendantNodes().OfType<BaseNamespaceDeclarationSyntax>().FirstOrDefault();
        return namespaceDeclaration?.Name.ToString() ?? string.Empty;
    }

    private static string FindTypeName(SyntaxNode node)
    {
        var current = node.Parent;
        while (current is not null)
        {
            switch (current)
            {
                case ClassDeclarationSyntax classDeclaration:
                    return classDeclaration.Identifier.Text;
                case StructDeclarationSyntax structDeclaration:
                    return structDeclaration.Identifier.Text;
                case RecordDeclarationSyntax recordDeclaration:
                    return recordDeclaration.Identifier.Text;
                case InterfaceDeclarationSyntax interfaceDeclaration:
                    return interfaceDeclaration.Identifier.Text;
            }

            current = current.Parent;
        }

        return string.Empty;
    }

    private static void WriteCsv(string outputPath, List<string[]> rows)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
        using var writer = new StreamWriter(outputPath, false, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
        writer.WriteLine("file,namespace,class,method,line,parameter_count,parameter_names");
        foreach (var row in rows)
        {
            writer.WriteLine(string.Join(",", row.Select(EscapeCsv)));
        }
    }

    private static string EscapeCsv(string value)
    {
        if (value.Contains('"') || value.Contains(',') || value.Contains('\n') || value.Contains('\r'))
        {
            return $"\"{value.Replace("\"", "\"\"", StringComparison.Ordinal)}\"";
        }

        return value;
    }
}
