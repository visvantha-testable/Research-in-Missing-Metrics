package com.testable.training;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class OrderServiceTest {

    private final OrderService service = new OrderService(new PaymentValidator());

    @Test
    void processOrderPriority() {
        assertEquals("priority", service.processOrder(true, true, 3));
    }

    @Test
    void processOrderStandardActive() {
        assertEquals("standard", service.processOrder(true, false, 0));
    }

    @Test
    void processOrderStandardPremium() {
        assertEquals("standard", service.processOrder(false, true, 0));
    }

    @Test
    void processOrderInactive() {
        assertEquals("inactive", service.processOrder(false, false, 0));
    }

    @Test
    void sumLoopZeroTrip() {
        assertEquals(0, service.sumLoop(0));
    }

    @Test
    void sumLoopPositive() {
        assertEquals(3, service.sumLoop(3));
    }

    @Test
    void nestedDecisionHigh() {
        assertEquals("high", service.nestedDecision(15, true, false));
    }

    @Test
    void nestedDecisionInvalid() {
        assertEquals("invalid", service.nestedDecision(-1, false, false));
    }

    @Test
    void nestedDecisionNormal() {
        assertEquals("normal", service.nestedDecision(5, false, false));
    }

    @Test
    void handleWithFallbackSuccess() {
        assertEquals("ok", service.handleWithFallback(" ok "));
    }

    @Test
    void handleWithFallbackError() {
        assertEquals("fallback", service.handleWithFallback(" "));
    }

    @Test
    void nestedDecisionHighWithFlagB() {
        assertEquals("high", service.nestedDecision(15, false, true));
    }

    @Test
    void crossModuleFlowLongToken() {
        assertEquals("ab****yz", service.crossModuleFlow("abcdefyz"));
    }

    @Test
    void crossModuleFlowShortToken() {
        assertEquals("****", service.crossModuleFlow("abc"));
    }
}
