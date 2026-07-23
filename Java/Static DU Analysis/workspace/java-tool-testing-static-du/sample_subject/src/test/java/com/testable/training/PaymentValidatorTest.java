package com.testable.training;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class PaymentValidatorTest {

    private PaymentValidator validator;

    @BeforeEach
    void setUp() {
        validator = new PaymentValidator();
    }

    @Test
    void validateAcceptsLongToken() {
        assertEquals("valid", validator.validate("12345678"));
    }

    @Test
    void validateRejectsBlank() {
        assertThrows(IllegalArgumentException.class, () -> validator.validate("  "));
    }

    @Test
    void validateRejectsShortToken() {
        assertThrows(IllegalArgumentException.class, () -> validator.validate("1234567"));
    }

    @Test
    void maskToken() {
        assertEquals("12****78", validator.maskToken("12345678"));
    }

    @Test
    void isPremiumTier() {
        assertTrue(validator.isPremiumTier("gold"));
        assertFalse(validator.isPremiumTier("silver"));
    }
}
