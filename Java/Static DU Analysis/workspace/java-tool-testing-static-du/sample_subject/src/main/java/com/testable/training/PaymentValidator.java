package com.testable.training;

public final class PaymentValidator {

    public String validate(String token) {
        if (token == null || token.isBlank()) {
            throw new IllegalArgumentException("token required");
        }
        if (token.length() < 8) {
            throw new IllegalArgumentException("token too short");
        }
        return "valid";
    }

    public String maskToken(String token) {
        if (token == null || token.length() < 4) {
            return "****";
        }
        return token.substring(0, 2) + "****" + token.substring(token.length() - 2);
    }

    public boolean isPremiumTier(String tier) {
        return "gold".equalsIgnoreCase(tier) || "platinum".equalsIgnoreCase(tier);
    }
}
