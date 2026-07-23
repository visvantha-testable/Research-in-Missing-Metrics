package com.testable.training;

public final class PaymentValidator {

    public String validate(String value) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("value required");
        }
        return value.trim();
    }

    public String maskToken(String token) {
        if (token.length() <= 4) {
            return "****";
        }
        return token.substring(0, 2) + "****" + token.substring(token.length() - 2);
    }
}
