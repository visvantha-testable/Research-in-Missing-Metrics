/* Nesting depth benchmark — loop + branch nesting (expected depth >= 5). */
int loop_nesting(int *items, int count) {
    int total = 0;
    for (int i = 0; i < count; i++) {
        if (items[i] > 0) {
            for (int j = 0; j < count; j++) {
                if (items[j] > 10) {
                    for (int k = 0; k < count; k++) {
                        if (items[k] > 20) {
                            total += items[k];
                        }
                    }
                }
            }
        }
    }
    return total;
}
