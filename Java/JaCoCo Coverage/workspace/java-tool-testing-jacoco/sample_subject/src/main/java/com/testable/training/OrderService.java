package com.testable.training;

public final class OrderService {

    private final PaymentValidator validator;

    public OrderService(PaymentValidator validator) {
        this.validator = validator;
    }

    public String processOrder(boolean active, boolean premium, int quantity) {
        if (active && premium && quantity > 0) {
            return "priority";
        }
        if (active || premium) {
            return "standard";
        }
        return "inactive";
    }

    public int sumLoop(int limit) {
        int total = 0;
        for (int i = 0; i < limit; i++) {
            total += i;
        }
        return total;
    }

    public String nestedDecision(int value, boolean flagA, boolean flagB) {
        if (value > 10 && (flagA || flagB)) {
            return "high";
        }
        if (value < 0) {
            return "invalid";
        }
        return "normal";
    }

    public String handleWithFallback(String input) {
        try {
            return validator.validate(input);
        } catch (IllegalArgumentException ex) {
            return "fallback";
        }
    }

    public String crossModuleFlow(String token) {
        String masked = validator.maskToken(token);
        return validator.validate(masked);
    }
}
