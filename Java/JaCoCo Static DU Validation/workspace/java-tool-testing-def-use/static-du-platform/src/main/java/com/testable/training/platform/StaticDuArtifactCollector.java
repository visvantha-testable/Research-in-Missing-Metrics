package com.testable.training.platform;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;

public final class StaticDuArtifactCollector {

    private StaticDuArtifactCollector() {
    }

    public static void collect(Path repoRoot, Path outputDir) throws Exception {
        Files.createDirectories(outputDir);
        Path sourceRoot = repoRoot.resolve("sample_subject/src/main/java");

        StaticDuAnalyzer.DuplicationSummary summary = StaticDuAnalyzer.analyze(sourceRoot);
        JsonUtils.write(outputDir.resolve("static_du_summary.json"), summary.toMap());
        JsonUtils.write(outputDir.resolve("cpd_report.json"), summary.toMap());

        Map<String, Object> meta = new LinkedHashMap<>();
        meta.put("tool", "static du");
        meta.put("tool_label", "Static DU");
        meta.put("source_root", sourceRoot.toString());
        meta.put("analysis_mode", "static_code_duplication");
        meta.put("min_block_lines", 6);
        meta.put("metrics_total", MetricDefinition.ALL.length);
        JsonUtils.write(outputDir.resolve("static_du_meta.json"), meta);

        System.out.println("Collected Static DU artifacts into " + outputDir);
        System.out.println("  total_lines=" + summary.totalLines());
        System.out.println("  duplicated_lines=" + summary.duplicatedLines());
        System.out.println("  duplicated_blocks=" + summary.duplicatedBlocks());
        System.out.println("  duplicated_files=" + summary.duplicatedFiles());
        System.out.println("  duplication_density_percent=" + summary.duplicationDensityPercent());
    }
}
