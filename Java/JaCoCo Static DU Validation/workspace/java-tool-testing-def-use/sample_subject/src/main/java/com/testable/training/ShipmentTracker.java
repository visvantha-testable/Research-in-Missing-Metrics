package com.testable.training;

import java.time.LocalDate;
import java.util.Locale;

/** Unique shipment tracking logic — no shared copy-paste with sibling classes. */
public final class ShipmentTracker {

    public String nextCheckpoint(String current) {
        if (current == null) {
            return "CREATED";
        }
        return switch (current.toUpperCase(Locale.ROOT)) {
            case "CREATED" -> "PICKED";
            case "PICKED" -> "IN_TRANSIT";
            case "IN_TRANSIT" -> "DELIVERED";
            default -> "UNKNOWN";
        };
    }

    public boolean isOverdue(LocalDate promised, LocalDate today) {
        if (promised == null || today == null) {
            return false;
        }
        return today.isAfter(promised);
    }

    public int transitDays(LocalDate start, LocalDate end) {
        if (start == null || end == null || end.isBefore(start)) {
            return 0;
        }
        return (int) (end.toEpochDay() - start.toEpochDay());
    }
}
