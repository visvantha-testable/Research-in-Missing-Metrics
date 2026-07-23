package com.testable.training.platform;

public record MetricDefinition(
        String l3,
        String l4,
        String l5,
        String scoreField
) {
    // Dashboard IDs 20–31 — Static DU code duplication metrics
    public static final MetricDefinition[] ALL = {
            new MetricDefinition("Code Quality", "Static Duplication", "Duplicated lines (%)", "duplicated_lines_percent_score"),
            new MetricDefinition("Code Quality", "Static Duplication", "Duplicated blocks", "duplicated_blocks_score"),
            new MetricDefinition("Code Quality", "Static Duplication", "Duplicated files", "duplicated_files_score"),
            new MetricDefinition("Code Quality", "Static Duplication", "Duplicated lines", "duplicated_lines_score"),
            new MetricDefinition("Code Quality", "Static Duplication", "duplicated_blocks_count", "duplicated_blocks_count_score"),
            new MetricDefinition("Code Quality", "Static Duplication", "duplicated_files_count", "duplicated_files_count_score"),
            new MetricDefinition("Code Quality", "Static Duplication", "duplicated_lines_count", "duplicated_lines_count_score"),
            new MetricDefinition("Code Quality", "Static Duplication", "duplication_density", "duplication_density_score"),
            new MetricDefinition("Code Quality", "Static Duplication", "duplication_density_percent", "duplication_density_percent_score"),
            new MetricDefinition("Code Quality", "Static Duplication", "number_of_duplicated_blocks", "number_of_duplicated_blocks_score"),
            new MetricDefinition("Code Quality", "Static Duplication", "number_of_duplicated_files", "number_of_duplicated_files_score"),
            new MetricDefinition("Code Quality", "Static Duplication", "number_of_duplicated_lines", "number_of_duplicated_lines_score")
    };

    public String key() {
        return l5;
    }
}
