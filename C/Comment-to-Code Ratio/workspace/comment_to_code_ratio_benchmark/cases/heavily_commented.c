/* Heavily commented C source for Comment-to-Code Ratio validation. */

#include "heavily_commented.h"

/* Add two integers with inline documentation. */
int hc_add(int left, int right) {
    /* Return the sum of left and right operands. */
    return left + right;
}

/* Multiply two integers. */
int hc_multiply(int left, int right) {
    int product; /* Holds intermediate product value. */
    product = left * right;
    return product;
}

/* Aggregate values from a small fixed-size array. */
int hc_sum_three(int a, int b, int c) {
    /* Accumulate all three values. */
    return a + b + c;
}
