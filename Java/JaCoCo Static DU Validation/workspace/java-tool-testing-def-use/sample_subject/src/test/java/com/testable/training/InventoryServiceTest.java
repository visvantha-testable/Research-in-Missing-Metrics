package com.testable.training;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class InventoryServiceTest {

    private final InventoryService service = new InventoryService();

    @Test
    void availableUnitsNormal() {
        assertEquals(7, service.availableUnits(10, 3));
        assertEquals(0, service.availableUnits(2, 5));
    }

    @Test
    void availableUnitsNegativeInputs() {
        assertEquals(0, service.availableUnits(-1, 3));
        assertEquals(0, service.availableUnits(3, -1));
    }

    @Test
    void stockStatus() {
        assertEquals("out_of_stock", service.stockStatus(0));
        assertEquals("low", service.stockStatus(3));
        assertEquals("ok", service.stockStatus(20));
    }

    @Test
    void allocateSkuValid() {
        List<String> slots = service.allocateSku("ABC", 2);
        assertEquals(2, slots.size());
        assertTrue(slots.get(0).startsWith("ABC-BIN-"));
    }

    @Test
    void allocateSkuInvalid() {
        assertEquals(0, service.allocateSku(null, 2).size());
        assertEquals(0, service.allocateSku("  ", 2).size());
        assertEquals(0, service.allocateSku("ABC", 0).size());
    }
}
