package com.testable.training.platform;

import java.util.LinkedHashMap;
import java.util.Map;

public final class StaticDuMetricsEngine {

    private StaticDuMetricsEngine() {
    }

    /**
     * Lower duplication is better. Zero duplication → 100/100 on all 12 metrics.
     */
    public static StaticDuDashboardMetrics compute(StaticDuAnalyzer.DuplicationSummary du) {
        double linesPercentScore = scoreFromDensity(du.duplicatedLinesPercent());
        double blocksScore = scoreFromCount(du.duplicatedBlocks());
        double filesScore = scoreFromCount(du.duplicatedFiles());
        double linesScore = scoreFromCount(du.duplicatedLines());
        double densityScore = scoreFromDensity(du.duplicationDensityPercent());

        Map<String, Double> scores = new LinkedHashMap<>();
        scores.put("Duplicated lines (%)", linesPercentScore);
        scores.put("Duplicated blocks", blocksScore);
        scores.put("Duplicated files", filesScore);
        scores.put("Duplicated lines", linesScore);
        scores.put("duplicated_blocks_count", blocksScore);
        scores.put("duplicated_files_count", filesScore);
        scores.put("duplicated_lines_count", linesScore);
        scores.put("duplication_density", densityScore);
        scores.put("duplication_density_percent", densityScore);
        scores.put("number_of_duplicated_blocks", blocksScore);
        scores.put("number_of_duplicated_files", filesScore);
        scores.put("number_of_duplicated_lines", linesScore);

        Map<String, Object> raw = new LinkedHashMap<>();
        raw.put("total_lines", du.totalLines());
        raw.put("duplicated_lines", du.duplicatedLines());
        raw.put("duplicated_lines_percent", du.duplicatedLinesPercent());
        raw.put("duplicated_blocks", du.duplicatedBlocks());
        raw.put("duplicated_files", du.duplicatedFiles());
        raw.put("duplicated_blocks_count", du.duplicatedBlocksCount());
        raw.put("duplicated_files_count", du.duplicatedFilesCount());
        raw.put("duplicated_lines_count", du.duplicatedLinesCount());
        raw.put("duplication_density", du.duplicationDensity());
        raw.put("duplication_density_percent", du.duplicationDensityPercent());
        raw.put("number_of_duplicated_blocks", du.numberOfDuplicatedBlocks());
        raw.put("number_of_duplicated_files", du.numberOfDuplicatedFiles());
        raw.put("number_of_duplicated_lines", du.numberOfDuplicatedLines());
        raw.put("metrics_total", MetricDefinition.ALL.length);

        return new StaticDuDashboardMetrics(scores, raw);
    }

    static double scoreFromDensity(double percent) {
        if (percent <= 0.0) {
            return 100.0;
        }
        return Math.max(0.0, Math.round(100.0 - percent));
    }

    static double scoreFromCount(int count) {
        if (count <= 0) {
            return 100.0;
        }
        return Math.max(0.0, Math.round(100.0 - count * 5.0));
    }

    public record StaticDuDashboardMetrics(Map<String, Double> scores, Map<String, Object> rawParameters) {
        public Map<String, Double> normalizedScores() {
            return scores;
        }
    }
}
