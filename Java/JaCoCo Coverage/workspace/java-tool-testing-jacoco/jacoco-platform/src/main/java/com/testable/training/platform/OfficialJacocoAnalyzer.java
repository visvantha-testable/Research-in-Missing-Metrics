package com.testable.training.platform;

import org.jacoco.core.analysis.Analyzer;
import org.jacoco.core.analysis.CoverageBuilder;
import org.jacoco.core.analysis.IBundleCoverage;
import org.jacoco.core.analysis.ICounter;
import org.jacoco.core.tools.ExecFileLoader;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Loads coverage using the official JaCoCo Core API from
 * <a href="https://github.com/jacoco/jacoco">jacoco/jacoco</a>.
 * Pattern based on org.jacoco.examples.ReportGenerator and CoreTutorial.
 */
public final class OfficialJacocoAnalyzer {

    private OfficialJacocoAnalyzer() {
    }

    public static JacocoCounters fromExec(Path execFile, Path classesDirectory) throws IOException {
        if (!Files.exists(execFile)) {
            throw new IOException("Missing JaCoCo exec file: " + execFile);
        }
        if (!Files.isDirectory(classesDirectory)) {
            throw new IOException("Missing compiled classes directory: " + classesDirectory);
        }

        ExecFileLoader loader = new ExecFileLoader();
        loader.load(execFile.toFile());

        CoverageBuilder builder = new CoverageBuilder();
        Analyzer analyzer = new Analyzer(loader.getExecutionDataStore(), builder);
        analyzer.analyzeAll(classesDirectory.toFile());

        JacocoCounters counters = fromClasses(builder);
        if (!loader.getSessionInfoStore().getInfos().isEmpty()) {
            counters.sessionId = loader.getSessionInfoStore().getInfos().get(0).getId();
        }
        return counters;
    }

    public static JacocoCounters fromClasses(CoverageBuilder builder) {
        JacocoCounters counters = new JacocoCounters();
        builder.getClasses().forEach(clazz -> {
            counters.lineMissed += clazz.getLineCounter().getMissedCount();
            counters.lineCovered += clazz.getLineCounter().getCoveredCount();
            counters.branchMissed += clazz.getBranchCounter().getMissedCount();
            counters.branchCovered += clazz.getBranchCounter().getCoveredCount();
            counters.instructionMissed += clazz.getInstructionCounter().getMissedCount();
            counters.instructionCovered += clazz.getInstructionCounter().getCoveredCount();
        });
        counters.ghostLines = counters.lineMissed;
        counters.partialBranchLines = 0;
        return counters;
    }

    public static JacocoCounters fromBundle(IBundleCoverage bundle) {
        JacocoCounters counters = new JacocoCounters();
        applyCounter(bundle.getLineCounter(), counters, CounterKind.LINE);
        applyCounter(bundle.getBranchCounter(), counters, CounterKind.BRANCH);
        applyCounter(bundle.getInstructionCounter(), counters, CounterKind.INSTRUCTION);
        counters.ghostLines = counters.lineMissed;
        counters.partialBranchLines = 0;
        return counters;
    }

    private enum CounterKind { LINE, BRANCH, INSTRUCTION }

    private static void applyCounter(ICounter counter, JacocoCounters counters, CounterKind kind) {
        switch (kind) {
            case LINE -> {
                counters.lineMissed = counter.getMissedCount();
                counters.lineCovered = counter.getCoveredCount();
            }
            case BRANCH -> {
                counters.branchMissed = counter.getMissedCount();
                counters.branchCovered = counter.getCoveredCount();
            }
            case INSTRUCTION -> {
                counters.instructionMissed = counter.getMissedCount();
                counters.instructionCovered = counter.getCoveredCount();
            }
        }
    }
}
