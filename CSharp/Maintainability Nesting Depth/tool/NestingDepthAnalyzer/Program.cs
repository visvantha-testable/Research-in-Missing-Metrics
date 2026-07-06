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
            Console.Error.WriteLine("Usage: NestingDepthAnalyzer --repo <path> --output <csv_path>");
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
                var className = FindContainingClassName(root, filePath);

                foreach (var method in root.DescendantNodes().OfType<MethodDeclarationSyntax>())
                {
                    if (method.Body is null && method.ExpressionBody is null)
                    {
                        continue;
                    }

                    var lineSpan = method.GetLocation().GetLineSpan();
                    var startLine = lineSpan.StartLinePosition.Line + 1;
                    var endLine = lineSpan.EndLinePosition.Line + 1;
                    var methodClass = FindClassName(method) ?? className;
                    var maxDepth = ComputeMethodMaxNestingDepth(method);

                    rows.Add([
                        filePath,
                        methodClass,
                        method.Identifier.Text,
                        startLine.ToString(CultureInfo.InvariantCulture),
                        endLine.ToString(CultureInfo.InvariantCulture),
                        maxDepth.ToString(CultureInfo.InvariantCulture),
                        "analyzed"
                    ]);
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"Failed to analyze {filePath}: {ex.Message}");
                rows.Add([filePath, "", "", "", "", "", $"failed: {ex.Message}"]);
            }
        }

        WriteCsv(outputPath, rows);
        Console.WriteLine($"Analyzed {csharpFiles.Count} C# files, {rows.Count} method rows written to {outputPath}");
        return 0;
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

    private static string FindContainingClassName(SyntaxNode root, string filePath)
    {
        var firstClass = root.DescendantNodes().OfType<ClassDeclarationSyntax>().FirstOrDefault();
        return firstClass?.Identifier.Text ?? Path.GetFileNameWithoutExtension(filePath);
    }

    private static string? FindClassName(SyntaxNode node)
    {
        var current = node.Parent;
        while (current is not null)
        {
            if (current is ClassDeclarationSyntax classDeclaration)
            {
                return classDeclaration.Identifier.Text;
            }

            if (current is StructDeclarationSyntax structDeclaration)
            {
                return structDeclaration.Identifier.Text;
            }

            current = current.Parent;
        }

        return null;
    }

    private static int ComputeMethodMaxNestingDepth(MethodDeclarationSyntax method)
    {
        var maxDepth = 0;
        if (method.Body is not null)
        {
            maxDepth = Math.Max(maxDepth, ComputeBlockMaxDepth(method.Body, 0));
        }

        if (method.ExpressionBody is not null)
        {
            maxDepth = Math.Max(maxDepth, ComputeNodeMaxDepth(method.ExpressionBody.Expression, 0));
        }

        return maxDepth;
    }

    private static int ComputeBlockMaxDepth(BlockSyntax block, int currentDepth)
    {
        var maxDepth = currentDepth;
        foreach (var statement in block.Statements)
        {
            maxDepth = Math.Max(maxDepth, ComputeStatementMaxDepth(statement, currentDepth));
        }

        return maxDepth;
    }

    private static int ComputeStatementMaxDepth(StatementSyntax statement, int currentDepth)
    {
        return statement switch
        {
            BlockSyntax nestedBlock => ComputeBlockMaxDepth(nestedBlock, currentDepth),
            IfStatementSyntax ifStatement => ComputeIfMaxDepth(ifStatement, currentDepth),
            SwitchStatementSyntax switchStatement => ComputeSwitchMaxDepth(switchStatement, currentDepth),
            ForStatementSyntax forStatement => ComputeLoopBodyMaxDepth(forStatement.Statement, currentDepth),
            ForEachStatementSyntax forEachStatement => ComputeLoopBodyMaxDepth(forEachStatement.Statement, currentDepth),
            WhileStatementSyntax whileStatement => ComputeLoopBodyMaxDepth(whileStatement.Statement, currentDepth),
            DoStatementSyntax doStatement => ComputeLoopBodyMaxDepth(doStatement.Statement, currentDepth),
            TryStatementSyntax tryStatement => ComputeTryMaxDepth(tryStatement, currentDepth),
            UsingStatementSyntax usingStatement => ComputeUsingMaxDepth(usingStatement, currentDepth),
            LockStatementSyntax lockStatement => ComputeLoopBodyMaxDepth(lockStatement.Statement, currentDepth),
            LocalFunctionStatementSyntax localFunction => ComputeLocalFunctionMaxDepth(localFunction),
            _ => currentDepth
        };
    }

    private static int ComputeIfMaxDepth(IfStatementSyntax ifStatement, int currentDepth)
    {
        var bodyDepth = currentDepth + 1;
        var maxDepth = bodyDepth;
        maxDepth = Math.Max(maxDepth, ComputeNodeMaxDepth(ifStatement.Statement, bodyDepth));

        if (ifStatement.Else is not null)
        {
            maxDepth = Math.Max(maxDepth, ComputeNodeMaxDepth(ifStatement.Else.Statement, currentDepth));
        }

        return maxDepth;
    }

    private static int ComputeSwitchMaxDepth(SwitchStatementSyntax switchStatement, int currentDepth)
    {
        var bodyDepth = currentDepth + 1;
        var maxDepth = bodyDepth;

        foreach (var section in switchStatement.Sections)
        {
            foreach (var statement in section.Statements)
            {
                maxDepth = Math.Max(maxDepth, ComputeStatementMaxDepth(statement, bodyDepth));
            }
        }

        return maxDepth;
    }

    private static int ComputeTryMaxDepth(TryStatementSyntax tryStatement, int currentDepth)
    {
        var bodyDepth = currentDepth + 1;
        var maxDepth = bodyDepth;
        maxDepth = Math.Max(maxDepth, ComputeBlockMaxDepth(tryStatement.Block, bodyDepth));

        foreach (var catchClause in tryStatement.Catches)
        {
            maxDepth = Math.Max(maxDepth, ComputeBlockMaxDepth(catchClause.Block, bodyDepth));
        }

        if (tryStatement.Finally is not null)
        {
            maxDepth = Math.Max(maxDepth, ComputeBlockMaxDepth(tryStatement.Finally.Block, bodyDepth));
        }

        return maxDepth;
    }

    private static int ComputeUsingMaxDepth(UsingStatementSyntax usingStatement, int currentDepth)
    {
        var bodyDepth = currentDepth + 1;
        var maxDepth = bodyDepth;
        maxDepth = Math.Max(maxDepth, ComputeNodeMaxDepth(usingStatement.Statement, bodyDepth));
        return maxDepth;
    }

    private static int ComputeLoopBodyMaxDepth(StatementSyntax statement, int currentDepth)
    {
        var bodyDepth = currentDepth + 1;
        var maxDepth = bodyDepth;
        maxDepth = Math.Max(maxDepth, ComputeNodeMaxDepth(statement, bodyDepth));
        return maxDepth;
    }

    private static int ComputeLocalFunctionMaxDepth(LocalFunctionStatementSyntax localFunction)
    {
        var maxDepth = 0;
        if (localFunction.Body is not null)
        {
            maxDepth = Math.Max(maxDepth, ComputeBlockMaxDepth(localFunction.Body, 0));
        }

        if (localFunction.ExpressionBody is not null)
        {
            maxDepth = Math.Max(maxDepth, ComputeNodeMaxDepth(localFunction.ExpressionBody.Expression, 0));
        }

        return maxDepth;
    }

    private static int ComputeNodeMaxDepth(SyntaxNode node, int currentDepth)
    {
        return node switch
        {
            BlockSyntax block => ComputeBlockMaxDepth(block, currentDepth),
            StatementSyntax statement => ComputeStatementMaxDepth(statement, currentDepth),
            _ => currentDepth
        };
    }

    private static void WriteCsv(string outputPath, List<string[]> rows)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outputPath))!);
        using var writer = new StreamWriter(outputPath, false, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
        writer.WriteLine("file,class,method,start_line,end_line,max_nesting_depth,status");
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
