package com.testable.training;

public final class DataFlowSample {

    public int compute(int base, boolean enabled) {
        int result = base;
        if (enabled) {
            result = result + 5;
        }
        return result * 2;
    }

    public String route(int score) {
        if (score >= 80) {
            return "pass";
        }
        if (score <= 0) {
            return "fail";
        }
        return "review";
    }
}
