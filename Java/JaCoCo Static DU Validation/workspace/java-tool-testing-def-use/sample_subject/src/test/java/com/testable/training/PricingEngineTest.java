package com.testable.training;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class PricingEngineTest {

    private final PricingEngine engine = new PricingEngine();

    @Test
    void applyDiscount() {
        assertEquals(90.0, engine.applyDiscount(100.0, 10.0), 0.001);
        assertEquals(0.0, engine.applyDiscount(0.0, 10.0), 0.001);
    }

    @Test
    void applyDiscountRejectsInvalid() {
        assertThrows(IllegalArgumentException.class, () -> engine.applyDiscount(-1, 10));
        assertThrows(IllegalArgumentException.class, () -> engine.applyDiscount(10, -1));
        assertThrows(IllegalArgumentException.class, () -> engine.applyDiscount(10, 150));
    }

    @Test
    void taxInclusive() {
        assertEquals(110.0, engine.taxInclusive(100.0, 0.10), 0.001);
        assertEquals(0.0, engine.taxInclusive(-1, 0.10), 0.001);
        assertEquals(0.0, engine.taxInclusive(100.0, -1), 0.001);
    }

    @Test
    void priceBand() {
        assertEquals("budget", engine.priceBand(5));
        assertEquals("standard", engine.priceBand(50));
        assertEquals("premium", engine.priceBand(250));
    }
}
