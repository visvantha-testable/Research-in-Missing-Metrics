/**
 * Heavily commented JavaScript module for Comment-to-Code Ratio validation.
 * Includes block and single-line comments throughout the file.
 */

/* Utility helpers documented with block comments. */

/**
 * Add two numbers and return the sum.
 * @param {number} left
 * @param {number} right
 * @returns {number}
 */
function add(left, right) {
  // Return the sum of both operands.
  return left + right;
}

/**
 * Multiply two numbers.
 */
function multiply(left, right) {
  // Compute product inline.
  return left * right;
}

/* Aggregate three values. */
function sumThree(a, b, c) {
  // Accumulate all values.
  return a + b + c;
}

module.exports = { add, multiply, sumThree };
