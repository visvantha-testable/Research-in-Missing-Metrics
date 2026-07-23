package com.testable.training.platform;

public final class JacocoCounters {
    public int lineMissed;
    public int lineCovered;
    public int branchMissed;
    public int branchCovered;
    public int instructionMissed;
    public int instructionCovered;
    public int ghostLines;
    public int partialBranchLines;
    public String sessionId = "";

    public double linePercent() {
        int total = lineMissed + lineCovered;
        return total == 0 ? 100.0 : lineCovered * 100.0 / total;
    }

    public double branchPercent() {
        int total = branchMissed + branchCovered;
        return total == 0 ? 100.0 : branchCovered * 100.0 / total;
    }

    public double instructionPercent() {
        int total = instructionMissed + instructionCovered;
        return total == 0 ? 100.0 : instructionCovered * 100.0 / total;
    }
}
