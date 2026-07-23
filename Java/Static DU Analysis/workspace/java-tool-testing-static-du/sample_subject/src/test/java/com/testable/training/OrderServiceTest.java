package com.testable.training;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class OrderServiceTest {

    private OrderService service;

    @BeforeEach
    void setUp() {
        service = new OrderService(new PaymentValidator());
    }

    @Test
    void processOrderPriority() {
        assertEquals("priority", service.processOrder(true, true, 5));
    }

    @Test
    void processOrderStandard() {
        assertEquals("standard", service.processOrder(true, false, 0));
    }

    @Test
    void processOrderInactive() {
        assertEquals("inactive", service.processOrder(false, false, 0));
    }

    @Test
    void sumLoop() {
        assertEquals(6, service.sumLoop(4));
    }

    @Test
    void handleWithFallbackValid() {
        assertEquals("valid", service.handleWithFallback("12345678"));
    }

    @Test
    void handleWithFallbackInvalid() {
        assertEquals("fallback", service.handleWithFallback(""));
    }

    @Test
    void crossModuleFlow() {
        assertEquals("valid", service.crossModuleFlow("12345678"));
    }
}
