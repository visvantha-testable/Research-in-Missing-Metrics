package com.testable.training;

import org.junit.jupiter.api.Test;

import java.time.LocalDate;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class ShipmentTrackerTest {

    private final ShipmentTracker tracker = new ShipmentTracker();

    @Test
    void nextCheckpointFromNull() {
        assertEquals("CREATED", tracker.nextCheckpoint(null));
    }

    @Test
    void nextCheckpointFlow() {
        assertEquals("PICKED", tracker.nextCheckpoint("CREATED"));
        assertEquals("IN_TRANSIT", tracker.nextCheckpoint("PICKED"));
        assertEquals("DELIVERED", tracker.nextCheckpoint("IN_TRANSIT"));
        assertEquals("UNKNOWN", tracker.nextCheckpoint("DELIVERED"));
    }

    @Test
    void isOverdue() {
        LocalDate promised = LocalDate.of(2026, 1, 1);
        assertTrue(tracker.isOverdue(promised, LocalDate.of(2026, 1, 5)));
        assertFalse(tracker.isOverdue(promised, LocalDate.of(2025, 12, 31)));
        assertFalse(tracker.isOverdue(null, LocalDate.now()));
        assertFalse(tracker.isOverdue(LocalDate.now(), null));
    }

    @Test
    void transitDays() {
        assertEquals(3, tracker.transitDays(LocalDate.of(2026, 1, 1), LocalDate.of(2026, 1, 4)));
        assertEquals(0, tracker.transitDays(LocalDate.of(2026, 1, 5), LocalDate.of(2026, 1, 1)));
        assertEquals(0, tracker.transitDays(null, LocalDate.now()));
        assertEquals(0, tracker.transitDays(LocalDate.now(), null));
    }
}
