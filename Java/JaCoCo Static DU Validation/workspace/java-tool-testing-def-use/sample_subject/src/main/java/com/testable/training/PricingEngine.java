package com.testable.training;

/** Unique pricing domain logic — different structure from inventory/shipment. */
public final class PricingEngine {

    public double applyDiscount(double basePrice, double percentOff) {
        if (basePrice < 0) {
            throw new IllegalArgumentException("basePrice must be non-negative");
        }
        if (percentOff < 0 || percentOff > 100) {
            throw new IllegalArgumentException("percentOff must be between 0 and 100");
        }
        return basePrice * (1.0 - percentOff / 100.0);
    }

    public double taxInclusive(double net, double taxRate) {
        if (net < 0 || taxRate < 0) {
            return 0.0;
        }
        return net + (net * taxRate);
    }

    public String priceBand(double amount) {
        if (amount < 10) {
            return "budget";
        }
        if (amount < 100) {
            return "standard";
        }
        return "premium";
    }
}
