package com.testable.training.platform;

public record MetricDefinition(
        String l3,
        String l4,
        String l5,
        String kpi,
        String scoreField
) {
    public static final MetricDefinition VARIABLE_DEFINITION = new MetricDefinition(
            "Data Flow Testing",
            "All Definition Coverage",
            "Variable Definition Detection",
            "All-Defs Coverage %",
            "all_defs_coverage_score"
    );
    public static final MetricDefinition DEFINITION_USE_MAPPING = new MetricDefinition(
            "Data Flow Testing",
            "All Definition Coverage",
            "Definition-Use Mapping",
            "Data Path Correlation",
            "data_path_correlation_score"
    );
    public static final MetricDefinition COVERAGE_MEASUREMENT = new MetricDefinition(
            "Data Flow Testing",
            "All Definition Coverage",
            "Coverage Measurement",
            "DU-Path Validation",
            "du_path_validation_score"
    );
    public static final MetricDefinition UNCOVERED_DEFINITION = new MetricDefinition(
            "Data Flow Testing",
            "All Definition Coverage",
            "Uncovered Definition Detection",
            "Dead Data Identification",
            "dead_data_identification_score"
    );
    public static final MetricDefinition VARIABLE_USE = new MetricDefinition(
            "Data Flow Testing",
            "All Uses Coverage",
            "Variable Use Detection",
            "All-Uses Coverage %",
            "all_uses_coverage_score"
    );

    public static final MetricDefinition[] ALL = {
            VARIABLE_DEFINITION,
            DEFINITION_USE_MAPPING,
            COVERAGE_MEASUREMENT,
            UNCOVERED_DEFINITION,
            VARIABLE_USE
    };

    public String key() {
        return l5;
    }
}
