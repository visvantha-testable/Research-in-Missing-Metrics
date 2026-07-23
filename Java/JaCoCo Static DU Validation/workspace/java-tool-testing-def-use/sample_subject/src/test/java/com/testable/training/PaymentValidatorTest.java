package com.testable.training;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class PaymentValidatorTest {

    private final PaymentValidator validator = new PaymentValidator();

    @Test
    void validateTrims() {
        assertEquals("token", validator.validate(" token "));
    }

    @Test
    void validateRejectsBlank() {
        assertThrows(IllegalArgumentException.class, () -> validator.validate(" "));
    }

    @Test
    void validateRejectsNull() {
        assertThrows(IllegalArgumentException.class, () -> validator.validate(null));
    }

    @Test
    void maskExactlyFourChars() {
        assertEquals("****", validator.maskToken("abcd"));
    }

    @Test
    void maskLongToken() {
        assertEquals("ab****yz", validator.maskToken("abcdefyz"));
    }
}
