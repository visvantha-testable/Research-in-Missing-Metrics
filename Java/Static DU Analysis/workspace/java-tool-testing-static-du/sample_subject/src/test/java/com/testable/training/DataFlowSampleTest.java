package com.testable.training;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class DataFlowSampleTest {

    private final DataFlowSample sample = new DataFlowSample();

    @Test
    void computeEnabled() {
        assertEquals(30, sample.compute(10, true));
    }

    @Test
    void computeDisabled() {
        assertEquals(20, sample.compute(10, false));
    }

    @Test
    void routePass() {
        assertEquals("pass", sample.route(90));
    }

    @Test
    void routeFail() {
        assertEquals("fail", sample.route(0));
    }

    @Test
    void routeReview() {
        assertEquals("review", sample.route(50));
    }
}
