package cases;

/**
 * Heavily documented demo class for Comment-to-Code Ratio validation.
 * Includes module-level Javadoc and inline documentation.
 */
public class HeavilyCommentedDemo {

    /**
     * Add two integers and return the sum.
     *
     * @param left first operand
     * @param right second operand
     * @return sum of operands
     */
    public int add(int left, int right) {
        // Return the sum of both operands.
        return left + right;
    }

    /* Multiply two integers using a block comment header. */
    public int multiply(int left, int right) {
        // Compute product inline.
        return left * right;
    }

    /**
     * Aggregate three values.
     */
    public int sumThree(int a, int b, int c) {
        // Accumulate all values.
        return a + b + c;
    }
}
