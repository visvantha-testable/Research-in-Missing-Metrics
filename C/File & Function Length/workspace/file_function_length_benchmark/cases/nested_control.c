/* Benchmark case: nested control structures for nesting depth analysis. */

int nested_example(int x) {
    if (x > 0) {
        if (x > 1) {
            if (x > 2) {
                return x;
            }
        }
    }
    return 0;
}
