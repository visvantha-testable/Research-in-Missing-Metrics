package com.testable.training;

import java.util.ArrayList;
import java.util.List;

/** Unique inventory domain logic — intentionally non-duplicated vs other modules. */
public final class InventoryService {

    public int availableUnits(int onHand, int reserved) {
        if (onHand < 0 || reserved < 0) {
            return 0;
        }
        int free = onHand - reserved;
        return Math.max(free, 0);
    }

    public String stockStatus(int available) {
        if (available == 0) {
            return "out_of_stock";
        }
        if (available < 5) {
            return "low";
        }
        return "ok";
    }

    public List<String> allocateSku(String sku, int qty) {
        List<String> slots = new ArrayList<>();
        if (sku == null || sku.isBlank() || qty <= 0) {
            return slots;
        }
        for (int i = 0; i < qty; i++) {
            slots.add(sku + "-BIN-" + (i + 1));
        }
        return slots;
    }
}
