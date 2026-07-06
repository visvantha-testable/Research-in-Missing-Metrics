/* Nesting depth benchmark — three nested if blocks (expected depth 3). */
int depth_three(int x) {
    if (x > 0) {
        if (x > 1) {
            if (x > 2) {
                return x;
            }
        }
    }
    return 0;
}
